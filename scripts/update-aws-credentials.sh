#!/usr/bin/env bash
# Actualiza el .env de la EC2 con las credenciales temporales de AWS Academy.
# Las credenciales de Academy expiran cada ~4 horas; correr este script al
# inicio de cada sesion de Lab.
#
# Uso:
#   scripts/update-aws-credentials.sh -i <llave.pem> \
#     -b <bucket-bronze> \
#     -k <AWS_ACCESS_KEY_ID> \
#     -s <AWS_SECRET_ACCESS_KEY> \
#     -t <AWS_SESSION_TOKEN>
#
# O con variables de entorno:
#   export AWS_ACCESS_KEY_ID=...
#   export AWS_SECRET_ACCESS_KEY=...
#   export AWS_SESSION_TOKEN=...
#   export BRONZE_BUCKET=...
#   scripts/update-aws-credentials.sh -i <llave.pem>

set -euo pipefail

EC2_USER="${EC2_USER:-ubuntu}"
EC2_HOST="${EC2_HOST:-api-hidraulicos-tipazos.duckdns.org}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/home/${EC2_USER}/Ingenieria_de_Software---Groba-Salomon-Di_Cola}"
REMOTE_ENV="${REMOTE_ENV:-${REMOTE_APP_DIR}/.env}"
BRONZE_BUCKET="${BRONZE_BUCKET:-datalake-bronze}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-}"

usage() {
  echo "Uso: $0 -i <llave.pem> [-b BUCKET] [-r REGION] [-k KEY_ID] [-s SECRET] [-t SESSION_TOKEN]"
  echo "     Tambien lee AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN / BRONZE_BUCKET"
  exit 1
}

PEM=""
while getopts "i:b:r:k:s:t:h" opt; do
  case $opt in
    i) PEM="$OPTARG" ;;
    b) BRONZE_BUCKET="$OPTARG" ;;
    r) AWS_DEFAULT_REGION="$OPTARG" ;;
    k) AWS_ACCESS_KEY_ID="$OPTARG" ;;
    s) AWS_SECRET_ACCESS_KEY="$OPTARG" ;;
    t) AWS_SESSION_TOKEN="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

[[ -z "$PEM" ]] && { echo "ERROR: falta -i <llave.pem>"; usage; }
[[ -z "${AWS_ACCESS_KEY_ID:-}" ]] && { echo "ERROR: falta AWS_ACCESS_KEY_ID"; usage; }
[[ -z "${AWS_SECRET_ACCESS_KEY:-}" ]] && { echo "ERROR: falta AWS_SECRET_ACCESS_KEY"; usage; }
[[ -z "${AWS_SESSION_TOKEN:-}" ]] && { echo "ERROR: falta AWS_SESSION_TOKEN"; usage; }
[[ -z "${BRONZE_BUCKET:-}" ]] && { echo "ERROR: falta BRONZE_BUCKET"; usage; }

echo "Actualizando .env en ${EC2_HOST}:${REMOTE_ENV}..."

ssh -i "$PEM" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" \
  AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
  AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  BRONZE_BUCKET="$BRONZE_BUCKET" \
  S3_ENDPOINT_URL="$S3_ENDPOINT_URL" \
  REMOTE_APP_DIR="$REMOTE_APP_DIR" \
  REMOTE_ENV="$REMOTE_ENV" \
  bash -s << 'REMOTE'
set -euo pipefail

mkdir -p "$(dirname "$REMOTE_ENV")"
touch "$REMOTE_ENV"
chmod 600 "$REMOTE_ENV"

update_or_add() {
  local key="$1" value="$2"
  local tmp
  tmp="$(mktemp)"

  awk -v key="$key" -v value="$value" '
    BEGIN { updated = 0 }
    $0 ~ "^" key "=" {
      print key "=" value
      updated = 1
      next
    }
    { print }
    END {
      if (!updated) {
        print key "=" value
      }
    }
  ' "$REMOTE_ENV" > "$tmp"

  cat "$tmp" > "$REMOTE_ENV"
  rm -f "$tmp"
}

update_or_add BRONZE_BUCKET "$BRONZE_BUCKET"
update_or_add S3_ENDPOINT_URL "$S3_ENDPOINT_URL"
update_or_add AWS_ACCESS_KEY_ID "$AWS_ACCESS_KEY_ID"
update_or_add AWS_SECRET_ACCESS_KEY "$AWS_SECRET_ACCESS_KEY"
update_or_add AWS_SESSION_TOKEN "$AWS_SESSION_TOKEN"
update_or_add AWS_DEFAULT_REGION "$AWS_DEFAULT_REGION"

echo "  BRONZE_BUCKET actualizado: ${BRONZE_BUCKET}"
echo "  S3_ENDPOINT_URL actualizado para AWS S3 real"
echo "  AWS_ACCESS_KEY_ID actualizado"
echo "  AWS_SECRET_ACCESS_KEY actualizado"
echo "  AWS_SESSION_TOKEN actualizado"
echo "  AWS_DEFAULT_REGION actualizado: ${AWS_DEFAULT_REGION}"
REMOTE

echo "Credenciales actualizadas. Reiniciando contenedores..."
ssh -i "$PEM" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" \
  REMOTE_APP_DIR="$REMOTE_APP_DIR" \
  bash -s << 'REMOTE'
set -euo pipefail

cd "$REMOTE_APP_DIR"

if command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d
else
  docker compose up -d
fi
REMOTE

echo "Listo."
