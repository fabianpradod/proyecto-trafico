#!/usr/bin/env bash
# Construye el grafo OSRM (pipeline MLD) sobre el extracto de Guatemala.
# Se corre UNA sola vez. Los cierres después solo re-ejecutan `cerrar.sh`,
# que es la parte barata.
#
#   ./osrm/construir.sh
#
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATOS="$RAIZ/data/osm"
PBF="${PBF:-guatemala-latest.osm.pbf}"
IMAGEN="${IMAGEN:-ghcr.io/project-osrm/osrm-backend:latest}"
# En Apple Silicon la imagen oficial puede no tener build arm64. Si el pull
# falla, exportar PLATAFORMA="--platform linux/amd64" y volver a correr.
PLATAFORMA="${PLATAFORMA:-}"

if [ ! -f "$DATOS/$PBF" ]; then
  echo "No está $DATOS/$PBF — correr primero la celda de descarga del notebook 01."
  exit 1
fi

correr() {
  docker run --rm $PLATAFORMA -v "$DATOS:/data" "$IMAGEN" "$@"
}

BASE="${PBF%.osm.pbf}"

echo "==> osrm-extract (perfil car) — el paso lento, varios minutos"
correr osrm-extract -p /opt/car.lua "/data/$PBF"

echo "==> osrm-partition"
correr osrm-partition "/data/$BASE.osrm"

echo "==> osrm-customize (línea base, sin cierres)"
correr osrm-customize "/data/$BASE.osrm"

echo
echo "Grafo listo. Levantar el servidor con:"
echo "  docker compose -f osrm/docker-compose.yml up -d"
