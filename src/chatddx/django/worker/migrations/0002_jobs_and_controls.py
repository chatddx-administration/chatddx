# The queue's rows become jobs: a batch's trials, stored for later or queued,
# placed in the queue by when they were put in it last, and run on their
# stack's slots; the controls become each owner's own.

import django.db.models.deletion
from django.db import migrations, models

# a job done is as its run came out: stopped as it ran, errored, or completed
STATUSES = """
UPDATE worker_queued AS job SET status = CASE
    WHEN job.status = 'done' AND run.status = 'errored' AND run.error = 'stopped'
        THEN 'aborted'
    WHEN job.status = 'done' AND run.status = 'errored' THEN 'errored'
    WHEN job.status = 'done' THEN 'completed'
    WHEN job.status = 'cancelled' THEN 'stopped'
    WHEN job.status = 'failed' THEN 'errored'
    ELSE job.status
END
FROM worker_queued AS queued LEFT JOIN history_run AS run ON run.id = queued.run_id
WHERE queued.id = job.id
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_pgqueuer_schema"),
        ("worker", "0001_initial"),
    ]

    operations = [
        # a job belongs to a batch
        migrations.RunSQL(
            "DELETE FROM worker_queued WHERE batch IS NULL", migrations.RunSQL.noop
        ),
        migrations.RunSQL(STATUSES, migrations.RunSQL.noop),
        migrations.RenameModel("QueuedModel", "JobModel"),
        migrations.AlterModelTable("jobmodel", "worker_job"),
        migrations.RemoveField("jobmodel", "drain"),
        migrations.AlterField(
            "jobmodel",
            "batch",
            models.UUIDField(db_index=True),
        ),
        migrations.AlterField(
            "jobmodel",
            "queued",
            models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            "jobmodel",
            "stack",
            models.CharField(db_index=True, max_length=255),
        ),
        migrations.RemoveField("workerstatemodel", "paused"),
        migrations.RemoveField("workerstatemodel", "stopping"),
        migrations.CreateModel(
            name="ControlsModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("paused", models.BooleanField(default=False)),
                ("stopping", models.PositiveSmallIntegerField(default=0)),
                (
                    "owner",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="core.identitymodel",
                    ),
                ),
            ],
            options={
                "db_table": "worker_controls",
            },
        ),
    ]
