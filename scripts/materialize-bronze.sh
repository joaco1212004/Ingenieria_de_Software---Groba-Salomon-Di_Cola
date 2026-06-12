#!/usr/bin/env bash
# Lanza un backfill de la capa bronze para una particion diaria.
#
# Uso:
#   scripts/materialize-bronze.sh                 # usa la fecha de hoy
#   scripts/materialize-bronze.sh 2026-06-12      # usa una fecha explicita

set -euo pipefail

PARTITION=${1:-$(date +%F)}

if docker compose version >/dev/null 2>&1; then
  COMPOSE='docker compose'
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE='docker-compose'
else
  echo 'ERROR: no encontre docker compose ni docker-compose en PATH' >&2
  exit 1
fi

echo Levantando servicios Dagster si hace falta...
$COMPOSE up -d dagster-code-server dagster-webserver dagster-daemon

echo Lanzando backfill bronze para particion ${PARTITION}...
docker exec predictiva-dagster-daemon \
  dagster job backfill \
    -w workspace.yaml \
    -j bronze_daily_job \
    --partitions ${PARTITION} \
    --noprompt

echo Backfill bronze solicitado para ${PARTITION}. Revisar estado en Dagster UI.
