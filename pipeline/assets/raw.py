import os
import re
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from dagster import (
    AssetExecutionContext,
    AssetKey,
    Backoff,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    asset,
)
from dagster_aws.s3 import S3Resource
from sqlalchemy import inspect, text

from pipeline.assets.bronze import bronze_key, fecha_extraccion_partitions
from pipeline.resources.postgres import postgres_engine_from_env

RAW_RETRY_POLICY = RetryPolicy(
    max_retries=2,
    delay=20,
    backoff=Backoff.EXPONENTIAL,
)


def _normalizar_nombre_columna(columna: object) -> str:
    nombre = str(columna).replace("\ufeff", "").strip().lower()
    nombre = re.sub(r"[^a-z0-9_]+", "_", nombre)
    return re.sub(r"_+", "_", nombre).strip("_")


def _leer_csv_bronze(raw_csv: bytes) -> pd.DataFrame:
    df = pd.read_csv(BytesIO(raw_csv), encoding="utf-8-sig", low_memory=False)
    columnas: list[str] = []
    vistos: dict[str, int] = {}
    for columna in df.columns:
        base = _normalizar_nombre_columna(columna)
        vistos[base] = vistos.get(base, 0) + 1
        columnas.append(base if vistos[base] == 1 else f"{base}_{vistos[base]}")
    df.columns = columnas
    return df


def _leer_bronze_desde_s3(
    s3: S3Resource, *, dataset: str, filename: str, fecha_extraccion: str
) -> tuple[bytes, str]:
    bucket = os.environ["BRONZE_BUCKET"]
    key = bronze_key(dataset, fecha_extraccion, filename)
    response = s3.get_client().get_object(Bucket=bucket, Key=key)
    return response["Body"].read(), f"s3://{bucket}/{key}"


def _cargar_raw_partition(
    context: AssetExecutionContext,
    s3: S3Resource,
    *,
    dataset: str,
    filename: str,
    table: str,
) -> MaterializeResult:
    fecha_extraccion = context.partition_key
    raw_csv, source_uri = _leer_bronze_desde_s3(
        s3,
        dataset=dataset,
        filename=filename,
        fecha_extraccion=fecha_extraccion,
    )
    df = _leer_csv_bronze(raw_csv)
    df["fecha_extraccion"] = pd.to_datetime(fecha_extraccion).date()
    df["source_uri"] = source_uri
    df["loaded_at"] = datetime.now(timezone.utc)
    df["raw_row_number"] = range(1, len(df) + 1)

    engine = postgres_engine_from_env()
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        if inspect(conn).has_table(table, schema="raw"):
            conn.execute(
                text(f"DELETE FROM raw.{table} WHERE fecha_extraccion = :fecha"),
                {"fecha": fecha_extraccion},
            )

    df.to_sql(
        table,
        engine,
        schema="raw",
        if_exists="append",
        index=False,
        chunksize=1000,
        method="multi",
    )
    with engine.begin() as conn:
        conn.execute(text(f"ANALYZE raw.{table}"))

    return MaterializeResult(
        metadata={
            "tabla": f"raw.{table}",
            "filas": len(df),
            "source_uri": MetadataValue.path(source_uri),
            "fecha_extraccion": fecha_extraccion,
            "tipo_carga": "delete_insert_by_fecha_extraccion",
        }
    )


@asset(
    group_name="raw",
    partitions_def=fecha_extraccion_partitions,
    deps=[AssetKey("listado_pozos_bronze")],
    retry_policy=RAW_RETRY_POLICY,
    description="Carga el snapshot Bronze de listado de pozos a raw.listado_pozos.",
)
def listado_pozos_raw(
    context: AssetExecutionContext, s3: S3Resource
) -> MaterializeResult:
    return _cargar_raw_partition(
        context,
        s3,
        dataset="listado_pozos",
        filename="listado_pozos.csv",
        table="listado_pozos",
    )


@asset(
    group_name="raw",
    partitions_def=fecha_extraccion_partitions,
    deps=[AssetKey("produccion_no_convencional_bronze")],
    retry_policy=RAW_RETRY_POLICY,
    description=(
        "Carga el snapshot Bronze de produccion no convencional a "
        "raw.produccion_no_convencional."
    ),
)
def produccion_no_convencional_raw(
    context: AssetExecutionContext, s3: S3Resource
) -> MaterializeResult:
    return _cargar_raw_partition(
        context,
        s3,
        dataset="produccion_no_convencional",
        filename="produccion_no_convencional.csv",
        table="produccion_no_convencional",
    )
