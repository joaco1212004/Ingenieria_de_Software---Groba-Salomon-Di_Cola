import os
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from urllib.parse import quote_plus

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
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from pipeline.assets.bronze import bronze_key, fecha_extraccion_partitions

POSTGRES_RETRY_POLICY = RetryPolicy(
    max_retries=2,
    delay=20,
    backoff=Backoff.EXPONENTIAL,
)

LISTADO_DATASET = "listado_pozos"
LISTADO_FILENAME = "listado_pozos.csv"
PRODUCCION_DATASET = "produccion_no_convencional"
PRODUCCION_FILENAME = "produccion_no_convencional.csv"


def postgres_url_from_env() -> str:
    user = quote_plus(os.getenv("POSTGRES_USER", "dwh"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "dwh"))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "warehouse")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def postgres_engine_from_env() -> Engine:
    return create_engine(postgres_url_from_env(), pool_pre_ping=True)


def _normalizar_nombre_columna(columna: object) -> str:
    nombre = str(columna).replace("\ufeff", "").strip().lower()
    nombre = re.sub(r"[^a-z0-9_]+", "_", nombre)
    return re.sub(r"_+", "_", nombre).strip("_")


def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    columnas: list[str] = []
    vistos: dict[str, int] = {}
    for columna in df.columns:
        base = _normalizar_nombre_columna(columna)
        vistos[base] = vistos.get(base, 0) + 1
        columnas.append(base if vistos[base] == 1 else f"{base}_{vistos[base]}")
    df = df.copy()
    df.columns = columnas
    return df


def _leer_csv(raw_csv: bytes) -> pd.DataFrame:
    return _normalizar_columnas(
        pd.read_csv(BytesIO(raw_csv), encoding="utf-8-sig", low_memory=False)
    )


