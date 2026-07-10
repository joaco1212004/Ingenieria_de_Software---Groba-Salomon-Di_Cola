from pipeline.definitions import (
    bronze_daily_job,
    bronze_daily_schedule,
    defs,
    medallion_daily_job,
    medallion_daily_schedule,
    ml_training_job,
    ml_training_schedule,
)


def test_jobs_y_schedules_expuestos():
    assert defs is not None
    assert bronze_daily_job.name == "bronze_daily_job"
    assert medallion_daily_job.name == "medallion_daily_job"
    assert ml_training_job.name == "ml_training_job"
    assert bronze_daily_schedule.name == "bronze_daily_schedule"
    assert medallion_daily_schedule.name == "medallion_daily_schedule"
    assert ml_training_schedule.name == "ml_training_schedule"
    assert bronze_daily_schedule.cron_schedule == "0 6 * * *"
    assert medallion_daily_schedule.cron_schedule == "0 6 * * *"
    # el retrain corre 1h despues del medallion para leer gold fresco
    assert ml_training_schedule.cron_schedule == "0 7 * * *"


def test_ml_training_job_incluye_features_y_assets():
    job = defs.resolve_job_def("ml_training_job")
    keys = {
        k.to_user_string()
        for k in job.asset_layer.asset_graph.materializable_asset_keys
    }
    assert {
        "gold/fct_features_declino",
        "entrenamiento_m3",
        "validacion_m3",
        "registro_m3",
    } <= keys
