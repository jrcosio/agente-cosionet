# AGENTS.md — contexto para agentes de IA

Este archivo lo leen solos los agentes de programación cuando abren el
proyecto: **Codex, Claude Code, Cursor, Devin, Jules** y cualquier otro que
siga la convención `AGENTS.md`. Está para que entiendan el repo sin que se lo
tengas que explicar cada vez.

Si eres una persona: lee el `README.md`, es el que está escrito para ti.

---

## Qué es esto

**CosioNET Agent.** Un agente de IA conversacional que corre en la máquina
del usuario. Sin servidor, sin hosting. Funciona con **la suscripción de
ChatGPT** (sin clave de API, y es el proveedor por defecto), Claude, OpenAI o
Gemini, intercambiables desde el `.env`.

Construido sobre **LangChain + LangGraph**. La memoria son los *checkpointers*
de LangGraph, indexados por `thread_id`.

Atiende por tres lados: terminal, una plataforma web local y **Telegram**. El
diseño está pensado para que agregar un canal nuevo no obligue a reescribir el
agente.

**Idioma del código: español de España.** Nombres de funciones, variables,
comentarios, docstrings, mensajes de error y textos de la interfaz, todo en
castellano peninsular, **tuteando** (*tienes*, *puedes*, *guarda*, *edítalo*).
Excepciones: los identificadores que vienen de librerías (`messages`,
`thread_id`, `checkpointer`, `StateGraph`) y los nombres de los proveedores.

**Si escribes código nuevo aquí, sigue esa convención.** Y en concreto: nada
de voseo (*sos*, *tenés*, *podés*, *mirá*, *guardá*, *fíjate*) ni de léxico
rioplatense (*acá*, *computadora*, *plata*, *al toque*, *recién* con el
sentido de "solo entonces", *andar* por *funcionar*). El repo estuvo escrito
así hasta que se tradujo entero; si ves una de esas formas, es un resto que
quedó y se corrige.

---

## Estructura

