"""Punto de entrada de Dagster: une assets y recursos del pipeline."""

from dagster import Definitions

from pipeline.assets.bronze import listado_pozos_bronze
from pipeline.resources.s3 import s3_resource_from_env

defs = Definitions(
    assets=[listado_pozos_bronze],
    resources={"s3": s3_resource_from_env()},
)
