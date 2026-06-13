import os
from io import BytesIO
from datetime import datetime, timezone

import pandas as pd
from dagster import AssetExecutionContext, MaterializeResult, MetadataValue, asset
from dagster_aws.s3 import S3Resource
from sqlalchemy import text

from pipeline.resources.postgres import postgres_engine_from_env


LISTADO_POZOS_KEY_TEMPLATE = (
    "datalake/bronze/listado_pozos/"
    "fecha_extraccion={fecha_extraccion}/listado_pozos.csv"
)

PRODUCCION_NO_CONVENCIONAL_KEY_TEMPLATE = (
    "datalake/bronze/produccion_no_convencional/"
    "fecha_extraccion={fecha_extraccion}/produccion_no_convencional.csv"
)


def _read_csv_from_s3(s3: S3Resource, bucket: str, key: str) -> pd.DataFrame:
    obj = s3.get_client().get_object(Bucket=bucket, Key=key)
    raw_bytes = obj["Body"].read()
    return pd.read_csv(BytesIO(raw_bytes))


def _normalize_empty_strings(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace({"": None})


def _to_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _to_datetime(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")
    return df


@asset(
    group_name="silver",
    description="Tabla silver limpia del listado de pozos.",
)
def listado_pozos_silver(
    context: AssetExecutionContext,
    s3: S3Resource,
) -> MaterializeResult:
    fecha_extraccion = datetime.now(timezone.utc).date().isoformat()
    bucket = os.environ["BRONZE_BUCKET"]

    key = LISTADO_POZOS_KEY_TEMPLATE.format(fecha_extraccion=fecha_extraccion)
    context.log.info("Leyendo s3://%s/%s", bucket, key)

    df = _read_csv_from_s3(s3, bucket, key)
    df = _normalize_empty_strings(df)

    numeric_columns = [
        "idpozo",
        "coordenadax",
        "coordenaday",
        "cota",
        "profundidad",
        "pet_inicial",
        "gas_inicial",
        "agua_inicial",
        "iny_agua_inicial",
        "iny_gas_inicial",
        "iny_otros_inicial",
        "iny_co2_inicial",
        "vida_util_inicial",
        "petroleo",
        "gas",
        "agua",
        "periodo",
    ]
    df = _to_numeric(df, numeric_columns)
    df = _to_datetime(df, ["fecha_data", "fechadeingreso"])

    df["fecha_extraccion"] = fecha_extraccion
    df["processed_at"] = datetime.now(timezone.utc)
    df["source_key"] = key

    if "idpozo" in df.columns:
        df = df.dropna(subset=["idpozo"])
        df = df.sort_values("processed_at").drop_duplicates(
            subset=["idpozo"], keep="last"
        )

    engine = postgres_engine_from_env()

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS silver"))

    df.to_sql(
        name="listado_pozos",
        con=engine,
        schema="silver",
        if_exists="replace",
        index=False,
    )

    return MaterializeResult(
        metadata={
            "tabla": "silver.listado_pozos",
            "filas": len(df),
            "s3_key": MetadataValue.path(f"s3://{bucket}/{key}"),
        }
    )


@asset(
    group_name="silver",
    description="Tabla silver limpia de producción no convencional.",
)
def produccion_no_convencional_silver(
    context: AssetExecutionContext,
    s3: S3Resource,
) -> MaterializeResult:
    fecha_extraccion = datetime.now(timezone.utc).date().isoformat()
    bucket = os.environ["BRONZE_BUCKET"]

    key = PRODUCCION_NO_CONVENCIONAL_KEY_TEMPLATE.format(
        fecha_extraccion=fecha_extraccion
    )
    context.log.info("Leyendo s3://%s/%s", bucket, key)

    df = _read_csv_from_s3(s3, bucket, key)
    df = _normalize_empty_strings(df)

    numeric_columns = [
        "anio",
        "mes",
        "idpozo",
        "prod_pet",
        "prod_gas",
        "prod_agua",
        "iny_agua",
        "iny_gas",
        "iny_co2",
        "iny_otro",
        "tef",
        "vida_util",
        "profundidad",
        "coordenadax",
        "coordenaday",
    ]
    df = _to_numeric(df, numeric_columns)
    df = _to_datetime(df, ["fechaingreso", "fecha_data"])

    df["fecha_extraccion"] = fecha_extraccion
    df["processed_at"] = datetime.now(timezone.utc)
    df["source_key"] = key

    if {"idpozo", "anio", "mes"}.issubset(df.columns):
        df = df.dropna(subset=["idpozo", "anio", "mes"])
        df = df.sort_values("processed_at").drop_duplicates(
            subset=["idpozo", "anio", "mes"], keep="last"
        )

    engine = postgres_engine_from_env()

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS silver"))

    df.to_sql(
        name="produccion_no_convencional",
        con=engine,
        schema="silver",
        if_exists="replace",
        index=False,
    )

    return MaterializeResult(
        metadata={
            "tabla": "silver.produccion_no_convencional",
            "filas": len(df),
            "s3_key": MetadataValue.path(f"s3://{bucket}/{key}"),
        }
    )