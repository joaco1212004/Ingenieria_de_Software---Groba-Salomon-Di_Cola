#!/usr/bin/env bash
# Smoke test post-deploy: valida que la API responde correctamente
# tras un docker-compose up. Si cualquier check falla, sale con
# código != 0 para que el caller (CI) dispare el rollback.
#
# Uso:
#   API_KEY=xxx scripts/smoke.sh                        # contra localhost:8000
#   API_KEY=xxx scripts/smoke.sh http://otro-host:8000  # contra otro host
#
# La API_KEY DEBE pasarse como variable de entorno. No tiene default
# para evitar testear contra producción con la clave equivocada por
# accidente. Tomar el valor del .env de la EC2 o del docker-compose.
#
# Cubre solo disponibilidad básica del servicio. Tests de performance
# (latencia bajo carga, spike, stress) son una familia distinta y
# quedan fuera del alcance de Fase 1.

set -euo pipefail

HOST="${1:-http://localhost:8000}"
HOST="${HOST%/}"  # quitar trailing slash si lo hay
: "${API_KEY:?API_KEY no seteada. Usá: API_KEY=xxx scripts/smoke.sh [host]}"

echo "Smoke test contra ${HOST}"

curl -fsSL "${HOST}/metrics" > /dev/null
echo "  /metrics OK"

curl -fsSL -H "X-API-Key: ${API_KEY}" \
  "${HOST}/api/v1/wells?date_query=$(date +%F)" > /dev/null
echo "  /api/v1/wells (autenticado) OK"

echo "Smoke test OK"
