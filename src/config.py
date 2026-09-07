"""Constantes compartidas del proyecto: zonas, escenarios, semilla y rutas.

Todo el proyecto importa de aquí. Nadie redefine coordenadas ni semillas
en su propio notebook: si un número vive en dos archivos, tarde o temprano
los dos números dejan de coincidir.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
OSM = DATA / "osm"
OSRM_DIR = DATA / "osrm"
DERIVADOS = DATA / "derivados"
FIGURAS = RAIZ / "figuras"

for _d in (OSM, OSRM_DIR, DERIVADOS, FIGURAS):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Reproducibilidad
# --------------------------------------------------------------------------
# Semilla global. Cualquier corrida del proyecto con esta semilla da los
# mismos números; los escenarios abierto/cerrado la comparten a propósito
# (números aleatorios comunes, ver estructura-proyecto.md §5.6).
SEMILLA = 20_172_026

# --------------------------------------------------------------------------
# Servidor OSRM
# --------------------------------------------------------------------------
# Puerto 5001 y no 5000: en macOS el 5000 lo ocupa el receptor de AirPlay
# (proceso ControlCenter), y el contenedor no puede enlazarlo.
OSRM_LOCAL = "http://127.0.0.1:5001"
OSRM_PUBLICO = "https://router.project-osrm.org"  # solo para sanity checks
PERFIL = "driving"

# Extracto de OpenStreetMap sobre el que se construye el grafo (~131 MB).
PBF_URL = "https://download.geofabrik.de/central-america/guatemala-latest.osm.pbf"
PBF_NOMBRE = "guatemala-latest.osm.pbf"

# --------------------------------------------------------------------------
# Área de estudio: zonas 10, 15 y 16 de la Ciudad de Guatemala
# --------------------------------------------------------------------------
# (sur, oeste, norte, este) — orden de Overpass.
BBOX = (14.575, -90.530, 14.630, -90.455)

ZONAS = {
    "z10": {
        "nombre": "Zona 10 (Zona Viva / Oakland)",
        "centro": (14.5990, -90.5120),
        "peso": 0.40,  # destino laboral/comercial dominante del área
    },
    "z15": {
        "nombre": "Zona 15 (Vista Hermosa)",
        "centro": (14.6047, -90.4896),
        "peso": 0.35,
    },
    "z16": {
        "nombre": "Zona 16 (Cayalá / Landívar)",
        "centro": (14.6084, -90.4865),
        "peso": 0.25,
    },
}

# Muestreo de orígenes y destinos dentro de cada zona: se sortea uniforme en un
# disco alrededor del centro y se ancla a la vía más cercana con OSRM `nearest`.
RADIO_ZONA_M = 900
N_PUNTOS_POR_ZONA = 8

# Puntos de interés reales, usados como orígenes/destinos ancla y para
# ubicar las figuras. Coordenadas en (lat, lon), geocodificadas con Nominatim.
PUNTOS = {
    "uvg": (14.6047, -90.4896),            # Universidad del Valle de Guatemala, z15
    "cayala": (14.6084, -90.4865),         # Paseo Cayalá, z16
    "proceres": (14.5897, -90.5051),       # Boulevard Los Próceres, z10
    "reforma": (14.6060, -90.5153),        # Avenida Reforma, z10
    "vista_hermosa": (14.6060, -90.5016),  # Boulevard Vista Hermosa, z15
}

# --------------------------------------------------------------------------
# Escenarios de cierre
# --------------------------------------------------------------------------
# Los nombres son los que OpenStreetMap trae en la etiqueta `name`; están
# verificados contra Overpass y no son inventados. Cambiar una tilde aquí
# rompe la selección de ways.
ESCENARIOS = {
    "base": {
        "etiqueta": "Sin cierres",
        "nombres_osm": [],
        "hipotesis": "Referencia contra la que se miden todos los Δ%.",
    },
    "vista_hermosa": {
        "etiqueta": "Cierre Boulevard Vista Hermosa",
        "nombres_osm": ["Boulevard Vista Hermosa"],
        "hipotesis": (
            "Corredor crítico: espina primary de la zona 15 encajonada entre "
            "barrancos, con pocas alternativas paralelas. Se espera un Δ% grande "
            "y muy asimétrico según el par origen-destino."
        ),
    },
    "reforma": {
        "etiqueta": "Cierre Avenida Reforma (calzada principal)",
        "nombres_osm": ["Avenida Reforma"],
        "hipotesis": (
            "Corredor redundante: la avenida corre dentro de una retícula densa "
            "y conserva sus carriles auxiliares, así que el tráfico se reacomoda "
            "a una cuadra de distancia. Se espera un Δ% pequeño."
        ),
    },
}

# `Avenida Reforma` y `Boulevard Vista Hermosa` están mapeadas como calzadas
# separadas por sentido (oneway=yes), así que cerrar "la calle" significa
# cerrar los ways de ambos sentidos. La selección por nombre ya los toma todos.
# Los carriles auxiliares llevan otro nombre ("Carril Auxiliar Avenida
# Reforma") y por eso NO se cierran: esa es justamente la redundancia que el
# escenario quiere medir.

# --------------------------------------------------------------------------
# Presentación
# --------------------------------------------------------------------------
NAVY = "#003865"
ORANGE = "#FC4C02"
GREY = "#696969"
YELLOW = "#FDB92E"
PALETA = [NAVY, ORANGE, GREY, YELLOW]
