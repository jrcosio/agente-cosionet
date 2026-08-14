"""Pasar una nota de voz a texto.

Lo usa el bot de Telegram cuando le mandas un audio en vez de escribir. Está
aparte por lo mismo que `imagenes.py`: es una cosa concreta y se lee de una vez.

**Transcribe en tu ordenador, sin clave y sin coste.** Y no es la primera
opción por gusto: la suscripción de ChatGPT **no puede** con el audio, y está
comprobado contra el endpoint —`input_audio` devuelve un 400 con
*"Audio input is not available."*, y las rutas de transcripción contestan 403—.
Así que para esto no valía el camino de las imágenes y hubo que elegir otro.

Usa **faster-whisper**, y es la única dependencia del proyecto que no se podía
evitar: nada de lo que ya estaba sabe convertir voz en texto. A cambio:

  · no pide ninguna credencial ni tarjeta;
  · funciona sin internet una vez descargado el modelo;
  · lee directamente el **OGG/Opus** que manda Telegram, sin ffmpeg ni ninguna
    otra cosa instalada aparte (esto es lo que más miedo daba y no es problema).

Dos cosas que conviene saber:

  · **El modelo se carga una sola vez** y se queda en memoria. Cargarlo tarda
    entre 6 y 9 segundos, y la primera vez además se descarga (unos 75 MB el
    `tiny`, 145 MB el `base`). Si se cargara en cada nota de voz, cada audio
    costaría diez segundos de más.
  · **Se guarda en `~/.cache/huggingface`**, fuera del repo. No hay nada que
    añadir al .gitignore.
"""

from __future__ import annotations

import io

# Los modelos, de menos a más: el que elijas sale de VOZ_MODELO en el .env.
#
#   tiny   ~75 MB   ya transcribe bien; se come alguna tilde y alguna coma
#   base  ~145 MB   el que viene puesto: la puntuación es visiblemente mejor
#   small ~480 MB   para audio con ruido o con acentos poco habituales
#   medium, large-v3   solo si te sobra disco y paciencia
MODELOS = ("tiny", "base", "small", "medium", "large-v3")

# Cargados, por nombre. No se recarga uno que ya esté en memoria.
_cargados: dict[str, object] = {}


class ErrorDeVoz(Exception):
    """No se pudo transcribir el audio."""


def transcribir(audio: bytes, modelo: str = "base", idioma: str | None = None) -> str:
    """El texto de una nota de voz.

    `idioma` en None deja que lo detecte solo, que es lo que quieres si a veces
    hablas en otro idioma. Poniéndolo (`"es"`) va algo más rápido y no se
    confunde con audios cortos, donde detectar el idioma es una lotería.

    Levanta `ErrorDeVoz` si no se puede. Quien la llama decide qué contar:
    en el bot, se le dice a la persona y la conversación sigue.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ErrorDeVoz(
            "Falta el paquete para transcribir: pip install faster-whisper "
            "(o uv sync, que ya lo trae)"
        ) from None

    if modelo not in _cargados:
        try:
            # int8 en la CPU: es lo que hace que una nota de voz se transcriba
            # en menos de un segundo en un portátil, sin tarjeta gráfica.
            _cargados[modelo] = WhisperModel(modelo, device="cpu", compute_type="int8")
        except Exception as e:
            raise ErrorDeVoz(
                f"No se pudo cargar el modelo de voz '{modelo}': {type(e).__name__}: {e}"
            ) from None

    try:
        # Se le pasa el audio en memoria, sin escribirlo en disco: una nota de
        # voz son unos kilobytes y no hace falta ensuciar nada.
        segmentos, _ = _cargados[modelo].transcribe(io.BytesIO(audio), language=idioma)
        return "".join(trozo.text for trozo in segmentos).strip()
    except Exception as e:
        raise ErrorDeVoz(f"No se pudo transcribir: {type(e).__name__}: {e}") from None
