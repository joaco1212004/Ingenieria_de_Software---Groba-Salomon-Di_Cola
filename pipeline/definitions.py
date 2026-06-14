from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    Definitions,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)
from dagster_dbt import DbtCliResource

from pipeline.assets.bronze import (
    listado_pozos_bronze,
    produccion_no_convencional_bronze,
)
from pipeline.assets.dbt import (
    DBT_PROFILES_DIR,
    DBT_PROJECT_DIR,
    dbt_executable_from_env,
    medallion_dbt_assets,
)
from pipeline.assets.raw import (
    listado_pozos_raw,
    produccion_no_convencional_raw,
)
from pipeline.resources.s3 import s3_resource_from_env

pipeline_assets = [
    listado_pozos_bronze,
    produccion_no_convencional_bronze,
    listado_pozos_raw,
    produccion_no_convencional_raw,
    medallion_dbt_assets,
]

bronze_daily_job = define_asset_job(
    name="bronze_daily_job",
    selection=AssetSelection.groups("bronze"),
)

medallion_daily_job = define_asset_job(
    name="medallion_daily_job",
    selection=AssetSelection.groups("bronze", "raw", "silver", "audit", "gold"),
)


@schedule(
    job=bronze_daily_job,
    cron_schedule="0 6 * * *",
    execution_timezone="America/Argentina/Buenos_Aires",
    default_status=DefaultScheduleStatus.STOPPED,
)
def bronze_daily_schedule(context: ScheduleEvaluationContext):
    partition_key = context.scheduled_execution_time.strftime("%Y-%m-%d")
    return RunRequest(partition_key=partition_key)


@schedule(
    job=medallion_daily_job,
    cron_schedule="0 6 * * *",
    execution_timezone="America/Argentina/Buenos_Aires",
    default_status=DefaultScheduleStatus.RUNNING,
)
def medallion_daily_schedule(context: ScheduleEvaluationContext):
    partition_key = context.scheduled_execution_time.strftime("%Y-%m-%d")
    return RunRequest(partition_key=partition_key)


defs = Definitions(
    assets=pipeline_assets,
    jobs=[bronze_daily_job, medallion_daily_job],
    schedules=[bronze_daily_schedule, medallion_daily_schedule],
    resources={
        "s3": s3_resource_from_env(),
        "dbt": DbtCliResource(
            project_dir=str(DBT_PROJECT_DIR),
            profiles_dir=str(DBT_PROFILES_DIR),
            dbt_executable=dbt_executable_from_env(),
        ),
    },
)
