#!/usr/bin/env bash
# Smoke test post-deploy: valida que la API responde correctamente
# tras un docker-compose up. Si cualquier check falla, sale con
# código != 0 para que el caller (CI) dispare el rollback.
#
# Uso:
#   scripts/smoke.sh                                    # contra localhost:8000
#   scripts/smoke.sh http://otro-host:8000              # contra otro host
#   scripts/smoke.sh http://localhost:8000 mi-api-key   # con otra API key
#
# Cubre solo disponibilidad básica del servicio. Tests de performance
# (latencia bajo carga, spike, stress) son una familia distinta y
# quedan fuera del alcance de Fase 1.

set -euo pipefail

HOST="${1:-http://localhost:8000}"
API_KEY="${2:-abcdef12345}"

echo "Smoke test contra ${HOST}"

curl -fsSL "${HOST}/metrics" > /dev/null
echo "  /metrics OK"

curl -fsSL -H "X-API-Key: ${API_KEY}" \
  "${HOST}/api/v1/wells?date_query=$(date +%F)" > /dev/null
echo "  /api/v1/wells (autenticado) OK"

echo "Smoke test OK"
