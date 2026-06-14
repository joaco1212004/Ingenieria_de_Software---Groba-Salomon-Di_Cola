#!/usr/bin/env bash
# Levanta DataHub en EC2-2 usando el quickstart OFICIAL pinneado a una version.
#
# Decision (ADR-0016 "recipes/config versionadas"): en lugar de mantener a mano
# el docker-compose de ~400 lineas del quickstart (fragil y atado a la version),
# se pinea la version y se usa el CLI oficial, que descarga el compose correcto
# para esa version. El artefacto versionado en el repo es el PIN (DATAHUB_VERSION)
# + este wrapper + las recetas de ingestion.
#
# Prerequisitos en EC2-2:
#   pipx install 'acryl-datahub==1.1.0'   (el CLI debe matchear el server v1.1.0)
#   Docker con >= 8 GB RAM disponibles (DataHub levanta ES + Kafka + MySQL + GMS).
#
# Expone: frontend web en :9002, GMS (metadata API) en :8080.
set -euo pipefail

DATAHUB="${DATAHUB_EXECUTABLE:-datahub}"
VERSION="${DATAHUB_VERSION:-v1.1.0}"

echo "[datahub-up] quickstart ${VERSION}"
"$DATAHUB" docker quickstart --version "$VERSION"
echo "[datahub-up] DataHub arriba: web http://localhost:9002 , GMS :8080"
