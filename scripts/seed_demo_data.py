"""Siembra datos raw minimos para materializar la capa gold en CI.

Carga una fila en cada tabla raw (`raw.listado_pozos` y
`raw.produccion_no_convencional`) para que un posterior `dbt build` produzca
las tablas del esquema estrella (`gold.dim_pozo`, `gold.dim_tiempo`,
`gold.fct_produccion_pozo_mes`, ...).

Lo usan dos jobs de CI:
  - `dbt-ci`: corre contra el postgres de servicio (POSTGRES_HOST=localhost).
  - `integration-test`: se ejecuta dentro del contenedor del stack compose
    (POSTGRES_HOST=postgres-dwh), antes de probar los endpoints de la API.

La conexion se arma desde las variables de entorno POSTGRES_* (misma
convencion que `pipeline.resources.postgres`), por lo que el mismo script
sirve en ambos contextos sin cambios.

La fecha de extraccion se toma de DBT_FECHA_EXTRACCION (default 2026-06-12)
y debe coincidir con la `--vars '{"fecha_extraccion": ...}'` del dbt build.
"""

import os
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

FECHA_EXTRACCION = os.getenv("DBT_FECHA_EXTRACCION", "2026-06-12")


def postgres_url_from_env() -> str:
    user = quote_plus(os.getenv("POSTGRES_USER", "dwh"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "dwh"))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "warehouse")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def build_listado(fecha) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "idpozo": "10",
                "sigla": "ABC",
                "formprod": "Vaca Muerta",
                "idempresa": "YPF",
                "idareapermisoconcesion": "A1",
                "idareayacimiento": "Y1",
                "idcuenca": "C1",
                "idprovincia": "P1",
                "codigopropio": "CP1",
                "nombrepropio": "Pozo 10",
                "coordenadax": "-68.5",
                "coordenaday": "-38.2",
                "cota": "100",
                "profundidad": "2500",
                "pet_inicial": "1",
                "gas_inicial": "2",
                "agua_inicial": "3",
                "iny_agua_inicial": "0",
                "iny_gas_inicial": "0",
                "iny_otros_inicial": "0",
                "iny_co2_inicial": "0",
                "vida_util_inicial": "20",
                "areapermisoconcesion": "Area 1",
                "areayacimiento": "Yacimiento 1",
                "cuenca": "Neuquina",
                "provincia": "Neuquen",
                "clasificacion": "Productivo",
                "subclasificacion": "Gas",
                "tipo_reservorio": "No convencional",
                "subtipo_reservorio": "Shale",
                "comp_perf": "Completo",
                "gasplus": "t",
                "fecha_extraccion": fecha,
                "source_uri": "s3://test/listado.csv",
                "loaded_at": pd.Timestamp.utcnow(),
                "raw_row_number": 1,
            }
        ]
    )


def build_produccion(fecha) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "idempresa": "YPF",
                "anio": "2026",
                "mes": "2",
                "idpozo": "10",
                "prod_pet": "1",
                "prod_gas": "2",
                "prod_agua": "3",
                "iny_agua": "0",
                "iny_gas": "0",
                "iny_co2": "0",
                "iny_otro": "0",
                "tef": "30",
                "tipoextraccion": "Surgencia",
                "tipoestado": "Activo",
                "tipopozo": "Gasifero",
                "fechaingreso": "2026-02-01",
                "fecha_data": "2026-02-28",
                "rectificado": "f",
                "habilitado": "t",
                "empresa": "YPF",
                "sigla": "ABC",
                "formprod": "Vaca Muerta",
                "profundidad": "2500",
                "formacion": "Vaca Muerta",
                "idareapermisoconcesion": "A1",
                "areapermisoconcesion": "Area 1",
                "idareayacimiento": "Y1",
                "areayacimiento": "Yacimiento 1",
                "idcuenca": "C1",
                "cuenca": "Neuquina",
                "idprovincia": "P1",
                "provincia": "Neuquen",
                "proyecto": "Proyecto 1",
                "clasificacion": "Productivo",
                "subclasificacion": "Gas",
                "sub_tipo_recurso": "Shale",
                "coordenadax": "-68.5",
                "coordenaday": "-38.2",
                "fecha_extraccion": fecha,
                "source_uri": "s3://test/produccion.csv",
                "loaded_at": pd.Timestamp.utcnow(),
                "raw_row_number": 1,
            }
        ]
    )


def main() -> None:
    engine = create_engine(postgres_url_from_env())
    fecha = pd.to_datetime(FECHA_EXTRACCION).date()

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS audit"))

    build_listado(fecha).to_sql(
        "listado_pozos", engine, schema="raw", if_exists="replace", index=False
    )
    build_produccion(fecha).to_sql(
        "produccion_no_convencional",
        engine,
        schema="raw",
        if_exists="replace",
        index=False,
    )
    print(f"Datos demo sembrados en raw (fecha_extraccion={fecha})")


if __name__ == "__main__":
    main()
