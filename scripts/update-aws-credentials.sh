#!/usr/bin/env bash
# Actualiza las credenciales temporales de AWS Academy en el .env de la EC2.
# Las credenciales de Academy expiran cada ~4 horas; correr este script
# al inicio de cada sesión de Lab.
#
# Uso:
#   scripts/update-aws-credentials.sh -i <llave.pem> \
#     -k <AWS_ACCESS_KEY_ID> \
#     -s <AWS_SECRET_ACCESS_KEY> \
#     -t <AWS_SESSION_TOKEN>
#
# O con variables de entorno (útil para pegar el bloque completo del Lab):
#   export AWS_ACCESS_KEY_ID=...
#   export AWS_SECRET_ACCESS_KEY=...
#   export AWS_SESSION_TOKEN=...
#   scripts/update-aws-credentials.sh -i <llave.pem>

set -euo pipefail

EC2_USER="ubuntu"
EC2_HOST="api-hidraulicos-tipazos.duckdns.org"
REMOTE_ENV="~/Ingenieria_de_Software---Groba-Salomon-Di_Cola/.env"

usage() {
  echo "Uso: $0 -i <llave.pem> [-k KEY_ID] [-s SECRET] [-t SESSION_TOKEN]"
  echo "     Las credenciales también se leen de AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN"
  exit 1
}

PEM=""
while getopts "i:k:s:t:h" opt; do
  case $opt in
    i) PEM="$OPTARG" ;;
    k) AWS_ACCESS_KEY_ID="$OPTARG" ;;
    s) AWS_SECRET_ACCESS_KEY="$OPTARG" ;;
    t) AWS_SESSION_TOKEN="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

[[ -z "$PEM" ]] && { echo "ERROR: falta -i <llave.pem>"; usage; }
[[ -z "${AWS_ACCESS_KEY_ID:-}"     ]] && { echo "ERROR: falta AWS_ACCESS_KEY_ID"; usage; }
[[ -z "${AWS_SECRET_ACCESS_KEY:-}" ]] && { echo "ERROR: falta AWS_SECRET_ACCESS_KEY"; usage; }
[[ -z "${AWS_SESSION_TOKEN:-}"     ]] && { echo "ERROR: falta AWS_SESSION_TOKEN"; usage; }

echo "Actualizando credenciales AWS en ${EC2_HOST}..."

ssh -i "$PEM" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" \
  AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
  REMOTE_ENV="$REMOTE_ENV" \
  bash -s << 'REMOTE'
set -euo pipefail

# Crea el .env si no existe
touch "$REMOTE_ENV"

update_or_add() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$REMOTE_ENV" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$REMOTE_ENV"
  else
    echo "${key}=${value}" >> "$REMOTE_ENV"
  fi
}

update_or_add AWS_ACCESS_KEY_ID     "$AWS_ACCESS_KEY_ID"
update_or_add AWS_SECRET_ACCESS_KEY "$AWS_SECRET_ACCESS_KEY"
update_or_add AWS_SESSION_TOKEN     "$AWS_SESSION_TOKEN"

echo "  AWS_ACCESS_KEY_ID  actualizado"
echo "  AWS_SECRET_ACCESS_KEY actualizado"
echo "  AWS_SESSION_TOKEN  actualizado"
REMOTE

echo "Credenciales actualizadas. Reiniciando contenedores..."
ssh -i "$PEM" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_HOST}" \
  "cd ~/Ingenieria_de_Software---Groba-Salomon-Di_Cola && docker-compose up -d"

echo "Listo."
