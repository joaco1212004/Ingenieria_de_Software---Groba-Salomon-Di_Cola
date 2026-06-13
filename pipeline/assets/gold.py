from dagster import AssetExecutionContext, MaterializeResult, asset
from sqlalchemy import text

from pipeline.resources.postgres import postgres_engine_from_env


def _execute_count(connection, table_name: str) -> int:
    result = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
    return int(result.scalar_one())


@asset(
    group_name="gold",
    description="Dimensión de empresas operadoras.",
)
def dim_empresa_gold(context: AssetExecutionContext) -> MaterializeResult:
    engine = postgres_engine_from_env()

    query = """
    CREATE TABLE IF NOT EXISTS gold.dim_empresa AS
    SELECT DISTINCT
        md5(COALESCE(idempresa, '')) AS empresa_key,
        idempresa,
        empresa
    FROM silver.produccion_no_convencional
    WHERE idempresa IS NOT NULL;

    TRUNCATE TABLE gold.dim_empresa;

    INSERT INTO gold.dim_empresa
    SELECT DISTINCT
        md5(COALESCE(idempresa, '')) AS empresa_key,
        idempresa,
        empresa
    FROM silver.produccion_no_convencional
    WHERE idempresa IS NOT NULL;
    """

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
        connection.execute(text(query))
        row_count = _execute_count(connection, "gold.dim_empresa")

    return MaterializeResult(metadata={"tabla": "gold.dim_empresa", "filas": row_count})


@asset(
    group_name="gold",
    description="Dimensión de áreas, yacimientos, cuencas y provincias.",
)
def dim_area_gold(context: AssetExecutionContext) -> MaterializeResult:
    engine = postgres_engine_from_env()

    query = """
    CREATE TABLE IF NOT EXISTS gold.dim_area AS
    SELECT DISTINCT
        md5(
            COALESCE(idareapermisoconcesion, '') || '|' ||
            COALESCE(idareayacimiento, '') || '|' ||
            COALESCE(cuenca, '') || '|' ||
            COALESCE(provincia, '')
        ) AS area_key,
        idareapermisoconcesion,
        areapermisoconcesion,
        idareayacimiento,
        areayacimiento,
        cuenca,
        provincia
    FROM silver.produccion_no_convencional
    WHERE idareapermisoconcesion IS NOT NULL;

    TRUNCATE TABLE gold.dim_area;

    INSERT INTO gold.dim_area
    SELECT DISTINCT
        md5(
            COALESCE(idareapermisoconcesion, '') || '|' ||
            COALESCE(idareayacimiento, '') || '|' ||
            COALESCE(cuenca, '') || '|' ||
            COALESCE(provincia, '')
        ) AS area_key,
        idareapermisoconcesion,
        areapermisoconcesion,
        idareayacimiento,
        areayacimiento,
        cuenca,
        provincia
    FROM silver.produccion_no_convencional
    WHERE idareapermisoconcesion IS NOT NULL;
    """

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
        connection.execute(text(query))
        row_count = _execute_count(connection, "gold.dim_area")

    return MaterializeResult(metadata={"tabla": "gold.dim_area", "filas": row_count})


@asset(
    group_name="gold",
    description="Dimensión de pozos.",
)
def dim_pozo_gold(context: AssetExecutionContext) -> MaterializeResult:
    engine = postgres_engine_from_env()

    query = """
    CREATE TABLE IF NOT EXISTS gold.dim_pozo AS
    SELECT DISTINCT ON (idpozo)
        md5(COALESCE(idpozo::text, '')) AS pozo_key,
        idpozo,
        sigla,
        formprod,
        idempresa,
        profundidad,
        coordenadax,
        coordenaday,
        clasificacion,
        subclasificacion,
        tipo_reservorio,
        subtipo_reservorio
    FROM silver.listado_pozos
    WHERE idpozo IS NOT NULL
    ORDER BY idpozo, processed_at DESC;

    TRUNCATE TABLE gold.dim_pozo;

    INSERT INTO gold.dim_pozo
    SELECT DISTINCT ON (idpozo)
        md5(COALESCE(idpozo::text, '')) AS pozo_key,
        idpozo,
        sigla,
        formprod,
        idempresa,
        profundidad,
        coordenadax,
        coordenaday,
        clasificacion,
        subclasificacion,
        tipo_reservorio,
        subtipo_reservorio
    FROM silver.listado_pozos
    WHERE idpozo IS NOT NULL
    ORDER BY idpozo, processed_at DESC;
    """

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
        connection.execute(text(query))
        row_count = _execute_count(connection, "gold.dim_pozo")

    return MaterializeResult(metadata={"tabla": "gold.dim_pozo", "filas": row_count})