El árbol de archivos está en el **[README](README.md#adentro)**.
Lo que importa aquí es qué hace cada uno:

| Archivo | Qué resuelve |
|---|---|
| `agente.py` | **El agente.** El grafo de LangGraph. Empieza por aquí. |
| `herramientas.py` | Lo que el agente puede hacer además de conversar. Hoy: el clima. |
| `modelos.py` | Crea el modelo y le pregunta al proveedor cuáles tiene |
| `sesion_chatgpt.py` | **La suscripción de ChatGPT**: la credencial sale de la sesión de Codex, no del `.env` |
| `modelo_chatgpt.py` | El `ChatOpenAI` apuntado a esa suscripción, con las tres reglas raras del endpoint |
| `memoria.py` | Los checkpointers: `ram` / `sqlite` / `postgres` |
| `prompts.py` | Lee y guarda `prompts/sistema.md` |
| `respuesta.py` | Parte una respuesta larga en varios mensajes |
| `consola.py` | Que la terminal de Windows no rompa con las tildes |
| `config.py` | Lee el `.env`. Única fuente de configuración. |
| `canales/base.py` | La forma de un canal |
| `canales/telegram.py` | **El bot de Telegram.** Polling, corre en tu máquina. |
| `../bot_telegram.py` | El punto de entrada del bot |
| `../Dockerfile` | Empaqueta el **bot de Telegram** (`bot_telegram.py`). Instala con `uv sync --locked`; no expone puertos |
| `../pyproject.toml` | Las dependencias, para uv. `package = false`: el paquete **no** se instala |
| `../uv.lock` | Las versiones exactas. Se commitea: es lo que hace que todos instalen lo mismo |
| `web/app.py` | La plataforma de pruebas (FastAPI + un solo HTML). Local, un solo usuario |

---

## Las cuatro decisiones de diseño

Entender esto evita romper cosas:

**1. El agente recibe texto y devuelve texto.**
No sabe si lo llaman desde la terminal, la web o Telegram. Esa frontera es
deliberada: es lo que permite agregar canales sin tocarlo.
`Agente.responder(texto, conversacion) -> Respuesta`.

**2. La memoria es un checkpointer intercambiable.**
`ram()` / `sqlite()` / `postgres()` en `memoria.py`. El `MODO` del `.env`
elige. Cambiar dónde se guardan las conversaciones no toca `agente.py`.

**3. El prompt del sistema vive en un archivo, no en el código.**
`prompts/sistema.md`, leído en **cada** mensaje (no una vez al arrancar).
Por eso se puede editar con el agente corriendo.

**4. Toda la configuración sale del `.env`, vía `config.py`.**
Ninguna credencial en el código, ni una. Las claves se leen únicamente en
`config.py`. La única credencial que no está en el `.env` es la de
`PROVEEDOR=chatgpt`, porque ahí no hay nada que pegar: la escribe Codex al
entrar con la cuenta. Se lee en `sesion_chatgpt.py` y entra al programa por
`config.py` igual que las otras, así que para `Agente` sigue siendo
`config.api_key` y nada más.

---

## Dónde tocar cada cosa

| Quieres… | Archivo | Cómo |
|---|---|---|
| Agregar un proveedor nuevo | `modelos.py` | Una rama en `crear_modelo()` + una en `listar_modelos()`, y sumarlo a `PROVEEDORES_VALIDOS` en `config.py` |
| Que la web muestre bien el proveedor nuevo | `web/static/index.html` | Un nombre en `NOMBRES` (y en `FALTA`, si lo que le falta no es una clave del `.env`) |
| Cambiar dónde se guardan las charlas | `.env` (`MODO`) | O una función nueva en `memoria.py` |
| Cambiar la personalidad | `prompts/sistema.md` | Es texto plano |
| **Agregar herramientas** | `herramientas.py` | Una función con `@tool` + sumarla a `HERRAMIENTAS`. El grafo ya está armado. |
| Agregar un canal | archivo nuevo en `canales/` | Traducir mensaje entrante → `agente.responder(texto, conversacion=<chat_id>)` |
| Nueva variable de configuración | `config.py` | Campo en `Config` + lectura en `desde_entorno()` + línea en `.env.example` |
| **Agregar una dependencia** | `pyproject.toml` | Y también en el `requirements*.txt` que corresponda, y después `uv lock`. Si te olvidas de alguno de los tres, falla `tests/test_dependencias.py` |
| Que se pueda editar desde la web | `config.py` | Agregarla a `AJUSTABLES` + campo en `AjustesEntrantes` (`web/app.py`) + control en la barra de estado |
| Tocar la interfaz | `web/static/index.html` | Un solo archivo, sin build ni npm |

---

## Reglas al escribir código aquí

- **Ninguna credencial en el código.** Todas viven en el `.env` y se leen en
  `config.py`. (Sí hay algún `os.getenv()` fuera de ahí, pero solo para rutas
  y nunca para una clave. La excepción de `sesion_chatgpt.py` está explicada
  en la decisión 4: tampoco está en el código, está en `~/.codex/auth.json`.)
- **Español**, según la convención de arriba.
- **Comentar el *por qué*, no el *qué*.** Este repo es material didáctico: si
  algo se hace de una forma no obvia, explica la razón.
- **El error del proveedor nunca se esconde.** Si Anthropic, OpenAI o Google
  devuelven un error, tiene que llegar tal cual a la pantalla del usuario.
  Sí se pueden tragar fallas que no son del modelo y no deben voltear la app,
  y hoy hay exactamente tres, todas a propósito y comentadas:
  `listar_modelos()` (sin lista, la app sigue), `consola.preparar()` (si la
  terminal no acepta UTF-8, se sigue igual) y `_mensajes_en_memoria()` (es un
  contador para la pantalla). **No agregues una cuarta sin dejar el motivo
  escrito al lado.**
- **Los tests no gastan tokens.** Usan `GenericFakeChatModel`. Si agregas una
  función que llama a un proveedor, el test va con modelo falso.
- **Sin dependencias nuevas** salvo que resuelvan algo que no se puede hacer
  con lo que ya está. Y si sumas una, va en los dos lados (`pyproject.toml` y
  el `requirements*.txt` que corresponda) más un `uv lock`: son tres pasos y
  el test los revisa.

---

## Cómo se corre

La instalación paso a paso está en el **[README](README.md#arrancar)** — no la
repito aquí para que no se desincronicen. Lo que hace falta saber:

**Las dependencias las maneja `uv`.** `uv sync` arma el entorno en `.venv/`
con las versiones del `uv.lock`, y `uv run` lo revisa antes de cada corrida.
No hay que activar nada:

```bash
uv run python servidor.py         # la plataforma de pruebas, en http://localhost:8000
uv run python chat.py             # lo mismo pero por terminal
uv run python bot_telegram.py     # el agente atendiendo en Telegram (polling, local)
```

Si el entorno está activado (`source .venv/bin/activate`), el `uv run` sobra.
Y con pip también sigue funcionando todo: los `requirements*.txt` están al día.

El bot se llama `bot_telegram.py` y no `telegram.py` a propósito: un módulo
llamado `telegram` en la raíz taparía la librería del mismo nombre si algún
día se instala.

Para `MODO=produccion` hacen falta dos paquetes más, que están en el grupo
`produccion` del `pyproject.toml` y no se instalan solos:

```bash
uv sync --group produccion
```

Los tests van con `uv run pytest`, sin instalar nada antes: `pytest` está en el
grupo `dev`, y ese grupo uv lo incluye por defecto.

`uv run pytest` da **96 pasados y 1 salteado**: el salteado es
`test_la_conexion_de_postgres_no_se_la_lleva_el_recolector`, que necesita el
grupo `produccion`. Con `uv sync --group produccion` pasan los 97. Si agregas
un test que dependa de una dependencia opcional, va con `importorskip` como
ese: la falta de un paquete que no se instala solo no es un test roto.

**Hay `pyproject.toml`, pero el paquete sigue sin instalarse.** Esa parte no
cambió con uv y no hay que cambiarla: `[tool.uv] package = false` es lo que se
lo impide. Cada punto de entrada y cada test hace `sys.path.insert(0, "src")`,
así que `pytest` se corre desde la raíz del repo y no desde otro lado. Si
alguien saca esa línea, uv empieza a instalar el proyecto en cada sync y
quedan dos copias del código en juego —la instalada y la de `src/`—; basta con
no hacer un sync para estar editando una y ejecutando la otra.
`tests/test_dependencias.py` lo cuida.

**La lista de dependencias está en dos lados a propósito:** `pyproject.toml`
(la que resuelve el `uv.lock`) y los `requirements*.txt` (para quien no tenga
uv, y porque están comentados como material de lectura). Si tocas una, toca la
otra — `tests/test_dependencias.py` falla si no lo haces.

---

## Detalles que ya mordieron

Cosas que parecen bugs y no lo son, o que cuestan de encontrar:

- **`stream_usage=True` en `ChatOpenAI`**: sin eso, OpenAI no informa tokens
  cuando la respuesta llega en streaming. Quedan en 0.
- **`use_responses_api=True` en `ChatOpenAI`, y no se puede sacar.** Por el
  endpoint viejo (`/v1/chat/completions`), pedirle herramientas a un modelo que
  razona —toda la familia gpt-5— devuelve un 400: *"Function tools with
  reasoning_effort are not supported... use /v1/responses"*. La otra salida que
  ofrece el propio error es apagarle el razonamiento al modelo, que es pagar
  por uno y usar otro. Con modelos viejos (gpt-4.1) el problema no aparece, así
  que si lo quitas no lo vas a ver hasta probar con un gpt-5.
- **La suscripción de ChatGPT y la API de OpenAI no son el mismo endpoint.**
  `PROVEEDOR=openai` va a `api.openai.com` con una clave y se paga por token.
  `PROVEEDOR=chatgpt` va a `chatgpt.com/backend-api/codex`, que es por donde
  entra Codex con tu cuenta. Es la Responses API, así que `ChatOpenAI` sirve
  igual, pero pide tres cosas distintas y **cada una es un 400 sin pista** si
  falta (todo esto está resuelto en `modelo_chatgpt.py`):
  · el prompt del sistema va en `instructions`, no como mensaje —
  *"System messages are not allowed"*;
  · `store` tiene que estar y estar en `false` — *"Store must be set to
  false"*;
  · solo contesta en streaming — *"Stream must be set to true"*, y por eso
  `responder()` (que no usa streaming) igual pide el stream y lo junta.
  Nada de esto está documentado en ningún lado: es un canal de un cliente
  propio, no una API con contrato. Si algún día se cae sin que nadie toque
  nada, empieza por ahí.
- **`MAX_TOKENS` no se aplica con `PROVEEDOR=chatgpt`.** Ese endpoint contesta
  *"Unsupported parameter: max_output_tokens"*, así que el tope de salida no se
  manda y lo decide él. Por eso la rama de `chatgpt` en `crear_modelo()` va
  **antes** de `limitar_max_tokens()`: no hay nada que ajustar y consultarlo
  sería una llamada en balde. En la barra de la plataforma ese chip dice
  "lo decide ChatGPT" en vez de un número que no haría nada.
- **El token de ChatGPT vence cada diez días y Codex lo rota solo.** Por eso
  `sesion_chatgpt.py` no cachea nada y `modelo_chatgpt._renovar_credencial()`
  lo relee antes de cada pedido: un bot de Telegram que arrancó antes de la
  rotación seguiría mandando el viejo y empezaría a comer 401 de la nada.
- **`PROVEEDOR=chatgpt` es para tu máquina, no para el contenedor.** La sesión
  vive en `~/.codex`, que en el contenedor no existe. Terminal, plataforma y
  Telegram sí; el bot desplegado en un servidor va con clave de API.
- **Los resultados de las herramientas también salen por el stream.**
  `responder_en_vivo()` filtra los `ToolMessage` a propósito: sin ese filtro, la
  persona ve el texto crudo de la consulta al clima en pantalla y después la
  respuesta de verdad.
- **Con herramientas el modelo habla dos veces**, así que la suma de chunks de
  `responder_en_vivo()` termina juntando el gasto de las dos llamadas. Es lo que
  quieres: es lo que costó la respuesta. Ojo que `responder()` (sin streaming)
  informa solo los tokens del último mensaje, porque mira `messages[-1]`.
- **`GenericFakeChatModel` no implementa `bind_tools()`** y el grafo lo llama al
  construirse. Por eso los tests usan `ModeloFalso`, que lo agrega. Si armas un
  modelo falso nuevo, acuérdate o no arranca ni un test.
- **Los chunks se suman** (`chunk_a + chunk_b`) en `responder_en_vivo()`. No es
  cosmético: varios proveedores mandan el conteo de tokens solo en el
  último chunk, y sumando es la única forma de tenerlo completo.
- **El caché de Claude es un bloque, no un string.** El `SystemMessage` pasa a
  ser `[{"type": "text", "text": ..., "cache_control": {...}}]`. Cualquier
  código que asuma que `content` es `str` se rompe. Ver `Agente._sistema()`.
- **El caché no se activa con prompts cortos** (~1.000 tokens mínimo). No es
  un bug: es cómo funciona. Con un prompt corto simplemente no cachea.
- **`check_same_thread=False`** en la conexión de SQLite: el servidor web
  atiende en varios hilos y sin eso rompe.
- **El pool de Postgres se deja abierto a propósito** en `memoria.postgres()`.
  Si se cierra el context manager, el checkpointer muere en el primer mensaje.
- **`--frozen` y `--locked` no son lo mismo, y la diferencia se paga en
  producción.** `uv sync --frozen` instala lo que dice el `uv.lock` **sin
  comprobarlo** contra el `pyproject.toml`: si alguien agregó una dependencia y
  no corrió `uv lock`, el deploy sale bien y sin esa dependencia. `--locked`
  compara y rompe el build. El Dockerfile usa `--locked` a propósito.
- **`langgraph-checkpoint-postgres` tiene que ser 3.x.** La 2.x arrastra un
  `langgraph-checkpoint` viejo (2.1) que se pelea con `langgraph` 1.2 y con el
  checkpointer de SQLite. `pip install` lo deja instalar igual y lo avisa como
  un warning que es fácil pasar por alto; el entorno queda roto.
- **`psycopg` va con `[binary]` en Windows.** Sin eso el import falla con
  *"no pq wrapper available"* porque no encuentra la libpq del sistema. El
  paquete está instalado y el error igual aparece.
- **El offset de Telegram se adelanta aunque el mensaje no sirva**
  (`Telegram.escuchar()`). Telegram reenvía todo lo que no le confirmaste, así
  que si alguien manda una foto y no avanzamos, esa foto vuelve para siempre y
  el bot se queda trabado ahí sin atender a nadie más.
- **El `chat_id` va como texto** al usarse de `thread_id`. Un `555` y un
  `"555"` son dos conversaciones distintas para LangGraph.
- **El bot de Telegram no expone puerto y eso confunde a los PaaS.** Al
  desplegarlo, el panel le asigna un dominio solo y después lo marca como
  *unhealthy* porque nadie contesta ahí. No está roto: con polling nadie
  entra al bot, sale él. Hay que borrarle el dominio y dejar el health check
  apagado. El Dockerfile ya está armado para eso: no expone ningún puerto.
- **Dos instancias del bot se roban los mensajes.** Telegram le entrega cada
  mensaje a quien lo pide primero, así que si corren el servidor y la máquina
  local a la vez, las respuestas salen la mitad de cada lado. Es la falla más
  confusa de todas, porque *parece* que funciona a veces sí y a veces no.
- **En un contenedor, `MODO=test` pierde las conversaciones en cada deploy**:
  el archivo de SQLite vive en el disco del contenedor y ese disco se
  descarta. En un servidor va Postgres.
- **`MEMORIA_MENSAJES=20` son 20 mensajes, no 20 tokens.** Aquí había un
  `trim_messages(token_counter=len)`; ahora es `_recortar()`, que corta por
  turnos completos (ver la sección de herramientas). La unidad no cambió: se
  siguen contando mensajes. Lo que cambió es que el corte cae siempre en el
  borde de un turno, así que el total puede quedar unos mensajes abajo del tope
  antes que partir una vuelta de herramienta al medio.
- **Sin `.env`, el proveedor es `chatgpt`.** Lo fija `PROVEEDOR_POR_DEFECTO` en
  `config.py`. Antes era `claude`, y en un clone recién bajado eso mostraba
  "Falta la clave de claude" en la plataforma aunque hubiera una sesión de
  ChatGPT lista y el botón encendido. `chatgpt` es el único que puede estar
  listo sin que nadie pegue una clave, así que es el que corresponde de
  arranque. El orden de `PROVEEDORES_VALIDOS` también cambió por eso: es el
  orden de los botones en la web.
- **La lista de modelos de OpenAI trae todo junto** (imágenes, audio,
  embeddings) y hay que filtrarla; la de Anthropic ya viene limpia y ordenada.
- **El listado de la suscripción pide la versión del cliente** y devuelve
  menos modelos si es vieja (con una 0.100 llegan tres; con la de hoy, seis).
  `_version_de_codex()` la saca de `~/.codex/models_cache.json`, que Codex
  mantiene al día, en vez de dejar un número escrito que envejece. De ahí
  salen los tres de hoy: **Sol** (`gpt-5.6-sol`), **Terra** (`gpt-5.6-terra`)
  y **Luna** (`gpt-5.6-luna`), en ese orden porque es el `priority` que manda
  el propio proveedor.
- **`max_salida` solo lo informan Anthropic y Google.** OpenAI no lo expone en
  su listado, así que queda en `None` y el tope no se ajusta para esos modelos.
  **Consecuencia real:** si vienes de un modelo de Claude con tope alto y pasas
  a OpenAI, el `MAX_TOKENS` guardado queda pegado del anterior. No rompe (OpenAI
  no valida el tope como Anthropic), pero el número que ves en la barra no es
  el de ese modelo.
- **`guardar_ajustes()` reescribe el `.env` línea por línea**, no lo regenera:
  los comentarios y el orden se conservan. También actualiza `os.environ` para
  que el proceso vivo vea los valores nuevos sin reiniciar.
- **`AJUSTABLES` es una lista corta a propósito.** Fuera quedan las claves de
  API (no se editan desde el navegador), `MODO` (la plataforma es para probar:
  siempre test) y `CACHE` (siempre activado). Lo que no está en esa lista se
  ignora aunque el navegador lo mande. **No agregues nada ahí sin que te lo
  pidan.**
- **`MAX_TOKENS` lo manda la plataforma, no el usuario.** Es el tope de salida
  del modelo elegido; se acomoda solo al cambiar de modelo. El único campo que
  toca una persona en la barra es `MEMORIA_MENSAJES`.

---

## Lo que NO tiene (todavía)

No lo agregues salvo que te lo pidan: son los próximos videos de la serie.

- Más herramientas (hay una sola: el clima)
- RAG / base de conocimiento
- Autenticación en la plataforma de pruebas (es local, un solo usuario)
- Varias conversaciones en paralelo en la web (usa un `thread_id` fijo)

---

## Cómo se agrega una herramienta

**El grafo ya es un ciclo** (modelo → herramientas → modelo, hasta que el
modelo deja de pedirlas), así que agregar una es una sola cosa: escribir la
función en `herramientas.py` y sumarla a `HERRAMIENTAS`. `agente.py` no se
toca.

```python
@tool
def clima(lugar: str) -> str:
    """Dice el clima que hace ahora mismo en una ciudad."""  # ← esto lee el modelo
    ...

HERRAMIENTAS = [clima]   # ← la única lista que mira el grafo
```

Tres cosas que importan:

- **El docstring es el prompt.** Es lo único que el modelo lee para decidir si
  la herramienta le sirve y qué mandarle. Escríbelo pensando en eso, no en un
  programador que lee el código.
- **Una herramienta no levanta excepciones: devuelve el problema como texto.**
  Si explota, LangGraph corta la respuesta entera y la persona ve un error
  crudo. Devolviéndolo, el modelo lo lee y lo explica. Está comentado en
  `clima()`.
- **Sin claves nuevas.** `clima` usa Open-Meteo justamente porque no pide
  registro ni tarjeta: arrancar el repo no tiene que depender de sacar una
  credencial más.

> ✅ **La trampa que estaba aquí ya está resuelta**, pero conviene entenderla
> antes de tocar `_armar_entrada()`. Una vuelta de herramienta son tres
> mensajes atados (el modelo la pide, la herramienta contesta, el modelo
> responde) y los proveedores los exigen juntos. El `trim_messages()` que
> había recortaba por mensaje suelto, así que tarde o temprano el corte caía
> en el medio y dejaba un `AIMessage` con `tool_calls` **sin** su
> `ToolMessage` → 400 del proveedor, sin explicación, y solo cuando la
> conversación se hacía larga. Ahora `_recortar()` corta por **turnos**
> completos y nunca los parte. `MEMORIA_MENSAJES` sigue contando mensajes.
> Los tests que lo cuidan son `test_el_recorte_no_parte_una_vuelta_de_herramienta`
> (probado con nueve topes distintos) y `test_el_turno_de_ahora_entra_entero_aunque_no_quepa`.

---

## Cómo se agrega un canal

`Canal` (en `canales/base.py`) define la **salida**: cómo le mandas mensajes a
una persona. La **entrada** la resuelve cada canal como le convenga, porque
cambia mucho entre uno y otro:

| | Cómo llegan los mensajes | Necesita URL pública |
|---|---|---|
| **Polling** (lo que usa Telegram) | Tu programa pregunta "¿hay mensajes?" cada tanto | No |
| **Webhook** | El canal le pega a una URL tuya | Sí, con HTTPS |

La forma es la misma en los dos casos:

```python
# 1. Llega algo del canal y lo traduces
entrante = MensajeEntrante(texto=..., conversacion=<id del chat>, identificador=<id del mensaje>)

# 2. Le preguntas al canal si hay que contestar
#    (persona atendiendo, bot apagado, mensaje repetido, mensaje propio)
if not canal.deberia_responder(entrante):
    return

# 3. El agente. Esta línea es la misma en todos los canales.
mensajes = agente.responder_partido(entrante.texto, conversacion=entrante.conversacion)

# 4. La respuesta sale por donde entró
canal.enviar(entrante.conversacion, mensajes)
```

**Un canal por webhook se monta en su propia app FastAPI**, no en la de la
plataforma de pruebas: son dos cosas distintas y la de pruebas no sale de
`localhost`.

**`conversacion` es el `thread_id` de LangGraph.** Es lo único que no se puede
equivocar: si dos personas comparten el mismo valor, comparten la conversación.

---

## Hacia dónde va (para no diseñar en contra)

**Los canales que hay hoy:** la terminal, la plataforma web local y Telegram.
`canales/telegram.py` implementa `Canal`, `conversacion` = el `chat_id`, y el
bucle que las pega está en `bot_telegram.py` (raíz). Funciona por *polling*, así
que corre en la máquina de uno sin dominio ni puertos abiertos. Sirve igual
con `MODO=test` (SQLite) que con `MODO=produccion` (Postgres): el agente no
cambia.

**Hubo un canal de WhatsApp (con Chatwoot en el medio) y se quitó**, a pedido.
Está en el historial de git si algún día hace falta volver a mirarlo:
`canales/chatwoot.py`, `canales/buffer.py`, `web/webhook.py` y
`webhook_chatwoot.py`, con sus tests en `tests/test_chatwoot.py`. **No lo
vuelvas a agregar sin que te lo pidan.**

**Decisiones que siguen en pie** (no volver a discutirlas):

- **Un solo repo.** Cada canal es un archivo nuevo; el núcleo no se toca.
  Se cumplió: `agente.py` no se tocó para agregar Telegram.
- **Cada canal es opcional.** El agente sigue funcionando por terminal y por la
  web sin ninguno configurado.
- **`MODO=test` responde y listo.** Postgres es para cuando hay varios
  procesos atendiendo.

**Ya preparado en el núcleo para que eso entre sin reescribir nada:**

- `canales/base.py` — la forma de un canal y el gancho `deberia_responder()`
- `respuesta.partir_respuesta()` — la respuesta en varios mensajes
- `Agente.responder_partido()` — lo mismo, listo para usar
- `Transmision` — el resumen vive en cada respuesta, **no** en el agente, así
  varias conversaciones a la vez no se pisan los datos
