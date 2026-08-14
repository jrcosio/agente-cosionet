"""El agente.

Esta es la pieza central y es corta a propósito. Un agente conversacional
son tres cosas juntas:

    1. Un prompt de sistema  → quién es y cómo se comporta
    2. Una memoria           → de qué vienen hablando
    3. Un modelo             → a quién le mandas las dos cosas de arriba

Con LangGraph esas tres cosas se arman como un grafo. Aquí el grafo es un ciclo
de dos nodos:

    modelo → ¿pidió una herramienta?
               sí → herramientas → vuelve al modelo
               no → listo, contesta

Mientras el modelo no pida nada, el camino es el de siempre: un solo paso y
responde. Las herramientas viven en herramientas.py.

El agente no sabe si lo están usando desde la terminal, desde la web o desde
Telegram. Recibe texto y devuelve texto. Esa frontera es lo que después
permite enchufarlo a cualquier canal sin tocar una línea de aquí adentro.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .config import Config
from .herramientas import AVISOS, HERRAMIENTAS
from .memoria import crear_memoria
from .modelos import crear_modelo
from .prompts import leer_prompt
from .respuesta import partir_respuesta


@dataclass
class Respuesta:
    """Lo que devuelve el agente cuando termina de responder."""

    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_salida: int = 0
    # Del total de entrada, cuántos salieron del caché (baratos) y cuántos
    # se guardaron en el caché para la próxima.
    tokens_cache_leidos: int = 0
    tokens_cache_guardados: int = 0
    # Los archivos que generó una herramienta en este turno: hoy, las rutas de
    # las imágenes de `crear_imagen`. Van aparte del texto porque el agente
    # sigue devolviendo texto —la frontera del proyecto no se mueve— y esto es
    # "además, mira estos archivos". Cada canal decide qué hacer con ellos: la
    # web los sirve por HTTP, Telegram los sube, y la terminal los ignora.
    imagenes: list[str] = field(default_factory=list)


class Aviso(str):
    """Un "estoy trabajando" en medio de la respuesta.

    Sale por el mismo hilo que el texto, y ese es todo el truco: cuando el
    modelo pide una herramienta que tarda medio minuto, el aviso tiene que
    llegar **mientras** la herramienta trabaja, no después. Si fuera una
    llamada aparte no serviría: quien recorre la transmisión está bloqueado
    esperando el siguiente pedazo, y no volvería a mirar hasta que la
    herramienta terminara.

    **Es un `str` a propósito.** Así quien solo quiera texto —la terminal, un
    `"".join(...)`— sigue funcionando sin enterarse, y quien quiera
    distinguirlo pregunta `isinstance(pedazo, Aviso)`. La web lo manda como un
    evento aparte y Telegram edita un mensaje con él; la terminal lo imprime
    como una línea más, que es exactamente lo que quieres ver ahí.

    No entra en `Respuesta.texto`: es andamiaje, no respuesta.

    Lleva dos cosas más además del texto:

      · `visible` — si es False, el aviso es **solo para la traza de la
        terminal** y los canales no lo muestran. Sirve para contar cosas que a
        quien está en Telegram le sobran (qué devolvió una herramienta) pero que
        en el equipo son justo lo que hace falta ver para saber que no se ha
        colgado.
      · `detalle` — la letra pequeña para esa traza: los argumentos con los que
        se llamó a la herramienta, por ejemplo.
    """

    visible: bool
    detalle: str

    def __new__(cls, texto: str, *, visible: bool = True, detalle: str = ""):
        # Un str es inmutable, así que los datos de más se ponen en __new__ y
        # no en __init__.
        aviso = super().__new__(cls, texto)
        aviso.visible = visible
        aviso.detalle = detalle
        return aviso


class Transmision:
    """Una respuesta que llega de a pedacitos.

    Se recorre con un for y, cuando termina, deja el resumen en `.resumen`:

        transmision = agente.responder_en_vivo("hola")
        for pedazo in transmision:
            print(pedazo, end="")
        print(transmision.resumen.tokens_salida)

    Por qué existe, en vez de guardar el resumen en el agente: porque el
    mismo agente puede estar atendiendo varias conversaciones al mismo
    tiempo. Si el resumen viviera en el agente, dos conversaciones que
    responden a la vez se pisarían los datos. Aquí cada transmisión tiene
    el suyo.
    """

    def __init__(self, pedazos, al_terminar) -> None:
        self._pedazos = pedazos
        self._al_terminar = al_terminar
        self._partes: list[str] = []
        self._terminada = False
        self.resumen: Respuesta | None = None

    def __iter__(self):
        # Una transmisión se consume una sola vez: los pedazos llegan del
        # modelo y no vuelven. Si ya la recorriste, te devolvemos lo que
        # quedó guardado en vez de un vacío silencioso.
        if self._terminada:
            yield from self._partes
            return

        for pedazo in self._pedazos:
            # Los avisos se dejan pasar pero no se guardan: no son parte de la
            # respuesta, y si entraran aquí acabarían dentro de
            # `resumen.texto` y en la memoria de la conversación.
            if not isinstance(pedazo, Aviso):
                self._partes.append(pedazo)
            yield pedazo

        self._terminada = True
        self.resumen = self._al_terminar()
        self.resumen.texto = "".join(self._partes)

    def texto(self) -> str:
        """El texto completo. Consume la transmisión si todavía no la recorriste."""
        return "".join(self)


class Agente:
    def __init__(self, config: Config | None = None, checkpointer=None) -> None:
        self.config = config or Config.desde_entorno()

        self.modelo = crear_modelo(
            proveedor=self.config.proveedor,
            api_key=self.config.api_key,
            modelo=self.config.modelo,
            max_tokens=self.config.max_tokens,
        )

        # La memoria: SQLite si MODO=test, Postgres si MODO=produccion.
        # Se le puede pasar otra a mano (los tests le pasan una en RAM).
        self.checkpointer = checkpointer or crear_memoria(self.config)

        self.grafo = self._construir_grafo()

    # -- El grafo -------------------------------------------------------------

    def _construir_grafo(self):
        """Arma el grafo: el modelo, las herramientas, y la vuelta al modelo."""

        # bind_tools() es lo que le avisa al modelo qué herramientas existe.
        # Sin esto nunca las pide, por más que estén escritas.
        modelo = self.modelo.bind_tools(HERRAMIENTAS)

        def nodo_modelo(estado: MessagesState) -> dict:
            respuesta = modelo.invoke(self._armar_entrada(estado))
            return {"messages": [respuesta]}

        grafo = StateGraph(MessagesState)
        grafo.add_node("modelo", nodo_modelo)
        grafo.add_node("herramientas", ToolNode(HERRAMIENTAS))
        grafo.add_edge(START, "modelo")

        # tools_condition mira la respuesta del modelo: si pidió herramientas
        # devuelve "tools", y si no, END. Como nuestro nodo se llama en
        # castellano, le pasamos el mapa para traducir esa salida.
        grafo.add_conditional_edges(
            "modelo",
            tools_condition,
            {"tools": "herramientas", END: END},
        )

        # Y con el resultado en la mano, el modelo vuelve a hablar. Este es el
        # ciclo: puede pedir varias herramientas seguidas antes de contestar.
        grafo.add_edge("herramientas", "modelo")

        return grafo.compile(checkpointer=self.checkpointer)

    def _armar_entrada(self, estado: MessagesState) -> list:
        """Prompt de sistema + los últimos mensajes de la conversación.

        El prompt se lee del archivo en CADA mensaje, no una sola vez al
        arrancar: por eso puedes editar prompts/sistema.md sin reiniciar.
        """
        recientes = _recortar(estado["messages"], self.config.memoria_mensajes)
        return [self._sistema(), *recientes]

    def _sistema(self) -> SystemMessage:
        """El prompt del sistema, marcado para que el proveedor lo cachee.

        El prompt viaja entero en CADA mensaje. Si es largo, lo estás pagando
        una y otra vez. El caché hace que el proveedor lo guarde de su lado y
        te cobre una fracción a partir del segundo mensaje.

        Cada proveedor lo maneja distinto:
          · Claude → hay que marcarlo a mano (es lo que hacemos aquí abajo)
          · OpenAI → automático, no hay que hacer nada
          · Gemini → automático, no hay que hacer nada

        Ojo: el caché solo se activa cuando el prompt supera cierto tamaño
        (más o menos 1.000 tokens). Con un prompt corto no pasa nada malo,
        simplemente no se cachea.
        """
        texto = leer_prompt(self.config.prompt_sistema)

        if self.config.cache and self.config.proveedor == "claude":
            return SystemMessage(
                content=[
                    {
                        "type": "text",
                        "text": texto,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            )

        return SystemMessage(texto)

    # -- Lo que usa todo el mundo --------------------------------------------

    def responder(
        self,
        texto: str,
        conversacion: str = "local",
        imagenes: list[bytes] | None = None,
    ) -> Respuesta:
        """Le mandas un mensaje, te devuelve la respuesta completa.

        `conversacion` es el thread_id de LangGraph: cada valor distinto es
        una conversación separada, con su propia memoria. En Telegram aquí va
        el chat_id de la persona.

        En `imagenes` van fotos que manda la persona, en bytes: el modelo las
        ve y puede hablar de ellas. Son bytes y no rutas porque no hay ningún
        archivo — llegan de Telegram y van directas al modelo.
        """
        salida = self.grafo.invoke(
            {"messages": [_entrada(texto, imagenes)]},
            config=self._config_hilo(conversacion),
        )
        mensajes = salida["messages"]

        respuesta = _a_respuesta(mensajes[-1], self.config.modelo)
        # Solo las de este turno, no las de toda la conversación: `messages`
        # trae el historial completo y reenviar la imagen de hace media hora
        # cada vez que alguien saluda no tiene ningún sentido. `_partir_en_turnos`
        # ya sabe dónde empieza el turno de ahora.
        respuesta.imagenes = _imagenes_de(_partir_en_turnos(mensajes)[-1])
        return respuesta

    def responder_en_vivo(
        self,
        texto: str,
        conversacion: str = "local",
        imagenes: list[bytes] | None = None,
    ) -> Transmision:
        """Igual que responder(), pero el texto llega mientras se escribe.

        Devuelve una Transmision: la recorres con un for y al terminar tienes
        el resumen (tokens, modelo) en `.resumen`.

        Por el camino puede colar algún `Aviso` ("estoy creando la imagen…").
        Es un `str`, así que si no te interesa no tienes que hacer nada; y si
        te interesa, `isinstance(pedazo, Aviso)` los distingue.
        """
        # Cada transmisión guarda su propio acumulado. Nada de estado en el
        # agente: puede haber muchas conversaciones respondiendo a la vez.
        acumulado: list = [None]

        # Las que GENERAN las herramientas, que no son las que manda la persona.
        # El nombre importa: cuando esta lista se llamaba `imagenes` tapaba al
        # parámetro del mismo nombre, y las fotos que llegaban de Telegram se
        # perdían sin ruido — el modelo contestaba "no veo ninguna imagen" y no
        # había forma de saber por qué. Lo cuida
        # `test_las_fotos_llegan_tambien_por_el_camino_en_vivo`.
        generadas: list[str] = []

        # Los pedidos de herramienta llegan partidos: hay que juntarlos.
        seguidor = _SeguidorDeHerramientas()

        def pedazos() -> Iterator[str]:
            for pedazo, _ in self.grafo.stream(
                {"messages": [_entrada(texto, imagenes)]},
                config=self._config_hilo(conversacion),
                stream_mode="messages",
            ):
                # Cuando el modelo pide una herramienta, avisamos ANTES de que
                # se ejecute: es el único momento útil. Después de ejecutarla
                # ya no hace falta decir que está trabajando.
                yield from seguidor.mirar(pedazo)
                # Por aquí también pasa lo que devuelven las herramientas, y eso
                # no es la respuesta: es materia prima para que el modelo la
                # escriba. Si lo dejáramos salir, la persona vería el listado
                # crudo del clima en pantalla y después la respuesta de verdad.
                #
                # Pero antes de descartarlo hay que mirarlo: este `for` es el
                # ÚNICO sitio por el que pasa el ToolMessage completo, con su
                # `artifact`. Si la imagen no se recoge aquí, se pierde — y con
                # ella la única forma que tiene la web de enterarse.
                if isinstance(pedazo, ToolMessage):
                    generadas.extend(_imagenes_de([pedazo]))
                    # Lo que devolvió la herramienta, solo para la traza: en
                    # Telegram esto sobra, pero en la terminal es la diferencia
                    # entre "está trabajando" y "no sé qué está pasando".
                    yield Aviso(
                        f"{pedazo.name or 'herramienta'} → {_resumir(pedazo)}",
                        visible=False,
                    )
                    continue

                # Los pedazos de LangChain se suman entre sí. Al sumarlos
                # vamos rearmando el mensaje entero, con el conteo de tokens
                # incluido (que en varios proveedores llega solo al final).
                # Cuando hay herramientas el modelo habla dos veces, así que
                # esta suma termina juntando el gasto de las dos llamadas:
                # que es justo lo que costó la respuesta.
                acumulado[0] = (
                    pedazo
                    if acumulado[0] is None
                    else _sumar(acumulado[0], pedazo)
                )

                trozo = _texto_de(pedazo)
                if trozo:
                    yield trozo

        def resumir() -> Respuesta:
            resumen = _a_respuesta(acumulado[0], self.config.modelo)
            resumen.imagenes = generadas
            return resumen

        return Transmision(pedazos(), resumir)

    # -- Utilidades -----------------------------------------------------------

    def responder_partido(
        self, texto: str, conversacion: str = "local"
    ) -> list[str]:
        """Como responder(), pero la respuesta ya viene partida en mensajes.

        Es lo que usa Telegram: en mensajería una respuesta larga se manda en
        varios globos cortos, no en un ladrillo.
        """
        return partir_respuesta(self.responder(texto, conversacion).texto)

    def historial(self, conversacion: str = "local") -> list:
        """Los mensajes guardados de una conversación."""
        estado = self.grafo.get_state(self._config_hilo(conversacion))
        return estado.values.get("messages", []) if estado.values else []

    def olvidar(self, conversacion: str = "local") -> None:
        """Borra de verdad una conversación: el agente arranca de cero con esa persona.

        Ojo: no basta con crear un agente nuevo. La conversación no vive en
        el agente, vive en el checkpointer — si no la borras de ahí, el agente
        nuevo la vuelve a levantar y parece que no pasó nada.
        """
        self.checkpointer.delete_thread(conversacion)

    def _config_hilo(self, conversacion: str) -> dict:
        return {"configurable": {"thread_id": conversacion}}


# -- Ayudantes ----------------------------------------------------------------


def _recortar(mensajes: list, tope: int) -> list:
    """Los últimos mensajes de la conversación, cortando en un turno completo.

    Aquí había un trim_messages() de LangChain, que recorta contando mensajes
    sueltos. Con herramientas eso se rompe, y es la trampa más cara de este
    proyecto: una vuelta de herramienta son tres mensajes atados entre sí
    (el modelo la pide, la herramienta contesta, el modelo responde), y los
    proveedores exigen que estén los tres. Si el corte cae justo en el medio y
    deja un pedido sin su resultado, la API devuelve un 400 que no explica
    nada y aparece solo cuando la conversación se hace larga.

    Por eso no recortamos por mensaje sino por turno: agrupamos y siempre
    entran o salen enteros. `tope` sigue siendo en mensajes (MEMORIA_MENSAJES),
    así que el número del .env significa lo mismo que antes.
    """
    turnos = _partir_en_turnos(mensajes)

    elegidos: list[list] = []
    total = 0

    for turno in reversed(turnos):
        # El turno más nuevo entra siempre, aunque se pase del tope: es la
        # pregunta que estamos respondiendo ahora mismo. Dejarlo afuera por
        # el presupuesto sería mandarle al modelo una conversación sin la
        # consulta — o peor, partida justo por la mitad de una herramienta.
        if elegidos and total + len(turno) > tope:
            break

        elegidos.insert(0, turno)
        total += len(turno)

    return [mensaje for turno in elegidos for mensaje in turno]


def _partir_en_turnos(mensajes: list) -> list[list]:
    """Agrupa la conversación en turnos.

    Un turno arranca en un mensaje de la persona y se lleva todo lo que se
    generó a partir de él: los pedidos de herramienta, sus resultados y la
    respuesta final. Es la unidad que no se puede partir al recortar.
    """
    turnos: list[list] = []

    for mensaje in mensajes:
        # El `or not turnos` es para el caso raro de que la conversación no
        # empiece con la persona: así el primer mensaje no se pierde.
        if isinstance(mensaje, HumanMessage) or not turnos:
            turnos.append([mensaje])
        else:
            turnos[-1].append(mensaje)

    return turnos


def _entrada(texto: str, imagenes: list[bytes] | None = None) -> HumanMessage:
    """El mensaje de la persona, con sus fotos si mandó alguna.

    Sin imágenes es un `HumanMessage` de toda la vida. Con imágenes, el
    contenido pasa a ser una lista de bloques: el texto y una entrada por foto.

    Se usa el formato estándar de LangChain (`{"type": "image",
    "source_type": "base64", ...}`) y no el de OpenAI (`image_url`) porque los
    dos funcionan pero solo el primero lo entienden también Claude y Gemini.
    Cada adaptador lo traduce a lo que su proveedor espera.

    Sobre el coste, que es lo que asusta y no debería: una foto de 3 MB en
    base64 son ~1.500 tokens, no 800.000. Una imagen se tokeniza como imagen,
    no como el texto de su base64 — que es justo lo contrario de lo que pasa
    si el base64 va en un campo de texto (ver `herramientas.crear_imagen`).
    Así que guardarla en la conversación sale barato y se puede seguir
    preguntando por ella en los mensajes siguientes.
    """
    if not imagenes:
        return HumanMessage(texto)

    bloques: list[dict] = [{"type": "text", "text": texto}]

    for foto in imagenes:
        bloques.append(
            {
                "type": "image",
                "source_type": "base64",
                "mime_type": "image/jpeg",
                "data": base64.b64encode(foto).decode("ascii"),
            }
        )

    return HumanMessage(content=bloques)


class _SeguidorDeHerramientas:
    """Junta los pedidos de herramienta, que llegan partidos en trozos.

    Y llegan de una forma que hay que ver para creer. Esto es lo que manda el
    modelo cuando pide el clima de Bilbao, un trozo por línea:

        {"name": "clima", "args": ""}      ← el nombre, sin argumentos
        {"name": null,    "args": "{\""}    ← y ahora los argumentos, letra
        {"name": null,    "args": "l"}         a letra, y ya sin el nombre
        {"name": null,    "args": "ugar"}
        {"name": null,    "args": "\":\""}
        {"name": null,    "args": "Bil"}
        {"name": null,    "args": "bao"}
        {"name": null,    "args": "\"}"}

    Así que para poder contar **con qué** se llamó a la herramienta hay que
    juntar los trozos por el `index` del pedido, que es lo único que los ata.
    Sin esto la traza dice "clima" a secas y no de dónde.

    Y hay dos avisos por herramienta, en dos momentos distintos a propósito:

      1. en cuanto se sabe el nombre, el aviso para la persona — cuanto antes,
         que de eso se trata;
      2. cuando los argumentos están completos, la línea para la traza. Llega
         un instante después y justo antes de que la herramienta se ejecute.
    """

    def __init__(self) -> None:
        self._nombres: dict[int, str] = {}
        self._crudos: dict[int, str] = {}
        self._avisados: set[int] = set()
        self._detallados: set[int] = set()

    def mirar(self, pedazo) -> list[Aviso]:
        """Los avisos que toca soltar por este pedazo. Vacío casi siempre."""
        avisos: list[Aviso] = []

        for trozo in getattr(pedazo, "tool_call_chunks", None) or []:
            if not isinstance(trozo, dict):
                continue

            indice = trozo.get("index") or 0
            if trozo.get("name"):
                self._nombres[indice] = trozo["name"]
            self._crudos[indice] = self._crudos.get(indice, "") + (trozo.get("args") or "")

            nombre = self._nombres.get(indice)
            if not nombre:
                continue

            argumentos = _argumentos_legibles(self._crudos.get(indice, ""))

            if indice not in self._avisados:
                self._avisados.add(indice)
                if argumentos:
                    self._detallados.add(indice)
                avisos.append(
                    Aviso(
                        AVISOS.get(nombre, f"Usando {nombre}…"),
                        # Una herramienta sin aviso escrito igual se cuenta en la
                        # traza: en el equipo se quiere ver todo.
                        visible=nombre in AVISOS,
                        detalle=f"{nombre}({argumentos})" if argumentos else nombre,
                    )
                )
            elif argumentos and indice not in self._detallados:
                self._detallados.add(indice)
                avisos.append(Aviso(f"{nombre}({argumentos})", visible=False))

        return avisos


def _argumentos_legibles(crudo: str) -> str:
    """Los argumentos de un pedido, si ya llegaron enteros.

    Devuelve cadena vacía mientras el JSON esté a medias, que es la mayor parte
    del tiempo: que parsee es justo la señal de que ya está completo.
    """
    if not crudo.strip():
        return ""

    try:
        datos = json.loads(crudo)
    except ValueError:
        return ""

    if not isinstance(datos, dict):
        return _acortar(str(datos))

    return _acortar(", ".join(f"{k}={v!r}" for k, v in datos.items()))


def _acortar(texto: str, tope: int = 110) -> str:
    """Corta dejando claro que cortó.

    Sin los puntos, un argumento largo cortado a la mitad parece un valor
    malformado y hace dudar de si el problema es el corte o la llamada.
    """
    return texto if len(texto) <= tope else texto[:tope] + "…"


def _resumir(mensaje) -> str:
    """Una línea con lo que devolvió una herramienta, para la traza."""
    artefacto = getattr(mensaje, "artifact", None)
    if isinstance(artefacto, dict) and artefacto.get("ruta"):
        return Path(str(artefacto["ruta"])).name

    texto = mensaje.content if isinstance(mensaje.content, str) else str(mensaje.content)
    texto = " ".join(texto.split())
    return texto[:90] + ("…" if len(texto) > 90 else "")


def _imagenes_de(mensajes: list) -> list[str]:
    """Las rutas de las imágenes que dejaron las herramientas en esos mensajes.

    Una herramienta que genera un archivo lo anuncia en el `artifact` de su
    `ToolMessage`, no en el `content` (el motivo está escrito en
    `herramientas.crear_imagen`: el contenido va al modelo y se guarda en la
    memoria, y un PNG ahí dentro cuesta cientos de miles de tokens por turno).

    Aquí solo se leen esos artifacts. Que la ruta exista o no es cosa del
    canal: si el archivo desapareció, quien lo envía se dará cuenta.
    """
    rutas = []

    for mensaje in mensajes:
        if not isinstance(mensaje, ToolMessage):
            continue

        artefacto = getattr(mensaje, "artifact", None)
        if isinstance(artefacto, dict) and artefacto.get("tipo") == "imagen":
            ruta = artefacto.get("ruta")
            if ruta:
                rutas.append(str(ruta))

    return rutas


def _sumar(acumulado, pedazo):
    """Suma dos pedazos de respuesta. Si el proveedor manda algo raro, sigue."""
    try:
        return acumulado + pedazo
    except (TypeError, ValueError):
        return pedazo


def _texto_de(mensaje) -> str:
    """Saca el texto de un pedazo de respuesta.

    Hace falta porque no todos los proveedores devuelven lo mismo: algunos
    mandan un string y otros una lista de bloques.
    """
    if mensaje is None:
        return ""

    contenido = getattr(mensaje, "content", "")

    if isinstance(contenido, str):
        return contenido

    if isinstance(contenido, list):
        return "".join(
            b.get("text", "")
            for b in contenido
            if isinstance(b, dict) and b.get("type") == "text"
        )

    return ""


def _a_respuesta(mensaje, modelo_por_defecto: str) -> Respuesta:
    """Convierte la respuesta de LangChain en algo simple de usar."""
    if mensaje is None:
        return Respuesta(texto="", modelo=modelo_por_defecto)

    uso = getattr(mensaje, "usage_metadata", None) or {}
    metadatos = getattr(mensaje, "response_metadata", None) or {}
    detalle = uso.get("input_token_details") or {}

    return Respuesta(
        texto=_texto_de(mensaje),
        modelo=(
            metadatos.get("model_name")
            or metadatos.get("model")
            or modelo_por_defecto
        ),
        tokens_entrada=uso.get("input_tokens", 0),
        tokens_salida=uso.get("output_tokens", 0),
        tokens_cache_leidos=detalle.get("cache_read", 0),
        tokens_cache_guardados=detalle.get("cache_creation", 0),
    )
