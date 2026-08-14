"""Pruebas del agente. No gastan un solo token: usan un modelo falso.

    pip install pytest
    pytest
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.agente import (  # noqa: E402
    Agente,
    Aviso,
    _entrada,
    _imagenes_de,
    _partir_en_turnos,
)
from agente.config import RAIZ, Config, ErrorDeConfiguracion  # noqa: E402
from agente.memoria import ram  # noqa: E402
from agente.prompts import leer_prompt  # noqa: E402


class ModeloFalso(GenericFakeChatModel):
    """El modelo de mentira, pero que se deja atar herramientas.

    GenericFakeChatModel no implementa bind_tools() y el grafo lo llama al
    construirse, así que sin esto no arranca ni un test. Como el modelo falso
    devuelve texto fijo, basta con que se devuelva a sí mismo.

    Y tiene su propio `_stream` porque el de la casa no sabe emitir un pedido
    de herramienta: con un mensaje sin texto y solo `tool_calls` no produce
    ningún trozo, y LangChain corta con "No generations found in stream". Sin
    esto no se puede probar en streaming nada que use herramientas, que es
    justo donde salen los avisos de progreso.
    """

    def bind_tools(self, herramientas, **kwargs):
        return self

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessageChunk
        from langchain_core.outputs import ChatGenerationChunk

        mensaje = next(self.messages)

        if mensaje.tool_calls:
            # El pedido entero en un solo trozo. Los de verdad llegan
            # partidos, pero lo que se prueba aquí es lo nuestro.
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=mensaje.content,
                    tool_call_chunks=[
                        {
                            "name": llamada["name"],
                            "args": json.dumps(llamada["args"]),
                            "id": llamada["id"],
                            "index": 0,
                        }
                        for llamada in mensaje.tool_calls
                    ],
                )
            )
            return

        for letra in mensaje.content:
            yield ChatGenerationChunk(message=AIMessageChunk(content=letra))


def agente_falso(respuestas: list, memoria_mensajes: int = 20) -> Agente:
    """Un agente igual al de verdad, pero con un modelo de mentira adentro.

    En `respuestas` van textos, o `AIMessage` ya armados cuando hace falta que
    el modelo pida una herramienta (un texto no puede llevar `tool_calls`).
    """
    config = Config(
        proveedor="claude",
        modelo="modelo-de-prueba",
        api_key="no-hace-falta",
        max_tokens=1024,
        memoria_mensajes=memoria_mensajes,
        prompt_sistema=RAIZ / "prompts/sistema.md",
    )

    a = Agente.__new__(Agente)
    a.config = config
    a.modelo = ModeloFalso(
        messages=iter(
            r if isinstance(r, AIMessage) else AIMessage(r) for r in respuestas
        )
    )
    a.checkpointer = ram()  # los tests no tocan el disco
    a.grafo = a._construir_grafo()
    return a


def test_responde():
    a = agente_falso(["Hola"])
    assert a.responder("hola").texto == "Hola"


def test_se_acuerda_de_la_conversacion():
    a = agente_falso(["primera", "segunda"])
    a.responder("uno")
    a.responder("dos")
    # 2 mensajes míos + 2 del agente
    assert len(a.historial()) == 4


def test_cada_conversacion_va_por_su_lado():
    a = agente_falso(["a", "b"])
    a.responder("hola", conversacion="chat-1")
    a.responder("hola", conversacion="chat-2")

    assert len(a.historial("chat-1")) == 2
    assert len(a.historial("chat-2")) == 2


def test_streaming_devuelve_lo_mismo_que_responder():
    a = agente_falso(["Esto llega de a pedacitos"])
    transmision = a.responder_en_vivo("dale")
    pedazos = list(transmision)

    assert "".join(pedazos) == "Esto llega de a pedacitos"
    assert transmision.resumen.texto == "Esto llega de a pedacitos"


def test_dos_conversaciones_a_la_vez_no_se_pisan():
    """El resumen vive en cada transmisión, no en el agente.

    Si viviera en el agente, dos conversaciones respondiendo al mismo tiempo
    se mezclarían los datos. Esto es lo que pasaría en produccion con varias
    personas escribiendo a la vez.
    """
    a = agente_falso(["respuesta para ana", "respuesta para beto"])

    ana = a.responder_en_vivo("hola", conversacion="ana")
    beto = a.responder_en_vivo("hola", conversacion="beto")

    # Se consumen intercalados, como pasaría de verdad
    lista_ana, lista_beto = [], []
    for pedazo in ana:
        lista_ana.append(pedazo)
    for pedazo in beto:
        lista_beto.append(pedazo)

    assert "".join(lista_ana) == "respuesta para ana"
    assert "".join(lista_beto) == "respuesta para beto"
    assert ana.resumen.texto == "respuesta para ana"
    assert beto.resumen.texto == "respuesta para beto"


def test_recorta_la_memoria_vieja():
    a = agente_falso([f"r{i}" for i in range(10)], memoria_mensajes=4)
    for i in range(6):
        a.responder(f"mensaje {i}")

    entrada = a._armar_entrada({"messages": a.historial()})

    assert isinstance(entrada[0], SystemMessage), "el prompt del sistema va primero"
    assert len(entrada) - 1 <= 4, "tendría que haber recortado los más viejos"


def conversacion_con_herramienta() -> list:
    """Tres turnos, y el del medio usa una herramienta.

    Los tres mensajes de esa vuelta (el pedido, el resultado y la respuesta)
    están atados entre sí: el proveedor los exige juntos.
    """
    return [
        HumanMessage("hola"),
        AIMessage("buenas"),

        HumanMessage("¿qué tiempo hace en Sevilla?"),
        AIMessage(
            "",
            tool_calls=[{"name": "clima", "args": {"lugar": "Sevilla"}, "id": "abc"}],
        ),
        ToolMessage("Clima en Sevilla: 19.1 °C", tool_call_id="abc"),
        AIMessage("En Sevilla hay 19 grados y está nublado."),

        HumanMessage("gracias"),
        AIMessage("de nada"),
    ]


def revisar_que_no_haya_huerfanos(mensajes: list) -> None:
    """Ningún pedido de herramienta sin su resultado, ni al revés.

    Esto es exactamente lo que el proveedor rechaza con un 400.
    """
    pedidos = {
        llamada["id"]
        for m in mensajes
        if isinstance(m, AIMessage)
        for llamada in (m.tool_calls or [])
    }
    resultados = {m.tool_call_id for m in mensajes if isinstance(m, ToolMessage)}

    assert pedidos == resultados, (
        f"quedaron colgados: pedidos sin resultado {pedidos - resultados}, "
        f"resultados sin pedido {resultados - pedidos}"
    )


@pytest.mark.parametrize("tope", [1, 2, 3, 4, 5, 6, 7, 8, 20])
def test_el_recorte_no_parte_una_vuelta_de_herramienta(tope):
    """La trampa que avisa AGENTS.md, y la razón por la que no usamos
    trim_messages().

    Recortando por mensajes sueltos, tarde o temprano el corte cae en el medio
    de una vuelta de herramienta y deja el pedido sin su resultado. El
    proveedor responde un 400 que no explica nada, y solo aparece cuando la
    conversación se hizo larga. Probamos todos los topes para que no haya un
    número que lo rompa.
    """
    a = agente_falso(["x"], memoria_mensajes=tope)

    entrada = a._armar_entrada({"messages": conversacion_con_herramienta()})
    recortado = entrada[1:]  # el [0] es el prompt del sistema

    revisar_que_no_haya_huerfanos(recortado)
    assert isinstance(recortado[0], HumanMessage), "tiene que arrancar en la persona"


def test_el_turno_de_ahora_entra_entero_aunque_no_quepa():
    """Con memoria en 1, la vuelta de herramienta igual tiene que ir completa.

    Es preferible pasarse del tope que mandar una conversación partida al
    medio: recortada así, la llamada directamente falla.
    """
    a = agente_falso(["x"], memoria_mensajes=1)

    # Una conversación que termina justo en medio de la vuelta de herramienta,
    # que es como llega el estado cuando el grafo vuelve al modelo.
    hasta_la_herramienta = conversacion_con_herramienta()[:5]
    recortado = a._armar_entrada({"messages": hasta_la_herramienta})[1:]

    revisar_que_no_haya_huerfanos(recortado)
    assert len(recortado) == 3, "el turno entero: pedido, resultado y su human"


def test_el_prompt_sale_del_archivo():
    a = agente_falso(["x"])
    a.config.cache = False  # sin caché el prompt viaja como texto pelado

    entrada = a._armar_entrada({"messages": []})

    assert entrada[0].content == leer_prompt(a.config.prompt_sistema)


def test_con_cache_el_prompt_va_marcado_para_claude():
    a = agente_falso(["x"])
    a.config.cache = True
    a.config.proveedor = "claude"

    bloque = a._armar_entrada({"messages": []})[0].content[0]

    assert bloque["cache_control"] == {"type": "ephemeral"}
    assert bloque["text"] == leer_prompt(a.config.prompt_sistema)


def test_sin_cache_el_prompt_va_pelado():
    a = agente_falso(["x"])
    a.config.cache = False

    assert isinstance(a._armar_entrada({"messages": []})[0].content, str)


def test_avisa_si_falta_la_clave(monkeypatch):
    monkeypatch.setenv("PROVEEDOR", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    with pytest.raises(ErrorDeConfiguracion, match="Falta la clave"):
        Config.desde_entorno()


def test_avisa_si_el_proveedor_no_existe():
    with pytest.raises(ErrorDeConfiguracion, match="no existe"):
        Config.desde_entorno("nube-magica")


def test_modo_produccion_sin_dsn_avisa(monkeypatch):
    from agente.memoria import crear_memoria

    config = Config(
        proveedor="claude", modelo="x", api_key="x", max_tokens=100,
        memoria_mensajes=10, prompt_sistema=RAIZ / "prompts/sistema.md",
        modo="produccion", postgres_dsn="",
    )

    with pytest.raises(ValueError, match="POSTGRES_DSN"):
        crear_memoria(config)


def test_modo_test_guarda_en_sqlite(tmp_path):
    from agente.memoria import crear_memoria

    archivo = tmp_path / "prueba.db"
    config = Config(
        proveedor="claude", modelo="x", api_key="x", max_tokens=100,
        memoria_mensajes=10, prompt_sistema=RAIZ / "prompts/sistema.md",
        modo="test", sqlite_ruta=str(archivo),
    )

    crear_memoria(config)
    assert archivo.exists(), "tendría que haber creado el archivo de la base"


def test_la_conexion_de_postgres_no_se_la_lleva_el_recolector(monkeypatch):
    """El bug que solo aparece con el agente corriendo un rato.

    `PostgresSaver.from_conn_string()` es un generador: adentro tiene un
    `with Connection.connect(...)`. Si nadie se guarda una referencia, el
    recolector de basura lo destruye, y destruirlo cierra la conexión.

    No falla al conectar —ahí funciona todo— sino en el primer mensaje que llega
    después, con un "the connection is closed" que no se parece en nada a su
    causa. En un script corto ni se nota, porque el proceso termina antes de
    que el recolector actúe.
    """
    import gc
    from contextlib import contextmanager

    # El paquete de Postgres está en el grupo `produccion`, que no se instala
    # solo (`uv sync --group produccion`). Sin él este test se salta en vez de
    # fallar: la falta de una dependencia opcional no es un test roto.
    postgres_de_langgraph = pytest.importorskip(
        "langgraph.checkpoint.postgres",
        reason="falta el grupo produccion: uv sync --group produccion",
    )

    from agente.memoria import postgres

    cerrada: list[bool] = []

    class GuardadorFalso:
        def setup(self):
            pass

    @contextmanager
    def conexion_falsa(dsn, **kwargs):
        try:
            yield GuardadorFalso()
        finally:
            cerrada.append(True)

    monkeypatch.setattr(
        postgres_de_langgraph.PostgresSaver,
        "from_conn_string",
        staticmethod(conexion_falsa),
    )

    guardador = postgres("postgresql://loquesea")
    gc.collect()  # el recolector, ahora y a propósito

    assert not cerrada, (
        "el recolector cerró la conexión: al checkpointer le falta guardarse "
        "el contexto, y el primer mensaje va a fallar con 'connection is closed'"
    )
    assert guardador is not None


def test_modo_invalido_avisa(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("MODO", "cualquier-cosa")

    with pytest.raises(ErrorDeConfiguracion, match="MODO"):
        Config.desde_entorno("claude")


def test_olvidar_borra_de_verdad():
    """El botón "borrar conversación" tiene que borrar.

    No basta con crear un agente nuevo: la conversación vive en el
    checkpointer, así que si no se borra de ahí, el agente nuevo la levanta
    igual y el botón miente.
    """
    a = agente_falso(["hola", "te llamas Javi", "no se como te llamas"])

    a.responder("me llamo Javi")
    assert len(a.historial()) == 2

    a.olvidar()

    assert a.historial() == [], "la conversación tenía que quedar vacía"


def test_la_transmision_se_puede_leer_dos_veces():
    """Consumirla y después pedir .texto() no tiene que devolver vacío.

    Los pedazos llegan del modelo y no vuelven, así que si alguien recorre la
    transmisión con un for y después llama a .texto(), le tenemos que dar lo
    que ya guardamos — no un vacío silencioso que además pise el resumen.
    """
    a = agente_falso(["hola que tal"])
    t = a.responder_en_vivo("dale")

    primero = "".join(t)
    segundo = t.texto()

    assert primero == "hola que tal"
    assert segundo == "hola que tal", "la segunda lectura no puede venir vacía"
    assert t.resumen.texto == "hola que tal", "el resumen no se tiene que pisar"


# -- Las imágenes que dejan las herramientas ----------------------------------


def turno_con_imagen(ruta="datos/imagenes/a.png") -> list:
    """Un turno en el que el modelo pidió una imagen y la herramienta la hizo."""
    return [
        HumanMessage("hazme un logo"),
        AIMessage(
            "",
            tool_calls=[
                {"name": "crear_imagen", "args": {"descripcion": "un logo"}, "id": "i1"}
            ],
        ),
        ToolMessage(
            "Imagen creada y enviada a la persona.",
            tool_call_id="i1",
            artifact={"tipo": "imagen", "ruta": ruta},
        ),
        AIMessage("Ahí la tienes."),
    ]


def test_la_ruta_de_la_imagen_sale_del_artifact():
    assert _imagenes_de(turno_con_imagen()) == ["datos/imagenes/a.png"]


def test_una_herramienta_sin_artifact_no_aporta_nada():
    """El clima devuelve texto pelado: no tiene que aparecer como imagen."""
    solo_clima = [ToolMessage("Clima en Sevilla: 24 °C", tool_call_id="c1")]

    assert _imagenes_de(solo_clima) == []


def test_solo_las_imagenes_del_turno_de_ahora():
    """La trampa: `messages` trae el historial completo.

    Si se leyeran todos, cada "hola" volvería a enviar la imagen de hace media
    hora. Por eso `responder()` mira solo el último turno.
    """
    historial = [
        *turno_con_imagen("datos/imagenes/vieja.png"),
        HumanMessage("gracias"),
        AIMessage("de nada"),
    ]

    ultimo = _partir_en_turnos(historial)[-1]

    assert _imagenes_de(ultimo) == [], "el turno de ahora no generó ninguna imagen"
    assert _imagenes_de(historial) == ["datos/imagenes/vieja.png"], "pero en el historial está"


def test_la_imagen_llega_a_la_respuesta_pasando_por_el_grafo(monkeypatch, tmp_path):
    """De punta a punta por el núcleo: el modelo la pide, el grafo la ejecuta.

    Es el test que ata todo: se usa la herramienta de verdad (con el generador
    parcheado para no salir a la red), el ToolNode de verdad y el grafo de
    verdad. Lo único de mentira es el modelo.
    """
    from agente import imagenes

    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    monkeypatch.setattr(imagenes, "generar", lambda d: b"\x89PNG\r\n\x1a\n" + b"x" * 200)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {
                        "name": "crear_imagen",
                        "args": {"descripcion": "un faro"},
                        "id": "i9",
                    }
                ],
            ),
            "Listo, ahí va.",
        ]
    )

    respuesta = a.responder("hazme un faro")

    assert respuesta.texto == "Listo, ahí va."
    assert len(respuesta.imagenes) == 1

    ruta = Path(respuesta.imagenes[0])
    assert ruta.is_file(), "la herramienta la escribió de verdad"
    assert ruta.parent == tmp_path


def test_el_estado_no_se_llena_de_base64(monkeypatch, tmp_path):
    """**La regla que no se negocia**, comprobada donde de verdad importa.

    El estado del grafo se guarda en la memoria y se le reenvía al modelo en
    cada mensaje siguiente. Si la imagen entrara ahí, serían cientos de miles
    de tokens por turno. Este test falla si alguien mueve la imagen del
    `artifact` al `content`.
    """
    from agente import imagenes

    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    # Un "PNG" de 300 KB, para que se note si se cuela en el estado.
    monkeypatch.setattr(imagenes, "generar", lambda d: b"\x89PNG\r\n\x1a\n" + b"x" * 300_000)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "crear_imagen", "args": {"descripcion": "x"}, "id": "i8"}
                ],
            ),
            "hecho",
        ]
    )
    a.responder("hazme algo")

    for mensaje in a.historial():
        contenido = mensaje.content
        largo = len(contenido if isinstance(contenido, str) else str(contenido))
        assert largo < 1_000, (
            f"un {type(mensaje).__name__} de {largo} caracteres en el estado: "
            "alguien metió la imagen en el content"
        )


# -- Fotos que entran ---------------------------------------------------------


def test_sin_fotos_el_mensaje_es_de_los_de_siempre():
    mensaje = _entrada("hola")

    assert isinstance(mensaje.content, str)
    assert mensaje.content == "hola"


def test_con_fotos_el_mensaje_pasa_a_bloques():
    mensaje = _entrada("¿qué es esto?", [b"unos-bytes-de-foto"])

    tipos = [b["type"] for b in mensaje.content]
    assert tipos == ["text", "image"]
    assert mensaje.content[0]["text"] == "¿qué es esto?"

    foto = mensaje.content[1]
    assert foto["source_type"] == "base64"
    assert base64.b64decode(foto["data"]) == b"unos-bytes-de-foto"


def test_varias_fotos_van_todas():
    mensaje = _entrada("míralas", [b"una", b"otra", b"y-otra"])

    assert [b["type"] for b in mensaje.content] == ["text", "image", "image", "image"]


# -- Los avisos de progreso ---------------------------------------------------


def test_el_aviso_es_un_str():
    """Para que quien no lo distinga siga funcionando: la terminal, un join."""
    aviso = Aviso("🎨 trabajando")

    assert isinstance(aviso, str)
    assert "".join(["a", aviso, "b"]) == "a🎨 trabajandob"


def test_el_aviso_llega_antes_de_que_la_herramienta_trabaje(monkeypatch, tmp_path):
    """El orden es TODO el sentido de esto.

    Si el aviso llegara después de la herramienta no serviría de nada: se
    trata justamente de que la persona sepa qué pasa durante los treinta
    segundos que tarda. La herramienta de mentira apunta cuándo se ejecutó.
    """
    from agente import imagenes

    orden = []

    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)

    def generar(descripcion):
        orden.append("la herramienta trabaja")
        return b"\x89PNG\r\n\x1a\n" + b"x" * 50

    monkeypatch.setattr(imagenes, "generar", generar)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "crear_imagen", "args": {"descripcion": "x"}, "id": "i1"}
                ],
            ),
            "ya está",
        ]
    )

    for pedazo in a.responder_en_vivo("hazme una imagen"):
        if isinstance(pedazo, Aviso):
            orden.append(f"aviso: {pedazo}")

    assert orden[0].startswith("aviso:"), f"el aviso llegó tarde: {orden}"
    assert orden[1] == "la herramienta trabaja"


def test_el_aviso_no_entra_en_la_respuesta(monkeypatch, tmp_path):
    """Es andamiaje: si entrara, se guardaría en la memoria como si fuera texto."""
    from agente import imagenes

    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    monkeypatch.setattr(imagenes, "generar", lambda d: b"\x89PNG\r\n\x1a\n" + b"x" * 50)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "crear_imagen", "args": {"descripcion": "x"}, "id": "i2"}
                ],
            ),
            "Hecho.",
        ]
    )

    t = a.responder_en_vivo("hazme una imagen")
    pedazos = list(t)

    assert any(isinstance(p, Aviso) for p in pedazos), "tiene que haber avisado"
    assert t.resumen.texto == "Hecho.", "el aviso no puede estar en el texto"


def test_una_herramienta_sin_aviso_no_rompe_nada(monkeypatch):
    """Si añades una herramienta y te olvidas del aviso, simplemente no avisa."""
    from agente import herramientas

    monkeypatch.setattr(herramientas, "AVISOS", {})
    import agente.agente as nucleo

    monkeypatch.setattr(nucleo, "AVISOS", {})

    a = agente_falso(["hola"])

    assert [p for p in a.responder_en_vivo("eh") if isinstance(p, Aviso)] == []


def test_no_repite_el_aviso_de_la_misma_herramienta(monkeypatch, tmp_path):
    """Un pedido de herramienta llega partido en varios trozos."""
    from agente import imagenes

    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    monkeypatch.setattr(imagenes, "generar", lambda d: b"\x89PNG\r\n\x1a\n" + b"x" * 50)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "crear_imagen", "args": {"descripcion": "x"}, "id": "i3"}
                ],
            ),
            "hecho",
        ]
    )

    avisos = [
        p
        for p in a.responder_en_vivo("dale")
        if isinstance(p, Aviso) and p.visible
    ]

    assert len(avisos) == 1


def test_las_fotos_llegan_tambien_por_el_camino_en_vivo():
    """El bug que se escapó: `responder_en_vivo` se comía las fotos.

    Dentro había una lista local llamada `imagenes` —la de las imágenes que
    GENERAN las herramientas— que tapaba al parámetro del mismo nombre. Así
    que las fotos que llegaban de Telegram se perdían sin ruido: el modelo
    contestaba "no veo ninguna imagen" y no había forma de saber por qué.

    No lo pillaron los tests de antes porque probaban `responder()` con fotos
    y `responder_en_vivo()` sin ellas — y el bot usa justo la combinación que
    faltaba. De ahí este test: mira lo que de verdad recibe el modelo.
    """
    a = agente_falso(["lo veo"])

    vistos = []
    original = a.modelo._stream

    def espiar(messages, **kwargs):
        vistos.append(messages)
        yield from original(messages, **kwargs)

    a.modelo._stream = espiar

    list(a.responder_en_vivo("¿qué ves?", imagenes=[b"los-bytes-de-la-foto"]))

    humano = vistos[0][-1]
    tipos = [b["type"] for b in humano.content]
    assert tipos == ["text", "image"], f"el modelo recibió {tipos}"

    # LangChain normaliza el bloque antes de dárselo al modelo: lo que se
    # escribe es {"source_type": "base64", "data": ...} y lo que llega es
    # {"base64": ...}. Los dos son válidos; se comprueba el que llega.
    foto = humano.content[1]
    assert base64.b64decode(foto["base64"]) == b"los-bytes-de-la-foto"
    assert foto["mime_type"] == "image/jpeg"


def test_las_fotos_que_entran_y_las_que_salen_no_se_pisan(monkeypatch, tmp_path):
    """Las dos direcciones a la vez: llega una foto y se genera otra."""
    from agente import imagenes as modulo

    monkeypatch.setattr(modulo, "CARPETA", tmp_path)
    monkeypatch.setattr(modulo, "generar", lambda d: b"\x89PNG\r\n\x1a\n" + b"x" * 50)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "crear_imagen", "args": {"descripcion": "otra"}, "id": "z1"}
                ],
            ),
            "aquí la tienes",
        ]
    )

    t = a.responder_en_vivo(
        "haz otra parecida a esta", imagenes=[b"la-foto-que-mando-la-persona"]
    )
    list(t)

    # La que se generó sale en el resumen…
    assert len(t.resumen.imagenes) == 1
    # …y la que entró llegó al modelo, no se perdió por el camino.
    humano = a.historial()[0]
    assert [b["type"] for b in humano.content] == ["text", "image"]


def test_los_avisos_de_la_traza_no_se_le_muestran_a_nadie(monkeypatch, tmp_path):
    """Hay dos clases de aviso y no se pueden confundir.

    Los visibles son para la persona ("🎨 Creando la imagen…"). Los invisibles
    son para la traza de la terminal: lo que devolvió una herramienta, que en
    Telegram sobra pero en el equipo es lo que te dice que no se ha colgado.
    """
    from agente import imagenes

    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    monkeypatch.setattr(imagenes, "generar", lambda d: b"\x89PNG\r\n\x1a\n" + b"x" * 50)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "crear_imagen", "args": {"descripcion": "un faro"}, "id": "t1"}
                ],
            ),
            "hecho",
        ]
    )

    avisos = [p for p in a.responder_en_vivo("dale") if isinstance(p, Aviso)]

    visibles = [a for a in avisos if a.visible]
    ocultos = [a for a in avisos if not a.visible]

    assert len(visibles) == 1, "uno para la persona: que la imagen se está creando"
    assert len(ocultos) == 1, "y uno para la traza: qué devolvió la herramienta"
    assert "crear_imagen" in ocultos[0]


def test_el_aviso_lleva_los_argumentos_para_la_traza(monkeypatch, tmp_path):
    """En el equipo se quiere ver CON QUÉ se llamó a la herramienta."""
    from agente import imagenes

    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    monkeypatch.setattr(imagenes, "generar", lambda d: b"\x89PNG\r\n\x1a\n" + b"x" * 50)

    a = agente_falso(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "crear_imagen", "args": {"descripcion": "un faro"}, "id": "t2"}
                ],
            ),
            "hecho",
        ]
    )

    primero = next(
        p for p in a.responder_en_vivo("dale") if isinstance(p, Aviso) and p.visible
    )

    assert "crear_imagen" in primero.detalle
    assert "un faro" in primero.detalle
