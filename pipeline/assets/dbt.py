import json
import os
import subprocess
from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from pipeline.assets.bronze import fecha_extraccion_partitions

DBT_PROJECT_DIR = Path(__file__).resolve().parents[2] / "dbt"
DBT_PROFILES_DIR = DBT_PROJECT_DIR
DBT_MANIFEST_PATH = DBT_PROJECT_DIR / "target" / "manifest.json"


def dbt_executable_from_env() -> str:
    return os.getenv("DBT_EXECUTABLE", "dbt")


def ensure_dbt_manifest() -> Path:
    if not DBT_MANIFEST_PATH.exists():
        subprocess.run(
            [
                dbt_executable_from_env(),
                "parse",
                "--project-dir",
                str(DBT_PROJECT_DIR),
                "--profiles-dir",
                str(DBT_PROFILES_DIR),
            ],
            check=True,
        )
    return DBT_MANIFEST_PATH


@dbt_assets(
    manifest=ensure_dbt_manifest(),
    partitions_def=fecha_extraccion_partitions,
)
def medallion_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    dbt_vars = {"fecha_extraccion": context.partition_key}
    yield from dbt.cli(
        ["build", "--vars", json.dumps(dbt_vars)],
        context=context,
    ).stream()
