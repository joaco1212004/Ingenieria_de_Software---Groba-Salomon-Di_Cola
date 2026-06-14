from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    Definitions,
    RunRequest,
    ScheduleEvaluationContext,
    define_asset_job,
    schedule,
)

from pipeline.assets.bronze import (
    listado_pozos_bronze,
    produccion_no_convencional_bronze,
)
from pipeline.assets.medallion import (
    data_quality_results,
    gold_star_schema,
    listado_pozos_silver,
    produccion_no_convencional_silver,
)
from pipeline.resources.s3 import s3_resource_from_env

pipeline_assets = [
    listado_pozos_bronze,
    produccion_no_convencional_bronze,
    listado_pozos_silver,
    produccion_no_convencional_silver,
    data_quality_results,
    gold_star_schema,
]

bronze_daily_job = define_asset_job(
    name="bronze_daily_job",
    selection=AssetSelection.groups("bronze"),
)

medallion_daily_job = define_asset_job(
    name="medallion_daily_job",
    selection=AssetSelection.groups("bronze", "silver", "audit", "gold"),
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
    resources={"s3": s3_resource_from_env()},
)
