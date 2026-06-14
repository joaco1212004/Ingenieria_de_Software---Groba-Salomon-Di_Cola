#!/usr/bin/env bash
# Ingesta metadata a DataHub (EC2-2) DESDE EC2-1.
#
# Por que aca y no dentro del contenedor Dagster: acryl-datahub trae muchas
# dependencias y conviene aislarlo (pipx) del entorno poetry del proyecto para
# no arriesgar conflictos. La ingestion necesita correr en EC2-1 porque ahi
# estan locales tanto el warehouse Postgres como los artefactos dbt (dbt/target).
#
# Prerequisitos en EC2-1:
#   pipx install 'acryl-datahub[postgres,dbt]'   (o venv dedicado)
#   variables de entorno cargadas (ver infra/platforms.env.example):
#     WAREHOUSE_HOST_PORT, WAREHOUSE_DB, WAREHOUSE_USER, WAREHOUSE_PASSWORD,
#     DATAHUB_GMS (http://<ip-privada-EC2-2>:8080), DATAHUB_TOKEN (opcional)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATAHUB="${DATAHUB_EXECUTABLE:-datahub}"
export DBT_TARGET_DIR="${DBT_TARGET_DIR:-$ROOT/dbt/target}"

# dbt vive en el venv de Poetry (no global). Orden de resolucion:
#   1) DBT_EXECUTABLE explicito (un solo token, p.ej. ruta absoluta del venv).
#   2) 'dbt' en el PATH (venv ya activado).
#   3) fallback 'poetry run dbt' (CD y EC2-1 sin venv activado).
if [[ -n "${DBT_EXECUTABLE:-}" ]]; then
  DBT=("$DBT_EXECUTABLE")
elif command -v dbt >/dev/null 2>&1; then
  DBT=(dbt)
else
  DBT=(poetry run dbt)
fi

# 1) Generar manifest.json + catalog.json (catalog consulta el warehouse).
echo "[datahub-ingest] dbt docs generate (${DBT[*]})"
"${DBT[@]}" docs generate --project-dir "$ROOT/dbt" --profiles-dir "$ROOT/dbt"

# 2) Ingerir cada receta (orden: tablas fisicas primero, luego lineage dbt).
for recipe in postgres_warehouse dbt; do
  echo "[datahub-ingest] ingest ${recipe}"
  "$DATAHUB" ingest -c "$ROOT/infra/datahub/recipes/${recipe}.yml"
done

echo "[datahub-ingest] OK"
