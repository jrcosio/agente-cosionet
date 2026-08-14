"""Generar imágenes y guardarlas en disco.

Lo usa la herramienta `crear_imagen` de `herramientas.py`. Está en su propio
archivo por lo mismo que `prompts.py` o `respuesta.py`: es una cosa concreta,
se lee de una vez, y `herramientas.py` se queda siendo lo que dice ser — la
lista de lo que el agente sabe hacer.

**Las imágenes las genera tu suscripción de ChatGPT**, no una clave de API. Es
el mismo endpoint que usa el proveedor `chatgpt` para conversar
(`/backend-api/codex/responses`), pidiéndole la herramienta integrada
`image_generation`. Por eso esta funcionalidad no suma ninguna credencial
nueva, que es la regla que `AGENTS.md` pone a las herramientas.

Dos cosas que se comprobaron contra el endpoint de verdad y que conviene saber
antes de tocar esto:

  · **El tamaño lo decide él, y no se puede forzar.** Se le pueden mandar
    `size` y `quality`: los acepta sin quejarse y los ignora. Probado con
    1024x1024, 1024x1536 y `quality: medium`, y las tres veces devolvió lo
    mismo que sin pedir nada. Lo que sí manda es la descripción: una escena
    ("un gato en un teclado") sale apaisada y un logo sale cuadrado. Así que
    la orientación se pide **con palabras**, dentro de la descripción, y no
    hay parámetro que mentir.
  · **Tarda entre 20 y 30 segundos.** De ahí la espera larga de abajo: con el
    timeout normal de 30 s no llega ninguna.

El binario **nunca** entra en la conversación. Se guarda en disco y lo que
viaja es la ruta. El porqué está en `herramientas.crear_imagen()`.
"""

from __future__ import annotations

import base64
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from secrets import token_hex

from .config import RAIZ
from .sesion_chatgpt import BASE, sesion_usable

# Donde quedan las imágenes. `datos/` ya está en .gitignore y en .dockerignore
# (es donde vive la base de conversaciones), así que no hay nada que añadir.
CARPETA = RAIZ / "datos" / "imagenes"

# Cuántas se conservan. Cada una pesa entre 0,7 y 2 MB, así que 50 son unos
# 50-100 MB en el peor caso. Al guardar una nueva se borran las más viejas.
MAXIMO = 50

# Generar una imagen tarda 20-30 segundos: con la espera de una petición
# normal no llegaría ninguna.
ESPERA_DE_RED = 180

# Con qué modelo se pide. Ojo: **no es el modelo que hace la imagen** —esa la
# hace el backend— sino el que recibe la orden y decide llamar a la
# herramienta. Ese trabajo es trivial, así que va con el más rápido y barato de
# la cuota, y da igual con qué modelo estés conversando.
MODELO = "gpt-5.6-luna"

# Lo que se le dice al modelo que conduce la generación. Corto y sin margen:
# no tiene que conversar, tiene que llamar a la herramienta.
ORDEN = (
    "Genera la imagen que te piden llamando a la herramienta de imagen. "
    "No preguntes nada, no describas la imagen, no contestes con texto."
)


class ErrorDeImagen(Exception):
    """No se pudo generar la imagen."""


def generar(descripcion: str) -> bytes:
    """Los bytes del PNG de una imagen creada a partir de la descripción.

    Levanta `ErrorDeImagen` si algo sale mal. Quien la llama
    (`herramientas.crear_imagen`) lo convierte en texto para el modelo: una
    herramienta no levanta excepciones hacia el grafo.
    """
    sesion = sesion_usable()

    cuerpo = {
        "model": MODELO,
        "instructions": ORDEN,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": descripcion}],
            }
        ],
        "tools": [{"type": "image_generation"}],
        "tool_choice": "auto",
        # Las tres reglas del endpoint, las mismas de modelo_chatgpt.py: sin
        # `store: false` y sin `stream: true` contesta 400.
        "store": False,
        "stream": True,
    }

    pedido = urllib.request.Request(
        f"{BASE}/responses",
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {sesion.token}",
            "chatgpt-account-id": sesion.cuenta,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )

    with urllib.request.urlopen(pedido, timeout=ESPERA_DE_RED) as respuesta:
        crudo = respuesta.read().decode("utf-8")

    imagen = _sacar_la_imagen(crudo)
    if imagen is None:
        raise ErrorDeImagen(
            "El modelo contestó pero no generó ninguna imagen. "
            "Puede que la descripción no sea aceptable para el generador."
        )

    return imagen


def guardar(imagen: bytes) -> Path:
    """Escribe la imagen en `datos/imagenes/` y devuelve su ruta.

    El nombre lleva la fecha delante para que ordenar por nombre sea ordenar
    por antigüedad — que es lo que usa `_tirar_las_viejas()` para saber cuál
    borrar. Y un trozo al azar detrás, porque dos imágenes del mismo segundo
    se pisarían.
    """
    CARPETA.mkdir(parents=True, exist_ok=True)

    ruta = CARPETA / f"{datetime.now():%Y%m%d-%H%M%S}-{token_hex(3)}.png"
    ruta.write_bytes(imagen)

    _tirar_las_viejas()
    return ruta


def _tirar_las_viejas() -> None:
    """Deja solo las últimas MAXIMO imágenes."""
    todas = sorted(CARPETA.glob("*.png"))

    for vieja in todas[:-MAXIMO] if len(todas) > MAXIMO else []:
        # Si otra cosa la borró primero, da igual: el objetivo es que no
        # sobren, y ya no sobra.
        vieja.unlink(missing_ok=True)


def _sacar_la_imagen(crudo: str) -> bytes | None:
    """Busca la imagen entre los eventos de la respuesta.

    La respuesta llega como Server-Sent Events y la imagen viene en un evento
    `response.output_item.done` cuyo item es de tipo `image_generation_call`,
    con el PNG en base64 en el campo `result`. Por el mismo stream pasan
    también vistas previas (`partial_image`) que no nos interesan: queremos la
    final.
    """
    for linea in crudo.splitlines():
        if not linea.startswith("data: "):
            continue

        try:
            evento = json.loads(linea[6:])
        except ValueError:
            continue

        if evento.get("type") != "response.output_item.done":
            continue

        item = evento.get("item") or {}
        if item.get("type") == "image_generation_call" and item.get("result"):
            return base64.b64decode(item["result"])

    return None
