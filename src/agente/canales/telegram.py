"""El canal de Telegram.

Traduce en las dos direcciones: lo que llega de Telegram se convierte en un
`MensajeEntrante`, y lo que responde el agente sale como uno o varios mensajes
del bot. **El agente no se toca**: recibe texto y devuelve texto.

Telegram se puede escuchar de dos formas, y aquí usamos la primera:

    polling  → tu programa le pregunta a Telegram "¿hay algo nuevo?"  ← esta
    webhook  → Telegram le pega a una URL tuya (necesita URL pública y HTTPS)

Polling es lo que hace que esto **funcione desde tu ordenador**, sin dominio,
sin certificado y sin abrir puertos. Un canal que obligara a webhook —hay
varios— necesitaría un servidor de verdad; este no.

El `conversacion` (el thread_id de LangGraph) es el **chat_id** de Telegram.
Eso es lo único que no se puede equivocar: si dos personas compartieran el
mismo valor, compartirían la memoria y leerían la conversación de otro.

Se usa `urllib`, de la biblioteca estándar, para no sumar una dependencia.
La API de Telegram son pedidos HTTP con JSON: no hace falta más.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path
from secrets import token_hex
from typing import Iterator

from .base import Canal, MensajeEntrante

API = "https://api.telegram.org"

# Cuánto se queda esperando cada consulta a Telegram. Esto es *long polling*:
# en vez de preguntar mil veces por segundo, la consulta queda abierta hasta
# que llega un mensaje o se cumple este tiempo. Menos tráfico y respuesta
# instantánea.
ESPERA_DE_ESCUCHA = 25

# El corte de urllib tiene que ser mayor que el de arriba: si fueran iguales,
# cortaríamos nosotros justo cuando Telegram está por contestar.
ESPERA_DE_RED = ESPERA_DE_ESCUCHA + 10

# Telegram rechaza cualquier mensaje más largo que esto.
LARGO_MAXIMO = 4096

# El pie de una foto tiene su propio tope, mucho más corto que un mensaje.
PIE_MAXIMO = 1024

# Bajar una foto que mandó la persona: son cientos de kilobytes, no una frase.
ESPERA_DE_BAJADA = 60


class Telegram(Canal):
    """El bot de Telegram."""

    nombre = "telegram"

    def __init__(self, token: str, espera: int = ESPERA_DE_ESCUCHA) -> None:
        if not token:
            raise ValueError(
                "Falta el token de Telegram. Abre el .env y completa "
                "TELEGRAM_TOKEN con el que te dio @BotFather."
            )

        self.token = token
        self.espera = espera

        # Desde qué novedad seguimos pidiendo. Telegram guarda los mensajes
        # hasta que le confirmas que los recibiste, y la confirmación es
        # justamente pedirle los siguientes.
        self._proxima = 0

        # Los últimos mensajes que ya contestamos. Telegram reenvía ante la
        # duda, y sin esto el agente contestaría dos veces lo mismo. Es una
        # cola corta: basta con acordarse de los últimos.
        self._ya_contestados: deque[str] = deque(maxlen=500)

    # -- Entrada ---------------------------------------------------------------

    def escuchar(self) -> Iterator[MensajeEntrante]:
        """Se queda esperando mensajes, para siempre.

        Devuelve un mensaje por vez, ya traducido. El que la recorre decide
        qué hacer con cada uno.
        """
        while True:
            for novedad in self._traer_novedades():
                # El offset se adelanta SIEMPRE, aunque el mensaje no nos
                # sirva. Si no, un mensaje que no sabemos atender (una foto,
                # por ejemplo) vuelve a llegar para siempre y el bot se
                # queda trabado en él.
                self._proxima = novedad["update_id"] + 1

                entrante = _traducir(novedad)
                if entrante is not None:
                    yield entrante

    def _traer_novedades(self) -> list[dict]:
        """Le pregunta a Telegram si hay mensajes nuevos."""
        # Por qué se traga el error: esto es la red, no el modelo. Que se
        # corte el wifi un segundo no puede matar al bot — si dejáramos que
        # explote, habría que levantarlo a mano cada vez. Devolvemos una
        # tanda vacía y en la próxima vuelta se intenta de nuevo. Un token
        # mal puesto sí se nota igual: no llega ningún mensaje nunca.
        try:
            respuesta = self._api(
                "getUpdates",
                {
                    "offset": self._proxima,
                    "timeout": self.espera,
                    # Solo mensajes: no nos interesan ediciones ni votos.
                    "allowed_updates": ["message"],
                },
                espera=ESPERA_DE_RED,
            )
        except Exception:
            return []

        return respuesta.get("result") or []

    def deberia_responder(self, mensaje: MensajeEntrante) -> bool:
        """Descarta lo que ya contestamos y lo que viene vacío.

        Telegram reenvía un mensaje si no le confirmamos que llegó, así que
        sin esto el agente contesta dos veces lo mismo.

        **Ojo con la condición de "vacío".** Antes era solo `not texto`, y eso
        se comía todas las notas de voz: una nota de voz no trae texto ninguno
        —el texto sale de transcribirla, más tarde y en otro sitio—, así que se
        descartaba aquí sin llegar nunca a Whisper. Desde fuera era idéntico a
        que el bot no funcionara: mandabas un audio y no pasaba nada. Una foto
        sin pie se salvaba de casualidad, porque `_traducir()` le pone un texto
        por defecto.
        """
        if not mensaje.texto.strip() and not mensaje.adjuntos and not mensaje.voz:
            return False

        if mensaje.identificador in self._ya_contestados:
            return False

        self._ya_contestados.append(mensaje.identificador)
        return True

    # -- Salida ----------------------------------------------------------------

    def enviar(self, conversacion: str, mensajes: list[str]) -> None:
        """Manda las respuestas a ese chat, en orden."""
        for mensaje in mensajes:
            # Un mensaje más largo que el tope lo rechaza Telegram entero, así
            # que lo cortamos. partir_respuesta() ya parte por sentido; esto es
            # la red de seguridad para el caso raro de una respuesta enorme.
            for pedazo in _cortar(mensaje, LARGO_MAXIMO):
                self._api("sendMessage", {"chat_id": conversacion, "text": pedazo})

    def descargar(self, identificador: str) -> bytes | None:
        """Los bytes de un archivo que mandó la persona, o None si no se pudo.

        Son dos pasos, porque Telegram no da el archivo directamente: primero
        `getFile` cambia el identificador por una ruta temporal, y después esa
        ruta se descarga de otro dominio (`/file/bot<token>/...`, no `/bot...`).

        Devuelve None en vez de levantar: una foto que no se pudo bajar no
        puede dejar sin respuesta a la persona. El agente contestará al texto
        y ya está.
        """
        try:
            datos = self._api("getFile", {"file_id": identificador})
            camino = (datos.get("result") or {}).get("file_path")
            if not camino:
                return None

            with urllib.request.urlopen(
                f"{API}/file/bot{self.token}/{camino}", timeout=ESPERA_DE_BAJADA
            ) as respuesta:
                return respuesta.read()
        except Exception:
            return None

    def avisar(self, conversacion: str, texto: str, anterior: int | None = None) -> int | None:
        """Pone (o cambia) el mensaje de "estoy trabajando".

        Devuelve el id del mensaje para poder editarlo la próxima vez, o
        borrarlo cuando ya no haga falta. Si `anterior` viene puesto, se edita
        ese en vez de mandar uno nuevo: así el chat no se llena de avisos.

        Todo va dentro de un try porque esto es andamiaje. Que falle el aviso
        no puede costarte la respuesta.
        """
        try:
            if anterior is not None:
                self._api(
                    "editMessageText",
                    {"chat_id": conversacion, "message_id": anterior, "text": texto},
                )
                return anterior

            respuesta = self._api(
                "sendMessage", {"chat_id": conversacion, "text": texto}
            )
            return (respuesta.get("result") or {}).get("message_id")
        except Exception:
            return anterior

    def quitar_aviso(self, conversacion: str, mensaje: int | None) -> None:
        """Borra el mensaje de aviso: ya llegó la respuesta y estorba."""
        if mensaje is None:
            return

        try:
            self._api(
                "deleteMessage", {"chat_id": conversacion, "message_id": mensaje}
            )
        except Exception:
            pass

    def enviar_imagen(self, conversacion: str, ruta: str, texto: str = "") -> None:
        """Manda una imagen: primero para verla, después para guardarla.

        Van los dos envíos a propósito. `sendPhoto` es lo que se ve en el chat
        sin tocar nada, pero Telegram la recomprime y le baja la resolución;
        `sendDocument` manda el PNG tal cual, con la calidad original, pero
        llega como un adjunto que hay que abrir. Con los dos tienes lo uno y lo
        otro.

        Si algo falla, se avisa por texto y la conversación sigue. Y ojo, que
        esto **no** es simétrico con `enviar()`: allí una excepción tira el bot
        (el envío queda fuera del try de `atender()`), y aquí no se puede
        permitir, porque subir un archivo falla mucho más a menudo que mandar
        una frase: por tamaño, por formato, o porque la red se cortó a medias.
        """
        archivo = Path(ruta)

        if not archivo.is_file():
            self.enviar(
                conversacion, ["Generé la imagen pero ya no la encuentro en el disco."]
            )
            return

        # El pie de foto tiene su propio tope, más corto que el de un mensaje.
        # Lo que sobre no se pierde: el texto de la respuesta va igual por su
        # cuenta en enviar().
        pie = texto[:PIE_MAXIMO] if texto else ""

        try:
            self._subir(
                "sendPhoto", {"chat_id": conversacion, "caption": pie}, "photo", archivo
            )
        except Exception as e:
            self.enviar(
                conversacion, [f"No pude enviar la imagen: {type(e).__name__}: {e}"]
            )
            return

        try:
            self._subir(
                "sendDocument", {"chat_id": conversacion}, "document", archivo
            )
        except Exception:
            # La foto ya llegó, que es lo que importa. El archivo en calidad
            # original es un extra: si falla, no merece un aviso de error.
            pass

    def escribiendo(self, conversacion: str, accion: str = "typing") -> None:
        """Muestra el "escribiendo..." mientras el modelo piensa.

        No es decorativo: una respuesta puede tardar varios segundos y sin
        esto la persona no sabe si el bot la escuchó o se colgó.

        `accion` existe para poder decir "subiendo una foto" (`upload_photo`)
        cuando lo que viene es una imagen: generarla tarda medio minuto, y seis
        "escribiendo..." seguidos sin nada detrás preocupan más que tranquilizan.
        """
        # Que falle el aviso no puede voltear la respuesta: es cosmético.
        try:
            self._api("sendChatAction", {"chat_id": conversacion, "action": accion})
        except Exception:
            pass

    # -- La API ----------------------------------------------------------------

    def yo_soy(self) -> dict:
        """Los datos del bot. Sirve para avisar al arrancar con cuál se habla."""
        return self._api("getMe").get("result") or {}

    def _subir(
        self, metodo: str, campos: dict, nombre: str, archivo: Path, espera: int = 120
    ) -> dict:
        """Como `_api()`, pero subiendo un archivo.

        Hace falta porque `_api()` manda JSON, y para subir bytes Telegram
        exige `multipart/form-data`. La otra salida sería darle una URL pública
        en vez del archivo, pero el bot corre en tu máquina: no hay ninguna URL
        a la que Telegram pueda entrar. Así que hay que subirlo.

        El multipart se arma a mano con `urllib`, como todo el módulo, para no
        sumar una dependencia por un formato que son diez líneas: una frontera
        al azar, un bloque por campo, el archivo con su nombre, y la frontera
        de cierre con dos guiones detrás.

        La espera es larga —dos minutos— porque aquí se suben megabytes, no una
        frase.
        """
        frontera = f"----agente{token_hex(8)}"
        cuerpo = bytearray()

        for clave, valor in campos.items():
            cuerpo += (
                f"--{frontera}\r\n"
                f'Content-Disposition: form-data; name="{clave}"\r\n\r\n'
                f"{valor}\r\n"
            ).encode("utf-8")

        # El tipo sale de la extensión y no está clavado a image/png: por aquí
        # también pasan audios cuando se reenvía una nota de voz, y mentirle el
        # tipo a Telegram funciona hasta que deja de funcionar.
        tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"

        cuerpo += (
            f"--{frontera}\r\n"
            f'Content-Disposition: form-data; name="{nombre}"; '
            f'filename="{archivo.name}"\r\n'
            f"Content-Type: {tipo}\r\n\r\n"
        ).encode("utf-8")
        cuerpo += archivo.read_bytes()
        cuerpo += f"\r\n--{frontera}--\r\n".encode("utf-8")

        pedido = urllib.request.Request(
            f"{API}/bot{self.token}/{metodo}",
            data=bytes(cuerpo),
            headers={"Content-Type": f"multipart/form-data; boundary={frontera}"},
        )

        with urllib.request.urlopen(pedido, timeout=espera) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))

    def _api(self, metodo: str, datos: dict | None = None, espera: int = 30) -> dict:
        """Una llamada a la API de Telegram."""
        url = f"{API}/bot{self.token}/{metodo}"
        cuerpo = json.dumps(datos or {}).encode("utf-8")

        pedido = urllib.request.Request(
            url,
            data=cuerpo,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(pedido, timeout=espera) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))


# -- Ayudantes ----------------------------------------------------------------


def _traducir(novedad: dict) -> MensajeEntrante | None:
    """Convierte lo que manda Telegram en algo que el agente entiende.

    Atiende texto, **fotos** y **notas de voz**. Devuelve None con lo que el
    agente no sabe leer todavía (un sticker, un documento, un vídeo).

    Con una foto, el texto sale del pie que la acompaña, y si no lo hay se pone
    uno por defecto: el modelo necesita saber qué se espera de él, y una imagen
    a secas no lo dice. La foto en sí no se descarga aquí —esto solo traduce, y
    descargar es salir a la red— sino en `escuchar()`.
    """
    mensaje = novedad.get("message") or {}
    chat = mensaje.get("chat") or {}
    quien = mensaje.get("from") or {}

    if not chat.get("id"):
        return None

    # Un bot contestándole a otro bot es un ida y vuelta infinito.
    if quien.get("is_bot"):
        return None

    fotos = mensaje.get("photo") or []
    texto = mensaje.get("text") or mensaje.get("caption") or ""

    # Una nota de voz (`voice`) o un archivo de audio (`audio`). Los dos hay que
    # transcribirlos, y eso lo hace el bot: aquí solo se apunta el
    # identificador, porque traducir no tiene que salir a la red.
    audio = mensaje.get("voice") or mensaje.get("audio") or {}
    voz = audio.get("file_id", "")

    if not texto and not fotos and not voz:
        return None

    if fotos and not texto:
        texto = "¿Qué ves en esta imagen?"

    return MensajeEntrante(
        texto=texto,
        # El chat_id es el thread_id: la memoria de cada persona por separado.
        conversacion=str(chat["id"]),
        identificador=str(novedad["update_id"]),
        datos=mensaje,
        # Telegram manda la misma foto en varios tamaños, del más chico al más
        # grande. Nos queda el último: es el que mejor lee el modelo, y el que
        # de todas formas ya está comprimido por Telegram.
        adjuntos=[fotos[-1]["file_id"]] if fotos else [],
        voz=voz,
    )


def _cortar(texto: str, largo: int) -> list[str]:
    """Parte un texto que no entra en un mensaje de Telegram.

    Corta en el último renglón que entre, para no partir una palabra al medio.
    """
    if len(texto) <= largo:
        return [texto]

    pedazos = []
    resto = texto

    while len(resto) > largo:
        tajo = resto.rfind("\n", 0, largo)
        if tajo <= 0:
            tajo = resto.rfind(" ", 0, largo)
        if tajo <= 0:
            tajo = largo  # una parrafada sin espacios: cortamos y listo

        pedazos.append(resto[:tajo].strip())
        resto = resto[tajo:].strip()

    if resto:
        pedazos.append(resto)

    return pedazos
