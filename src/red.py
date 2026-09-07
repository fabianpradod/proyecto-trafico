"""Red vial: descarga del extracto, consulta a Overpass y archivos de cierre.

La pieza central es `archivo_velocidades`: convierte una lista de nombres de
calle en el CSV que `osrm-customize` necesita para bloquearlas. Ese archivo es
todo el mecanismo de cierre del proyecto.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable, Sequence

import requests

from config import BBOX, DERIVADOS, OSM, PBF_NOMBRE, PBF_URL

OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Clases de vía que cuentan como red conducible para el estudio. Se dejan
# fuera `service`, `living_street` y los caminos peatonales: no absorben
# tráfico de paso y solo ensucian la red.
VIAS = ["motorway", "trunk", "primary", "secondary", "tertiary",
        "unclassified", "residential",
        "motorway_link", "trunk_link", "primary_link", "secondary_link"]


# --------------------------------------------------------------------------
# Extracto OSM
# --------------------------------------------------------------------------
def descargar_pbf(destino: Path | None = None, forzar: bool = False) -> Path:
    """Baja el extracto de Guatemala de Geofabrik (~131 MB). Idempotente."""
    destino = destino or (OSM / PBF_NOMBRE)
    if destino.exists() and not forzar:
        print(f"ya existe: {destino} ({destino.stat().st_size / 1e6:.0f} MB)")
        return destino

    print(f"descargando {PBF_URL} ...")
    with requests.get(PBF_URL, stream=True, timeout=600) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        leidos = 0
        with open(destino, "wb") as f:
            for trozo in r.iter_content(chunk_size=1 << 20):
                f.write(trozo)
                leidos += len(trozo)
                if total:
                    print(f"\r  {leidos / 1e6:6.0f} / {total / 1e6:.0f} MB", end="")
    print(f"\nlisto: {destino}")
    return destino


# --------------------------------------------------------------------------
# Overpass
# --------------------------------------------------------------------------
def _overpass(consulta: str) -> list[dict]:
    ultimo = None
    for url in OVERPASS:
        try:
            req = urllib.request.Request(
                url,
                data=urllib.parse.urlencode({"data": consulta}).encode(),
                headers={"User-Agent": "uvg-cc2017-proyecto/1.0"},
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)["elements"]
        except Exception as e:  # el espejo principal se satura con frecuencia
            ultimo = e
            print(f"  espejo {url} falló ({e}); probando el siguiente")
    raise RuntimeError(f"Overpass no respondió en ningún espejo: {ultimo}")


def ways_por_nombre(nombres: Sequence[str], bbox: tuple = BBOX) -> list[dict]:
    """Ways conducibles cuyo `name` coincide exactamente con alguno de `nombres`.

    Coincidencia exacta y anclada a propósito: `Avenida Reforma` no debe
    arrastrar `Carril Auxiliar Avenida Reforma`, porque los carriles auxiliares
    son la redundancia que el escenario quiere dejar viva.
    """
    if not nombres:
        return []
    patron = "|".join(f"^{n}$" for n in nombres)
    s, o, n, e = bbox
    consulta = f"""
    [out:json][timeout:180];
    way["highway"~"^({'|'.join(VIAS)})$"]["name"~"{patron}"]({s},{o},{n},{e});
    out ids tags geom;
    """
    els = _overpass(consulta)
    return [
        {
            "way_id": el["id"],
            "nombre": el.get("tags", {}).get("name"),
            "highway": el.get("tags", {}).get("highway"),
            "oneway": el.get("tags", {}).get("oneway", "no"),
            "carriles": el.get("tags", {}).get("lanes"),
            "nodos": el.get("nodes", []),
            "geom": [(p["lat"], p["lon"]) for p in el.get("geometry", [])],
        }
        for el in els
    ]


def ways_con_nodos(nombres: Sequence[str], bbox: tuple = BBOX) -> list[dict]:
    """Igual que `ways_por_nombre` pero garantizando la lista de nodos.

    `out geom` devuelve coordenadas pero no siempre los IDs de nodo, y el
    archivo de velocidades se escribe con IDs, no con coordenadas.
    """
    if not nombres:
        return []
    patron = "|".join(f"^{n}$" for n in nombres)
    s, o, n, e = bbox
    consulta = f"""
    [out:json][timeout:180];
    way["highway"~"^({'|'.join(VIAS)})$"]["name"~"{patron}"]({s},{o},{n},{e});
    out body;
    >;
    out skel;
    """
    els = _overpass(consulta)
    nodos_xy = {el["id"]: (el["lat"], el["lon"]) for el in els if el["type"] == "node"}
    ways = []
    for el in els:
        if el["type"] != "way":
            continue
        t = el.get("tags", {})
        ways.append({
            "way_id": el["id"],
            "nombre": t.get("name"),
            "highway": t.get("highway"),
            "oneway": t.get("oneway", "no"),
            "carriles": t.get("lanes"),
            "nodos": el.get("nodes", []),
            "geom": [nodos_xy[i] for i in el.get("nodes", []) if i in nodos_xy],
        })
    return ways


# --------------------------------------------------------------------------
# Cierre de calles
# --------------------------------------------------------------------------
def pares_de_nodos(ways: Iterable[dict]) -> list[tuple[int, int]]:
    """Segmentos (nodo_a, nodo_b) de cada way, en ambos sentidos.

    OSRM identifica un segmento por su par de nodos OSM consecutivos. Se
    escriben los dos sentidos aunque el way sea `oneway`: el sentido que no
    existe en el grafo simplemente se ignora, y así no hay que razonar sobre
    la dirección del mapeo.
    """
    pares: set[tuple[int, int]] = set()
    for w in ways:
        ns = w["nodos"]
        for a, b in zip(ns, ns[1:]):
            pares.add((a, b))
            pares.add((b, a))
    return sorted(pares)


def archivo_velocidades(nombres: Sequence[str], salida: Path,
                        velocidad: int = 0, bbox: tuple = BBOX) -> dict:
    """Escribe el CSV que `osrm-customize --segment-speed-file` consume.

    Formato: `nodo_origen,nodo_destino,velocidad_kmh` por línea.
    Velocidad 0 marca el segmento como intransitable, que es el cierre total
    que el proyecto modela. Un valor pequeño (1-5 km/h) modelaría en cambio
    un carril reducido o un paso restringido, y sirve para el análisis de
    sensibilidad de §9.3 de estructura-proyecto.md.
    """
    salida = Path(salida)
    ways = ways_con_nodos(nombres, bbox)
    pares = pares_de_nodos(ways)

    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w") as f:
        for a, b in pares:
            f.write(f"{a},{b},{velocidad}\n")

    resumen = {
        "nombres": list(nombres),
        "ways": len(ways),
        "segmentos": len(pares),
        "velocidad_kmh": velocidad,
        "archivo": str(salida),
    }
    print(f"{salida.name}: {len(ways)} ways -> {len(pares)} segmentos a {velocidad} km/h")
    return resumen


def guardar_derivado(obj, nombre: str) -> Path:
    """Guarda un JSON pequeño en data/derivados (esos sí van al repo)."""
    p = DERIVADOS / nombre
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return p


def red_del_area(bbox: tuple = BBOX) -> list[dict]:
    """Todos los ways conducibles dentro de la caja, con etiquetas y geometría.

    Es la red sobre la que trabaja el proyecto. Sirve para caracterizarla
    (cuántos km de cada clase) y para dibujarla.
    """
    s, o, n, e = bbox
    consulta = f"""
    [out:json][timeout:180];
    way["highway"~"^({'|'.join(VIAS)})$"]({s},{o},{n},{e});
    out tags geom;
    """
    els = _overpass(consulta)
    return [
        {
            "way_id": el["id"],
            "nombre": el.get("tags", {}).get("name"),
            "highway": el.get("tags", {}).get("highway"),
            "oneway": el.get("tags", {}).get("oneway", "no"),
            "geom": [(p["lat"], p["lon"]) for p in el.get("geometry", [])],
        }
        for el in els
    ]


def largo_km(geom: Sequence[tuple[float, float]]) -> float:
    """Longitud de una polilínea en km (haversine sobre puntos consecutivos)."""
    import math

    R = 6371.0088
    total = 0.0
    for (la1, lo1), (la2, lo2) in zip(geom, geom[1:]):
        p1, p2 = math.radians(la1), math.radians(la2)
        dp, dl = p2 - p1, math.radians(lo2 - lo1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        total += 2 * R * math.asin(math.sqrt(a))
    return total
