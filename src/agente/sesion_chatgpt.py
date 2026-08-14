"""La sesión de ChatGPT: de acá sale la credencial del proveedor `chatgpt`.

Los otros tres proveedores se autentican con una clave de API que vos pegás
en el `.env` y que se paga por token. Este no: usa **tu suscripción de
ChatGPT**. La credencial la escribe Codex cuando entrás con tu cuenta, y
queda en `~/.codex/auth.json`. Nosotros la leemos de ahí.

Por eso este archivo es la única excepción a la regla de que las claves se
leen en `config.py`: no hay nada que pegar en el `.env`. Y pedirte que
copiaras el token a mano sería peor, porque vence cada diez días y Codex lo
renueva solo.

Lo que hace:

    leer_sesion()         → el token de acceso y la cuenta, tal como están
    credencial()          → el token, o cadena vacía si no sirve
    modelos_disponibles() → qué modelos ofrece la suscripción hoy

**Acá no se cachea nada a propósito.** Codex rota el token cada tanto y
reescribe el archivo; si nos guardáramos el primero, un proceso que vive
días (el bot de Telegram) seguiría mandando el viejo y de golpe empezaría a
comer 401 sin razón aparente. El archivo son cuatro kilobytes: releerlo sale
más barato que el error.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# Donde Codex guarda lo suyo. Respetamos CODEX_HOME porque es la variable
# con la que Codex mismo se puede mudar de carpeta.
CARPETA_CODEX = Path(os.getenv("CODEX_HOME") or Path.home() / ".codex")

# La dirección de la suscripción. Ojo que **no** es api.openai.com: eso es la
# API que se paga por token. Esta es la que usa Codex con tu cuenta.
BASE = "https://chatgpt.com/backend-api/codex"

# El listado de modelos exige la versión del cliente y devuelve menos modelos
# si es vieja. Usamos la del Codex que tengas instalado; este número es solo
# el respaldo para cuando no la encontramos.
VERSION_CLIENTE = "0.146.0"

ESPERA_DE_RED = 20

# No mandamos un token que vence en el próximo minuto: entre que lo leemos y
# que el modelo termina de contestar pasa tiempo.
MARGEN_DE_VENCIMIENTO = 60

# El mismo mensaje para los dos lugares que lo necesitan (config.py cuando
# arma el agente, modelo_chatgpt.py cuando ya está andando). Que sea uno solo
# es lo que hace que la explicación no se desincronice.
AVISO_SIN_SESION = (
    "No encontré una sesión de ChatGPT en "
    f"{CARPETA_CODEX / 'auth.json'}. Abrí la app de ChatGPT (o corré "
    "'codex login') y entrá con tu cuenta; con eso ya podés usar "
    "PROVEEDOR=chatgpt."
)

AVISO_SESION_VENCIDA = (
    "La sesión de ChatGPT venció. Abrí la app de ChatGPT (o corré "
    "'codex login') para renovarla: Codex lo hace solo con usarlo."
)


class ErrorDeSesion(Exception):
    """No hay una sesión de ChatGPT usable."""


@dataclass
class Sesion:
    """Lo que hace falta para hablarle a la suscripción."""

    token: str
    cuenta: str
    # Cuándo vence el token, en segundos desde 1970. En 0 si no se pudo leer.
    vence: int = 0

    @property
    def vencida(self) -> bool:
        return bool(self.vence) and self.vence - MARGEN_DE_VENCIMIENTO <= time.time()


# ---------------------------------------------------------------------------
# Leer la sesión
# ---------------------------------------------------------------------------


def leer_sesion() -> Sesion | None:
    """La sesión que dejó Codex, o None si no hay archivo.

    Devuelve la sesión **aunque esté vencida**: quien la use decide qué
    decir, y "venció" y "nunca entraste" son dos problemas con dos
    soluciones distintas.
    """
    try:
        datos = json.loads(
            (CARPETA_CODEX / "auth.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None

    tokens = datos.get("tokens") or {}
    token = (tokens.get("access_token") or "").strip()
    if not token:
        return None

    return Sesion(
        token=token,
        cuenta=(tokens.get("account_id") or "").strip(),
        vence=_vencimiento(token),
    )


def credencial() -> str:
    """El token de acceso, o cadena vacía si no hay sesión o ya venció.

    Es lo que `config.py` usa como `api_key` del proveedor `chatgpt`, para
    que el resto del programa no tenga que saber de dónde salió.
    """
    sesion = leer_sesion()
    return sesion.token if sesion and not sesion.vencida else ""


def sesion_usable() -> Sesion:
    """La sesión, o una excepción con la explicación de qué le falta."""
    sesion = leer_sesion()
    if sesion is None:
        raise ErrorDeSesion(AVISO_SIN_SESION)
    if sesion.vencida:
        raise ErrorDeSesion(AVISO_SESION_VENCIDA)
    return sesion


def _vencimiento(token: str) -> int:
    """Cuándo vence el token, leído del propio token (es un JWT).

    Sirve para poder avisar con una frase clara en vez de dejar que el
    servidor conteste un 401 pelado. Si no se puede leer, devolvemos 0: se
    manda igual y que decida el servidor.
    """
    try:
        carga = token.split(".")[1]
        carga += "=" * (-len(carga) % 4)  # el JWT viene sin el relleno
        return int(json.loads(base64.urlsafe_b64decode(carga))["exp"])
    except (IndexError, KeyError, TypeError, ValueError, binascii.Error):
        return 0


# ---------------------------------------------------------------------------
# Preguntarle a la suscripción qué modelos tiene
# ---------------------------------------------------------------------------


def modelos_disponibles(sesion: Sesion) -> list[dict]:
    """Los modelos que la suscripción ofrece hoy, del recomendado para abajo.

    Devuelve `{"id", "nombre", "max_salida"}`, el mismo formato que los otros
    proveedores en `modelos.py`.

    `max_salida` va siempre en None, y no es un olvido: este endpoint no
    acepta que le pidas un tope de salida, así que no hay nada que ajustar
    (está explicado en `modelo_chatgpt.py`).
    """
    datos = _pedir(f"/models?client_version={_version_de_codex()}", sesion)

    # `visibility` es la respuesta del propio proveedor a "¿esto se le
    # muestra a una persona?": deja afuera los alias internos y los modelos
    # que usa Codex para tareas suyas.
    modelos = [
        m
        for m in datos.get("models") or []
        if m.get("slug")
        and m.get("visibility") == "list"
        and m.get("supported_in_api")
    ]

    # `priority` es el orden en que los ofrece Codex: 1 es el mejor de hoy.
    modelos.sort(key=lambda m: m.get("priority", 9999))

    return [
        {
            "id": m["slug"],
            "nombre": m.get("display_name") or m["slug"],
            "max_salida": None,
        }
        for m in modelos
    ]


def _version_de_codex() -> str:
    """La versión de Codex que tenés instalada.

    El endpoint de modelos la pide y la usa para decidir qué te muestra: con
    una versión vieja devuelve una lista corta. La leemos de lo que Codex ya
    dejó escrito para que esto no envejezca solo.
    """
    try:
        datos = json.loads(
            (CARPETA_CODEX / "models_cache.json").read_text(encoding="utf-8")
        )
        return str(datos["client_version"])
    except (OSError, ValueError, KeyError):
        return VERSION_CLIENTE


def _pedir(camino: str, sesion: Sesion) -> dict:
    """Un GET a la suscripción. Con urllib, para no sumar una dependencia."""
    pedido = urllib.request.Request(
        f"{BASE}{camino}",
        headers={
            "Authorization": f"Bearer {sesion.token}",
            # Hace falta cuando la cuenta tiene más de un espacio de trabajo:
            # sin esto, el servidor elige uno por su cuenta.
            "chatgpt-account-id": sesion.cuenta,
        },
    )

    with urllib.request.urlopen(pedido, timeout=ESPERA_DE_RED) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))
