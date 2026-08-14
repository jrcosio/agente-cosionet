"""Hablar con el agente desde la terminal.

    uv run python chat.py

Para probar con otro proveedor sin tocar el .env:

    uv run python chat.py openai
    uv run python chat.py chatgpt   # tu suscripción, sin clave de API
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agente.consola import preparar  # noqa: E402

preparar()  # antes de imprimir nada, para que las tildes no rompan Windows

from agente import Agente, Aviso, Config, ErrorDeConfiguracion  # noqa: E402

AMBAR = "\033[38;5;214m"
GRIS = "\033[90m"
ROJO = "\033[91m"
FIN = "\033[0m"


def main() -> int:
    proveedor = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        config = Config.desde_entorno(proveedor)
    except ErrorDeConfiguracion as e:
        print(f"{ROJO}{e}{FIN}")
        return 1

    agente = Agente(config)

    print(f"\n{AMBAR}Agente listo{FIN} - {config.proveedor} - {config.modelo}")
    print(f"{GRIS}Escribe 'salir' para terminar.{FIN}\n")

    while True:
        try:
            texto = input(f"{GRIS}tú >{FIN} ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return 0

        if not texto:
            continue
        if texto.lower() in ("salir", "chau", "exit", "quit"):
            return 0

        print(f"\n{AMBAR}agente >{FIN} ", end="", flush=True)

        transmision = agente.responder_en_vivo(texto)

        try:
            for pedazo in transmision:
                # Un Aviso es un "estoy trabajando", no la respuesta: va en
                # gris y en su propio renglón. Como es un `str`, si no se
                # distinguiera saldría pegado al texto y parecería parte de él.
                if isinstance(pedazo, Aviso):
                    # Aquí sí sale todo, incluida la letra pequeña: estás
                    # delante del programa y es lo que quieres ver.
                    print(f"{GRIS}{pedazo.detalle or pedazo}{FIN}\n", flush=True)
                else:
                    print(pedazo, end="", flush=True)
        except Exception as e:
            print(f"{ROJO}{type(e).__name__}: {e}{FIN}")
            continue

        respuesta = transmision.resumen
        if respuesta:
            print(
                f"\n{GRIS}   entrada {respuesta.tokens_entrada} tokens"
                f" - salida {respuesta.tokens_salida} tokens{FIN}"
            )
        print()


if __name__ == "__main__":
    raise SystemExit(main())
