#!/usr/bin/env bash
# Aplica un único cierre sobre una copia limpia; siempre puede restaurar base.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATOS="$RAIZ/data/osm"
PBF="${PBF:-guatemala-latest.osm.pbf}"
BASE="${PBF%.osm.pbf}"
IMAGEN="${IMAGEN:-ghcr.io/project-osrm/osrm-backend:latest}"
PLATAFORMA="${PLATAFORMA:-}"
CSV="${1:-}"
RESPALDO="$DATOS/base_original"
[ -f "$RESPALDO/$BASE.osrm.geometry" ] || {
  echo 'Falta base_original: ejecutar bash osrm/construir.sh una vez.'; exit 1;
}
if [ -n "$CSV" ]; then
  case "$CSV" in /*) RUTA="$CSV";; *) RUTA="$RAIZ/$CSV";; esac
  [ -f "$RUTA" ] || { echo "No existe $RUTA"; exit 1; }
fi
LOCK="$DATOS/.cambio_escenario"
mkdir "$LOCK" 2>/dev/null || { echo 'Otro cambio de escenario está en curso.'; exit 1; }
restaurar() { cp "$RESPALDO/$BASE.osrm."* "$DATOS/"; }
salir() {
  ESTADO=$?
  trap - EXIT
  if [ "$ESTADO" -ne 0 ]; then
    echo 'Falló el cambio; restaurando línea base.'
    restaurar
    docker compose -f "$RAIZ/osrm/docker-compose.yml" up -d osrm
  fi
  rmdir "$LOCK"
  exit "$ESTADO"
}
trap salir EXIT
docker compose -f "$RAIZ/osrm/docker-compose.yml" stop osrm >/dev/null
restaurar
if [ -n "$CSV" ]; then
  cp "$RUTA" "$DATOS/cierre_actual.csv"
  echo "==> customize con cierre: $CSV"
  docker run --rm $PLATAFORMA -v "$DATOS:/data" "$IMAGEN" \
    osrm-customize "/data/$BASE.osrm" --segment-speed-file /data/cierre_actual.csv
else
  echo '==> línea base restaurada desde snapshot original'
fi
docker compose -f "$RAIZ/osrm/docker-compose.yml" up -d osrm >/dev/null
echo 'listo; el cliente debe esperar a que OSRM responda.'
