"""El modelo de LangChain apuntado a la suscripción de ChatGPT.

La suscripción atiende en el mismo dialecto que la API de OpenAI —la
*Responses API*— así que no hace falta escribir un modelo desde cero:
basta con `ChatOpenAI` mirando a otra dirección. Streaming, herramientas,
conteo de tokens y caché siguen funcionando igual.

Lo que sí hace falta es acomodar tres cosas que ese endpoint pide distinto, y
eso es **todo** lo que hay en este archivo:

    1. El prompt del sistema no puede ir como mensaje. Un `SystemMessage`
       devuelve 400 ("System messages are not allowed"): el texto va en el
       campo `instructions` del pedido.
    2. `store` tiene que ir en `false`, y explícito. Si no está el campo,
       también es 400 ("Store must be set to false").
    3. Solo contesta en streaming. Un pedido normal es 400 ("Stream must be
       set to true"), así que `responder()` —que no usa streaming— se atiende
       igual con el stream y se junta al final.

Nada de esto está en la documentación de nadie: son las reglas del canal de
Codex, que es un cliente propio y no una API con contrato público. **Si algún
día la suscripción empieza a fallar sin que hayas tocado nada, es aquí donde
hay que mirar.** Con la clave de API (PROVEEDOR=openai) eso no pasa: es la
diferencia entre las dos formas de usar los modelos de OpenAI.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

from langchain_core.language_models.chat_models import (
    agenerate_from_stream,
    generate_from_stream,
)
from langchain_openai import ChatOpenAI

from .sesion_chatgpt import BASE, sesion_usable

# Los roles que este endpoint no acepta como mensaje y que hay que mover a
# `instructions`. LangChain manda "system"; los modelos que razonan usan
# "developer" para lo mismo.
ROLES_DE_SISTEMA = ("system", "developer")


class ModeloChatGPT(ChatOpenAI):
    """`ChatOpenAI` con las tres reglas de la suscripción ya puestas."""

    # -- Regla 1 y 2: cómo se arma el pedido ---------------------------------

    def _get_request_payload(
        self, input_: Any, *, stop: list[str] | None = None, **kwargs: Any
    ) -> dict:
        cuerpo = super()._get_request_payload(input_, stop=stop, **kwargs)

        entrada = cuerpo.get("input")
        if isinstance(entrada, list):
            sistema, resto = [], []
            for item in entrada:
                if isinstance(item, dict) and item.get("role") in ROLES_DE_SISTEMA:
                    sistema.append(_texto_de(item))
                else:
                    resto.append(item)

            if sistema:
                # `instructions` puede venir ya con algo si alguien lo pasó a
                # mano: lo respetamos y agregamos el prompt atrás.
                previas = cuerpo.get("instructions")
                cuerpo["instructions"] = "\n\n".join(
                    ([previas] if previas else []) + sistema
                )
                cuerpo["input"] = resto

        # Va aquí y no solo en el constructor porque es un requisito del
        # endpoint, no una preferencia nuestra: sin esto, 400.
        cuerpo["store"] = False

        return cuerpo

    # -- Regla 3: siempre streaming ------------------------------------------

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> Any:
        """Una respuesta completa, armada con los pedazos del stream.

        `Agente.responder()` (y con él el bot de Telegram) no usa streaming.
        Como el endpoint no sabe contestar de otra forma, pedimos el stream y
        lo juntamos: para quien llama, es una respuesta común.
        """
        return generate_from_stream(
            self._stream(messages, stop=stop, run_manager=run_manager, **kwargs)
        )

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> Any:
        """Lo mismo que `_generate()`, para el camino asincrónico.

        Hoy el repo no lo usa: todo lo que hay es sincrónico. Pero LangGraph
        ofrece las dos versiones, y quien tome la asincrónica se comería el 400
        sin entender por qué.
        """
        return await agenerate_from_stream(
            self._astream(messages, stop=stop, run_manager=run_manager, **kwargs)
        )

    # -- La credencial, siempre fresca ---------------------------------------

    def _stream(self, *args: Any, **kwargs: Any) -> Iterator:
        self._renovar_credencial()
        return super()._stream(*args, **kwargs)

    async def _astream(self, *args: Any, **kwargs: Any) -> AsyncIterator:
        self._renovar_credencial()
        async for pedazo in super()._astream(*args, **kwargs):
            yield pedazo

    def _renovar_credencial(self) -> None:
        """Relee la sesión antes de cada pedido y actualiza el token si cambió.

        Codex rota el token cada tanto y reescribe `~/.codex/auth.json`. Un
        proceso largo —el bot de Telegram, la plataforma abierta toda la
        tarde— arrancó antes de esa rotación: si se quedara con el token de
        cuando arrancó, en algún momento empieza a fallar todo con 401 y no
        hay forma de adivinar por qué.

        Si no hay sesión usable, la excepción explica qué hacer. Es mejor que
        el 401 pelado, y no esconde nada: sin sesión no hay respuesta posible.
        """
        token = sesion_usable().token

        for cliente in (self.root_client, self.root_async_client):
            # El cliente de OpenAI arma el header de autenticación en cada
            # pedido a partir de este atributo, así que basta con cambiarlo.
            if cliente is not None and cliente.api_key != token:
                cliente.api_key = token


def crear_modelo_chatgpt(modelo: str, token: str) -> ModeloChatGPT:
    """El modelo listo para usar, con la sesión de Codex adentro.

    `max_tokens` no está entre los argumentos y no es un olvido: la
    suscripción **no acepta** que le pidas un tope de salida ("Unsupported
    parameter: max_output_tokens"). Lo que diga `MAX_TOKENS` en el `.env` no
    se aplica con este proveedor.
    """
    sesion = sesion_usable()

    return ModeloChatGPT(
        model=modelo,
        api_key=token,
        base_url=BASE,
        # El endpoint es la Responses API. Además es lo que ya hace falta para
        # que un modelo que razona acepte herramientas (ver modelos.py).
        use_responses_api=True,
        store=False,
        # Sin esto no informa el consumo de tokens cuando la respuesta llega
        # en vivo, y como aquí todo llega en vivo, quedaría siempre en 0.
        stream_usage=True,
        timeout=120,
        default_headers={
            # Hace falta cuando la cuenta tiene más de un espacio de trabajo:
            # sin esto, el servidor elige uno por su cuenta.
            "chatgpt-account-id": sesion.cuenta,
        },
    )


def _texto_de(item: dict) -> str:
    """El texto de un mensaje del pedido, venga como string o como bloques."""
    contenido = item.get("content")

    if isinstance(contenido, str):
        return contenido

    if isinstance(contenido, list):
        return "".join(
            b.get("text", "")
            for b in contenido
            if isinstance(b, dict) and b.get("text")
        )

    return ""
