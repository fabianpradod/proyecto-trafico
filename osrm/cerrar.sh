#!/usr/bin/env bash
# Aplica un escenario de cierre y reinicia el servidor.
#
#   ./osrm/cerrar.sh                          -> línea base (sin cierres)
#   ./osrm/cerrar.sh data/derivados/vista_hermosa.csv
#
# Solo re-ejecuta `osrm-customize`, que tarda segundos: por eso el proyecto
# puede permitirse decenas de escenarios en vez de dos.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATOS="$RAIZ/data/osm"
PBF="${PBF:-guatemala-latest.osm.pbf}"
BASE="${PBF%.osm.pbf}"
IMAGEN="${IMAGEN:-ghcr.io/project-osrm/osrm-backend:latest}"
PLATAFORMA="${PLATAFORMA:-}"

CSV="${1:-}"

if [ -z "$CSV" ]; then
  echo "==> customize: línea base (sin cierres)"
  docker run --rm $PLATAFORMA -v "$DATOS:/data" "$IMAGEN" \
    osrm-customize "/data/$BASE.osrm"
else
  RUTA="$RAIZ/$CSV"
  [ -f "$RUTA" ] || { echo "No existe $RUTA"; exit 1; }
  cp "$RUTA" "$DATOS/cierre_actual.csv"
  echo "==> customize con cierre: $CSV ($(wc -l < "$RUTA" | tr -d ' ') segmentos)"
  docker run --rm $PLATAFORMA -v "$DATOS:/data" "$IMAGEN" \
    osrm-customize "/data/$BASE.osrm" --segment-speed-file /data/cierre_actual.csv
fi

echo "==> reiniciando osrm-routed"
docker compose -f "$RAIZ/osrm/docker-compose.yml" restart osrm >/dev/null
sleep 3
echo "listo."
