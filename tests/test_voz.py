"""Pruebas de la transcripción. No descargan modelos ni tocan la red.

Whisper se reemplaza por uno de mentira que anota lo que se le pidió. Lo que se
prueba es lo nuestro: que el modelo se cargue una sola vez, que el idioma
llegue, y que un fallo salga como `ErrorDeVoz` y no como una excepción cruda de
la librería.

Lo que **no** se prueba aquí es que Whisper transcriba bien: eso es cosa de
ellos, y comprobarlo costaría descargar 145 MB en cada `pytest`. Se verificó a
mano con una nota de voz de verdad de Telegram (OGG/Opus, 17 KB): 0,8 segundos
y la frase completa con su puntuación.

    pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente import voz  # noqa: E402
from agente.voz import ErrorDeVoz, transcribir  # noqa: E402


class WhisperFalso:
    """El modelo de mentira. Anota cada transcripción que se le pide."""

    creados: list[dict] = []

    def __init__(self, nombre, device=None, compute_type=None):
        WhisperFalso.creados.append(
            {"nombre": nombre, "device": device, "compute_type": compute_type}
        )
        self.pedidos: list[dict] = []

    def transcribe(self, audio, language=None):
        self.pedidos.append({"audio": audio.read(), "language": language})
        # Whisper devuelve trozos con `.text`, y hay que juntarlos.
        return [Trozo(" Hola,"), Trozo(" esto es una prueba.")], None


class Trozo:
    def __init__(self, texto):
        self.text = texto


@pytest.fixture(autouse=True)
def sin_whisper(monkeypatch):
    """Whisper de mentira, y la memoria de modelos cargados en blanco."""
    WhisperFalso.creados = []
    monkeypatch.setattr(voz, "_cargados", {})

    modulo = type(sys)("faster_whisper")
    modulo.WhisperModel = WhisperFalso
    monkeypatch.setitem(sys.modules, "faster_whisper", modulo)


def test_transcribe_y_junta_los_trozos():
    assert transcribir(b"unos-bytes-de-audio") == "Hola, esto es una prueba."


def test_los_bytes_llegan_tal_cual():
    """Se le pasa el audio en memoria, sin escribirlo en disco."""
    transcribir(b"OggS-y-lo-que-venga")

    modelo = voz._cargados["base"]
    assert modelo.pedidos[0]["audio"] == b"OggS-y-lo-que-venga"


def test_el_modelo_se_carga_una_sola_vez():
    """Cargarlo tarda entre 6 y 9 segundos: hacerlo por audio sería absurdo."""
    transcribir(b"uno")
    transcribir(b"dos")
    transcribir(b"tres")

    assert len(WhisperFalso.creados) == 1
    assert len(voz._cargados["base"].pedidos) == 3


def test_dos_modelos_distintos_se_cargan_los_dos():
    transcribir(b"uno", modelo="tiny")
    transcribir(b"dos", modelo="base")

    assert sorted(c["nombre"] for c in WhisperFalso.creados) == ["base", "tiny"]


def test_se_carga_en_int8_en_la_cpu():
    """Es lo que hace que una nota de voz tarde menos de un segundo sin GPU."""
    transcribir(b"uno")

    assert WhisperFalso.creados[0]["device"] == "cpu"
    assert WhisperFalso.creados[0]["compute_type"] == "int8"


def test_el_idioma_llega_al_modelo():
    transcribir(b"uno", idioma="es")

    assert voz._cargados["base"].pedidos[0]["language"] == "es"


def test_sin_idioma_lo_detecta_solo():
    transcribir(b"uno")

    assert voz._cargados["base"].pedidos[0]["language"] is None


def test_si_no_carga_el_modelo_sale_un_ErrorDeVoz(monkeypatch):
    """Sin esto saltaría la excepción cruda de la librería, que no dice nada."""

    def explota(*a, **k):
        raise RuntimeError("no se pudo bajar el modelo")

    monkeypatch.setattr(sys.modules["faster_whisper"], "WhisperModel", explota)

    with pytest.raises(ErrorDeVoz) as fallo:
        transcribir(b"uno")

    assert "modelo de voz" in str(fallo.value)


def test_si_el_audio_es_basura_sale_un_ErrorDeVoz(monkeypatch):
    class Roto(WhisperFalso):
        def transcribe(self, audio, language=None):
            raise ValueError("Invalid data found")

    monkeypatch.setattr(sys.modules["faster_whisper"], "WhisperModel", Roto)

    with pytest.raises(ErrorDeVoz) as fallo:
        transcribir(b"esto no es audio")

    assert "No se pudo transcribir" in str(fallo.value)


def test_sin_el_paquete_instalado_lo_dice_claro(monkeypatch):
    """Es una dependencia nueva: si falta, el mensaje tiene que ser útil."""
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    with pytest.raises(ErrorDeVoz) as fallo:
        transcribir(b"uno")

    assert "faster-whisper" in str(fallo.value)
