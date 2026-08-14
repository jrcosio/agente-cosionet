"""Qué es un canal.

Un canal es el pegamento entre un lugar donde la gente escribe (Telegram, tu
web, lo que venga) y el agente. Traduce en las dos direcciones:

    mensaje que llega  →  agente.responder(texto, conversacion)  →  mensaje que sale

El agente no sabe nada de esto. Recibe texto y devuelve texto. Por eso se
puede enchufar a cualquier lado sin tocarlo.

Lo único que hay que resolver bien en cada canal es **de dónde sale el
`conversacion`** (el thread_id de LangGraph), porque eso es lo que hace que
las charlas de distintas personas no se mezclen:

    plataforma de pruebas  →  siempre "web", hay un solo usuario
    Telegram               →  el chat_id

Este archivo es solo la forma. El canal de verdad está en `telegram.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MensajeEntrante:
    """Un mensaje que llega de afuera, ya traducido a algo que el agente entiende."""

    texto: str
    conversacion: str          # el thread_id: quién habla
    identificador: str = ""    # el id del mensaje en el canal, para no repetirlo
    datos: dict = field(default_factory=dict)  # lo crudo, por si el canal lo necesita
    # Lo que venga con el mensaje además del texto: hoy, los identificadores de
    # las fotos que mandó la persona. Son identificadores del canal y no bytes
    # porque traducir un mensaje no tiene que salir a la red — descargarlos es
    # cosa del canal, cuando toque.
    adjuntos: list[str] = field(default_factory=list)
    # El identificador de una nota de voz, si el mensaje era un audio en vez de
    # texto. Va aparte de `adjuntos` porque no es lo mismo: una foto se le pasa
    # al modelo tal cual, y un audio hay que convertirlo en texto antes — el
    # modelo no oye (ver voz.py).
    voz: str = ""


class Canal(ABC):
    """Un lugar por donde entran y salen mensajes."""

    nombre: str = "sin nombre"

    @abstractmethod
    def enviar(self, conversacion: str, mensajes: list[str]) -> None:
        """Manda una o varias respuestas a esa conversación.

        Es una lista y no un texto porque en mensajería conviene partir las
        respuestas largas en varios mensajes (ver respuesta.partir_respuesta).
        """

    def enviar_imagen(self, conversacion: str, ruta: str, texto: str = "") -> None:
        """Manda un archivo de imagen a esa conversación.

        Por defecto no hace nada, y es a propósito: no todos los canales saben
        mandar archivos, y el agente no tiene por qué enterarse de cuáles sí.
        Un canal que pueda lo sobrescribe —lo hace `Telegram`— y el que no,
        deja pasar la imagen sin romperse. Es el mismo criterio que
        `deberia_responder()`: implementación por defecto sensata y cada canal
        la ajusta.

        `ruta` es un archivo en el disco de esta máquina, no una URL: la
        generó una herramienta hace un segundo (ver `Respuesta.imagenes`).
        """

    def deberia_responder(self, mensaje: MensajeEntrante) -> bool:
        """Si el agente tiene que contestar este mensaje o dejarlo pasar.

        Aquí va lo que en producción evita que el bot moleste:
          · que una persona haya tomado la conversación
          · que el bot esté apagado para ese contacto
          · que sea un mensaje que mandó el propio bot
          · que sea un reenvío repetido del mismo mensaje

        Por defecto contesta todo. Cada canal lo ajusta.
        """
        return True