def _asegurar_columnas(df: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    for columna in columnas:
        if columna not in df.columns:
            df[columna] = None
    return df[columnas].copy()


def _a_entero(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce").astype("Int64")


def _a_numero(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce")


def _a_booleano(serie: pd.Series) -> pd.Series:
    valores = serie.astype("string").str.strip().str.lower()
    return valores.map(
        {
            "t": True,
            "true": True,
            "1": True,
            "si": True,
            "s": True,
            "f": False,
            "false": False,
            "0": False,
            "no": False,
            "n": False,
        }
    ).astype("boolean")


def _normalizar_texto(serie: pd.Series, default: str = "SIN DATO") -> pd.Series:
    valores = serie.astype("string").str.strip()
    return valores.mask(valores.isna() | (valores == ""), default)


def _ultimo_dia_mes(anio: pd.Series, mes: pd.Series) -> pd.Series:
    fechas = pd.to_datetime(
        {
            "year": pd.to_numeric(anio, errors="coerce"),
            "month": pd.to_numeric(mes, errors="coerce"),
            "day": 1,
        },
        errors="coerce",
    )
    return fechas + pd.offsets.MonthEnd(0)


def _dataframe_para_sql(df: pd.DataFrame) -> pd.DataFrame:
    return df.astype(object).where(pd.notna(df), None)


def _normalizar_listado_pozos(raw_csv: bytes, fecha_extraccion: str) -> pd.DataFrame:
    df = _leer_csv(raw_csv).rename(
        columns={"coordenadax": "longitud", "coordenaday": "latitud"}
    )
    columnas = [
        "idpozo",
        "sigla",
        "formprod",
        "idempresa",
        "idareapermisoconcesion",
        "idareayacimiento",
        "idcuenca",
        "idprovincia",
        "codigopropio",
        "nombrepropio",
        "longitud",
        "latitud",
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
        "areapermisoconcesion",
        "areayacimiento",
        "cuenca",
        "provincia",
        "clasificacion",
        "subclasificacion",
        "tipo_reservorio",
        "subtipo_reservorio",
        "comp_perf",
        "gasplus",
    ]
    df = _asegurar_columnas(df, columnas)

    for columna in ["idpozo"]:
        df[columna] = _a_entero(df[columna])
    for columna in [
        "longitud",
        "latitud",
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
    ]:
        df[columna] = _a_numero(df[columna])
    df["gasplus"] = _a_booleano(df["gasplus"])
    for columna in [
        "cuenca",
        "provincia",
        "clasificacion",
        "subclasificacion",
        "tipo_reservorio",
        "subtipo_reservorio",
    ]:
        df[columna] = _normalizar_texto(df[columna])

    df["fecha_extraccion"] = pd.to_datetime(fecha_extraccion).date()
    return df.drop_duplicates(subset=["idpozo"], keep="last")


def _normalizar_produccion_no_convencional(
    raw_csv: bytes, fecha_extraccion: str
) -> pd.DataFrame:
    df = _leer_csv(raw_csv).rename(
        columns={"coordenadax": "longitud", "coordenaday": "latitud"}
    )
    columnas = [
        "idempresa",
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
        "tipoextraccion",
        "tipoestado",
        "tipopozo",
        "fechaingreso",
        "fecha_data",
        "rectificado",
        "habilitado",
        "empresa",
        "sigla",
        "formprod",
        "profundidad",
        "formacion",
        "idareapermisoconcesion",
        "areapermisoconcesion",
        "idareayacimiento",
        "areayacimiento",
        "idcuenca",
        "cuenca",
        "idprovincia",
        "provincia",
        "proyecto",
        "clasificacion",
        "subclasificacion",
        "sub_tipo_recurso",
        "longitud",
        "latitud",
    ]
    df = _asegurar_columnas(df, columnas)

    for columna in ["anio", "mes", "idpozo"]:
        df[columna] = _a_entero(df[columna])
    for columna in [
        "prod_pet",
        "prod_gas",
        "prod_agua",
        "iny_agua",
        "iny_gas",
        "iny_co2",
        "iny_otro",
        "tef",
        "profundidad",
        "longitud",
        "latitud",
    ]:
        df[columna] = _a_numero(df[columna])
    for columna in ["rectificado", "habilitado"]:
        df[columna] = _a_booleano(df[columna])
    for columna in ["fechaingreso", "fecha_data"]:
        df[columna] = pd.to_datetime(df[columna], errors="coerce")
    for columna in [
        "tipoextraccion",
        "tipoestado",
        "tipopozo",
        "cuenca",
        "provincia",
        "clasificacion",
        "subclasificacion",
        "sub_tipo_recurso",
    ]:
        df[columna] = _normalizar_texto(df[columna])

    fecha_periodo = df["fecha_data"].copy()
    df["fecha_periodo"] = fecha_periodo.fillna(_ultimo_dia_mes(df["anio"], df["mes"]))
    df["flag_prod_negativa"] = (df["prod_pet"] < 0) | (df["prod_gas"] < 0)
    df["flag_tef_fuera_rango"] = (df["tef"] < 0) | (df["tef"] > 31)
    df["flag_profundidad_fuera_rango"] = (df["profundidad"] < 0) | (
        df["profundidad"] > 10000
    )
    df["flag_coordenadas_fuera_rango"] = ~(
        df["latitud"].between(-56, -21) & df["longitud"].between(-74, -53)
    )
    df["fecha_extraccion"] = pd.to_datetime(fecha_extraccion).date()
    return df.drop_duplicates(subset=["idpozo", "anio", "mes"], keep="last")


def _leer_bronze_desde_s3(
    s3: S3Resource, *, dataset: str, filename: str, fecha_extraccion: str
) -> bytes:
    bucket = os.environ["BRONZE_BUCKET"]
    key = bronze_key(dataset, fecha_extraccion, filename)
    response = s3.get_client().get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def _escribir_tabla(
    engine: Engine, df: pd.DataFrame, *, schema: str, table: str
) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    _dataframe_para_sql(df).to_sql(
        table,
        engine,
        schema=schema,
        if_exists="replace",
        index=False,
        chunksize=1000,
        method="multi",
    )
    with engine.begin() as conn:
        conn.execute(text(f"ANALYZE {schema}.{table}"))


def _conteo(conn: Any, sql: str) -> int:
    valor = conn.execute(text(sql)).scalar()
    return int(valor or 0)


def _persistir_resultados_calidad(
    engine: Engine,
    *,
    context: AssetExecutionContext,
    fecha_extraccion: str,
) -> list[dict[str, Any]]:
    checks = [
        {
            "layer": "silver",
            "table_name": "listado_pozos",
            "check_name": "idpozo_not_null",
            "dimension": "completitud",
            "severity": "error",
            "sql": "SELECT count(*) FROM silver.listado_pozos WHERE idpozo IS NULL",
        },
        {
            "layer": "silver",
            "table_name": "listado_pozos",
            "check_name": "idpozo_unique",
            "dimension": "unicidad",
            "severity": "error",
            "sql": """
                SELECT COALESCE(SUM(n - 1), 0)
                FROM (
                    SELECT idpozo, count(*) AS n
                    FROM silver.listado_pozos
                    WHERE idpozo IS NOT NULL
                    GROUP BY idpozo
                    HAVING count(*) > 1
                ) duplicados
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "grain_keys_not_null",
            "dimension": "completitud",
            "severity": "error",
            "sql": """
                SELECT count(*)
                FROM silver.produccion_no_convencional
                WHERE idpozo IS NULL OR anio IS NULL OR mes IS NULL
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "grain_idpozo_anio_mes_unique",
            "dimension": "unicidad",
            "severity": "error",
            "sql": """
                SELECT COALESCE(SUM(n - 1), 0)
                FROM (
                    SELECT idpozo, anio, mes, count(*) AS n
                    FROM silver.produccion_no_convencional
                    WHERE idpozo IS NOT NULL AND anio IS NOT NULL AND mes IS NOT NULL
                    GROUP BY idpozo, anio, mes
                    HAVING count(*) > 1
                ) duplicados
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "mes_valid",
            "dimension": "validez",
            "severity": "error",
            "sql": """
                SELECT count(*)
                FROM silver.produccion_no_convencional
                WHERE mes IS NULL OR mes < 1 OR mes > 12
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "measures_not_null",
            "dimension": "completitud",
            "severity": "error",
            "sql": """
                SELECT count(*)
                FROM silver.produccion_no_convencional
                WHERE prod_pet IS NULL OR prod_gas IS NULL OR prod_agua IS NULL
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "idpozo_relationship_listado",
            "dimension": "integridad_referencial",
            "severity": "warn",
            "sql": """
                SELECT count(*)
                FROM silver.produccion_no_convencional p
                LEFT JOIN silver.listado_pozos l ON p.idpozo = l.idpozo
                WHERE p.idpozo IS NOT NULL AND l.idpozo IS NULL
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "produccion_no_negativa",
            "dimension": "exactitud",
            "severity": "warn",
            "sql": """
                SELECT count(*)
                FROM silver.produccion_no_convencional
                WHERE prod_pet < 0 OR prod_gas < 0
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "tef_0_31",
            "dimension": "validez",
            "severity": "warn",
            "sql": """
                SELECT count(*)
                FROM silver.produccion_no_convencional
                WHERE tef < 0 OR tef > 31
            """,
        },
        {
            "layer": "silver",
            "table_name": "produccion_no_convencional",
            "check_name": "coordenadas_argentina",
            "dimension": "exactitud",
            "severity": "warn",
            "sql": """
                SELECT count(*)
                FROM silver.produccion_no_convencional
                WHERE latitud NOT BETWEEN -56 AND -21
                   OR longitud NOT BETWEEN -74 AND -53
            """,
        },
    ]

    now = datetime.now(timezone.utc)
    resultados: list[dict[str, Any]] = []
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS audit"))
        for check in checks:
            failed_rows = _conteo(conn, check["sql"])
            resultados.append(
                {
                    "run_id": context.run_id,
                    "fecha_extraccion": fecha_extraccion,
                    "layer": check["layer"],
                    "table_name": check["table_name"],
                    "check_name": check["check_name"],
                    "dimension": check["dimension"],
                    "severity": check["severity"],
                    "status": "pass" if failed_rows == 0 else "fail",
                    "failed_rows": failed_rows,
                    "checked_at": now,
                }
            )

    pd.DataFrame(resultados).to_sql(
        "quality_results",
        engine,
        schema="audit",
        if_exists="append",
        index=False,
        chunksize=1000,
        method="multi",
    )
    return resultados


def _materializar_gold(engine: Engine) -> None:
    statements = [
        "CREATE SCHEMA IF NOT EXISTS gold",
        "DROP TABLE IF EXISTS gold.fct_produccion_pozo_mes",
        "DROP TABLE IF EXISTS gold.dim_tiempo",
        "DROP TABLE IF EXISTS gold.dim_area",
        "DROP TABLE IF EXISTS gold.dim_empresa",
        "DROP TABLE IF EXISTS gold.dim_pozo",
        """
        CREATE TABLE gold.dim_pozo AS
        SELECT DISTINCT ON (idpozo)
            md5(idpozo::text) AS sk_pozo,
            idpozo,
            sigla,
            formprod,
            clasificacion,
            subclasificacion,
            tipo_reservorio,
            subtipo_reservorio,
            profundidad,
            gasplus,
            latitud,
            longitud,
            pet_inicial,
            gas_inicial,
            agua_inicial,
            fecha_extraccion
        FROM silver.listado_pozos
        WHERE idpozo IS NOT NULL
        ORDER BY idpozo, fecha_extraccion DESC
        """,
        """
        INSERT INTO gold.dim_pozo (
            sk_pozo, idpozo, sigla, formprod, clasificacion, subclasificacion,
            tipo_reservorio, subtipo_reservorio, profundidad, gasplus, latitud,
            longitud, pet_inicial, gas_inicial, agua_inicial, fecha_extraccion
        )
        VALUES (
            md5('__unknown__'), -1, 'DESCONOCIDO', 'DESCONOCIDO', 'SIN DATO',
            'SIN DATO', 'SIN DATO', 'SIN DATO', NULL, NULL, NULL, NULL,
            NULL, NULL, NULL, NULL
        )
        """,
        """
        CREATE TABLE gold.dim_empresa AS
        SELECT DISTINCT ON (idempresa)
            md5(idempresa::text) AS sk_empresa,
            idempresa,
            empresa,
            fecha_extraccion
        FROM silver.produccion_no_convencional
        WHERE idempresa IS NOT NULL
        ORDER BY idempresa, fecha_extraccion DESC
        """,
        """
        INSERT INTO gold.dim_empresa (sk_empresa, idempresa, empresa, fecha_extraccion)
        VALUES (md5('__unknown__'), 'DESCONOCIDO', 'DESCONOCIDO', NULL)
        """,
        """
        CREATE TABLE gold.dim_area AS
        SELECT DISTINCT ON (
            idareapermisoconcesion, idareayacimiento, idcuenca, idprovincia
        )
            md5(
                concat_ws(
                    '|',
                    coalesce(idareapermisoconcesion, ''),
                    coalesce(idareayacimiento, ''),
                    coalesce(idcuenca, ''),
                    coalesce(idprovincia, '')
                )
            ) AS sk_area,
            idareapermisoconcesion,
            areapermisoconcesion,
            idareayacimiento,
            areayacimiento,
            idcuenca,
            cuenca,
            idprovincia,
            provincia,
            fecha_extraccion
        FROM silver.produccion_no_convencional
        ORDER BY idareapermisoconcesion, idareayacimiento, idcuenca, idprovincia,
                 fecha_extraccion DESC
        """,
        """
        INSERT INTO gold.dim_area (
            sk_area, idareapermisoconcesion, areapermisoconcesion,
            idareayacimiento, areayacimiento, idcuenca, cuenca, idprovincia,
            provincia, fecha_extraccion
        )
        VALUES (
            md5('__unknown__'), 'DESCONOCIDO', 'DESCONOCIDO', 'DESCONOCIDO',
            'DESCONOCIDO', 'DESCONOCIDO', 'DESCONOCIDO', 'DESCONOCIDO',
            'DESCONOCIDO', NULL
        )
        """,
        """
        CREATE TABLE gold.dim_tiempo AS
        SELECT DISTINCT
            to_char(fecha_periodo::date, 'YYYYMMDD')::integer AS sk_tiempo,
            fecha_periodo::date AS fecha_periodo,
            anio,
            mes,
            extract(quarter from fecha_periodo::date)::integer AS trimestre
        FROM silver.produccion_no_convencional
        WHERE fecha_periodo IS NOT NULL
        """,
        """
        CREATE TABLE gold.fct_produccion_pozo_mes AS
        SELECT
            md5(concat_ws('|', p.idpozo::text, p.anio::text, p.mes::text))
                AS sk_produccion_pozo_mes,
            coalesce(dp.sk_pozo, md5('__unknown__')) AS sk_pozo,
            coalesce(de.sk_empresa, md5('__unknown__')) AS sk_empresa,
            coalesce(da.sk_area, md5('__unknown__')) AS sk_area,
            dt.sk_tiempo,
            p.idpozo AS idpozo_natural,
            p.anio,
            p.mes,
            p.fecha_periodo::date AS fecha_periodo,
            p.prod_pet,
            p.prod_gas,
            p.prod_gas * 1000 AS prod_gas_m3,
            p.prod_agua,
            p.iny_agua,
            p.iny_gas,
            p.iny_co2,
            p.iny_otro,
            p.tef,
            p.rectificado,
            p.tipoestado,
            p.tipoextraccion,
            p.tipopozo,
            p.sub_tipo_recurso,
            p.flag_prod_negativa,
            p.flag_tef_fuera_rango,
            p.flag_profundidad_fuera_rango,
            p.flag_coordenadas_fuera_rango,
            p.fecha_extraccion
        FROM silver.produccion_no_convencional p
        LEFT JOIN gold.dim_pozo dp ON p.idpozo = dp.idpozo
        LEFT JOIN gold.dim_empresa de ON p.idempresa = de.idempresa
        LEFT JOIN gold.dim_area da
            ON coalesce(p.idareapermisoconcesion, '') = coalesce(da.idareapermisoconcesion, '')
           AND coalesce(p.idareayacimiento, '') = coalesce(da.idareayacimiento, '')
           AND coalesce(p.idcuenca, '') = coalesce(da.idcuenca, '')
           AND coalesce(p.idprovincia, '') = coalesce(da.idprovincia, '')
        LEFT JOIN gold.dim_tiempo dt ON p.fecha_periodo::date = dt.fecha_periodo
        """,
        "ALTER TABLE gold.dim_pozo ADD PRIMARY KEY (sk_pozo)",
        "ALTER TABLE gold.dim_empresa ADD PRIMARY KEY (sk_empresa)",
        "ALTER TABLE gold.dim_area ADD PRIMARY KEY (sk_area)",
        "ALTER TABLE gold.dim_tiempo ADD PRIMARY KEY (sk_tiempo)",
        "ALTER TABLE gold.fct_produccion_pozo_mes ADD PRIMARY KEY (sk_produccion_pozo_mes)",
        "CREATE INDEX idx_fct_prod_pozo ON gold.fct_produccion_pozo_mes (sk_pozo)",
        "CREATE INDEX idx_fct_prod_empresa ON gold.fct_produccion_pozo_mes (sk_empresa)",
        "CREATE INDEX idx_fct_prod_area ON gold.fct_produccion_pozo_mes (sk_area)",
        "CREATE INDEX idx_fct_prod_tiempo ON gold.fct_produccion_pozo_mes (sk_tiempo)",
        "ANALYZE gold.dim_pozo",
        "ANALYZE gold.dim_empresa",
        "ANALYZE gold.dim_area",
        "ANALYZE gold.dim_tiempo",
        "ANALYZE gold.fct_produccion_pozo_mes",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


@asset(
    group_name="silver",
    partitions_def=fecha_extraccion_partitions,
    deps=[AssetKey("listado_pozos_bronze")],
    retry_policy=POSTGRES_RETRY_POLICY,
    description="Tabla silver tipada y normalizada del listado de pozos.",
)
def listado_pozos_silver(
    context: AssetExecutionContext, s3: S3Resource
) -> MaterializeResult:
    raw_csv = _leer_bronze_desde_s3(
        s3,
        dataset=LISTADO_DATASET,
        filename=LISTADO_FILENAME,
        fecha_extraccion=context.partition_key,
    )
    df = _normalizar_listado_pozos(raw_csv, context.partition_key)
    _escribir_tabla(
        postgres_engine_from_env(), df, schema="silver", table="listado_pozos"
    )
    return MaterializeResult(
        metadata={
            "tabla": "silver.listado_pozos",
            "filas": len(df),
            "fecha_extraccion": context.partition_key,
        }
    )


@asset(
    group_name="silver",
    partitions_def=fecha_extraccion_partitions,
    deps=[AssetKey("produccion_no_convencional_bronze")],
    retry_policy=POSTGRES_RETRY_POLICY,
    description="Tabla silver tipada y normalizada de produccion no convencional.",
)
def produccion_no_convencional_silver(
    context: AssetExecutionContext, s3: S3Resource
) -> MaterializeResult:
    raw_csv = _leer_bronze_desde_s3(
        s3,
        dataset=PRODUCCION_DATASET,
        filename=PRODUCCION_FILENAME,
        fecha_extraccion=context.partition_key,
    )
    df = _normalizar_produccion_no_convencional(raw_csv, context.partition_key)
    _escribir_tabla(
        postgres_engine_from_env(),
        df,
        schema="silver",
        table="produccion_no_convencional",
    )
    return MaterializeResult(
        metadata={
            "tabla": "silver.produccion_no_convencional",
            "filas": len(df),
            "fecha_extraccion": context.partition_key,
        }
    )


@asset(
    group_name="audit",
    partitions_def=fecha_extraccion_partitions,
    deps=[
        AssetKey("listado_pozos_silver"),
        AssetKey("produccion_no_convencional_silver"),
    ],
    retry_policy=POSTGRES_RETRY_POLICY,
    description="Resultados persistidos de calidad de datos sobre Silver.",
)
def data_quality_results(context: AssetExecutionContext) -> MaterializeResult:
    engine = postgres_engine_from_env()
    resultados = _persistir_resultados_calidad(
        engine, context=context, fecha_extraccion=context.partition_key
    )
    errores = [
        resultado
        for resultado in resultados
        if resultado["severity"] == "error" and resultado["status"] == "fail"
    ]
    warnings = [
        resultado
        for resultado in resultados
        if resultado["severity"] == "warn" and resultado["status"] == "fail"
    ]
    if errores:
        resumen = ", ".join(
            f"{error['check_name']}={error['failed_rows']}" for error in errores
        )
        raise RuntimeError(f"Fallaron checks bloqueantes de calidad: {resumen}")

    return MaterializeResult(
        metadata={
            "tabla": "audit.quality_results",
            "checks": len(resultados),
            "warnings": len(warnings),
            "fecha_extraccion": context.partition_key,
        }
    )


@asset(
    group_name="gold",
    partitions_def=fecha_extraccion_partitions,
    deps=[AssetKey("data_quality_results")],
    retry_policy=POSTGRES_RETRY_POLICY,
    description="Modelo estrella gold con dimensiones y fact de produccion mensual.",
)
def gold_star_schema(context: AssetExecutionContext) -> MaterializeResult:
    engine = postgres_engine_from_env()
    _materializar_gold(engine)
    with engine.begin() as conn:
        fact_rows = _conteo(conn, "SELECT count(*) FROM gold.fct_produccion_pozo_mes")
        dim_pozo_rows = _conteo(conn, "SELECT count(*) FROM gold.dim_pozo")
    return MaterializeResult(
        metadata={
            "fact": MetadataValue.text("gold.fct_produccion_pozo_mes"),
            "filas_fact": fact_rows,
            "filas_dim_pozo": dim_pozo_rows,
            "fecha_extraccion": context.partition_key,
        }
    )
