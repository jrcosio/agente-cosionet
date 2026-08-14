"""Pruebas del proveedor `chatgpt`. No salen a internet ni gastan tokens.

La sesión de Codex se reemplaza por una carpeta de mentira con un token
inventado, y el listado de modelos por una respuesta escrita a mano. Lo que
se prueba es lo nuestro: leer la sesión, darse cuenta de que venció, ordenar
los modelos, y las tres reglas raras del endpoint (el prompt del sistema va
en `instructions`, `store` en false, y todo por streaming).

Los tres tests que más importan son:

  · `test_el_prompt_del_sistema_va_en_instructions`, porque un mensaje con
    role "system" es un 400 y sin él el agente pierde su personalidad.
  · `test_responder_sin_streaming_igual_usa_el_stream`, porque de eso depende
    el bot de Telegram: llama a responder(), que no usa streaming, y el
    endpoint no sabe contestar de otra forma.
  · `test_sin_sesion_el_pedido_no_sale`, porque un token vencido tiene que
    explicarse solo en vez de aparecer como un 401 pelado.

    pytest
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGenerationChunk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente import sesion_chatgpt  # noqa: E402
from agente.modelo_chatgpt import ModeloChatGPT  # noqa: E402
from agente.sesion_chatgpt import (  # noqa: E402
    ErrorDeSesion,
    Sesion,
    credencial,
    leer_sesion,
    modelos_disponibles,
    sesion_usable,
)


# -- Ayudantes ----------------------------------------------------------------


def token_falso(vence_en: int = 3600) -> str:
    """Un JWT de mentira: solo la parte del medio nos importa (el `exp`).

    No hace falta que la firma sirva. Nosotros no lo validamos: el `exp` es
    para poder avisar antes de que el servidor conteste un 401.
    """
    carga = base64.urlsafe_b64encode(
        json.dumps({"exp": int(time.time()) + vence_en}).encode()
    ).decode().rstrip("=")
    return f"cabecera.{carga}.firma"


@pytest.fixture
def codex(tmp_path, monkeypatch):
    """Una carpeta ~/.codex de mentira. Devuelve la función que la llena."""
    monkeypatch.setattr(sesion_chatgpt, "CARPETA_CODEX", tmp_path)

    def escribir(token: str | None = None, cuenta: str = "cuenta-1") -> None:
        (tmp_path / "auth.json").write_text(
            json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "tokens": {
                        "access_token": token if token is not None else token_falso(),
                        "account_id": cuenta,
                    },
                }
            ),
            encoding="utf-8",
        )

    return escribir


def modelo_de_prueba(clase=ModeloChatGPT, **extra) -> ModeloChatGPT:
    """El modelo, sin sesión de verdad: no hace ningún pedido."""
    return clase(
        model="gpt-5.6-terra",
        api_key="token-de-mentira",
        base_url=sesion_chatgpt.BASE,
        use_responses_api=True,
        **{"store": False, **extra},
    )


# -- Leer la sesión -----------------------------------------------------------


def test_sin_carpeta_de_codex_no_hay_sesion(codex):
    assert leer_sesion() is None
    assert credencial() == ""


def test_lee_el_token_y_la_cuenta(codex):
    codex(cuenta="abc-123")

    sesion = leer_sesion()
    assert sesion is not None
    assert sesion.cuenta == "abc-123"
    assert not sesion.vencida
    assert credencial() == sesion.token


def test_un_token_vencido_no_se_usa(codex):
    codex(token=token_falso(vence_en=-10))

    # Se lee igual: "venció" y "nunca entraste" son dos problemas distintos y
    # cada uno tiene su mensaje.
    sesion = leer_sesion()
    assert sesion is not None and sesion.vencida
    # Pero no se ofrece como credencial.
    assert credencial() == ""


def test_un_token_que_vence_ya_mismo_tampoco(codex):
    """El margen existe porque entre leerlo y contestar pasa tiempo."""
    codex(token=token_falso(vence_en=sesion_chatgpt.MARGEN_DE_VENCIMIENTO - 5))
    assert leer_sesion().vencida


def test_un_token_que_no_es_un_jwt_se_manda_igual(codex):
    """Si no se puede leer el vencimiento, decide el servidor, no nosotros."""
    codex(token="esto-no-es-un-jwt")

    sesion = leer_sesion()
    assert sesion.vence == 0
    assert not sesion.vencida
    assert credencial() == sesion.token


def test_el_archivo_roto_no_voltea_nada(codex, tmp_path):
    (tmp_path / "auth.json").write_text("{ esto no es json", encoding="utf-8")
    assert leer_sesion() is None


def test_cada_lectura_vuelve_al_disco(codex):
    """Codex rota el token: si lo cacheáramos, se empezaría a caer solo."""
    codex(token=token_falso())
    primero = credencial()

    codex(token=token_falso(vence_en=7200))
    assert credencial() != primero


def test_el_error_distingue_no_haber_entrado_de_haber_vencido(codex):
    with pytest.raises(ErrorDeSesion) as sin:
        sesion_usable()

    codex(token=token_falso(vence_en=-10))
    with pytest.raises(ErrorDeSesion) as vencida:
        sesion_usable()

    assert "codex login" in str(sin.value)
    assert "venció" in str(vencida.value)


# -- El listado de modelos ----------------------------------------------------


RESPUESTA_DE_MODELOS = {
    "models": [
        {"slug": "gpt-5.4", "display_name": "GPT-5.4",
         "visibility": "list", "supported_in_api": True, "priority": 16},
        {"slug": "gpt-5.6-luna", "display_name": "GPT-5.6-Luna",
         "visibility": "list", "supported_in_api": True, "priority": 3},
        {"slug": "gpt-5.6-sol", "display_name": "GPT-5.6-Sol",
         "visibility": "list", "supported_in_api": True, "priority": 1},
        {"slug": "gpt-5.6-terra", "display_name": "GPT-5.6-Terra",
         "visibility": "list", "supported_in_api": True, "priority": 2},
        # Un alias interno de Codex: no se le muestra a nadie.
        {"slug": "gpt-5.6-sol-wm", "display_name": "GPT-5.6-Sol-WM",
         "visibility": "hide", "supported_in_api": False, "priority": 1},
        # Uno visible que igual no se puede usar por API.
        {"slug": "un-modelo-raro", "display_name": "Raro",
         "visibility": "list", "supported_in_api": False, "priority": 4},
    ]
}


@pytest.fixture
def sin_red(monkeypatch):
    monkeypatch.setattr(
        sesion_chatgpt, "_pedir", lambda camino, sesion: RESPUESTA_DE_MODELOS
    )


def test_los_modelos_salen_ordenados_por_el_que_recomienda_codex(sin_red):
    modelos = modelos_disponibles(Sesion(token="x", cuenta="y"))

    assert [m["id"] for m in modelos] == [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.4",
    ]
    assert modelos[0]["nombre"] == "GPT-5.6-Sol"


def test_el_tope_de_salida_va_en_none(sin_red):
    """No es un olvido: este endpoint no acepta que le pidas un tope."""
    assert all(m["max_salida"] is None for m in modelos_disponibles(Sesion("x", "y")))


def test_la_version_del_cliente_sale_de_codex(codex, tmp_path):
    (tmp_path / "models_cache.json").write_text(
        json.dumps({"client_version": "9.9.9", "models": []}), encoding="utf-8"
    )
    assert sesion_chatgpt._version_de_codex() == "9.9.9"


def test_sin_cache_de_codex_hay_una_version_de_respaldo(codex):
    assert sesion_chatgpt._version_de_codex() == sesion_chatgpt.VERSION_CLIENTE


# -- Las tres reglas del endpoint ---------------------------------------------


def test_el_prompt_del_sistema_va_en_instructions():
    cuerpo = modelo_de_prueba()._get_request_payload(
        [SystemMessage("Eres Javi."), HumanMessage("hola")]
    )

    assert cuerpo["instructions"] == "Eres Javi."
    # Y no queda ningún mensaje de sistema en la entrada: eso es un 400.
    assert all(m.get("role") != "system" for m in cuerpo["input"])
    assert [m["role"] for m in cuerpo["input"]] == ["user"]


def test_el_prompt_en_bloques_tambien_se_mueve():
    """El caché de Claude convierte el prompt en bloques. Aquí igual entra."""
    cuerpo = modelo_de_prueba()._get_request_payload(
        [SystemMessage(content=[{"type": "text", "text": "Eres Javi."}])]
    )

    assert cuerpo["instructions"] == "Eres Javi."


def test_store_siempre_va_en_false():
    # Aunque alguien lo pida al revés: sin store=false el endpoint no contesta.
    cuerpo = modelo_de_prueba(store=True)._get_request_payload([HumanMessage("hola")])
    assert cuerpo["store"] is False


def test_no_se_pide_tope_de_salida():
    """El endpoint contesta "Unsupported parameter: max_output_tokens"."""
    cuerpo = modelo_de_prueba()._get_request_payload([HumanMessage("hola")])
    assert "max_output_tokens" not in cuerpo


def test_responder_sin_streaming_igual_usa_el_stream():
    """El endpoint solo contesta en streaming: responder() lo junta."""
    pedidos = []

    class ModeloQueAnota(ModeloChatGPT):
        def _stream(self, messages, stop=None, run_manager=None, **kwargs):
            pedidos.append(messages)
            yield ChatGenerationChunk(message=AIMessageChunk(content="ho"))
            yield ChatGenerationChunk(message=AIMessageChunk(content="la"))

    resultado = modelo_de_prueba(ModeloQueAnota)._generate([HumanMessage("hola")])

    assert len(pedidos) == 1
    assert resultado.generations[0].message.content == "hola"


def test_sin_sesion_el_pedido_no_sale(codex):
    """Mejor una frase que explique qué hacer que un 401 sin contexto."""
    with pytest.raises(ErrorDeSesion):
        # El stream es perezoso: hay que consumirlo para que salga el pedido.
        list(modelo_de_prueba()._stream([HumanMessage("hola")]))


def test_el_token_nuevo_reemplaza_al_viejo_sin_reiniciar(codex):
    """Codex rota el token mientras el bot sigue corriendo."""
    codex(token=token_falso())
    modelo = modelo_de_prueba()

    modelo._renovar_credencial()
    primero = modelo.root_client.api_key

    codex(token=token_falso(vence_en=7200))
    modelo._renovar_credencial()

    assert modelo.root_client.api_key != primero
    assert modelo.root_client.api_key == credencial()
