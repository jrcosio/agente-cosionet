"""Que el pyproject.toml y los requirements*.txt digan lo mismo.

Hay dos formas de instalar este proyecto y las dos tienen que traer lo mismo:

    uv sync                          → lee pyproject.toml
    pip install -r requirements.txt  → lee requirements.txt

Tener la lista escrita en dos lados es una decisión, no un descuido: uv es el
camino recomendado, y los requirements*.txt quedan para quien no lo tenga (y
porque están comentados como material de lectura). Pero dos listas que hay que
mantener a mano se desincronizan siempre, y el día que pase, el que instaló
con pip va a tener un error que el otro no puede reproducir.

Este archivo es el que no lo deja pasar. Si agregás una dependencia en un
lado y te olvidás del otro, falla acá y no en la máquina de otra persona.

    pytest

Ojo: `tomllib` entró en Python 3.11. En 3.10 estos tests se saltean solos —
el proyecto sigue soportando 3.10, pero para leer un TOML sin sumar una
dependencia hace falta 3.11.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

tomllib = pytest.importorskip(
    "tomllib", reason="tomllib entró en Python 3.11; en 3.10 no hay con qué leer el TOML"
)

RAIZ = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(RAIZ / "src"))


def pyproject() -> dict:
    with open(RAIZ / "pyproject.toml", "rb") as archivo:
        return tomllib.load(archivo)


def requerimientos(nombre: str) -> set[str]:
    """Las dependencias de un requirements.txt, sin comentarios ni `-r`."""
    lineas = (RAIZ / nombre).read_text(encoding="utf-8").splitlines()

    pedidos = set()
    for linea in lineas:
        # El comentario puede estar al final de la línea, no solo al principio.
        limpia = linea.split("#", 1)[0].strip()
        # Las líneas `-r otro.txt` son inclusiones, no dependencias.
        if not limpia or limpia.startswith("-"):
            continue
        pedidos.add(limpia)

    return pedidos


# -- Las tres listas ----------------------------------------------------------


def test_las_dependencias_de_siempre_coinciden():
    assert set(pyproject()["project"]["dependencies"]) == requerimientos(
        "requirements.txt"
    )


def test_las_de_los_tests_coinciden():
    grupos = pyproject()["dependency-groups"]
    assert set(grupos["dev"]) == requerimientos("requirements-dev.txt")


def test_las_de_produccion_coinciden():
    grupos = pyproject()["dependency-groups"]
    assert set(grupos["produccion"]) == requerimientos("requirements-produccion.txt")


# -- Y que no se rompa lo que uv tiene que respetar ---------------------------


def test_el_paquete_no_se_instala():
    """`package = false` es lo que mantiene en pie el sys.path.insert("src").

    Si algún día alguien saca esta línea, uv va a empezar a instalar el
    proyecto como paquete en cada sync. Andaría igual, pero dejaría dos copias
    del código en juego —la instalada y la de src/— y basta con no hacer un
    sync para estar editando una y ejecutando la otra. Es de los errores más
    difíciles de ver.
    """
    assert pyproject()["tool"]["uv"]["package"] is False


def test_sigue_andando_en_310():
    """El README promete 3.10. Si eso cambia, que cambie a propósito."""
    assert pyproject()["project"]["requires-python"] == ">=3.10"


def test_tu_python_y_el_del_contenedor_son_el_mismo():
    """`.python-version` y el `FROM` del Dockerfile tienen que coincidir.

    Son dos archivos que dicen la misma cosa en dos lados: con qué Python
    corre esto. Si se separan, desarrollás en uno y desplegás en otro, y el
    día que aparezca una diferencia de versión nadie va a mirar acá.

    (El Dockerfile no copia el `.python-version` a propósito —adentro la fija
    la imagen base—, así que un desajuste no rompe el build: pasa callado. Por
    eso hace falta el test.)
    """
    version = (RAIZ / ".python-version").read_text(encoding="utf-8").strip()
    dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")

    assert f"FROM python:{version}-slim" in dockerfile


def test_hay_lock_y_es_del_pyproject():
    """El uv.lock se commitea: es lo que hace que todos instalen lo mismo.

    No lo parseamos entero (son medio megabyte), pero sí revisamos que estén
    los paquetes que pedimos a mano. Si el lock quedó viejo, `uv lock` lo
    arregla; en el Dockerfile se usa `--locked` justamente para que un lock
    desactualizado rompa el build en vez de desplegar en silencio la lista
    anterior.
    """
    lock = (RAIZ / "uv.lock").read_text(encoding="utf-8")

    directas = [
        *pyproject()["project"]["dependencies"],
        *pyproject()["dependency-groups"]["produccion"],
        *pyproject()["dependency-groups"]["dev"],
    ]

    for pedido in directas:
        # "psycopg[binary]>=3.2,<4" → "psycopg"
        nombre = pedido.split(">")[0].split("<")[0].split("[")[0].strip()
        assert f'name = "{nombre}"' in lock, f"{nombre} no está en el uv.lock"
