from pipeline.definitions import bronze_daily_job, bronze_daily_schedule, defs


def test_bronze_job_y_schedule_expuestos():
    assert defs is not None
    assert bronze_daily_job.name == 'bronze_daily_job'
    assert bronze_daily_schedule.name == 'bronze_daily_schedule'
    assert bronze_daily_schedule.cron_schedule == '0 6 * * *'
