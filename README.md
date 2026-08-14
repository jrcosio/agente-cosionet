<div align="center">

<br>

# 🤖 CosioNET Agent

### Un agente de IA que corre **en tu ordenador**

**Sin servidor. Sin hosting. Sin pagar infraestructura.**<br>
Y si ya pagas ChatGPT, **sin clave de API y sin tarjeta.**

<br>

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-FF6F00?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white)
<br>
![Tests](https://img.shields.io/badge/tests-154%20passing-2EA043?style=for-the-badge)
![Licencia](https://img.shields.io/badge/licencia-MIT-A31F34?style=for-the-badge)
![Idioma](https://img.shields.io/badge/código%20en-español-FFB300?style=for-the-badge)

<br>

**[⚡ Arrancar](#arrancar)** &nbsp;·&nbsp;
**[🟢 Con tu ChatGPT](#chatgpt)** &nbsp;·&nbsp;
**[✈️ Telegram](#telegram)** &nbsp;·&nbsp;
**[🚢 Servidor](#servidor)** &nbsp;·&nbsp;
**[📋 Variables](#variables)** &nbsp;·&nbsp;
**[❓ Dudas](#dudas)**

<br>

</div>

> [!TIP]
> **¿Ya pagas ChatGPT?** Entonces no necesitas ninguna clave de API, ninguna
> tarjeta y no vas a pagar por token: el agente usa tu suscripción y eliges
> entre **Sol**, **Terra** y **Luna** desde la misma lista.
> Es una línea en el `.env` → **[cómo se hace](#chatgpt)**.

<details>
<summary><b>📑 Índice</b></summary>

<br>

| | | |
|---|---|---|
| [Qué es](#que-es) | [Cómo funciona](#como-funciona) | [⚡ Arrancar](#arrancar) |
| [🗂️ Qué hay adentro](#adentro) | [🎚️ Elegir el modelo](#modelo) | [🟢 **Con tu ChatGPT**](#chatgpt) |
| [🎛️ La barra de ajustes](#ajustes) | [💾 La memoria](#memoria) | [🗄️ Test y producción](#modos) |
| [⚡ El caché](#cache) | [🌦️ El clima](#clima) | [🎨 Las imágenes](#imagenes) |
| [🎤 Háblale](#voz) | [⏳ Te va contando](#avisos) | [✈️ Telegram](#telegram) |
| [🚢 En un servidor](#servidor) | [🎭 La personalidad](#personalidad) | [🧩 Desde tu código](#codigo) |
| [📋 Las variables](#variables) | [❓ Dudas](#dudas) | |

</details>

<br>

<a id="que-es"></a>

## Qué es

Un agente conversacional de verdad —con memoria, con personalidad editable y
con herramientas— que arranca en tu máquina con dos comandos. Viene con una
**plataforma de pruebas**: una web local donde le hablas, cambias de modelo en
caliente, editas quién es y ves cuántos tokens gastas en cada mensaje.

<table>
<tr>
<td width="33%" valign="top">

**🧠 Memoria de verdad**

Cada conversación tiene su hilo y su historia. Sobrevive al reinicio. Mil
personas a la vez sin mezclarse.

</td>
<td width="33%" valign="top">

**🔀 Cuatro proveedores**

Claude, OpenAI, Gemini **o tu suscripción de ChatGPT**. Se cambia con un
botón, sin reiniciar y sin perder la charla.

</td>
<td width="33%" valign="top">

**🎨 Crea imágenes**

Pídele una imagen y la genera con tu suscripción, sin pagar aparte. La ves en
el chat y en Telegram te llega como foto.

</td>
</tr>
<tr>
<td width="33%" valign="top">

**🎭 Personalidad en un `.md`**

Editas `prompts/sistema.md`, guardas, y el próximo mensaje ya sale distinto.
Sin reiniciar nada.

</td>
<td width="33%" valign="top">

**✈️ Funciona en Telegram**

En tu teléfono y sin pagar hosting. Le mandas fotos y notas de voz, y las
entiende.

</td>
<td width="33%" valign="top">

**🌦️ Y sabe el tiempo**

Pregúntale por cualquier ciudad y sale a buscarlo. Sin clave y sin registro:
es la otra herramienta que trae.

</td>
</tr>
<tr>
<td colspan="3" valign="top">

**📖 Escrito para leerse**

Código y comentarios **en español**, y 154 tests que no gastan un solo token.
Es material para aprender.

</td>
</tr>
</table>

<br>

<a id="como-funciona"></a>

## Cómo funciona

Un agente son tres cosas juntas, y el grafo que las pega son 12 líneas:

```mermaid
flowchart LR
    V(["Tú<br>escribes"]) --> M

    subgraph AG["El agente · agente.py"]
        S["<b>Prompt del sistema</b><br>prompts/sistema.md"] --> M{{"<b>El modelo</b><br>Claude · OpenAI · Gemini<br>o tu ChatGPT"}}
        MEM[("<b>Memoria</b><br>LangGraph · thread_id")] --> M
        M -.->|"¿necesita un dato?"| H["<b>Herramientas</b><br>el clima"]
        H -.->|"aquí tienes"| M
    end

    M --> R(["El agente<br>responde"])
```

Y **el agente no sabe quién lo llama.** Recibe texto y devuelve texto: esa
frontera es lo que permite enchufarle canales nuevos sin tocarlo por dentro.

```mermaid
flowchart LR
    T["🖥️ Terminal"] --> A
    W["🌐 Plataforma web"] --> A
    G["✈️ Telegram"] --> A
    A["<b>agente.responder</b><br>entra texto · sale texto"] --> P[("El modelo")]
```

<br>

---

<a id="arrancar"></a>

## ⚡ Arrancar

### 1 · Instalar

```bash
git clone https://github.com/jrcosio/agente-cosionet
cd agente-cosionet

uv sync
```

**Y ya está.** [uv](https://docs.astral.sh/uv/) arma el entorno en `.venv/`,
instala todo con las versiones exactas del `uv.lock` y —si no tienes el Python
que pide el proyecto— se lo baja solo. No hay que crear ni activar nada.

<details>
<summary><b>¿No tienes uv?</b> Se instala en una línea — o sigue con pip</summary>

<br>

**Instalar uv** (no necesita Python: es un binario):

| | |
|---|---|
| **Windows** | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| **Mac o Linux** | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

También está en Homebrew (`brew install uv`), en winget y en pip
(`pip install uv`). Más formas en
[docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/).

<br>

**O quédate con pip**, que sigue funcionando igual:

```bash
python -m venv .venv
```

| Activar el entorno | |
|---|---|
| **Windows** | `.venv\Scripts\activate` |
| **Mac o Linux** | `source .venv/bin/activate` |

```bash
pip install -r requirements.txt
```

Con pip, quítale el `uv run` a todos los comandos de aquí en adelante: con el
entorno activado, `python servidor.py` es lo mismo que `uv run python
servidor.py`.

</details>

### 2 · Elegir con qué modelo habla

```bash
copy .env.example .env      # Windows
cp .env.example .env        # Mac o Linux
```

Abre el `.env` y deja listo **uno solo** de estos cuatro:

| | Proveedor | Qué necesitas | Qué completas |
|:--:|---|---|---|
| 🟢 | **ChatGPT** | Tu suscripción. **Nada más.** | `PROVEEDOR=chatgpt` |
| 🟠 | **Claude** | Clave de [console.anthropic.com](https://console.anthropic.com/settings/keys) | `ANTHROPIC_API_KEY` |
| ⚫ | **OpenAI** | Clave de [platform.openai.com](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |
| 🔵 | **Gemini** | Clave de [aistudio.google.com](https://aistudio.google.com/apikey) | `GOOGLE_API_KEY` |

Con uno basta. Si dejas varios listos, los cambias desde la web con un botón.

> [!IMPORTANT]
> El `.env` está en `.gitignore`. **Nunca se sube a GitHub.**

### 3 · Probarlo

```bash
uv run python servidor.py
```

Abre **http://localhost:8000** &nbsp;·&nbsp; ¿prefieres la terminal?
`uv run python chat.py`

> [!TIP]
> `uv run` revisa el entorno antes de cada corrida: si alguien tocó las
> dependencias, las pone al día solo. Si prefieres no escribirlo cada vez,
> activa el entorno (`source .venv/bin/activate`) y quédate con
> `python servidor.py`.

<br>

---

<a id="adentro"></a>

## 🗂️ Qué hay adentro

```
agente-cosionet/
├── prompts/
│   └── sistema.md          ← la personalidad del agente (edítalo)
├── src/agente/
│   ├── agente.py           ← EL AGENTE. El grafo de LangGraph.
│   ├── herramientas.py     ← lo que sabe hacer además de hablar
│   ├── imagenes.py         ← genera imágenes y las guarda
│   ├── voz.py              ← pasa las notas de voz a texto
│   ├── modelos.py          ← Claude / OpenAI / Gemini / ChatGPT
│   ├── sesion_chatgpt.py   ← la suscripción de ChatGPT (sin clave de API)
│   ├── modelo_chatgpt.py   ← y las tres reglas raras de ese endpoint
│   ├── memoria.py          ← dónde se guardan las conversaciones
│   ├── prompts.py          ← lee el prompt del archivo
│   ├── respuesta.py        ← parte una respuesta larga en varios mensajes
│   ├── config.py           ← lee el .env
│   ├── canales/
│   │   ├── base.py         ← la forma de un canal
│   │   └── telegram.py     ← EL BOT DE TELEGRAM
│   └── web/
│       └── app.py          ← la plataforma de pruebas
├── tests/                  ← 154 tests que no gastan un solo token
├── chat.py                 ← hablarle desde la terminal
├── servidor.py             ← levantar la web
├── bot_telegram.py         ← levantar el bot de Telegram
├── pyproject.toml          ← las dependencias (las lee uv)
├── uv.lock                 ← las versiones exactas, iguales para todos
├── requirements.txt        ← lo mismo, para quien use pip
├── AGENTS.md               ← contexto para Codex, Claude Code, Cursor…
├── CLAUDE.md               ← apunta a AGENTS.md
└── .env                    ← tus claves (no se sube)
```

### Los comandos

| | |
|---|---|
| `uv run python servidor.py` | la plataforma de pruebas, en `localhost:8000` |
| `uv run python chat.py` | lo mismo, por la terminal |
| `uv run python bot_telegram.py` | el agente atendiendo Telegram |
| `uv run pytest` | los tests |
| `uv sync --group produccion` | agrega Postgres, para `MODO=produccion` |

Uno de los 154 se salta si no tienes el grupo `produccion`: es el que prueba
la conexión a Postgres. Con `uv sync --group produccion` corren los 154.

> [!NOTE]
> **Si vas a leer un solo archivo, lee `src/agente/agente.py`.** Ahí está todo
> el agente: el grafo son 12 líneas, el resto es explicación y ayudantes.

<br>

---

<a id="modelo"></a>

## 🎚️ Elegir el modelo

La plataforma **le pregunta a cada proveedor qué modelos tiene hoy** y te los
muestra en una lista, con el más nuevo arriba. No hay una lista escrita a mano
que envejezca: si mañana sale un modelo nuevo, aparece solo.

- El selector de arriba muestra los modelos disponibles.
- El botón **↻** vuelve a preguntar (por si acaba de salir uno).
- Cambiar de modelo **no borra la conversación**: puedes arrancar con uno,
  cambiar a otro y seguir la misma charla.
- **El máximo de respuesta se acomoda solo.** Cada modelo aguanta una cantidad
  distinta de tokens de respuesta; la plataforma le pregunta cuánto es y lo
  pone. No es algo que tengas que saber ni tocar.

¿No quieres tocar la web? Ponlo en el `.env` y listo:

```bash
PROVEEDOR=claude
MODELO_CLAUDE=claude-opus-5
```

Si el modelo del `.env` no existe o la lista no carga (sin internet, clave
vencida), la plataforma usa igual lo que diga el `.env`.

<br>

---

<a id="chatgpt"></a>

<div align="center">

## 🟢 Usarlo con tu suscripción de ChatGPT

![Sol](https://img.shields.io/badge/GPT--5.6-Sol-10A37F?style=for-the-badge&logo=openai&logoColor=white)
![Terra](https://img.shields.io/badge/GPT--5.6-Terra-1A7F64?style=for-the-badge&logo=openai&logoColor=white)
![Luna](https://img.shields.io/badge/GPT--5.6-Luna-2D6E8E?style=for-the-badge&logo=openai&logoColor=white)

**Sin clave de API · sin tarjeta · sin pagar por token**

</div>

Los otros tres proveedores se pagan por consumo: pides una clave, pones una
tarjeta y te cobran por lo que gastas. **Con ChatGPT no.** Si ya tienes la
suscripción (Plus, Pro o Business), el agente puede usar esa.

### Los tres pasos

**1.** Instala la app de **ChatGPT** en tu ordenador — o el CLI, desde
[chatgpt.com/codex](https://chatgpt.com/codex).

**2.** **Entra con tu cuenta.** Desde la terminal:

```bash
codex login
```

**3.** Una línea en el `.env`:

```bash
PROVEEDOR=chatgpt
```

Listo. `uv run python servidor.py` y el botón **ChatGPT** ya está encendido.

No hay ninguna clave que pegar porque la credencial ya está en tu máquina: al
entrar con tu cuenta se guarda en `~/.codex/auth.json`, y el agente la lee de
ahí. Vence cada diez días y se renueva sola con que uses ChatGPT; si se venció,
el agente te lo dice con esas palabras en vez de tirarte un error de HTTP.

### Los tres modelos

| | Modelo | En el `.env` | Cuándo usarlo |
|:--:|---|---|---|
| ☀️ | **Sol** | `gpt-5.6-sol` | El mejor de los tres. Tarda más y gasta más cuota. |
| 🌍 | **Terra** | `gpt-5.6-terra` | El equilibrado, para todos los días. |
| 🌙 | **Luna** | `gpt-5.6-luna` | El rápido. Para probar sin quemar la cuota. |

```bash
PROVEEDOR=chatgpt
MODELO_CHATGPT=gpt-5.6-sol
```

En la plataforma los eliges del mismo selector de siempre, y aparecen en ese
orden porque es el que recomienda el proveedor. También vas a ver modelos
anteriores (GPT-5.5, GPT-5.4): la lista sale de preguntarle a la suscripción,
no de una lista escrita aquí que envejezca.

### Las diferencias con la clave de API

Es el mismo modelo del otro lado, pero no es el mismo camino:

| | Con tu suscripción | Con clave de API |
|---|---|---|
| **Qué pagas** | Nada aparte: la cuota que ya tienes | Por token, con tarjeta |
| **Si se agota** | Se agotó también para ChatGPT y Codex | No hay cuota: hay factura |
| **`MAX_TOKENS`** | No se aplica: lo decide ChatGPT | Se respeta |
| **Dónde corre** | Tu ordenador | Tu ordenador **o un servidor** |

> [!WARNING]
> **Esto es para tu máquina, no para un servidor.** La sesión vive en tu
> `~/.codex`, que dentro de un contenedor no existe. Terminal, plataforma y el
> bot de Telegram funcionan perfectamente; para dejar el bot corriendo en un servidor
> va con clave de API.

> [!CAUTION]
> **Y una que es honesto decir:** este camino es el que usa Codex, no una API
> con contrato público. Funciona bien y no tiene truco, pero si OpenAI le cambia
> algo un martes, se puede romper sin que hayas tocado nada. Con
> `PROVEEDOR=openai` eso no pasa. Todo lo que hace falta para arreglarlo está
> comentado en [`src/agente/modelo_chatgpt.py`](src/agente/modelo_chatgpt.py).

<details>
<summary><b>Qué hay adentro, si te interesa el cómo</b></summary>

<br>

La suscripción atiende en el mismo dialecto que la API de OpenAI (la Responses
API), así que no hay un modelo nuevo escrito desde cero: es el mismo
`ChatOpenAI` mirando a otra dirección. Lo que sí hay son **tres reglas de ese
endpoint, y cada una es un 400 sin pista** si falta:

1. **El prompt del sistema no puede ir como mensaje.** Va en el campo
   `instructions` — un `SystemMessage` devuelve *"System messages are not
   allowed"*.
2. **`store` tiene que estar, y en `false`.** Si el campo no está, *"Store must
   be set to false"*.
3. **Solo contesta en streaming.** Un pedido normal es *"Stream must be set to
   true"*, así que `responder()` —que no usa streaming, y es el que usa el bot
   de Telegram— igual pide el stream y lo junta al final.

Dos archivos, y el agente no se tocó:

- **`src/agente/sesion_chatgpt.py`** — lee la sesión, se da cuenta de si venció
  (mirando el `exp` del propio token) y le pregunta a la suscripción qué
  modelos tiene. Solo biblioteca estándar.
- **`src/agente/modelo_chatgpt.py`** — el `ChatOpenAI` apuntado ahí, con esas
  tres reglas resueltas y con el token releído antes de cada pedido, porque
  Codex lo rota cada tanto y un bot que lleva días corriendo se quedaría con
  el viejo.

**Cero dependencias nuevas:** usa el `langchain-openai` que ya estaba.

</details>

<br>

---

<a id="ajustes"></a>

## 🎛️ La barra de ajustes

Debajo de los modelos hay una barra con el estado del agente:

```
modo test    memoria SQLite    caché activado    máx. respuesta 128.000 tokens    recuerda [20] mensajes
```

**Lo único editable ahí es "recuerda".** Escribes el número y listo: se guarda
en el `.env` y se aplica al instante, sin reiniciar el servidor.

El resto está fijo a propósito:

| | Por qué |
|---|---|
| **modo** | La plataforma es para probar en tu máquina: siempre `test`. Para pasar a producción se edita el `.env`. |
| **caché** | Siempre activado. No hay razón para apagarlo salvo que estés midiendo cuánto ahorra. |
| **máx. respuesta** | **Lo define el modelo, no tú.** Cada modelo aguanta un máximo distinto, así que la plataforma le pregunta cuánto es y lo pone. Cambias de modelo y se acomoda solo. (Con `PROVEEDOR=chatgpt` dice "lo decide ChatGPT": ese endpoint no acepta que se le pida un tope.) |

Todo lo demás se cambia editando el `.env`. Cuando la plataforma escribe ahí,
**respeta los comentarios y el orden** del archivo: solo reemplaza la línea de
esa variable. Y las claves de API nunca se editan desde el navegador.

<br>

---

<a id="memoria"></a>

## 💾 La memoria: cómo funciona

Esto es lo que más confunde y lo que casi nadie explica:

> [!IMPORTANT]
> **Las APIs de los modelos no recuerdan nada.**
> Cada llamada es independiente. Que el agente "se acuerde" de lo que hablaron
> es puro trabajo tuyo: le vuelves a mandar la conversación entera cada vez.

LangGraph resuelve eso con dos ideas:

- **`thread_id`** — el identificador de una conversación. Cada valor distinto
  es una charla separada, con su propia memoria.
- **checkpointer** — dónde se guardan esas conversaciones.

```python
agente.responder("Hola, me llamo Javi", conversacion="chat-1")
agente.responder("¿Cómo me llamo?",     conversacion="chat-1")  # → "Javi"
agente.responder("¿Cómo me llamo?",     conversacion="chat-2")  # → no sabe
```

Ese `thread_id` es exactamente lo que en Telegram es el chat de cada persona.
**Ahí está el truco de todo esto:**
el mismo agente atiende a mil personas sin mezclar las conversaciones.

### Cuánto recuerda

`MEMORIA_MENSAJES=20` en el `.env`, o el campo **recuerda** en la plataforma.
Son **mensajes**, no tokens (cuentan los tuyos y los del agente).

Ojo con la diferencia:

- **Se guardan todos.** El historial completo queda en la base.
- **Se le mandan al modelo solo los últimos N.** Eso es lo que controla este
  número.

Por eso es la palanca más directa sobre el costo: la conversación viaja entera
en cada mensaje, así que bajar de 20 a 10 es, más o menos, la mitad del gasto
en charlas largas. La contra es que el agente se olvida antes.

> [!TIP]
> Para verlo funcionar: ponlo en 4, dile tu nombre, mándale tres mensajes
> cualquiera y después pregúntale cómo te llamas. No se va a acordar.

<br>

---

<a id="modos"></a>

## 🗄️ Modo test y modo producción

Una sola variable decide dónde se guardan las conversaciones:

```bash
MODO=test        # SQLite: un archivo. No instalas nada.
MODO=produccion  # Postgres: para varios procesos atendiendo a la vez.
```

|  | `test` | `produccion` |
|---|---|---|
| Guarda en | Un archivo `.db` | Postgres |
| Sobrevive al reinicio | ✅ | ✅ |
| Varios procesos a la vez | ❌ | ✅ |
| Hay que instalar algo | No | Sí (ver abajo) |
| Para qué sirve | Desarrollar · un bot chico de Telegram | Un bot en un servidor, atendiendo de verdad |

### Pasar a producción

```bash
uv sync --group produccion
```

Con pip: `pip install -r requirements-produccion.txt`

Dos detalles que cuestan una tarde si no te los avisan:

- **La versión 3.x no es un capricho.** La 2.x se lleva por delante el
  `langgraph` que usa el resto del proyecto. `pip` te deja instalarla igual y
  lo avisa en un renglón perdido entre otros veinte. (uv no: no resuelve y te
  lo dice de frente. Es una de las razones para usarlo.)
- **`psycopg[binary]`, con los corchetes.** Sin eso, en Windows falla con
  *"no pq wrapper available"* aunque el paquete figure instalado. Ya viene así
  en el grupo `produccion`.

En el `.env`:

```bash
MODO=produccion
POSTGRES_DSN=postgresql://usuario:clave@servidor:5432/agente
```

Nada más. **Las tablas las crea solo** la primera vez que arranca. Y el agente
no se toca: es la misma clase, el mismo grafo, el mismo código.

<details>
<summary><b>¿No tienes Postgres? Con Docker, en una línea</b></summary>

<br>

```bash
docker run -d --name agente-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=clave -e POSTGRES_DB=agente postgres:17
```

Y el DSN queda: `postgresql://postgres:clave@localhost:5432/agente`

</details>

<details>
<summary><b>Y si quieres memoria que no guarde nada</b></summary>

<br>

Existe una tercera, para tests o para ver el agente en su forma más simple:

```python
from agente import Agente
from agente.memoria import ram

a = Agente(checkpointer=ram())   # se borra al cerrar el programa
```

</details>

<br>

---

<a id="cache"></a>

## ⚡ El caché: gastar menos

El prompt del sistema viaja **entero, en cada mensaje**. Si tu prompt tiene
2.000 tokens y mandas 100 mensajes, pagaste 200.000 tokens por el mismo texto.

El caché hace que el proveedor lo guarde de su lado y te cobre una fracción a
partir del segundo mensaje.

```bash
CACHE=true    # en el .env — viene activado, déjalo así
```

| Proveedor | Cómo funciona |
|---|---|
| **Claude** | Hay que marcarlo a mano — es lo que hace este repo por ti |
| **OpenAI** | Automático, no hay que hacer nada |
| **Gemini** | Automático, no hay que hacer nada |
| **ChatGPT** | Automático, no hay que hacer nada |

**Dos cosas para tener en cuenta:**

1. El caché **solo se activa cuando el prompt supera cierto tamaño**
   (alrededor de 1.000 tokens). Con un prompt corto no pasa nada malo:
   simplemente no se cachea. No es un error.
2. La plataforma te muestra el ahorro en cada mensaje: cuando el caché entra,
   aparece **⚡ N desde caché** debajo de la respuesta.

<br>

---

<a id="clima"></a>

## 🌦️ El clima: la primera herramienta

Hasta aquí el agente solo conversaba: contestaba con lo que sabía de antes. Una
**herramienta** es una función que puede usar cuando la necesita, y con eso
deja de adivinar y sale a buscar el dato.

Prueba:

```
¿qué tiempo hace en Sevilla?
¿me llevo chaqueta a Bilbao?
¿está lloviendo en Madrid?
```

Fíjate que **tú no le dices que use la herramienta**. El modelo lee la
pregunta, se da cuenta de que necesita el clima, la pide, recibe el resultado
y solo entonces te contesta. Si le preguntas cualquier otra cosa, ni la toca.

**No hay que pagar ni registrarse.** Usa [Open-Meteo](https://open-meteo.com):
gratis, sin clave de API y sin tarjeta para uso no comercial. Es a propósito —
arrancar este repo no tiene que depender de sacar una credencial más. Lo único
que sigues pagando es el modelo, como siempre.

**Lo que sí cuesta un poco más.** Una pregunta con herramienta son **dos
llamadas al modelo**, no una: la primera para que pida el clima, la segunda
para que te lo cuente. En la barra vas a ver los tokens de las dos sumados. Es
el precio de que el dato sea real.

**Si la ciudad no existe o se cae internet**, te lo dice y la charla sigue. La
herramienta nunca voltea la conversación: cuando algo falla, le devuelve el
problema al modelo y el modelo te lo explica.

<br>

---

<a id="imagenes"></a>

## 🎨 Crear imágenes

Pídesela y te la manda:

```
créame una imagen de un faro en un acantilado al atardecer
hazme un logo minimalista con una C azul
dibuja un gato naranja durmiendo en un teclado, estilo fotográfico
```

**No pagas nada aparte**: las genera tu suscripción de ChatGPT, la misma que ya
usa el agente para conversar. No hay ninguna clave nueva que sacar.

| Dónde | Cómo llega |
|---|---|
| **La web** | Dentro del chat. Clic para abrirla a tamaño completo. |
| **Telegram** | Dos mensajes: la foto para verla y el PNG sin comprimir para guardarlo. |

### Y también las mira

Mándale una foto **por Telegram** y la ve:

```
[foto de una planta]  ¿qué planta es esta?
[foto de un ticket]   ¿cuánto he gastado?
[foto sin más]        (te dice qué hay en ella)
```

Si la foto va con un pie, ese pie es la pregunta. Si va sola, te cuenta qué ve.

**Y se acuerda de ella**: puedes seguir preguntando sin reenviarla —"¿de qué
color es el cielo?"— porque la foto se queda en la memoria de la conversación.
Cuesta unos 1.500 tokens, no los cientos de miles que parecería por su tamaño:
una imagen se cuenta como imagen, no como el texto de su base64.

> [!NOTE]
> Lee **fotos**. Los audios, los documentos y los vídeos los deja pasar sin
> romperse, pero todavía no sabe abrirlos. Y ve la foto para hablar de ella: no
> la retoca.

Tres cosas que conviene saber:

- **Tarda entre 20 y 30 segundos.** Es lo que tarda, no es que se haya colgado.
  En Telegram verás "subiendo una foto" mientras trabaja.
- **La forma la decide la descripción, no un ajuste.** Si quieres un cartel
  vertical, dilo con palabras ("un cartel vertical"): una escena sale apaisada
  y un logo sale cuadrado. No hay parámetro de tamaño porque el generador lo
  ignora — probado.
- **Se guardan las últimas 50** en `datos/imagenes/`, y las más viejas se
  borran solas. Esa carpeta ya está en `.gitignore`: no se sube nunca.

> [!NOTE]
> Funciona **con cualquier modelo**, no solo con ChatGPT. Si estás conversando
> con Claude o con Gemini, ellos deciden llamar a la herramienta igual y la
> imagen la genera tu suscripción por detrás.
>
> Lo único que hace falta es **haber entrado con tu cuenta**, y eso tiene una
> consecuencia: como toda la funcionalidad va con la sesión de ChatGPT, que
> vive en tu `~/.codex`, **las imágenes son cosa de tu ordenador**. El bot
> desplegado en un servidor no puede generarlas — el mismo límite que
> [`PROVEEDOR=chatgpt`](#chatgpt).

<details>
<summary><b>Por qué la imagen no viaja dentro de la conversación</b></summary>

<br>

Es la decisión de diseño de toda la funcionalidad, y está medida.

Una herramienta le devuelve al modelo un texto que **entra en la memoria de la
conversación** y se le reenvía en cada mensaje siguiente. Si la imagen viajara
ahí, un PNG de 1 MB son ~1,4 MB en base64: del orden de **350.000 tokens por
turno**, más que la ventana de contexto de cualquier modelo. Y encima se
guardaría en la base de datos, reescrita entera en cada paso.

Así que el binario se queda en disco y por la conversación solo viaja la ruta.
El modelo recibe una frase de 37 caracteres —"Imagen creada y enviada a la
persona."— y cada canal se ocupa de hacerla llegar.

Se ve en los números: pedir una imagen gastó **698 tokens de entrada**. Si el
base64 hubiera entrado, serían cientos de miles.

</details>

<br>

---

<a id="voz"></a>

## 🎤 Háblale en vez de escribir

Mándale una **nota de voz por Telegram** y la entiende. La transcripción pasa a
ser tu mensaje, así que funciona con todo lo demás: puedes pedirle el tiempo
hablando, o pedirle una imagen hablando.

Probado con una nota de voz de verdad: *«dime qué tiempo hace en Bilbao»* →
transcrita en 0,8 s → llamó a la herramienta del clima → *«En Bilbao está
nublado, con 24,8 °C»*.

**Transcribe en tu ordenador: sin clave, sin coste y sin internet.** Y no es
por gusto — es que la suscripción de ChatGPT **no puede** con el audio: su
endpoint contesta *"Audio input is not available"*. Así que aquí no valía el
camino de las imágenes y se usa [Whisper](https://github.com/SYSTRAN/faster-whisper)
en local.

| | |
|---|---|
| **Primera nota de voz** | Descarga el modelo (145 MB) y tarda unos 10 s |
| **De ahí en adelante** | Medio segundo por nota |
| **Dónde se guarda** | `~/.cache/huggingface`, fuera del proyecto |

Puedes cambiar el modelo en el `.env` si quieres más precisión o menos disco:

```bash
VOZ_MODELO=base     # tiny (75 MB) · base (145 MB) · small (480 MB)
VOZ_IDIOMA=es       # vacío = que lo detecte solo
```

Mientras transcribe te enseña lo que ha entendido, así que si se equivoca lo
ves y no te quedas con la duda de por qué contestó algo raro.

> [!NOTE]
> Es la **única dependencia** que suma el proyecto, y se añadió porque nada de
> lo que ya había sabe pasar voz a texto. Te entiende hablando, pero contesta
> escribiendo: no manda notas de voz.

<br>

---

<a id="avisos"></a>

## ⏳ Te va contando lo que hace

Crear una imagen tarda medio minuto. Medio minuto sin decir nada es
indistinguible de un programa colgado, así que el agente avisa **mientras
trabaja**, no cuando ya acabó:

| Dónde | Qué ves |
|---|---|
| **La web** | Una línea en gris con un punto que late, dentro de la burbuja: *🎨 Creando la imagen…* Desaparece en cuanto empieza a escribir la respuesta. |
| **Telegram** | Un mensaje que se va editando y **se borra solo** al terminar, más el "subiendo una foto" de Telegram. El chat no se queda con el rastro. |
| **La terminal** | Una traza completa, con la hora en cada línea. |

Avisa de **todas** las herramientas, no solo de las lentas: también verás
*🌦️ Consultando el tiempo…*. Si añades una herramienta nueva, le pones su
aviso en una línea (`AVISOS`, en `herramientas.py`) y ya está.

### En el equipo se ve todo

El bot de Telegram deja una traza de cada mensaje, para que nunca tengas que
adivinar si está funcionando o colgado:

```
23:47:19 ┌ [12212910] 🎤 nota de voz: (sin texto)
23:47:20 │ audio bajado: 17 KB
23:47:20 │ 🎤 transcrito en 0.9s (whisper base): «Dime qué tiempo hace en Bilbao.»
23:47:20 │ al modelo (chatgpt · gpt-5.6-terra)
23:47:22 │ 🔧 clima
23:47:23 │ clima(lugar='Bilbao, España')
23:47:23 │ clima → Clima en Bilbao, País Vasco, España: - Temperatura: 24.2 °C…
23:47:25 │ ✉️ 1 mensaje(s): En Bilbao hace 24,2 °C, con cielo nublado…
23:47:25 └ listo en 6.0s · ↑630 ↓37 tokens
```

**La hora en cada línea es lo que hace útil la traza**: se ve de un golpe
*dónde* se está tardando — bajar el audio, transcribir, el modelo, o la
herramienta. Y los mensajes que **no** se contestan también salen, con el
motivo, en vez de desaparecer en silencio.

Al arrancar te dice qué sabe hacer **ese** proceso:

```
Bot escuchando - @tu_bot
   chatgpt - gpt-5.6-terra - memoria SQLite
   Sabe: texto, fotos que le mandes, notas de voz (whisper base), clima, crear_imagen
```

> [!TIP]
> Esa línea vale más de lo que parece. Si le mandas una nota de voz y ahí no
> pone "notas de voz", el proceso que está corriendo es viejo: reinícialo y
> deja de buscar el fallo en otro sitio.

<details>
<summary><b>Por qué esto era más difícil de lo que parece</b></summary>

<br>

El aviso tiene que llegar **mientras** la herramienta trabaja, y ahí está el
problema: quien está leyendo la respuesta —la web, el bot— se queda bloqueado
esperando el siguiente trozo de texto, y no vuelve a mirar nada hasta que
llegue. Un aviso por otra vía se emitiría a tiempo pero no podría entregarse
hasta 30 segundos después, que es justo cuando ya no sirve.

Así que el aviso viaja **por el mismo hilo que el texto**, mezclado con él. Es
un `Aviso`, que es una subclase de `str`: quien no lo distingue lo trata como
texto y no se entera de nada; quien quiere, pregunta `isinstance(pedazo, Aviso)`
y lo pinta a su manera. Y no entra en la respuesta final.

Medido contra un servidor de verdad: el aviso a los **3 s**, el texto a los
**31 s**.

</details>

<br>

---

<a id="telegram"></a>

## ✈️ Ponerlo en Telegram

Hasta aquí el agente vivía en tu navegador. Con esto lo tienes en el teléfono, y
**sin pagar hosting**: corre en tu ordenador igual que todo lo demás.

### Los tres pasos

**1.** Pídele un bot a Telegram. Abre [@BotFather](https://t.me/BotFather),
mándale `/newbot` y sigue la conversación. Al final te da un token, que es
una tira larga tipo `8983476848:AAG4j4...`.

**2.** Pégalo en el `.env`:

```bash
TELEGRAM_TOKEN=el-que-te-dio-BotFather
```

**3.** Arráncalo:

```bash
uv run python bot_telegram.py
```

Busca tu bot por nombre en Telegram, escríbele, y listo.

### Por qué no hace falta un servidor

Telegram se puede escuchar de dos formas. Este bot usa la primera:

|  | Cómo funciona | ¿Necesita URL pública? |
|---|---|---|
| **Polling** ← esta | Tu programa le pregunta a Telegram si hay algo nuevo | **No** |
| **Webhook** | Telegram le pega a una URL tuya | Sí, con HTTPS |

Por eso el bot arranca en tu ordenador sin más: un canal que obligara a
webhook necesitaría un servidor de verdad, con dominio y certificado.

**Mientras la ventana esté abierta, el bot contesta.** Si la cierras, deja de
contestar — y los mensajes que le lleguen mientras tanto los va a atender
cuando lo vuelvas a levantar (Telegram los guarda 24 horas).

¿Quieres que conteste siempre, sin tener el ordenador encendido? Está en
[Dejarlo corriendo en un servidor](#servidor).

### Cada persona, su propia conversación

Aquí está lo que hace que esto sirva de verdad: el `chat_id` de Telegram es el
`thread_id` de LangGraph.

```
tú          → chat_id 555  → tu conversación
tu hermana   → chat_id 888  → la de ella, aparte
```

**El mismo bot atiende a mil personas sin mezclar nada.** No hay que hacer
nada especial: es la misma línea de siempre, con el chat de cada uno como
`conversacion`.

Eso sí, si son muchos a la vez conviene `MODO=produccion` (Postgres): SQLite
es un archivo y no le gusta que varios procesos le escriban al mismo tiempo.

<details>
<summary><b>Cosas que ya están resueltas</b></summary>

<br>

- **Contesta en varios mensajitos**, no en un ladrillo (`partir_respuesta`).
- **No contesta dos veces lo mismo.** Telegram reenvía cuando duda.
- **Muestra "escribiendo…"** mientras el modelo piensa.
- **Las fotos y los audios los deja pasar** sin trabarse: el agente todavía no
  sabe leerlos.
- **Un error con una persona no voltea el bot** ni deja sin respuesta al resto.

</details>

<br>

---

<a id="servidor"></a>

## 🚢 Dejarlo corriendo en un servidor

Hasta aquí el bot vivía mientras tu ordenador estuviera encendido. Para que
conteste siempre —desde el gimnasio, de viaje, a las 3 de la mañana— tiene que
correr en un servidor.

El `Dockerfile` del repo hace exactamente eso: empaqueta `bot_telegram.py`.

```bash
docker build -t agente .
docker run -d --env-file .env --name agente agente
```

> [!IMPORTANT]
> **Esta imagen no expone ningún puerto, y eso confunde a casi cualquier
> PaaS.** El bot funciona por *polling*: sale él a buscar los mensajes, no entra
> nadie. Así que al desplegarlo el panel te va a asignar un dominio solo,
> después le va a pegar para ver si contesta, no va a contestar nadie, y lo va
> a marcar *unhealthy* aunque el bot esté atendiendo perfecto.
>
> **Bórrale el dominio y deja el health check apagado.** No está roto: es que
> con polling no hay a quién pegarle.

### Con Coolify (o cualquier PaaS que lea un Dockerfile)

1. Sube el código a un repositorio (privado está bien).
2. Crea una aplicación de tipo **Dockerfile** apuntando a ese repo.
3. **Quítale el dominio** si te asignó uno, y **apaga el health check**.
4. Carga las variables en el panel — **el `.env` no se sube al repo**.
   Aquí va con clave de API: `PROVEEDOR=chatgpt` no sirve en un servidor,
   porque la sesión vive en tu `~/.codex` y en el contenedor no existe.

   ```
   PROVEEDOR · OPENAI_API_KEY · MODELO_OPENAI
   MODO=produccion · POSTGRES_DSN
   TELEGRAM_TOKEN
   CACHE · MAX_TOKENS · MEMORIA_MENSAJES · PROMPT_SISTEMA
   ```

5. Despliega, y escríbele al bot desde tu teléfono para confirmar.

**Si la base de datos está en el mismo servidor**, usa el nombre interno del
contenedor en el `POSTGRES_DSN` en vez de la IP pública: es más rápido y no
sale a internet para volver a entrar.

### Dos cosas para no comerte

**`MODO=produccion`, o vas a perder las conversaciones.** En un contenedor,
SQLite vive en el disco del contenedor, y ese disco se borra en cada deploy.
Con Postgres la memoria sobrevive a los despliegues.

**Una sola instancia a la vez.** Si el bot queda corriendo en el servidor *y*
en tu ordenador, los dos le van a preguntar a Telegram por los mismos
mensajes y se los van a repartir al azar: la mitad de las respuestas van a
salir de una máquina y la otra mitad de la otra. Es la falla más confusa de
todas, porque *parece* que funciona a veces sí y a veces no. Apaga el local antes.

### Cómo actualizarlo después

```bash
git push
```

Y redespliegas desde el panel. El código nuevo entra en el próximo deploy; la
conversación de cada persona sigue intacta, porque vive en Postgres y no en
el contenedor.

<br>

---

<a id="personalidad"></a>

## 🎭 Cambiar la personalidad

Edita **`prompts/sistema.md`**, guarda, y el próximo mensaje ya sale distinto.
**No hay que reiniciar nada**: el archivo se lee en cada mensaje.

Desde la web lo tienes al costado, con un botón de guardar.

Es la forma más rápida de ver qué cambia: escribe algo, cambia el prompt,
vuelve a escribir lo mismo.

<br>

---

<a id="codigo"></a>

## 🧩 Usarlo desde tu código

El agente recibe texto y devuelve texto. Nada más. Eso es lo que después
permite enchufarlo a cualquier canal:

```python
import sys; sys.path.insert(0, "src")
from agente import Agente

a = Agente()

# Respuesta completa
respuesta = a.responder("Hola", conversacion="usuario-123")
print(respuesta.texto)
print(respuesta.tokens_entrada, respuesta.tokens_salida)
print(respuesta.tokens_cache_leidos)   # cuánto salió del caché

# Respuesta en vivo, mientras se escribe
transmision = a.responder_en_vivo("Cuéntame un chiste", conversacion="usuario-123")
for pedazo in transmision:
    print(pedazo, end="", flush=True)
print(transmision.resumen.tokens_salida)

# Ya partida en varios mensajes (para mensajería)
for mensaje in a.responder_partido("Explícame cómo funciona", conversacion="usuario-123"):
    print("─", mensaje)
```

Conectarlo a un canal nuevo es escribir el pegamento que traduce
"mensaje que llega" → `a.responder(texto, conversacion=<id del chat>)` →
"mensaje que sale". **El agente no cambia.**

Un detalle que importa cuando haya muchas conversaciones a la vez: el
resumen (tokens, modelo) vive en cada `Transmision`, **no** en el agente.
Si viviera en el agente, dos personas escribiendo al mismo tiempo se
pisarían los datos.

### Agregar herramientas

Las herramientas viven en **`src/agente/herramientas.py`**. Agregar una es
escribir una función y sumarla a la lista `HERRAMIENTAS`: el grafo ya está
armado para usarlas, así que no se toca nada más.

```python
@tool
def clima(lugar: str) -> str:
    """Dice el clima que hace ahora mismo en una ciudad."""
    ...

HERRAMIENTAS = [clima]
```

> [!IMPORTANT]
> **Ese docstring no es un comentario: es lo que lee el modelo** para decidir
> si la herramienta le sirve. Si está mal escrito, la herramienta no se usa
> nunca.

<br>

---

<a id="variables"></a>

## 📋 Todas las variables del `.env`

| Variable | Por defecto | Qué hace |
|---|---|---|
| `PROVEEDOR` | `chatgpt` | `chatgpt`, `claude`, `openai` o `gemini` |
| `ANTHROPIC_API_KEY` | — | Tu clave de Claude |
| `OPENAI_API_KEY` | — | Tu clave de OpenAI |
| `GOOGLE_API_KEY` | — | Tu clave de Gemini |
| — | — | **ChatGPT no lleva clave**: usa la sesión de tu cuenta |
| `MODELO_CHATGPT` | `gpt-5.6-sol` | Sol, Terra o Luna |
| `MODELO_CLAUDE` | `claude-opus-5` | Qué modelo de Claude usar |
| `MODELO_OPENAI` | `gpt-5` | Qué modelo de OpenAI usar |
| `MODELO_GEMINI` | `gemini-2.5-pro` | Qué modelo de Gemini usar |
| `MODO` | `test` | `test` (SQLite) o `produccion` (Postgres) |
| `SQLITE_RUTA` | `datos/conversaciones.db` | Dónde va el archivo, en modo test |
| `POSTGRES_DSN` | — | La conexión, en modo producción |
| `CACHE` | `true` | Cachear el prompt del sistema |
| `MAX_TOKENS` | `4096` | Cuánto puede escribir el agente por respuesta (no se usa con `chatgpt`) |
| `MEMORIA_MENSAJES` | `20` | Cuántos mensajes recuerda |
| `PROMPT_SISTEMA` | `prompts/sistema.md` | Qué archivo usar de personalidad |
| `TELEGRAM_TOKEN` | — | El token de @BotFather, para `bot_telegram.py` |
| `VOZ_MODELO` | `base` | Qué Whisper transcribe: `tiny`, `base`, `small`… |
| `VOZ_IDIOMA` | `es` | El idioma del audio; vacío para detectarlo solo |

<br>

---

<a id="dudas"></a>

## ❓ Preguntas que aparecen siempre

<details>
<summary><b>¿Necesito pagar un servidor?</b></summary>

<br>

No. Corre en tu ordenador. Lo único que pagas es el consumo del modelo — y
si usas tu suscripción de ChatGPT, ni eso (Gemini además tiene un plan gratis
para empezar).

</details>

<details>
<summary><b>¿Tengo que pagar tokens aparte si ya pago ChatGPT?</b></summary>

<br>

No: pon `PROVEEDOR=chatgpt` y usa tu suscripción, sin clave y sin tarjeta.
Se gasta de la misma cuota que ChatGPT y Codex.
Está todo en [Usarlo con tu suscripción de ChatGPT](#chatgpt).

</details>

<details>
<summary><b>¿Funciona sin internet?</b></summary>

<br>

Con estos proveedores no, porque el modelo corre en la nube de ellos.
Si quieres 100% local, hay que cambiar `modelos.py` para que apunte a Ollama.

</details>

<details>
<summary><b>¿Por qué se olvida de todo cuando cierro el programa?</b></summary>

<br>

No debería: en `MODO=test` guarda en un archivo y sobrevive al reinicio.
Si estás usando `ram()` a mano, eso sí se borra.

</details>

<details>
<summary><b>¿Cuánto sale?</b></summary>

<br>

Depende del modelo y de cuánto hables. La web te muestra los tokens de cada
mensaje. Cuatro formas de gastar menos, de mayor a menor impacto:

1. Usar tu suscripción de ChatGPT (`PROVEEDOR=chatgpt`): no se paga aparte
2. Usar un modelo más chico (los "mini" / "haiku" / Luna salen mucho menos)
3. Bajar `MEMORIA_MENSAJES`
4. Dejar `CACHE=true` (ya viene así)

</details>

<details>
<summary><b>Me da un error y no lo entiendo</b></summary>

<br>

La web muestra el error tal cual viene del proveedor, sin esconderlo. Los
motivos habituales:

- La clave está mal pegada (le sobra un espacio o le falta un pedazo)
- Con `PROVEEDOR=chatgpt`: no entraste con tu cuenta, o la sesión venció.
  Abre la app de ChatGPT (o corre `codex login`) y vuelve a probar.
- El nombre del modelo en el `.env` no existe → elígelo de la lista
- No tienes saldo en la cuenta del proveedor

</details>

<details>
<summary><b>¿Por qué uv y no pip?</b></summary>

<br>

Porque resuelve tres cosas que en este repo dolían:

- **Todos instalan lo mismo.** El `uv.lock` fija las versiones exactas de las
  79 dependencias que salen de las 10 que pedimos. Con `pip install` cada uno
  se lleva las de ese día.
- **Avisa en vez de dejarte el entorno roto.** El caso real de este repo es
  `langgraph-checkpoint-postgres` 2.x: pip te lo instalaba y avisaba en un
  renglón que nadie lee. uv no resuelve y te lo dice.
- **No hay que crear ni activar el entorno**, ni tener el Python correcto: si
  te falta, `uv sync` se lo baja.

Y es rápido de una forma que se nota: instalar todo de cero tarda segundos.

**pip sigue funcionando igual**, con los `requirements*.txt`. Hay un test
([`tests/test_dependencias.py`](tests/test_dependencias.py)) que compara las
dos listas para que no se desincronicen.

</details>

<details>
<summary><b>¿Puedo usarlo con Claude Code, Codex o Cursor?</b></summary>

<br>

Sí, y los tres se ponen al día solos. El archivo **[`AGENTS.md`](AGENTS.md)**
lo leen sin que se lo pidas: les explica la arquitectura, dónde tocar cada
cosa, las convenciones y las trampas del código. Abre el agente que uses en la
carpeta y pídele lo que quieras.

</details>

<br>

---

<a id="hecho"></a>

## 🛠️ Con qué está hecho

[LangChain](https://python.langchain.com) + [LangGraph](https://langchain-ai.github.io/langgraph/)
para el agente y la memoria · [FastAPI](https://fastapi.tiangolo.com) para la
plataforma de pruebas · [Open-Meteo](https://open-meteo.com) para el clima ·
[uv](https://docs.astral.sh/uv/) para las dependencias · Python 3.10 o más
nuevo.

<br>

---

<div align="center">

### 📄 Licencia y créditos

Publicado con licencia **[MIT](LICENSE)**.

**CosioNET Agent** es un fork de **[AgentKit](https://github.com/fcori47/basdonax-ai-agentkit)**,
de [Basdonax AI](https://basdonax.com).<br>
Los cambios de este fork —entre ellos el proveedor `chatgpt`— son de
**[J. Ramón Blanco](https://github.com/jrcosio)**.

Los dos copyright conviven en el [`LICENSE`](LICENSE), que es como se hace:
el aviso original viaja con el código.

<br>

<sub>⭐ Si te sirvió, déjale una estrella al repo — y también al original.</sub>

</div>
