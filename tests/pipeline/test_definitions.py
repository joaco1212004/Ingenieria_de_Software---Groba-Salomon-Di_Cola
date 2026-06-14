from pipeline.definitions import (
    bronze_daily_job,
    bronze_daily_schedule,
    defs,
    medallion_daily_job,
    medallion_daily_schedule,
)


def test_jobs_y_schedules_expuestos():
    assert defs is not None
    assert bronze_daily_job.name == "bronze_daily_job"
    assert medallion_daily_job.name == "medallion_daily_job"
    assert bronze_daily_schedule.name == "bronze_daily_schedule"
    assert medallion_daily_schedule.name == "medallion_daily_schedule"
    assert bronze_daily_schedule.cron_schedule == "0 6 * * *"
    assert medallion_daily_schedule.cron_schedule == "0 6 * * *"
