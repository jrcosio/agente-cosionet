"""Las herramientas: lo que el agente puede hacer además de conversar.

Una herramienta es una función común de Python que el modelo puede decidir
llamar. El modelo no la ejecuta: dice "quiero llamar a clima con lugar=Sevilla"
y LangGraph la corre y le devuelve el resultado. Por eso el **docstring importa
tanto como el código**: es literalmente lo único que el modelo lee para decidir
si esta herramienta le sirve y qué mandarle.

Aquí hay dos: el clima y crear imágenes. La de imágenes es la primera que
devuelve algo que no es texto, y cómo lo hace está explicado en su propio
comentario: importa, porque marca el camino para el audio y lo que venga.

Ninguna de las dos pide una credencial nueva, que es la regla del proyecto: el
clima usa **Open-Meteo** (https://open-meteo.com), gratis y sin registro, y las
imágenes van con tu suscripción de ChatGPT, la misma que ya usa el agente para
conversar (ver `imagenes.py`).

El clima son dos consultas encadenadas, porque la API del tiempo habla en
coordenadas y las personas hablan en nombres de ciudades:

    1. Geocoding  → "Sevilla"       se convierte en  (37.39, -5.98)
    2. Pronóstico → (37.39, -5.98)  se convierte en  19 °C y nublado

Se usa `urllib`, de la biblioteca estándar, para no sumar una dependencia al
requirements.txt por dos pedidos HTTP.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from langchain_core.tools import tool

from . import imagenes

GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
PRONOSTICO = "https://api.open-meteo.com/v1/forecast"

# Si Open-Meteo no contesta en este tiempo, cortamos. Sin un tope, una consulta
# colgada deja al agente mudo en la mitad de la conversación.
ESPERA = 15

# Open-Meteo devuelve el estado del cielo como un número (el código WMO, un
# estándar meteorológico). Esta es la traducción a algo que una persona lea.
CIELO = {
    0: "despejado",
    1: "casi despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "con niebla",
    48: "con niebla que escarcha",
    51: "con llovizna suave",
    53: "con llovizna",
    55: "con llovizna fuerte",
    56: "con llovizna helada",
    57: "con llovizna helada fuerte",
    61: "con lluvia suave",
    63: "con lluvia",
    65: "con lluvia fuerte",
    66: "con lluvia helada",
    67: "con lluvia helada fuerte",
    71: "con nevada suave",
    73: "con nevada",
    75: "con nevada fuerte",
    77: "con granizo fino",
    80: "con chaparrones",
    81: "con chaparrones fuertes",
    82: "con chaparrones muy fuertes",
    85: "con chaparrones de nieve",
    86: "con chaparrones de nieve fuertes",
    95: "con tormenta",
    96: "con tormenta y algo de granizo",
    99: "con tormenta y granizo",
}


@tool
def clima(lugar: str) -> str:
    """Dice el clima que hace ahora mismo en una ciudad.

    Úsala cuando te pregunten por el clima, la temperatura, si llueve, si hace
    frío o calor, o si conviene salir con abrigo o paraguas.

    Args:
        lugar: La ciudad, en lo posible con el país. Por ejemplo "Sevilla",
            "Buenos Aires, Argentina" o "Madrid". Si hay varias ciudades con
            el mismo nombre, se toma la más conocida.
    """
    # Por qué la herramienta devuelve el error en vez de levantarlo (esta es la
    # cuarta falla que se traga el proyecto, y va con el motivo escrito al lado,
    # como pide AGENTS.md): si una herramienta explota, LangGraph corta toda la
    # respuesta y la persona ve un error crudo. Devolviéndolo como texto, el
    # resultado le llega al modelo, que lo cuenta con sus palabras y la
    # conversación sigue. Ojo con la diferencia: aquí no se esconde nada, el
    # problema igual termina en la pantalla — pero explicado y sin voltear la
    # charla. Los errores del *proveedor* siguen saliendo tal cual: esto es
    # una consulta a Open-Meteo, no al modelo.
    try:
        encontrado = _buscar_lugar(lugar)
    except Exception as e:
        return f"No se pudo consultar el clima de '{lugar}': {type(e).__name__}: {e}"

    if encontrado is None:
        return (
            f"No encontré ninguna ciudad que se llame '{lugar}'. "
            "Puede estar mal escrita, o convenir agregarle el país."
        )

    try:
        datos = _pedir_el_clima(encontrado["latitud"], encontrado["longitud"])
    except Exception as e:
        return f"No se pudo consultar el clima de '{lugar}': {type(e).__name__}: {e}"

    return _redactar(encontrado, datos)


@tool(response_format="content_and_artifact")
def crear_imagen(descripcion: str) -> tuple[str, dict]:
    """Crea una imagen a partir de una descripción y se la envía a la persona.

    Úsala cuando te pidan crear, generar, dibujar o diseñar una imagen, un
    dibujo, un logo, un cartel o una ilustración.

    **La imagen se le envía sola a la persona en cuanto termina esta
    herramienta.** No hace falta que la describas, ni que pongas un enlace, ni
    que expliques cómo verla: ya la está viendo. Con una frase corta diciendo
    qué hiciste es suficiente.

    Tarda entre 20 y 30 segundos, así que no la uses para cosas que se pueden
    contestar con texto.

    Args:
        descripcion: Qué tiene que salir en la imagen, con todo el detalle que
            te hayan dado: el asunto, el estilo ("fotográfico", "acuarela",
            "plano"), los colores y el texto que tenga que aparecer. **La
            orientación va aquí también, con palabras** ("un cartel vertical",
            "una escena apaisada"): eso es lo que decide la forma de la imagen.
    """
    # Esta herramienta devuelve una TUPLA, y es la única del proyecto que lo
    # hace. El motivo es la decisión más importante de toda la funcionalidad:
    #
    #   · lo primero (`content`) es lo que ve el modelo, y va al estado del
    #     grafo: se guarda en la memoria y se le reenvía en cada mensaje
    #     siguiente;
    #   · lo segundo (`artifact`) se queda en el mensaje y no lo lee el modelo.
    #
    # Si el PNG viajara en el `content`, un megabyte de imagen son ~1,4 MB de
    # base64: del orden de 350.000 tokens, más que la ventana de contexto de
    # cualquier modelo, reenviados en cada turno mientras el recorte los deje
    # vivos — y `_recortar()` cuenta mensajes, no bytes, así que no protege de
    # nada. Encima se persistiría en el checkpoint de SQLite/Postgres, y ahí
    # se reescribe entero en cada paso del grafo.
    #
    # De ahí la regla: en el `content` va una frase, y los bytes se quedan en
    # disco con la ruta viajando por el `artifact`.
    try:
        bytes_png = imagenes.generar(descripcion)
    except Exception as e:
        # Por qué se devuelve el error en vez de levantarlo: es la misma razón
        # que en clima() y está explicada arriba. Si esto explota, LangGraph
        # corta la respuesta entera y la persona ve un error crudo en vez de
        # una explicación.
        return (f"No se pudo crear la imagen: {type(e).__name__}: {e}", {})

    try:
        ruta = imagenes.guardar(bytes_png)
    except OSError as e:
        return (f"La imagen se creó pero no se pudo guardar: {e}", {})

    return (
        "Imagen creada y enviada a la persona.",
        {"tipo": "imagen", "ruta": str(ruta)},
    )


# Lo que el agente tiene atado. Cuando agregues otra herramienta, súmala aquí:
# es la única lista que mira el grafo.
HERRAMIENTAS = [clima, crear_imagen]

# Qué se le dice a la persona mientras cada herramienta trabaja.
#
# No es decoración: `crear_imagen` tarda medio minuto, y medio minuto sin una
# palabra es indistinguible de un programa colgado. El aviso sale ANTES de
# ejecutar la herramienta y por el mismo hilo que el texto (ver `Aviso` en
# agente.py), así que llega mientras se trabaja y no cuando ya acabó.
#
# Si añades una herramienta, añade su aviso aquí. Y si no lo haces no se rompe
# nada: simplemente esa no avisa.
AVISOS = {
    "clima": "🌦️ Consultando el tiempo…",
    "crear_imagen": "🎨 Creando la imagen… esto tarda medio minuto",
}


# -- Las consultas ------------------------------------------------------------


def _buscar_lugar(nombre: str) -> dict | None:
    """Convierte un nombre de ciudad en coordenadas. None si no existe."""
    datos = _traer(
        GEOCODING,
        {"name": nombre, "count": 1, "language": "es", "format": "json"},
    )

    resultados = datos.get("results") or []
    if not resultados:
        return None

    primero = resultados[0]
    return {
        "nombre": primero.get("name") or nombre,
        # admin1 es la provincia o el estado. Sirve para desambiguar cuando hay
        # cinco ciudades con el mismo nombre en países distintos.
        "provincia": primero.get("admin1") or "",
        "pais": primero.get("country") or "",
        "latitud": primero["latitude"],
        "longitud": primero["longitude"],
    }


def _pedir_el_clima(latitud: float, longitud: float) -> dict:
    """El clima de este momento en esas coordenadas."""
    return _traer(
        PRONOSTICO,
        {
            "latitude": latitud,
            "longitude": longitud,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m"
            ),
            # timezone=auto hace que la hora venga en la del lugar consultado,
            # no en la nuestra. Si preguntas por Tokio quieres la hora de Tokio.
            "timezone": "auto",
        },
    )


def _traer(url: str, parametros: dict) -> dict:
    """Un GET que devuelve JSON."""
    completa = f"{url}?{urllib.parse.urlencode(parametros)}"

    with urllib.request.urlopen(completa, timeout=ESPERA) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


# -- El texto que lee el modelo -----------------------------------------------


def _redactar(lugar: dict, datos: dict) -> str:
    """Arma la respuesta en texto.

    Le devolvemos al modelo una frase escrita, no el JSON crudo: entiende
    cualquiera de los dos, pero con el texto ya redactado es mucho menos
    probable que se equivoque de unidad o invente un dato que no está.
    """
    ahora = datos.get("current") or {}

    partes = [f"Clima en {_nombre_completo(lugar)}:"]
    partes.append(f"- Temperatura: {ahora.get('temperature_2m', '?')} °C")

    sensacion = ahora.get("apparent_temperature")
    if sensacion is not None:
        partes.append(f"- Sensación térmica: {sensacion} °C")

    partes.append(f"- Cielo: {_describir_cielo(ahora.get('weather_code'))}")

    humedad = ahora.get("relative_humidity_2m")
    if humedad is not None:
        partes.append(f"- Humedad: {humedad} %")

    viento = ahora.get("wind_speed_10m")
    if viento is not None:
        partes.append(f"- Viento: {viento} km/h")

    hora = ahora.get("time")
    if hora:
        partes.append(f"- Medido a las {hora[11:16]}, hora local del lugar")

    return "\n".join(partes)


def _nombre_completo(lugar: dict) -> str:
    """"Sevilla, Andalucía, España" — sin comas de más."""
    return ", ".join(
        p for p in (lugar.get("nombre"), lugar.get("provincia"), lugar.get("pais")) if p
    )


def _describir_cielo(codigo) -> str:
    """El código WMO en castellano. Si es uno raro, devolvemos el número."""
    if codigo is None:
        return "sin datos"
    return CIELO.get(codigo, f"sin descripción (código {codigo})")
