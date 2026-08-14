"""Pruebas del canal de Telegram. No salen a internet ni gastan tokens.

La API de Telegram se reemplaza por una de mentira que anota lo que se le
pidió. Lo que se prueba es lo nuestro: qué mensajes se atienden, cómo se
traducen y qué sale para el otro lado.

    pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.canales.telegram import (  # noqa: E402
    LARGO_MAXIMO,
    PIE_MAXIMO,
    Telegram,
    _cortar,
    _traducir,
)


def novedad(texto="hola", chat=555, update=1, es_bot=False, tipo="text") -> dict:
    """Un mensaje como lo manda Telegram."""
    mensaje = {"chat": {"id": chat}, "from": {"id": 9, "is_bot": es_bot}}
    if tipo == "text":
        mensaje["text"] = texto
    else:
        mensaje[tipo] = {"file_id": "xxx"}  # una foto, un audio, lo que sea

    return {"update_id": update, "message": mensaje}


class TelegramFalso(Telegram):
    """El canal, pero con la API de mentira. Anota todo lo que se mandó."""

    def __init__(self, tandas=None):
        super().__init__(token="123:falso")
        self.enviados: list[dict] = []
        self._tandas = list(tandas or [])

    def _api(self, metodo, datos=None, espera=30):
        self.enviados.append({"metodo": metodo, "datos": datos or {}})

        if metodo == "getUpdates":
            return {"result": self._tandas.pop(0) if self._tandas else []}
        return {"ok": True, "result": {}}

    def _subir(self, metodo, campos, nombre, archivo, espera=120):
        # Se anota igual que una llamada normal, más el archivo, para poder
        # comprobar que se sube el que toca y por el campo que toca.
        self.enviados.append(
            {"metodo": metodo, "datos": campos, "campo": nombre, "archivo": archivo}
        )
        return {"ok": True, "result": {}}


# -- Traducir lo que llega ----------------------------------------------------


def test_traduce_un_mensaje_normal():
    entrante = _traducir(novedad("¿que tiempo hace?", chat=777, update=42))

    assert entrante is not None
    assert entrante.texto == "¿que tiempo hace?"
    assert entrante.conversacion == "777", "el chat_id es el thread_id"
    assert entrante.identificador == "42"


def test_el_chat_id_va_como_texto():
    """Es el thread_id de LangGraph, y ahí un 555 y un "555" no son lo mismo."""
    assert isinstance(_traducir(novedad(chat=555)).conversacion, str)


@pytest.mark.parametrize("tipo", ["sticker", "document", "video"])
def test_lo_que_no_sabe_leer_se_deja_pasar(tipo):
    """El agente no sabe abrir documentos ni ver vídeos.

    Las fotos y las notas de voz sí: están más abajo. Lo importante de dejar
    pasar el resto es que el offset avanza igual (ver el test del offset), o
    volverían para siempre.
    """
    assert _traducir(novedad(tipo=tipo)) is None


def test_no_le_contesta_a_otro_bot():
    """Dos bots hablándose es un ida y vuelta que no termina más."""
    assert _traducir(novedad(es_bot=True)) is None


# -- Qué se contesta y qué no -------------------------------------------------


def test_no_contesta_dos_veces_el_mismo_mensaje():
    """Telegram reenvía ante la duda. Sin esto, el agente contesta repetido."""
    canal = TelegramFalso()
    entrante = _traducir(novedad(update=7))

    assert canal.deberia_responder(entrante) is True
    assert canal.deberia_responder(entrante) is False, "la segunda vez ya no"


def test_ignora_los_mensajes_vacios():
    canal = TelegramFalso()
    assert canal.deberia_responder(_traducir(novedad("   "))) is False


# -- El bucle de escucha ------------------------------------------------------


def test_escuchar_devuelve_los_mensajes_traducidos():
    canal = TelegramFalso(tandas=[[novedad("hola", update=1)]])

    primero = next(canal.escuchar())

    assert primero.texto == "hola"


def test_el_offset_avanza_aunque_el_mensaje_no_sirva():
    """Si no avanzara, un mensaje que no sabemos atender vuelve para siempre.

    Telegram reenvía todo lo que no le confirmaste. Un sticker en el medio
    dejaría al bot trabado ahí, sin contestarle nunca más a nadie.
    """
    canal = TelegramFalso(
        tandas=[
            [novedad(tipo="sticker", update=10)],  # este no se puede atender
            [novedad("hola", update=11)],
        ]
    )

    escucha = canal.escuchar()
    primero = next(escucha)

    assert primero.texto == "hola", "tendría que haber seguido de largo"
    assert canal._proxima == 12, "el offset tiene que haber pasado la foto"


# -- Lo que sale --------------------------------------------------------------


def test_envia_cada_mensaje_por_separado():
    canal = TelegramFalso()

    canal.enviar("555", ["primero", "segundo"])

    envios = [e for e in canal.enviados if e["metodo"] == "sendMessage"]
    assert [e["datos"]["text"] for e in envios] == ["primero", "segundo"]
    assert all(e["datos"]["chat_id"] == "555" for e in envios)


def test_un_mensaje_gigante_se_corta_antes_de_mandarlo():
    """Telegram rechaza el mensaje entero si se pasa del largo."""
    canal = TelegramFalso()

    canal.enviar("555", ["palabra " * 2000])

    envios = [e for e in canal.enviados if e["metodo"] == "sendMessage"]
    assert len(envios) > 1, "tendría que haberlo partido"
    assert all(len(e["datos"]["text"]) <= LARGO_MAXIMO for e in envios)


def test_el_escribiendo_no_voltea_la_respuesta(monkeypatch):
    """Es cosmético: si falla, la respuesta tiene que salir igual."""
    canal = TelegramFalso()

    def explota(*a, **k):
        raise ConnectionError("se cayó")

    monkeypatch.setattr(canal, "_api", explota)
    canal.escribiendo("555")  # no tiene que levantar nada


# -- Cortar textos largos -----------------------------------------------------


def test_cortar_respeta_el_largo():
    pedazos = _cortar("a" * 100, largo=30)
    assert all(len(p) <= 30 for p in pedazos)
    assert "".join(pedazos) == "a" * 100


def test_cortar_no_parte_palabras_al_medio():
    pedazos = _cortar("hola " * 40, largo=50)
    assert not any(p.endswith("hol") or p.startswith("la ") for p in pedazos)


def test_cortar_deja_en_paz_lo_que_ya_entra():
    assert _cortar("corto", largo=100) == ["corto"]


# -- Configuración ------------------------------------------------------------


def test_sin_token_avisa_que_falta():
    with pytest.raises(ValueError, match="TELEGRAM_TOKEN"):
        Telegram(token="")


def test_el_token_sale_del_env(monkeypatch):
    """Sin esto el token está en el .env pero no lo lee nadie."""
    from agente.config import Config

    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")

    assert Config.desde_entorno("claude").telegram_token == "123:abc"


# -- El bucle entero, de punta a punta ----------------------------------------
#
# Aquí se pegan todas las piezas: llega un mensaje de Telegram, contesta el
# agente, sale la respuesta. Con un canal de mentira y un modelo de mentira,
# así que no toca la red ni gasta un token.

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot_telegram import atender  # noqa: E402

from test_agente import agente_falso  # noqa: E402  (el agente con modelo falso)


class TelegramQueTermina(TelegramFalso):
    """Como el falso, pero corta cuando se le acaban los mensajes.

    El bucle de verdad es infinito a propósito (un bot escucha para siempre),
    así que para poder probarlo lo cortamos igual que Ctrl+C.
    """

    def _traer_novedades(self):
        if not self._tandas:
            raise KeyboardInterrupt
        return self._tandas.pop(0)


def test_el_mensaje_da_la_vuelta_completa():
    canal = TelegramQueTermina(tandas=[[novedad("hola", chat=555, update=1)]])
    agente = agente_falso(["¡Buenas! ¿En qué te ayudo?"])

    with pytest.raises(KeyboardInterrupt):  # así corta el bot
        atender(agente, canal)

    enviados = [e for e in canal.enviados if e["metodo"] == "sendMessage"]
    assert len(enviados) == 1
    assert enviados[0]["datos"]["text"] == "¡Buenas! ¿En qué te ayudo?"
    assert enviados[0]["datos"]["chat_id"] == "555"


def test_cada_chat_tiene_su_propia_memoria():
    """Lo único que no se puede equivocar.

    Si dos personas compartieran el `conversacion`, compartirían la memoria:
    una leería la conversación de la otra.
    """
    canal = TelegramQueTermina(
        tandas=[
            [novedad("hola", chat=111, update=1)],
            [novedad("hola", chat=222, update=2)],
        ]
    )
    agente = agente_falso(["para el primero", "para el segundo"])

    with pytest.raises(KeyboardInterrupt):
        atender(agente, canal)

    assert len(agente.historial("111")) == 2
    assert len(agente.historial("222")) == 2
    assert agente.historial("333") == [], "un chat que no escribió no tiene nada"


def test_si_el_modelo_falla_el_bot_no_se_cae():
    """Un error con una persona no puede dejar sin atender a las demás."""

    canal = TelegramQueTermina(tandas=[[novedad("hola", chat=555, update=1)]])
    agente = agente_falso([])  # sin respuestas: el modelo falso revienta

    with pytest.raises(KeyboardInterrupt):  # llegó al final, no murió antes
        atender(agente, canal)

    enviados = [e for e in canal.enviados if e["metodo"] == "sendMessage"]
    assert len(enviados) == 1, "le tiene que avisar a la persona"
    assert "rompió" in enviados[0]["datos"]["text"]


# -- Enviar imágenes ----------------------------------------------------------


@pytest.fixture
def imagen(tmp_path) -> Path:
    """Un PNG de 1x1 de verdad, para no inventar bytes."""
    import base64

    ruta = tmp_path / "prueba.png"
    ruta.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
            "z8AAAwAB/AF+jQAAAABJRU5ErkJggg=="
        )
    )
    return ruta


def test_la_imagen_va_como_foto_y_como_archivo(imagen):
    """Las dos cosas: la foto se ve en el chat, el archivo va sin recomprimir."""
    canal = TelegramFalso()

    canal.enviar_imagen("555", str(imagen), texto="un faro")

    metodos = [e["metodo"] for e in canal.enviados]
    assert metodos == ["sendPhoto", "sendDocument"]

    foto = canal.enviados[0]
    assert foto["datos"]["chat_id"] == "555"
    assert foto["datos"]["caption"] == "un faro"
    assert foto["campo"] == "photo"
    assert foto["archivo"] == imagen

    assert canal.enviados[1]["campo"] == "document"


def test_el_pie_de_foto_se_recorta():
    """Telegram rechaza un caption más largo que PIE_MAXIMO."""
    canal = TelegramFalso()
    ruta = Path(__file__)  # cualquier archivo que exista

    canal.enviar_imagen("555", str(ruta), texto="x" * (PIE_MAXIMO + 500))

    assert len(canal.enviados[0]["datos"]["caption"]) == PIE_MAXIMO


def test_si_la_imagen_no_esta_se_avisa_por_texto():
    """No puede quedar en silencio: la persona pidió una imagen."""
    canal = TelegramFalso()

    canal.enviar_imagen("555", "/no/existe/nada.png")

    assert canal.enviados[0]["metodo"] == "sendMessage"
    assert "no la encuentro" in canal.enviados[0]["datos"]["text"]


def test_si_falla_la_subida_no_se_cae_el_bot(imagen):
    """Subir un archivo falla mucho más que mandar texto: no puede tirar el bot.

    Ojo con la diferencia: `enviar()` a propósito NO captura nada (una
    excepción ahí sube hasta main y corta), pero aquí sí, porque el envío de
    una imagen se rompe por tamaño, por formato o porque la red se cortó a
    medias, y eso no puede dejar sin bot a las demás personas.
    """
    canal = TelegramFalso()

    def explota(*a, **k):
        raise OSError("se cortó la red")

    canal._subir = explota

    canal.enviar_imagen("555", str(imagen))  # no levanta

    assert canal.enviados[0]["metodo"] == "sendMessage"
    assert "No pude enviar la imagen" in canal.enviados[0]["datos"]["text"]


def test_si_falla_solo_el_archivo_la_foto_ya_llego(imagen):
    """El PNG sin comprimir es un extra: si falla, no se avisa de nada."""
    canal = TelegramFalso()
    original = canal._subir

    def falla_el_segundo(metodo, campos, nombre, archivo, espera=120):
        if metodo == "sendDocument":
            raise OSError("demasiado grande")
        return original(metodo, campos, nombre, archivo, espera)

    canal._subir = falla_el_segundo

    canal.enviar_imagen("555", str(imagen))

    metodos = [e["metodo"] for e in canal.enviados]
    assert metodos == ["sendPhoto"], "no se avisa: la foto ya se vio"


def test_el_multipart_esta_bien_armado(imagen):
    """El cuerpo se arma a mano, así que conviene mirarlo.

    Sin las fronteras y los CRLF exactos, Telegram devuelve un 400 que no
    explica nada.
    """
    capturado = {}

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true}'

    import urllib.request

    def urlopen_falso(pedido, timeout=None):
        capturado["cuerpo"] = pedido.data
        capturado["tipo"] = pedido.headers.get("Content-type", "")
        return Respuesta()

    original = urllib.request.urlopen
    urllib.request.urlopen = urlopen_falso
    try:
        Telegram("123:falso")._subir(
            "sendPhoto", {"chat_id": "555"}, "photo", imagen
        )
    finally:
        urllib.request.urlopen = original

    frontera = capturado["tipo"].split("boundary=")[1]
    cuerpo = capturado["cuerpo"]

    assert cuerpo.startswith(f"--{frontera}\r\n".encode())
    assert cuerpo.rstrip().endswith(f"--{frontera}--".encode()), "cierra con dos guiones"
    assert b'name="photo"; filename="prueba.png"' in cuerpo
    assert imagen.read_bytes() in cuerpo, "el archivo va entero"


def test_el_escribiendo_puede_decir_que_sube_una_foto():
    """Generar una imagen tarda medio minuto: 'escribiendo' no es lo que pasa."""
    canal = TelegramFalso()

    canal.escribiendo("555", "upload_photo")

    assert canal.enviados[0]["datos"]["action"] == "upload_photo"


def test_por_defecto_sigue_diciendo_escribiendo():
    canal = TelegramFalso()

    canal.escribiendo("555")

    assert canal.enviados[0]["datos"]["action"] == "typing"


# -- Fotos que llegan ---------------------------------------------------------


def con_foto(pie=None, update=1, chat=555) -> dict:
    """Un mensaje con foto, como lo manda Telegram: la misma en varios tamaños."""
    mensaje = {
        "chat": {"id": chat},
        "from": {"id": 9, "is_bot": False},
        "photo": [
            {"file_id": "chica", "width": 90},
            {"file_id": "mediana", "width": 320},
            {"file_id": "grande", "width": 1280},
        ],
    }
    if pie is not None:
        mensaje["caption"] = pie

    return {"update_id": update, "message": mensaje}


def test_una_foto_ya_no_se_descarta():
    entrante = _traducir(con_foto(pie="¿qué flor es esta?"))

    assert entrante is not None
    assert entrante.texto == "¿qué flor es esta?", "el pie de la foto es el mensaje"
    assert entrante.adjuntos == ["grande"]


def test_se_queda_con_la_foto_mas_grande():
    """Telegram manda varios tamaños. El grande es el que mejor lee el modelo."""
    assert _traducir(con_foto()).adjuntos == ["grande"]


def test_una_foto_sin_pie_igual_pregunta_algo():
    """Una imagen a secas no le dice al modelo qué se espera de él."""
    entrante = _traducir(con_foto(pie=None))

    assert entrante.texto, "no puede quedar vacío"
    assert "imagen" in entrante.texto.lower()


def test_un_mensaje_de_texto_no_trae_adjuntos():
    assert _traducir(novedad("hola")).adjuntos == []


# -- El aviso de "estoy trabajando" -------------------------------------------


class TelegramConIds(TelegramFalso):
    """Como el falso, pero devolviendo un message_id, que es lo que se edita."""

    def _api(self, metodo, datos=None, espera=30):
        super()._api(metodo, datos, espera)
        if metodo == "getUpdates":
            return {"result": self._tandas.pop(0) if self._tandas else []}
        return {"ok": True, "result": {"message_id": 4242}}


def test_el_primer_aviso_manda_un_mensaje():
    canal = TelegramConIds()

    identificador = canal.avisar("555", "🎨 Creando la imagen…")

    assert canal.enviados[0]["metodo"] == "sendMessage"
    assert canal.enviados[0]["datos"]["text"] == "🎨 Creando la imagen…"
    assert identificador == 4242, "devuelve el id para poder editarlo"


def test_el_segundo_aviso_edita_el_primero():
    """Uno solo, editándose: si no, el chat se llena de andamiaje."""
    canal = TelegramConIds()

    canal.avisar("555", "🌦️ Consultando el tiempo…", anterior=4242)

    assert canal.enviados[0]["metodo"] == "editMessageText"
    assert canal.enviados[0]["datos"]["message_id"] == 4242


def test_el_aviso_se_borra_al_terminar():
    canal = TelegramConIds()

    canal.quitar_aviso("555", 4242)

    assert canal.enviados[0]["metodo"] == "deleteMessage"


def test_sin_aviso_puesto_no_se_borra_nada():
    canal = TelegramConIds()

    canal.quitar_aviso("555", None)

    assert canal.enviados == []


def test_si_falla_el_aviso_no_pasa_nada():
    """Es andamiaje: que falle no puede costar la respuesta."""
    canal = TelegramConIds()

    def explota(*a, **k):
        raise OSError("sin red")

    canal._api = explota

    assert canal.avisar("555", "hola") is None       # no levanta
    canal.quitar_aviso("555", 4242)                  # tampoco


# -- Bajar la foto que mandó la persona ---------------------------------------


class TelegramQueBaja(TelegramFalso):
    """Simula los dos pasos de Telegram: getFile y después la descarga."""

    def __init__(self, camino="fotos/abc.jpg", contenido=b"los-bytes"):
        super().__init__()
        self._camino = camino
        self._contenido = contenido

    def _api(self, metodo, datos=None, espera=30):
        super()._api(metodo, datos, espera)
        if metodo == "getFile":
            return {"result": {"file_path": self._camino} if self._camino else {}}
        return {"ok": True, "result": {}}


def test_bajar_una_foto_son_dos_pasos(monkeypatch):
    canal = TelegramQueBaja()

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"los-bytes"

    pedidas = []

    def urlopen_falso(url, timeout=None):
        pedidas.append(url)
        return Respuesta()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_falso)

    assert canal.descargar("un-file-id") == b"los-bytes"
    assert canal.enviados[0]["metodo"] == "getFile"
    # La descarga va por /file/bot..., que es otro camino que el de la API
    assert "/file/bot" in pedidas[0]
    assert pedidas[0].endswith("fotos/abc.jpg")


def test_si_la_foto_no_se_puede_bajar_devuelve_none():
    """Una foto que falla no puede dejar sin respuesta a la persona."""
    canal = TelegramQueBaja(camino=None)

    assert canal.descargar("un-file-id") is None


# -- Notas de voz -------------------------------------------------------------


def con_voz(clave="voice", pie=None, update=1, chat=555) -> dict:
    """Un mensaje de audio, como lo manda Telegram."""
    mensaje = {
        "chat": {"id": chat},
        "from": {"id": 9, "is_bot": False},
        clave: {"file_id": "el-audio", "duration": 4, "mime_type": "audio/ogg"},
    }
    if pie is not None:
        mensaje["caption"] = pie

    return {"update_id": update, "message": mensaje}


def test_una_nota_de_voz_ya_no_se_descarta():
    entrante = _traducir(con_voz())

    assert entrante is not None
    assert entrante.voz == "el-audio"


def test_un_archivo_de_audio_tambien_vale():
    """`voice` es la nota grabada; `audio` es un archivo que te reenvían."""
    assert _traducir(con_voz(clave="audio")).voz == "el-audio"


def test_el_audio_no_se_confunde_con_una_foto():
    assert _traducir(con_voz()).adjuntos == [], "una nota de voz no es un adjunto de imagen"
    assert _traducir(con_foto()).voz == "", "una foto no es una nota de voz"


def test_un_mensaje_de_texto_no_trae_voz():
    assert _traducir(novedad("hola")).voz == ""


def test_una_nota_de_voz_no_se_descarta_por_no_traer_texto():
    """El bug que hacía que mandar un audio no hiciera nada.

    `deberia_responder` descartaba todo mensaje sin texto, y una nota de voz no
    trae ninguno: el texto sale de transcribirla, después. Así que el audio se
    caía aquí sin llegar nunca a Whisper, y desde fuera era exactamente igual a
    que el bot estuviera roto.
    """
    canal = TelegramFalso()
    entrante = _traducir(con_voz())

    assert canal.deberia_responder(entrante) is True


def test_una_foto_sin_pie_tampoco():
    canal = TelegramFalso()

    assert canal.deberia_responder(_traducir(con_foto())) is True


def test_un_mensaje_de_verdad_vacio_si_se_descarta():
    """Lo que no trae nada de nada sigue sin contestarse."""
    canal = TelegramFalso()
    from agente.canales.base import MensajeEntrante

    vacio = MensajeEntrante(texto="   ", conversacion="555", identificador="1")

    assert canal.deberia_responder(vacio) is False
