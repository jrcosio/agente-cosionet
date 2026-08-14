"""Configuración del agente.

Todo sale del archivo .env. Nada de credenciales escritas en el código.

Con una excepción, y es la del proveedor `chatgpt`: ese no usa una clave de
API sino tu suscripción de ChatGPT, y esa credencial no la pegas tú en
ningún lado — la escribe Codex cuando entras con tu cuenta. La leemos en
`sesion_chatgpt.py` y entra al resto del programa por aquí, igual que las
otras: para `Agente` sigue siendo `config.api_key` y nada más.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from . import sesion_chatgpt

# Raíz del proyecto (donde vive el .env)
RAIZ = Path(__file__).resolve().parents[2]

load_dotenv(RAIZ / ".env")


# El orden es el de los botones en la plataforma, y `chatgpt` va primero
# porque es el que no pide ninguna clave: si no dijiste nada en el .env, es el
# que se usa (ver PROVEEDOR_POR_DEFECTO más abajo).
PROVEEDORES_VALIDOS = ("chatgpt", "claude", "openai", "gemini")

# Con qué habla el agente si el .env no dice nada. Es ChatGPT porque es el
# único que puede estar listo sin que pegues una clave en ningún lado: si
# entraste con tu cuenta, ya está.
PROVEEDOR_POR_DEFECTO = "chatgpt"
MODOS_VALIDOS = ("test", "produccion")

# Qué variable de entorno lleva la clave de cada proveedor.
# `chatgpt` no está: no lleva clave, lleva sesión (ver sesion_chatgpt.py).
CLAVE_POR_PROVEEDOR = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}

MODELOS_POR_DEFECTO = {
    # Sol es el que Codex ofrece primero. Los otros dos son Terra (equilibrado)
    # y Luna (el rápido); en la plataforma los eliges de la lista.
    "chatgpt": "gpt-5.6-sol",
    "claude": "claude-opus-5",
    "openai": "gpt-5",
    "gemini": "gemini-2.5-pro",
}


class ErrorDeConfiguracion(Exception):
    """Falta algo en el .env o está mal puesto."""


@dataclass
class Config:
    proveedor: str
    modelo: str
    api_key: str
    max_tokens: int
    memoria_mensajes: int
    prompt_sistema: Path
    modo: str = "test"
    cache: bool = True
    sqlite_ruta: str = "datos/conversaciones.db"
    postgres_dsn: str = ""
    # Vacío mientras el agente corra solo en el ordenador. Lo usa el bot
    # de Telegram; el resto del proyecto ni lo mira.
    telegram_token: str = ""

    # -- Las notas de voz (solo las mira el bot de Telegram) -----------------
    # Qué modelo de Whisper transcribe. Cuanto más grande, mejor puntuación y
    # más disco: `tiny` 75 MB, `base` 145 MB, `small` 480 MB. Se descarga solo
    # la primera vez que le mandes un audio.
    voz_modelo: str = "base"
    # Vacío = que detecte el idioma solo. Poniendo "es" va algo más rápido y no
    # se equivoca con audios de dos segundos, donde adivinar es una lotería.
    voz_idioma: str = "es"

    @classmethod
    def desde_entorno(
        cls, proveedor: str | None = None, modelo: str | None = None
    ) -> "Config":
        """Arma la configuración leyendo el .env.

        Se le puede pasar un proveedor y un modelo a mano para pisar los del
        .env: así la plataforma de pruebas los cambia en caliente.
        """
        proveedor = (
            proveedor or os.getenv("PROVEEDOR", PROVEEDOR_POR_DEFECTO)
        ).strip().lower()

        if proveedor not in PROVEEDORES_VALIDOS:
            raise ErrorDeConfiguracion(
                f"El proveedor '{proveedor}' no existe. "
                f"Elige uno de: {', '.join(PROVEEDORES_VALIDOS)}."
            )

        if proveedor == "chatgpt":
            # Aquí no hay nada que completar en el .env: la credencial es la
            # sesión de Codex. Si no sirve, el error dice qué hacer.
            try:
                api_key = sesion_chatgpt.sesion_usable().token
            except sesion_chatgpt.ErrorDeSesion as e:
                raise ErrorDeConfiguracion(str(e)) from None
        else:
            nombre_clave = CLAVE_POR_PROVEEDOR[proveedor]
            api_key = (os.getenv(nombre_clave) or "").strip()

            if not api_key:
                raise ErrorDeConfiguracion(
                    f"Falta la clave de {proveedor}. "
                    f"Abre el archivo .env y completa {nombre_clave}."
                )

        modelo = (
            modelo
            or os.getenv(f"MODELO_{proveedor.upper()}")
            or MODELOS_POR_DEFECTO[proveedor]
        ).strip()

        modo = (os.getenv("MODO", "test") or "test").strip().lower()
        if modo not in MODOS_VALIDOS:
            raise ErrorDeConfiguracion(
                f"MODO tiene que ser 'test' o 'produccion', no '{modo}'."
            )

        return cls(
            proveedor=proveedor,
            modelo=modelo,
            api_key=api_key,
            max_tokens=_entero("MAX_TOKENS", 4096),
            memoria_mensajes=_entero("MEMORIA_MENSAJES", 20),
            prompt_sistema=RAIZ / os.getenv("PROMPT_SISTEMA", "prompts/sistema.md"),
            modo=modo,
            cache=_booleano("CACHE", True),
            sqlite_ruta=os.getenv("SQLITE_RUTA", "datos/conversaciones.db"),
            postgres_dsn=(os.getenv("POSTGRES_DSN") or "").strip(),
            telegram_token=(os.getenv("TELEGRAM_TOKEN") or "").strip(),
            voz_modelo=(os.getenv("VOZ_MODELO") or "base").strip(),
            voz_idioma=(os.getenv("VOZ_IDIOMA") or "es").strip(),
        )


def proveedores_disponibles() -> dict[str, bool]:
    """Qué proveedores están listos para usar. Lo usa la web para los botones.

    "Listo" es tener la clave en el .env, salvo para `chatgpt`, que es tener
    una sesión de ChatGPT abierta y sin vencer.
    """
    return {nombre: bool(clave_de(nombre)) for nombre in PROVEEDORES_VALIDOS}


# ---------------------------------------------------------------------------
# Guardar ajustes en el .env
# ---------------------------------------------------------------------------

# Solo estas variables se pueden tocar desde la plataforma de pruebas.
#
# NO están en la lista, a propósito:
#   · las claves de API  → no se editan desde el navegador
#   · MODO               → la plataforma es para probar: siempre test
#   · CACHE              → siempre activado; se apaga editando el .env a mano
AJUSTABLES = (
    "PROVEEDOR",
    "MODELO_CLAUDE",
    "MODELO_OPENAI",
    "MODELO_GEMINI",
    "MODELO_CHATGPT",
    "MAX_TOKENS",
    "MEMORIA_MENSAJES",
)


def guardar_ajustes(cambios: dict[str, str]) -> None:
    """Escribe los cambios en el .env y los aplica sin reiniciar.

    Reemplaza solo la línea de cada variable y deja el resto del archivo
    intacto: los comentarios y el orden se conservan. Si la variable no
    estaba, la agrega al final.
    """
    archivo = RAIZ / ".env"

    permitidos = {
        clave: str(valor) for clave, valor in cambios.items() if clave in AJUSTABLES
    }
    if not permitidos:
        return

    lineas = (
        archivo.read_text(encoding="utf-8").splitlines()
        if archivo.exists()
        else []
    )

    pendientes = dict(permitidos)

    for i, linea in enumerate(lineas):
        pelada = linea.strip()
        if not pelada or pelada.startswith("#") or "=" not in pelada:
            continue

        nombre = pelada.split("=", 1)[0].strip()
        if nombre in pendientes:
            lineas[i] = f"{nombre}={pendientes.pop(nombre)}"

    for nombre, valor in pendientes.items():
        lineas.append(f"{nombre}={valor}")

    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    # Que el proceso que está corriendo vea los valores nuevos ya mismo.
    for nombre, valor in permitidos.items():
        os.environ[nombre] = valor


def clave_de(proveedor: str) -> str:
    """La credencial de un proveedor, o cadena vacía si no está.

    Para tres es la clave del .env. Para `chatgpt` es el token de la sesión
    de Codex, que se lee del disco y puede estar vencido.
    """
    proveedor = proveedor.strip().lower()

    if proveedor == "chatgpt":
        return sesion_chatgpt.credencial()

    variable = CLAVE_POR_PROVEEDOR.get(proveedor, "")
    return (os.getenv(variable) or "").strip() if variable else ""


def _entero(nombre: str, por_defecto: int) -> int:
    valor = (os.getenv(nombre) or "").strip()
    if not valor:
        return por_defecto
    try:
        return int(valor)
    except ValueError:
        raise ErrorDeConfiguracion(
            f"{nombre} tiene que ser un número entero, no '{valor}'."
        ) from None


def _booleano(nombre: str, por_defecto: bool) -> bool:
    valor = (os.getenv(nombre) or "").strip().lower()
    if not valor:
        return por_defecto
    return valor in ("1", "true", "si", "sí", "on", "yes")
