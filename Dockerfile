# El bot de Telegram, en un servidor.
#
# Corre `bot_telegram.py`, y eso decide todo lo demás: el bot anda por
# *polling* —le pregunta a Telegram si hay mensajes nuevos— así que **sale él,
# no entra nadie**. Por eso esta imagen:
#
#   · no expone ningún puerto
#   · no necesita dominio
#   · no necesita health check (y si el panel te lo prende solo, apagalo)
#
# Eso último confunde a casi cualquier PaaS: al desplegarlo te asigna un
# dominio por su cuenta, después le pega para ver si contesta, nadie contesta,
# y lo marca *unhealthy* aunque el bot esté atendiendo perfecto. No está roto:
# es que con polling no hay a quién pegarle. Borrale el dominio y dejá el
# health check apagado.
#
# Toda la configuración entra por variables de entorno. El .env no se copia
# acá adentro: en el servidor las variables las pone el panel.
#
# Ojo con dos cosas al desplegarlo:
#
#   · `MODO=produccion` (Postgres). En un contenedor, el SQLite de MODO=test
#     vive en el disco del contenedor y ese disco se borra en cada deploy.
#   · **Una sola instancia a la vez.** Si el bot queda corriendo acá y también
#     en tu computadora, los dos le piden a Telegram los mismos mensajes y se
#     los reparten al azar: la mitad de las respuestas sale de cada lado. Es
#     la falla más confusa de todas, porque parece que anda a veces sí y a
#     veces no.
#   · `PROVEEDOR=chatgpt` **no sirve acá.** La sesión de ChatGPT vive en tu
#     ~/.codex, que en el contenedor no existe. En un servidor va con clave de
#     API.
#
# Las dependencias las instala **uv**, con el uv.lock del repo: el servidor
# instala exactamente las mismas versiones que tenés en tu máquina.

FROM python:3.13-slim

# uv no se instala con pip: se copia el binario de su imagen oficial. Va con
# la versión clavada para que el build de hoy y el de dentro de seis meses
# hagan lo mismo.
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

# Sin esto, Python se guarda los logs en un buffer y en el panel del servidor
# no ves nada hasta que el proceso muere. Con un bot que corre para siempre,
# eso es no ver nunca nada.
ENV PYTHONUNBUFFERED=1

# Que las tildes no rompan cuando se imprime un mensaje.
ENV PYTHONIOENCODING=utf-8

# Tres cosas que le pedimos a uv acá adentro:
#
#   · compilar a bytecode al instalar, así el primer mensaje que atiende el
#     bot no paga la compilación (en tu máquina no importa; en un contenedor
#     que se recrea en cada deploy, sí).
#   · copiar en vez de enlazar: el caché de uv y el entorno pueden caer en
#     capas distintas de Docker, y ahí el hardlink no se puede hacer. Sin
#     esto avisa con un warning en cada build.
#   · no descargar ningún Python: el de esta imagen alcanza. Si algo no
#     cuadra, queremos que falle el build y no que se traiga otro por su
#     cuenta.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Las dependencias primero y el código después: así, mientras no toques el
# pyproject ni el lock, Docker reusa la capa ya instalada y el deploy tarda
# segundos en vez de minutos.
#
# Dos banderas que importan:
#
#   --locked  instala lo que dice el uv.lock y **rompe el build si el lock
#             quedó viejo** respecto del pyproject. Es lo que querés en un
#             servidor: que avise acá y no que resuelva versiones nuevas por
#             su cuenta, sin que nadie mire. (Ojo con `--frozen`, que se
#             parece pero no es lo mismo: ese instala del lock sin
#             comprobarlo, así que una dependencia que agregaste y no
#             lockeaste se despliega en silencio como si no existiera.)
#   --no-dev  pytest no tiene nada que hacer en producción.
#
# Y `--group produccion` es lo que suma Postgres, que es la memoria de verdad.
#
# No copiamos el `.python-version`: acá la versión de Python la fija la
# imagen base de arriba, no el archivo del repo.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --group produccion

# Que `python` sea el del entorno que armó uv, sin tener que activar nada ni
# escribir `uv run` en el CMD.
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/
COPY prompts/ ./prompts/
COPY bot_telegram.py ./

# Sin esto corre como root sin necesidad: el bot no escribe nada en disco
# (la memoria va a Postgres).
RUN useradd --create-home agente && chown -R agente:agente /app
USER agente

CMD ["python", "bot_telegram.py"]
