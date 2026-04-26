#!/usr/bin/env bash
# Generador de trafico para la demo: hace requests variados contra la API
# para que los paneles del dashboard de Grafana se llenen mientras se graba
# el video. Mezcla:
#   - Requests OK a /forecast con distintos pozos y rangos.
#   - Requests OK a /wells.
#   - Requests sin X-API-Key (genera 403, llena la métrica de errores).
#   - Requests con fechas invertidas (genera 400, llena la métrica de errores).
#
# No reemplaza al smoke test (scripts/smoke.sh). No es un stress test.
# Es solo decoracion para la demo.
#
# Uso:
#   scripts/demo-traffic.sh                                   # local, 200 iter
#   scripts/demo-traffic.sh http://api-hidraulicos-tipazos.duckdns.org:8000
#   scripts/demo-traffic.sh http://localhost:8000 500         # 500 iter

set -uo pipefail

HOST="${1:-http://localhost:8000}"
HOST="${HOST%/}"  # quitar trailing slash si lo hay, evita //api/v1/...
ITERATIONS="${2:-200}"
API_KEY="abcdef12345"

POZOS=("POZO-001" "POZO-002" "POZO-003" "WELL-001" "WELL-002")

echo "Generando trafico contra ${HOST} (${ITERATIONS} iteraciones)"

for i in $(seq 1 "$ITERATIONS"); do
  POZO="${POZOS[$((RANDOM % ${#POZOS[@]}))]}"
  DAYS=$((RANDOM % 25 + 5))
  END_DATE=$(printf '2026-01-%02d' "$DAYS")

  # 70% requests OK a /forecast con rangos variables
  if (( RANDOM % 10 < 7 )); then
    curl -s -o /dev/null -H "X-API-Key: ${API_KEY}" \
      "${HOST}/api/v1/forecast?id_well=${POZO}&date_start=2026-01-01&date_end=${END_DATE}" &
  fi

  # 25% requests OK a /wells
  if (( RANDOM % 10 < 3 )); then
    curl -s -o /dev/null -H "X-API-Key: ${API_KEY}" \
      "${HOST}/api/v1/wells?date_query=2026-04-26" &
  fi

  # 1% requests sin api key (genera 403) — solo para que el panel
  # de errores no quede a 0 y se vea movimiento sin disparar alertas.
  if (( RANDOM % 100 < 1 )); then
    curl -s -o /dev/null \
      "${HOST}/api/v1/wells?date_query=2026-04-26" &
  fi

  # 1% requests con fecha invertida (genera 400)
  if (( RANDOM % 100 < 1 )); then
    curl -s -o /dev/null -H "X-API-Key: ${API_KEY}" \
      "${HOST}/api/v1/forecast?id_well=POZO-001&date_start=2026-12-31&date_end=2026-01-01" &
  fi

  # 3% requests al endpoint de debug (genera 500 deliberado para validar
  # que el panel de error rate y la alerta TasaErrorAlta detectan 5xx).
  if (( RANDOM % 100 < 3 )); then
    curl -s -o /dev/null -H "X-API-Key: ${API_KEY}" \
      "${HOST}/api/v1/_debug/error" &
  fi

  sleep 0.5
done

wait
echo "Trafico generado: ${ITERATIONS} iteraciones"
