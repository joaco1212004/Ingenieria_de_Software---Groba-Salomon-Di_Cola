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

from pipeline.assets.silver import (
    listado_pozos_silver,
    produccion_no_convencional_silver,
)

from pipeline.assets.gold import (
    dim_area_gold,
    dim_empresa_gold,
    dim_pozo_gold,
    dim_tiempo_gold,
    fct_produccion_pozo_mes_gold,
)

from pipeline.resources.s3 import s3_resource_from_env

bronze_assets = [
    listado_pozos_bronze,
    produccion_no_convencional_bronze,
]

silver_assets = [
    listado_pozos_silver,
    produccion_no_convencional_silver,
]

gold_assets = [
    dim_empresa_gold,
    dim_area_gold,
    dim_pozo_gold,
    dim_tiempo_gold,
    fct_produccion_pozo_mes_gold,
]

bronze_daily_job = define_asset_job(
    name="bronze_daily_job",
    selection=AssetSelection.groups("bronze"),
)


@schedule(
    job=bronze_daily_job,
    cron_schedule="0 6 * * *",
    execution_timezone="America/Argentina/Buenos_Aires",
    default_status=DefaultScheduleStatus.RUNNING,
)
def bronze_daily_schedule(context: ScheduleEvaluationContext):
    partition_key = context.scheduled_execution_time.strftime("%Y-%m-%d")
    return RunRequest(partition_key=partition_key)


defs = Definitions(
    assets=[*bronze_assets, *silver_assets, *gold_assets],
    jobs=[bronze_daily_job],
    schedules=[bronze_daily_schedule],
    resources={"s3": s3_resource_from_env()},
)
