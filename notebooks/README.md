# notebooks/ — EDA exploratorio

Análisis exploratorio **ad-hoc** de los datos crudos del bronze, usado para diseñar las
transformaciones de silver/gold y los chequeos de calidad. **No es parte del pipeline
orquestado** (Dagster/dbt) ni de la imagen de producción.

## Por qué un entorno aparte (y no poetry)

El `pyproject.toml` del repo es deliberadamente *lean* (data engineering, SQL-first vía dbt —
ver `docs/decisions/0011-*`). La stack de datascience (pandas, jupyter, duckdb) **no debe
contaminar** el lockfile ni la imagen de producción. Por eso el EDA corre en un env conda
dedicado, definido en [`environment.yml`](./environment.yml).

## Setup

```bash
# 1. Crear el entorno
conda env create -f notebooks/environment.yml
conda activate eda-bronze

# 2. Registrar el kernel para Jupyter
python -m ipykernel install --user --name eda-bronze --display-name "EDA Bronze"

# 3. Abrir la notebook
jupyter lab notebooks/01_eda_bronze.ipynb
```

## Datos

La notebook lee los **CSV locales de `../data/`** (los mismos bytes que la capa bronze sube a
S3), por lo que **no requiere credenciales AWS**. Si querés analizar la última partición real
del datalake en vez del snapshot local, podés apuntar DuckDB a S3/MinIO con la extensión
`httpfs` (`INSTALL httpfs; LOAD httpfs;`) y leer
`s3://<bucket>/datalake/bronze/<dataset>/fecha_extraccion=<YYYY-MM-DD>/...`.

> Alcance: solo los 2 datasets que ingesta el bronze (`listado_pozos`,
> `produccion_no_convencional`). El `produccin-...-2026.csv` (convencional) **no** es parte del
> bronze y queda fuera del análisis.

## Salida

Los hallazgos destilados —y su mapeo a transformaciones silver, modelo estrella y tests de
calidad— viven en [`../docs/data/eda-bronze.md`](../docs/data/eda-bronze.md).

## Convención de commits

Commitear la notebook con **outputs limpiados** (`jupyter nbconvert --clear-output --inplace
notebooks/01_eda_bronze.ipynb`) para no inflar el repo ni generar diffs ruidosos.
