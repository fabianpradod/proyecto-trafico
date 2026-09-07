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
# Horizonte y llegadas — fuente A
# --------------------------------------------------------------------------
# Hora pico de la tarde. `t` va siempre en HORAS desde el inicio del horizonte.
HORA_INICIO = 16
HORIZONTE_H = 3.0

# λ(t) = λ_min + (λ_max − λ_min) · exp(−(t − t_pico)² / (2 τ²))   (§5.1)
# Los valores dan ≈ 5 000 vehículos por réplica, el tamaño de §9.1.
LAMBDA_MIN = 800.0    # veh/h, flujo de fondo fuera del pico
LAMBDA_MAX = 2300.0   # veh/h, instantáneo en el máximo
T_PICO_H = 1.5        # 17:30
TAU_H = 0.75          # ancho del pico


def lambda_llegadas(t, minimo=None, maximo=None, pico=None, tau=None):
    """Intensidad en veh/h, con `t` en horas desde HORA_INICIO.

    Acepta escalar o arreglo. Es la única definición del pico en el proyecto:
    el adelgazamiento la recibe como argumento y no la reimplementa.
    """
    import numpy as _np

    t = _np.asarray(t, dtype=float)
    minimo = LAMBDA_MIN if minimo is None else minimo
    maximo = LAMBDA_MAX if maximo is None else maximo
    pico = T_PICO_H if pico is None else pico
    tau = TAU_H if tau is None else tau
    return minimo + (maximo - minimo) * _np.exp(-((t - pico) ** 2) / (2.0 * tau**2))


# Cota para el adelgazamiento: λ(t) vale λ_max justo en t_pico, así que la
# cota es ajustada y no hay que buscarla numéricamente.
LAMBDA_COTA = LAMBDA_MAX

# --------------------------------------------------------------------------
# Velocidad del conductor — fuente D
# --------------------------------------------------------------------------
# Multiplicador s sobre la velocidad de flujo libre. Lognormal de mediana 1.0
# (μ = 0); con σ = 0.20 el 90 % central de los conductores va entre 0.72× y
# 1.39×, con la cola asimétrica a la derecha.
LOGN_MU = 0.0
LOGN_SIGMA = 0.20

# --------------------------------------------------------------------------
# Demora en intersección semaforizada — fuente E
# --------------------------------------------------------------------------
# Erlang(k=2): espera de semáforo más despeje de cola. Media k/λ = 30 s, la
# demora típica de una intersección urbana en hora pico.
ERLANG_K = 2
ERLANG_MEDIA_S = 30.0
ERLANG_LAMBDA = ERLANG_K / ERLANG_MEDIA_S  # 1/s

# --------------------------------------------------------------------------
# Generadores de números pseudoaleatorios — §7 par 3
# --------------------------------------------------------------------------
# LCG de Numerical Recipes: el generador propio del proyecto.
LCG_A, LCG_C, LCG_M = 1664525, 1013904223, 2**32

# RANDU: control negativo. Sus tripletas caen en 15 planos porque
# x[n+2] = 6·x[n+1] − 9·x[n] (mod 2^31). No se usa para producir resultados.
RANDU_A, RANDU_C, RANDU_M = 65539, 0, 2**31

# --------------------------------------------------------------------------
# Congestión — fuente F y §5.3
# --------------------------------------------------------------------------
# Valores clásicos del Bureau of Public Roads, ya fijados en §5.3.
ALFA_BPR = 0.15
BETA_BPR = 4.0
# Las capacidades, ventanas y pesos de demanda están definidos al final.

# --------------------------------------------------------------------------
# Presentación
# --------------------------------------------------------------------------
NAVY = "#003865"
ORANGE = "#FC4C02"
GREY = "#696969"
YELLOW = "#FDB92E"
PALETA = [NAVY, ORANGE, GREY, YELLOW]

# Pista C: supuestos de simulación, NO estimaciones calibradas de Guatemala.
VENTANA_H = 0.25                         # cohortes de salida de 15 minutos
PESOS_ORIGEN = (0.40, 0.35, 0.25)
FRACCION_INTRAZONAL = 0.20
CAPACIDAD_POR_CARRIL = {                 # veh/h/carril, hipótesis nominales
    'motorway': 2000., 'trunk': 1800., 'primary': 1500.,
    'secondary': 1200., 'tertiary': 1000., 'residential': 600.,
    'unclassified': 800., 'service': 400., 'living_street': 400.,
}
CAPACIDAD_CV = 0.10
CAPACIDAD_MIN_REL = 0.50
CAPACIDAD_MAX_REL = 1.50
REPLICAS = 30
BOOTSTRAP_REPLICAS = 2000
NIVEL_CONFIANZA = 0.95
FACTORES_DEMANDA = (0.5, 1.0, 1.5, 2.0)
GENERADORES = (('pcg64', 'polar'), ('pcg64', 'rechazo'),
               ('lcg', 'polar'), ('randu', 'polar'))
