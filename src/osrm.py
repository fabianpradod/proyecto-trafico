"""Cliente mínimo de OSRM.

Cubre los tres servicios que el proyecto usa (`route`, `table`, `nearest`) y
nada más. Apunta por defecto al servidor local levantado con Docker; el
servidor público solo sirve como control de que la red de Guatemala en OSRM
se ve igual desde afuera.
"""

from __future__ import annotations

import time
from typing import Iterable, Sequence

import requests

from config import OSRM_LOCAL, PERFIL

Coord = tuple[float, float]  # siempre (lat, lon), como en el resto del proyecto


class ErrorOSRM(RuntimeError):
    pass


def _coords(puntos: Iterable[Coord]) -> str:
    # OSRM pide lon,lat separados por ';' — el orden invertido es la fuente
    # número uno de rutas absurdas, así que la conversión vive en un solo lugar.
    return ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in puntos)


def _pedir(servicio: str, puntos: Sequence[Coord], servidor: str, **params) -> dict:
    url = f"{servidor}/{servicio}/v1/{PERFIL}/{_coords(puntos)}"
    r = requests.get(url, params=params, timeout=60)
    d = r.json()
    if d.get("code") != "Ok":
        raise ErrorOSRM(f"{d.get('code')}: {d.get('message', 'sin mensaje')}")
    r.raise_for_status()
    return d


def disponible(servidor: str = OSRM_LOCAL) -> bool:
    """True si el servidor responde una ruta trivial."""
    try:
        _pedir("route", [(14.6047, -90.4896), (14.6084, -90.4865)],
               servidor, overview="false")
        return True
    except Exception:
        return False


def esperar(servidor: str = OSRM_LOCAL, intentos: int = 30, pausa: float = 2.0) -> None:
    """Bloquea hasta que el servidor levante, o revienta con un mensaje útil."""
    for i in range(intentos):
        if disponible(servidor):
            return
        time.sleep(pausa)
    raise ErrorOSRM(
        f"{servidor} no respondió tras {intentos * pausa:.0f}s. "
        "Revisar `docker compose -f osrm/docker-compose.yml logs`."
    )


def ruta(origen: Coord, destino: Coord, servidor: str = OSRM_LOCAL,
         geometria: bool = False, nodos: bool = True) -> dict | None:
    """Ruta más rápida entre dos puntos.

    Devuelve `None` cuando OSRM no encuentra ruta — que es exactamente lo que
    pasa cuando un cierre deja un origen o un destino sin salida. Ese caso NO
    es un error: es un resultado del experimento y hay que contarlo.
    """
    params = {
        "overview": "full" if geometria else "false",
        "geometries": "polyline",
        "alternatives": "false",
        "steps": "false",
    }
    if nodos:
        # `nodes` da los IDs de nodo OSM que la ruta atraviesa. Es lo que
        # permite verificar que una ruta efectivamente ya no pasa por la
        # calle cerrada, sin depender de la geometría dibujada.
        params["annotations"] = "nodes,duration,distance"

    try:
        d = _pedir("route", [origen, destino], servidor, **params)
    except ErrorOSRM as e:
        if "NoRoute" in str(e):
            return None
        raise

    r = d["routes"][0]
    salida = {"distancia_m": r["distance"], "duracion_s": r["duration"]}
    if geometria:
        salida["geometria"] = r["geometry"]
    if nodos:
        ann = r["legs"][0]["annotation"]
        salida["nodos"] = ann["nodes"]
        salida["duraciones_s"] = ann["duration"]
        salida["distancias_m"] = ann["distance"]
        if len(ann["nodes"]) != len(ann["duration"]) + 1:
            raise ErrorOSRM("Anotaciones de nodos y segmentos desalineadas")
        # Las anotaciones excluyen giros; conservar el residuo evita perderlos.
        salida["residuo_s"] = r["duration"] - sum(ann["duration"])
    return salida


def tabla(origenes: Sequence[Coord], destinos: Sequence[Coord] | None = None,
          servidor: str = OSRM_LOCAL) -> dict:
    """Matriz origen-destino de duraciones y distancias.

    Una sola petición en vez de |O|x|D| llamadas a `route`. El servidor local
    no tiene el tope de 100 coordenadas del demo público, pero el costo crece
    como el producto, así que conviene no pasarse de unos cientos.
    """
    if destinos is None:
        puntos, params = list(origenes), {}
    else:
        puntos = list(origenes) + list(destinos)
        n = len(origenes)
        params = {
            "sources": ";".join(str(i) for i in range(n)),
            "destinations": ";".join(str(i) for i in range(n, len(puntos))),
        }
    d = _pedir("table", puntos, servidor, annotations="duration,distance", **params)
    return {"duraciones_s": d["durations"], "distancias_m": d["distances"]}


def nearest(punto: Coord, servidor: str = OSRM_LOCAL) -> dict:
    """Nodo de la red vial más cercano al punto. Sirve para anclar orígenes
    y destinos a la calle en vez de a un patio o un techo."""
    d = _pedir("nearest", [punto], servidor, number="1")
    w = d["waypoints"][0]
    lon, lat = w["location"]
    return {"lat": lat, "lon": lon, "nombre": w.get("name", ""),
            "distancia_m": w["distance"], "nodos": w.get("nodes", [])}
