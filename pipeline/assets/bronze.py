# Capa bronze: extraccion de CSVs crudos de datos.gob.ar hacia S3.
# Cada materializacion descarga el snapshot completo publicado por la fuente
# y lo escribe byte a byte bajo la particion fecha_extraccion. Re-materializar
# una particion sobrescribe esa particion y mantiene idempotencia.

import os

import requests
from dagster import (
    AssetExecutionContext,
    Backoff,
    DailyPartitionsDefinition,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    asset,
)
from dagster_aws.s3 import S3Resource

LISTADO_POZOS_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/"
    "resource/cbfa4d79-ffb3-4096-bab5-eb0dde9a8385/download/"
    "listado-de-pozos-cargados-por-empresas-operadoras.csv"
)

PRODUCCION_NO_CONVENCIONAL_URL = (
    "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/"
    "resource/b5b58cdc-9e07-41f9-b392-fb9ec68b0725/download/"
    "produccin-de-pozos-de-gas-y-petrleo-no-convencional.csv"
)

DOWNLOAD_TIMEOUT_SECONDS = 300

BRONZE_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    delay=30,
    backoff=Backoff.EXPONENTIAL,
)

fecha_extraccion_partitions = DailyPartitionsDefinition(
    start_date="2026-06-01", end_offset=1
)


def bronze_key(dataset: str, fecha_extraccion: str, filename: str) -> str:
    return (
        f"datalake/bronze/{dataset}/" f"fecha_extraccion={fecha_extraccion}/{filename}"
    )


def _materializar_csv_crudo(
    context: AssetExecutionContext,
    s3: S3Resource,
    *,
    dataset: str,
    filename: str,
    source_url: str,
) -> MaterializeResult:
    fecha_extraccion = context.partition_key
    bucket = os.environ["BRONZE_BUCKET"]
    key = bronze_key(dataset, fecha_extraccion, filename)

    context.log.info("Descargando %s", source_url)
    response = requests.get(
        source_url,
        stream=True,
        timeout=DOWNLOAD_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    raw_csv = response.content

    context.log.info("Subiendo %d bytes a s3://%s/%s", len(raw_csv), bucket, key)
    s3.get_client().put_object(Bucket=bucket, Key=key, Body=raw_csv)

    return MaterializeResult(
        metadata={
            "s3_key": MetadataValue.path(f"s3://{bucket}/{key}"),
            "source_url": MetadataValue.url(source_url),
            "bytes": len(raw_csv),
            "filas_estimadas": max(raw_csv.count(b"\n") - 1, 0),
            "tipo_carga": "full_snapshot_partitioned_by_fecha_extraccion",
        }
    )


@asset(
    group_name="bronze",
    partitions_def=fecha_extraccion_partitions,
    retry_policy=BRONZE_RETRY_POLICY,
    description="Snapshot crudo del listado de pozos de datos.gob.ar en S3.",
)
def listado_pozos_bronze(
    context: AssetExecutionContext, s3: S3Resource
) -> MaterializeResult:
    return _materializar_csv_crudo(
        context,
        s3,
        dataset="listado_pozos",
        filename="listado_pozos.csv",
        source_url=LISTADO_POZOS_URL,
    )


@asset(
    group_name="bronze",
    partitions_def=fecha_extraccion_partitions,
    retry_policy=BRONZE_RETRY_POLICY,
    description=(
        "Snapshot crudo de produccion de pozos de gas y petroleo "
        "no convencional de datos.gob.ar en S3."
    ),
)
def produccion_no_convencional_bronze(
    context: AssetExecutionContext, s3: S3Resource
) -> MaterializeResult:
    return _materializar_csv_crudo(
        context,
        s3,
        dataset="produccion_no_convencional",
        filename="produccion_no_convencional.csv",
        source_url=PRODUCCION_NO_CONVENCIONAL_URL,
    )
