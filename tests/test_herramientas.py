"""Pruebas de las herramientas. No salen a internet ni gastan tokens.

Open-Meteo se reemplaza por datos escritos a mano: lo que se prueba es lo
nuestro (cómo se arma el texto, qué pasa cuando algo falla), no que la API
de ellos funcione.

    pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente import herramientas, imagenes  # noqa: E402
from agente.herramientas import HERRAMIENTAS, clima  # noqa: E402

SEVILLA = {
    "nombre": "Sevilla",
    "provincia": "Andalucía",
    "pais": "España",
    "latitud": 37.38283,
    "longitud": -5.97317,
}

MEDICION = {
    "current": {
        "time": "2026-07-28T14:30",
        "temperature_2m": 19.1,
        "relative_humidity_2m": 83,
        "apparent_temperature": 18.4,
        "weather_code": 3,
        "wind_speed_10m": 13.8,
    }
}


def sin_internet(monkeypatch, lugar=SEVILLA, medicion=MEDICION) -> None:
    """Deja la herramienta en marcha con datos inventados, sin tocar la red."""
    monkeypatch.setattr(herramientas, "_buscar_lugar", lambda nombre: lugar)
    monkeypatch.setattr(
        herramientas, "_pedir_el_clima", lambda latitud, longitud: medicion
    )


def test_el_clima_sale_en_castellano_y_con_los_datos(monkeypatch):
    sin_internet(monkeypatch)

    texto = clima.invoke({"lugar": "Sevilla"})

    assert "Sevilla, Andalucía, España" in texto
    assert "19.1 °C" in texto
    assert "nublado" in texto, "el código 3 del WMO es cielo nublado"
    assert "83 %" in texto
    assert "13.8 km/h" in texto
    assert "14:30" in texto


def test_traduce_los_codigos_del_cielo():
    assert herramientas._describir_cielo(0) == "despejado"
    assert herramientas._describir_cielo(95) == "con tormenta"
    assert herramientas._describir_cielo(None) == "sin datos"
    # Un código que no está en la tabla no puede romper: se informa el número.
    assert "444" in herramientas._describir_cielo(444)


def test_si_falta_un_dato_no_se_rompe(monkeypatch):
    """Open-Meteo no siempre manda todo. Lo que falta se omite, no explota."""
    sin_internet(monkeypatch, medicion={"current": {"temperature_2m": 7.0}})

    texto = clima.invoke({"lugar": "Sevilla"})

    assert "7.0 °C" in texto
    assert "Humedad" not in texto, "lo que no vino no se inventa ni se muestra vacío"


def test_si_no_existe_la_ciudad_lo_dice(monkeypatch):
    monkeypatch.setattr(herramientas, "_buscar_lugar", lambda nombre: None)

    texto = clima.invoke({"lugar": "Ciudad Gótica"})

    assert "Ciudad Gótica" in texto
    assert "no encontré" in texto.lower()


def test_si_se_cae_la_api_la_charla_sigue(monkeypatch):
    """Una herramienta que levanta una excepción corta toda la respuesta.

    Devolviendo el problema como texto, el modelo lo lee y se lo explica a la
    persona en vez de que la conversación se caiga con un error crudo.
    """

    def explota(nombre):
        raise TimeoutError("tardó demasiado")

    monkeypatch.setattr(herramientas, "_buscar_lugar", explota)

    texto = clima.invoke({"lugar": "Sevilla"})

    assert "TimeoutError" in texto
    assert "tardó demasiado" in texto


def test_el_nombre_completo_no_deja_comas_sueltas():
    """Cuando no hay provincia, no puede quedar "Madrid, , España"."""
    solo = {"nombre": "Madrid", "provincia": "", "pais": "España"}

    assert herramientas._nombre_completo(solo) == "Madrid, España"


def test_la_herramienta_esta_en_la_lista_que_mira_el_grafo():
    """Si no está aquí, el modelo no se entera de que existe."""
    assert clima in HERRAMIENTAS


def test_el_modelo_recibe_una_descripcion_util():
    """El docstring no es decorativo: es lo único que el modelo lee para
    decidir si la herramienta le sirve."""
    assert clima.name == "clima"
    assert "clima" in clima.description.lower()
    assert "lugar" in clima.args


# -- Crear imágenes -----------------------------------------------------------
#
# Se parchea `imagenes.generar`, que es la que sale a la red, igual que arriba
# se parchean `_buscar_lugar` y `_pedir_el_clima`. Y `imagenes.CARPETA` se
# manda a una carpeta temporal para no ensuciar datos/imagenes.

PNG = (
    b"\x89PNG\r\n\x1a\n" + b"esto no es un PNG de verdad, pero da igual: "
    b"lo que se prueba es que los bytes llegan al disco tal cual"
)


@pytest.fixture
def sin_generador(monkeypatch, tmp_path):
    """La herramienta lista para usar, sin red y escribiendo en tmp_path."""
    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    monkeypatch.setattr(imagenes, "generar", lambda descripcion: PNG)
    return tmp_path


def test_la_imagen_se_guarda_y_devuelve_la_ruta(sin_generador):
    # Con un tool_call entero, invoke() devuelve el ToolMessage: es la única
    # forma de ver el artifact, que es donde viaja la imagen.
    mensaje = herramientas.crear_imagen.invoke(
        {"args": {"descripcion": "un faro"}, "id": "2", "name": "crear_imagen",
         "type": "tool_call"}
    )

    assert mensaje.artifact["tipo"] == "imagen"
    ruta = Path(mensaje.artifact["ruta"])
    assert ruta.is_file()
    assert ruta.read_bytes() == PNG
    assert ruta.parent == sin_generador


def test_el_contenido_que_ve_el_modelo_no_lleva_la_imagen(sin_generador):
    """**La regla que no se negocia.**

    Si el PNG viajara en el `content`, iría al estado del grafo: se guardaría
    en la memoria y se le reenviaría al modelo en cada mensaje siguiente. Un
    megabyte de imagen son ~1,4 MB de base64, del orden de 350.000 tokens por
    turno. Por eso va en el `artifact`, que el modelo no lee.
    """
    mensaje = herramientas.crear_imagen.invoke(
        {"args": {"descripcion": "un faro"}, "id": "3", "name": "crear_imagen",
         "type": "tool_call"}
    )

    assert len(mensaje.content) < 100, "el content es una frase, no una imagen"
    assert "PNG" not in mensaje.content
    assert "base64" not in mensaje.content


def test_si_no_se_puede_generar_lo_dice_como_texto(monkeypatch, tmp_path):
    """Una herramienta no levanta excepciones: devuelve el problema."""
    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)

    def explota(descripcion):
        raise RuntimeError("el generador dijo que no")

    monkeypatch.setattr(imagenes, "generar", explota)

    mensaje = herramientas.crear_imagen.invoke(
        {"args": {"descripcion": "algo"}, "id": "4", "name": "crear_imagen",
         "type": "tool_call"}
    )

    assert "No se pudo crear la imagen" in mensaje.content
    assert "el generador dijo que no" in mensaje.content
    assert mensaje.artifact == {}, "sin imagen no hay artefacto"


def test_solo_se_guardan_las_ultimas(monkeypatch, tmp_path):
    """El límite existe para que la carpeta no crezca sin fin."""
    monkeypatch.setattr(imagenes, "CARPETA", tmp_path)
    monkeypatch.setattr(imagenes, "MAXIMO", 3)

    guardadas = []
    for i in range(6):
        # El nombre lleva la fecha, y aquí se guardan seis en el mismo
        # segundo: los distingue el trozo al azar del final.
        guardadas.append(imagenes.guardar(PNG + bytes([i])))

    quedan = sorted(p.name for p in tmp_path.glob("*.png"))
    assert len(quedan) == 3
    # Las que quedan son las tres últimas, y ordenar por nombre es ordenar por
    # antigüedad porque el nombre empieza por la fecha.
    assert quedan == sorted(p.name for p in guardadas)[-3:]


def test_la_herramienta_esta_atada_y_se_explica_sola():
    nombres = [h.name for h in herramientas.HERRAMIENTAS]
    assert "crear_imagen" in nombres

    descripcion = herramientas.crear_imagen.description
    # Lo que el modelo tiene que entender: que la imagen se envía sola. Sin
    # esto se pone a describirla o a inventar un enlace.
    assert "envía" in descripcion
    assert "descripcion" in herramientas.crear_imagen.args