@asset(
    group_name="gold",
    description="Dimensión tiempo a nivel mes.",
)
def dim_tiempo_gold(context: AssetExecutionContext) -> MaterializeResult:
    engine = postgres_engine_from_env()

    query = """
    CREATE TABLE IF NOT EXISTS gold.dim_tiempo AS
    SELECT DISTINCT
        md5(anio::text || '-' || mes::text) AS tiempo_key,
        anio,
        mes,
        MAKE_DATE(anio::int, mes::int, 1) AS fecha_mes,
        EXTRACT(QUARTER FROM MAKE_DATE(anio::int, mes::int, 1))::int AS trimestre
    FROM silver.produccion_no_convencional
    WHERE anio IS NOT NULL
      AND mes IS NOT NULL;

    TRUNCATE TABLE gold.dim_tiempo;

    INSERT INTO gold.dim_tiempo
    SELECT DISTINCT
        md5(anio::text || '-' || mes::text) AS tiempo_key,
        anio,
        mes,
        MAKE_DATE(anio::int, mes::int, 1) AS fecha_mes,
        EXTRACT(QUARTER FROM MAKE_DATE(anio::int, mes::int, 1))::int AS trimestre
    FROM silver.produccion_no_convencional
    WHERE anio IS NOT NULL
      AND mes IS NOT NULL;
    """

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
        connection.execute(text(query))
        row_count = _execute_count(connection, "gold.dim_tiempo")

    return MaterializeResult(metadata={"tabla": "gold.dim_tiempo", "filas": row_count})


@asset(
    group_name="gold",
    description="Fact table de producción por pozo y mes.",
)
def fct_produccion_pozo_mes_gold(context: AssetExecutionContext) -> MaterializeResult:
    engine = postgres_engine_from_env()

    query = """
    CREATE TABLE IF NOT EXISTS gold.fct_produccion_pozo_mes AS
    SELECT
        md5(p.idpozo::text || '|' || p.anio::text || '|' || p.mes::text) AS produccion_key,
        md5(COALESCE(p.idpozo::text, '')) AS pozo_key,
        md5(COALESCE(p.idempresa, '')) AS empresa_key,
        md5(
            COALESCE(p.idareapermisoconcesion, '') || '|' ||
            COALESCE(p.idareayacimiento, '') || '|' ||
            COALESCE(p.cuenca, '') || '|' ||
            COALESCE(p.provincia, '')
        ) AS area_key,
        md5(p.anio::text || '-' || p.mes::text) AS tiempo_key,
        p.idpozo,
        p.anio,
        p.mes,
        p.prod_pet,
        p.prod_gas,
        p.prod_agua,
        p.iny_agua,
        p.iny_gas,
        p.iny_co2,
        p.iny_otro,
        p.tef,
        p.tipoextraccion,
        p.tipoestado,
        p.t_de_recurso
    FROM (
        SELECT
            *,
            tipo_de_recurso AS t_de_recurso
        FROM silver.produccion_no_convencional
    ) p
    WHERE p.idpozo IS NOT NULL
      AND p.anio IS NOT NULL
      AND p.mes IS NOT NULL;

    TRUNCATE TABLE gold.fct_produccion_pozo_mes;

    INSERT INTO gold.fct_produccion_pozo_mes
    SELECT
        md5(p.idpozo::text || '|' || p.anio::text || '|' || p.mes::text) AS produccion_key,
        md5(COALESCE(p.idpozo::text, '')) AS pozo_key,
        md5(COALESCE(p.idempresa, '')) AS empresa_key,
        md5(
            COALESCE(p.idareapermisoconcesion, '') || '|' ||
            COALESCE(p.idareayacimiento, '') || '|' ||
            COALESCE(p.cuenca, '') || '|' ||
            COALESCE(p.provincia, '')
        ) AS area_key,
        md5(p.anio::text || '-' || p.mes::text) AS tiempo_key,
        p.idpozo,
        p.anio,
        p.mes,
        p.prod_pet,
        p.prod_gas,
        p.prod_agua,
        p.iny_agua,
        p.iny_gas,
        p.iny_co2,
        p.iny_otro,
        p.tef,
        p.tipoextraccion,
        p.tipoestado,
        p.t_de_recurso
    FROM (
        SELECT
            *,
            tipo_de_recurso AS t_de_recurso
        FROM silver.produccion_no_convencional
    ) p
    WHERE p.idpozo IS NOT NULL
      AND p.anio IS NOT NULL
      AND p.mes IS NOT NULL;
    """

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
        connection.execute(text(query))
        row_count = _execute_count(connection, "gold.fct_produccion_pozo_mes")

    return MaterializeResult(
        metadata={"tabla": "gold.fct_produccion_pozo_mes", "filas": row_count}
    )