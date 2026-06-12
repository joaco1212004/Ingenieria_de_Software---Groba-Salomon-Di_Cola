"""Capa bronze: extracción de CSVs crudos de datos.gob.ar hacia S3.

Cada materialización descarga el snapshot completo publicado por la fuente
y lo escribe byte a byte (sin transformar) bajo la partición de la fecha de
extracción (ADR-0010, ADR-0013). Re-materializar una partición sobrescribe
únicamente esa partición: la extracción es idempotente y los snapshots de
otras fechas quedan intactos.
"""

import os

import requests
from dagster import (
    AssetExecutionContext,
    DailyPartitionsDefinition,
    MaterializeResult,
    MetadataValue,
    asset,
)
from dagster_aws.s3 import S3Resource

# URL de descarga directa del recurso CKAN referenciado en la Adenda 2
# (datos.gob.ar -> energia_cbfa4d79-ffb3-4096-bab5-eb0dde9a8385).
LISTADO_POZOS_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/"
    "resource/cbfa4d79-ffb3-4096-bab5-eb0dde9a8385/download/"
    "listado-de-pozos-cargados-por-empresas-operadoras.csv"
)

DOWNLOAD_TIMEOUT_SECONDS = 300

# La particion diaria representa la fecha_extraccion del layout bronze. El
# end_offset permite correr la extraccion del dia en curso.
fecha_extraccion_partitions = DailyPartitionsDefinition(
    start_date="2026-06-01", end_offset=1
)


def bronze_key(dataset: str, fecha_extraccion: str, filename: str) -> str:
    """Arma la key S3 del layout particionado definido en el ADR-0010."""
    return (
        f"datalake/bronze/{dataset}/" f"fecha_extraccion={fecha_extraccion}/{filename}"
    )


@asset(
    group_name="bronze",
    partitions_def=fecha_extraccion_partitions,
    description="Snapshot crudo del listado de pozos de datos.gob.ar en S3.",
)
def listado_pozos_bronze(
    context: AssetExecutionContext, s3: S3Resource
) -> MaterializeResult:
    """Descarga el CSV completo y lo sube crudo a la partición del día."""
    fecha_extraccion = context.partition_key
    bucket = os.environ["BRONZE_BUCKET"]
    key = bronze_key("listado_pozos", fecha_extraccion, "listado_pozos.csv")

    context.log.info("Descargando %s", LISTADO_POZOS_URL)
    response = requests.get(
        LISTADO_POZOS_URL, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    raw_csv = response.content

    context.log.info("Subiendo %d bytes a s3://%s/%s", len(raw_csv), bucket, key)
    s3.get_client().put_object(Bucket=bucket, Key=key, Body=raw_csv)

    return MaterializeResult(
        metadata={
            "s3_key": MetadataValue.path(f"s3://{bucket}/{key}"),
            "bytes": len(raw_csv),
            "filas_estimadas": max(raw_csv.count(b"\n") - 1, 0),
        }
    )
