#!/usr/bin/env bash
# Materializa la capa bronze para una particion diaria.
#
# Uso:
#   scripts/materialize-bronze.sh                 # usa la fecha de hoy
#   scripts/materialize-bronze.sh 2026-06-12      # usa una fecha explicita

set -euo pipefail

PARTITION="${1:-$(date +%F)}"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "ERROR: no encontre docker compose ni docker-compose en PATH" >&2
  exit 1
fi

echo "Materializando listado_pozos_bronze para particion ${PARTITION}..."

"${COMPOSE[@]}" run --rm api \
  dagster asset materialize \
    -m pipeline.definitions \
    --select listado_pozos_bronze \
    --partition "${PARTITION}"

echo "Bronze materializado para ${PARTITION}."
