#!/usr/bin/env bash
# Integration test: levanta el stack completo (api + prometheus + grafana +
# node-exporter) y valida que los 4 servicios estén integrados entre sí.
# A diferencia de smoke.sh (que solo prueba la API), este script verifica:
#   - La API responde y autentica.
#   - Prometheus scrapea a la API y a node-exporter (targets up=1).
#   - Grafana responde /api/health y su datasource Prometheus está OK.
#
# Pensado para correr en CI tras `docker compose up -d --build`.
# Sale con código != 0 si cualquier check falla.

set -euo pipefail

API_HOST="${API_HOST:-http://localhost:8000}"
PROM_HOST="${PROM_HOST:-http://localhost:9090}"
GRAFANA_HOST="${GRAFANA_HOST:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-admin}"
: "${API_KEY:?API_KEY no seteada. Usá: API_KEY=xxx scripts/integration-test.sh}"

# Espera hasta READY_TIMEOUT a que un endpoint devuelva 2xx.
wait_for() {
  local url="$1"
  local name="$2"
  local timeout="${3:-90}"
  local elapsed=0
  until curl -fsSL -o /dev/null "$url"; do
    if (( elapsed >= timeout )); then
      echo "  ${name} no respondió tras ${timeout}s en ${url}" >&2
      return 1
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
  echo "  ${name} listo (${url})"
}

echo "Esperando a que los servicios estén arriba..."
wait_for "${API_HOST}/metrics" "API"
wait_for "${PROM_HOST}/-/ready" "Prometheus"
wait_for "${GRAFANA_HOST}/api/health" "Grafana"

echo "1) API responde y autentica"
curl -fsSL -H "X-API-Key: ${API_KEY}" \
  "${API_HOST}/api/v1/wells?date_query=$(date +%F)" > /dev/null
echo "  /api/v1/wells OK"

echo "2) Prometheus scrapea targets esperados (up=1)"
# Da margen para el primer scrape (scrape_interval=15s).
sleep 20
TARGETS_JSON=$(curl -fsSL "${PROM_HOST}/api/v1/targets?state=active")
for job in predictiva-api node-exporter; do
  health=$(echo "$TARGETS_JSON" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); \
print(next((t['health'] for t in d['data']['activeTargets'] \
if t['labels'].get('job')=='${job}'), 'missing'))")
  if [[ "$health" != "up" ]]; then
    echo "  target ${job} está '${health}', esperaba 'up'" >&2
    echo "$TARGETS_JSON" >&2
    exit 1
  fi
  echo "  target ${job} up=1"
done

echo "3) Grafana datasource Prometheus está healthy"
DS_UID=$(curl -fsSL -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
  "${GRAFANA_HOST}/api/datasources/name/Prometheus_FAST_API_data" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['uid'])")
DS_HEALTH=$(curl -fsSL -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
  "${GRAFANA_HOST}/api/datasources/uid/${DS_UID}/health" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))")
if [[ "$DS_HEALTH" != "OK" ]]; then
  echo "  datasource Prometheus health='${DS_HEALTH}', esperaba 'OK'" >&2
  exit 1
fi
echo "  datasource Prometheus OK (uid=${DS_UID})"

echo "Integration test OK"
