"""El agente atendiendo en Telegram.

    uv run python bot_telegram.py

Corre en tu ordenador: no hace falta hosting, ni dominio, ni abrir puertos.
El programa le pregunta a Telegram si hay mensajes nuevos (polling), así que
mientras esta ventana esté abierta, el bot contesta.

Antes de arrancar, en el .env:

    TELEGRAM_TOKEN=  ← el que te da @BotFather

Para cortar: Ctrl+C.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from agente.consola import preparar  # noqa: E402

preparar()  # antes de imprimir nada, para que las tildes no rompan Windows

from agente import Agente, Aviso, Config, ErrorDeConfiguracion, partir_respuesta  # noqa: E402
from agente import voz  # noqa: E402
from agente.herramientas import HERRAMIENTAS  # noqa: E402
from agente.canales.telegram import Telegram  # noqa: E402

AMBAR = "\033[38;5;214m"
GRIS = "\033[90m"
ROJO = "\033[91m"
VERDE = "\033[92m"
FIN = "\033[0m"


def traza(texto: str, color: str = GRIS, marca: str = "│") -> None:
    """Una línea de la traza, con la hora delante.

    Todo lo que hace el bot sale por aquí, y no es decoración: un bot que tarda
    treinta segundos en contestar es indistinguible de un bot colgado si no
    cuenta nada. Con la hora en cada línea se ve enseguida **dónde** se está
    tardando: en bajar el audio, en transcribirlo, en el modelo o en la
    herramienta.

    `flush=True` porque si no, Python se guarda el texto en un buffer cuando la
    salida no es una terminal (un archivo, un contenedor) y no ves nada hasta
    que el proceso muere. Es la misma razón que en servidor.py.
    """
    print(f"{GRIS}{datetime.now():%H:%M:%S}{FIN} {color}{marca} {texto}{FIN}", flush=True)


def main() -> int:
    try:
        config = Config.desde_entorno()
        canal = Telegram(config.telegram_token)
    except (ErrorDeConfiguracion, ValueError) as e:
        print(f"{ROJO}{e}{FIN}")
        return 1

    agente = Agente(config)

    try:
        quien = canal.yo_soy()
    except Exception as e:
        print(f"{ROJO}No se pudo hablar con Telegram: {type(e).__name__}: {e}{FIN}")
        print(f"{GRIS}Revisa el TELEGRAM_TOKEN del .env.{FIN}")
        return 1

    memoria = "Postgres" if config.modo == "produccion" else "SQLite"

    print(f"\n{AMBAR}Bot escuchando{FIN} - @{quien.get('username', '?')}")
    print(f"{GRIS}   {config.proveedor} - {config.modelo} - memoria {memoria}{FIN}")

    # Qué sabe hacer **este** proceso, no lo que sabe hacer el repo. Es la línea
    # más útil del arranque: si le mandas una nota de voz y no ves "notas de
    # voz" aquí, el proceso es viejo y no hace falta buscar el fallo en otro
    # lado. Pasó de verdad, dos veces.
    print(f"{GRIS}   Sabe: {', '.join(_lo_que_sabe_hacer(config))}{FIN}")
    print(f"{GRIS}   Escríbele por Telegram. Para cortar: Ctrl+C.{FIN}\n")

    try:
        atender(agente, canal)
    except KeyboardInterrupt:
        print(f"\n{GRIS}Listo, cortamos.{FIN}")

    return 0


def _lo_que_sabe_hacer(config: Config) -> list[str]:
    """Las capacidades de este proceso, para el banner de arranque."""
    sabe = ["texto", "fotos que le mandes"]

    try:
        import faster_whisper  # noqa: F401

        sabe.append(f"notas de voz (whisper {config.voz_modelo})")
    except ImportError:
        sabe.append("SIN notas de voz: falta faster-whisper")

    sabe += [h.name for h in HERRAMIENTAS]
    return sabe


def atender(agente: Agente, canal: Telegram) -> None:
    """El bucle: llega un mensaje, contesta el agente, sale por el canal.

    Estas líneas son las mismas para cualquier canal. Lo único que cambia de
    un canal a otro es de dónde salen los mensajes y por dónde se mandan
    — el agente ni se entera.
    """
    for entrante in canal.escuchar():
        if not canal.deberia_responder(entrante):
            # Antes esto era un `continue` callado, y un mensaje que no se
            # contesta sin decir por qué es indistinguible de un bot roto.
            traza(f"[{entrante.conversacion}] ignorado (repetido o de un bot)", marca="·")
            continue

        arranque = time.monotonic()
        que_trae = "📷 foto" if entrante.adjuntos else ("🎤 nota de voz" if entrante.voz else "texto")
        traza(f"[{entrante.conversacion}] {que_trae}: {entrante.texto or '(sin texto)'}",
              AMBAR, "┌")

        # El "escribiendo..." mientras el modelo piensa.
        canal.escribiendo(entrante.conversacion)

        aviso = None

        # Si mandó una nota de voz, primero se pasa a texto: el modelo no oye.
        # La transcripción **es** el mensaje, así que en la memoria de la
        # conversación queda lo que dijo, no un audio.
        if entrante.voz:
            aviso = canal.avisar(entrante.conversacion, "🎤 Escuchando la nota de voz…", aviso)
            texto = escuchar(agente, canal, entrante)
            if texto is None:
                canal.quitar_aviso(entrante.conversacion, aviso)
                traza(f"sin respuesta ({time.monotonic() - arranque:.1f}s)", ROJO, "└")
                continue
            entrante.texto = texto
            # Que la vea: si transcribió mal, así se entiende la respuesta rara.
            aviso = canal.avisar(entrante.conversacion, f"🎤 «{texto}»", aviso)

        # Si mandó fotos, se bajan y van con el mensaje: el modelo las ve.
        fotos = []
        for identificador in entrante.adjuntos:
            reloj = time.monotonic()
            bajada = canal.descargar(identificador)
            if bajada:
                fotos.append(bajada)
                traza(f"foto bajada: {len(bajada) / 1024:.0f} KB "
                      f"en {time.monotonic() - reloj:.1f}s")
            else:
                traza("la foto no se pudo bajar; sigo con el texto", ROJO)

        traza(f"al modelo ({agente.config.proveedor} · {agente.config.modelo})")

        try:
            # LA línea. `conversacion` es el chat_id, y es lo que hace que
            # cada persona tenga su propia memoria sin mezclarse con la de al
            # lado. En la web era siempre "web" porque había un solo usuario.
            #
            # Se responde **en vivo** aunque en Telegram no se escriba de a
            # poco, y es por los avisos: los `Aviso` llegan por el mismo hilo
            # que el texto, así que mientras la herramienta trabaja se le puede
            # ir contando a la persona. Con `responder()` no habría forma de
            # enterarse hasta que todo hubiera terminado, que es justo cuando
            # ya no sirve avisar.
            transmision = agente.responder_en_vivo(
                entrante.texto, conversacion=entrante.conversacion, imagenes=fotos
            )

            for pedazo in transmision:
                if not isinstance(pedazo, Aviso):
                    continue

                # A la terminal va todo, con la letra pequeña incluida.
                traza(f"🔧 {pedazo.detalle or pedazo}" if pedazo.detalle else str(pedazo))

                # A la persona, solo los avisos pensados para ella: lo que
                # devuelve una herramienta en Telegram es ruido.
                if pedazo.visible:
                    # El mismo mensaje se va editando: uno solo, y al final se
                    # borra. Así el chat no queda con el rastro del andamiaje.
                    aviso = canal.avisar(entrante.conversacion, str(pedazo), aviso)
                    canal.escribiendo(
                        entrante.conversacion,
                        "upload_photo" if "imagen" in pedazo.lower() else "typing",
                    )

            respuesta = transmision.resumen
        except Exception as e:
            # El error del proveedor no se esconde: se lo decimos a la persona
            # y lo dejamos en la terminal. Pero no volteamos el bot, porque
            # atiende a varias personas y un error con una no puede dejar sin
            # respuesta a las demás.
            canal.quitar_aviso(entrante.conversacion, aviso)
            fallo = f"{type(e).__name__}: {e}"
            traza(fallo, ROJO)
            canal.enviar(entrante.conversacion, [f"Se me rompió algo: {fallo}"])
            traza(f"error ({time.monotonic() - arranque:.1f}s)", ROJO, "└")
            continue

        # Ya hay respuesta: el aviso cumplió y estorba.
        canal.quitar_aviso(entrante.conversacion, aviso)

        mensajes = partir_respuesta(respuesta.texto)
        canal.enviar(entrante.conversacion, mensajes)
        traza(f"✉️ {len(mensajes)} mensaje(s): {mensajes[0][:60] if mensajes else '(vacío)'}"
              f"{'…' if mensajes and len(mensajes[0]) > 60 else ''}")

        # Y si el turno dejó imágenes, van detrás del texto.
        for ruta in respuesta.imagenes:
            reloj = time.monotonic()
            canal.escribiendo(entrante.conversacion, "upload_photo")
            canal.enviar_imagen(entrante.conversacion, ruta)
            traza(f"🖼️ enviada {Path(ruta).name} en {time.monotonic() - reloj:.1f}s")

        traza(
            f"listo en {time.monotonic() - arranque:.1f}s · "
            f"↑{respuesta.tokens_entrada} ↓{respuesta.tokens_salida} tokens"
            + (f" · {len(respuesta.imagenes)} imagen(es)" if respuesta.imagenes else ""),
            VERDE,
            "└",
        )


def escuchar(agente: Agente, canal: Telegram, entrante) -> str | None:
    """La nota de voz, convertida en texto. None si no se pudo.

    Devuelve None en vez de levantar porque un audio que no se entiende no
    puede tirar el bot ni dejar a la persona sin respuesta: se le dice qué pasó
    y se sigue escuchando.

    Ojo con la primera vez: transcribir descarga el modelo (unos 145 MB con el
    `base` que viene puesto), así que la primera nota de voz tarda diez segundos
    más que las siguientes. De ahí el aviso antes de llamar aquí.
    """
    audio = canal.descargar(entrante.voz)
    if not audio:
        canal.enviar(
            entrante.conversacion, ["No pude descargar la nota de voz. ¿La reenvías?"]
        )
        return None

    traza(f"audio bajado: {len(audio) / 1024:.0f} KB")

    reloj = time.monotonic()
    try:
        texto = voz.transcribir(
            audio,
            modelo=agente.config.voz_modelo,
            idioma=agente.config.voz_idioma or None,
        )
    except voz.ErrorDeVoz as e:
        traza(str(e), ROJO)
        canal.enviar(entrante.conversacion, [f"No pude entender el audio: {e}"])
        return None

    if not texto:
        canal.enviar(
            entrante.conversacion,
            ["No he oído nada en esa nota de voz. ¿Lo intentas otra vez?"],
        )
        return None

    traza(f"🎤 transcrito en {time.monotonic() - reloj:.1f}s "
          f"(whisper {agente.config.voz_modelo}): «{texto}»")

    # Si además traía un pie escrito, va delante: son dos cosas que dijo.
    return f"{entrante.texto}\n\n{texto}" if entrante.texto else texto


if __name__ == "__main__":
    raise SystemExit(main())
