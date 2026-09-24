import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orm", "0004_tool_blob"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScoreModel",
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
                ("scorer", models.CharField(max_length=64)),
                ("view", models.CharField(max_length=32)),
                ("target", models.TextField()),
                ("blob", models.CharField(max_length=64)),
                ("value", models.FloatField(blank=True, default=None, null=True)),
                ("answer", models.TextField(blank=True, default=None, null=True)),
                (
                    "reason",
                    models.CharField(
                        blank=True, default=None, max_length=64, null=True
                    ),
                ),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scores",
                        to="orm.runmodel",
                    ),
                ),
            ],
            options={
                "ordering": ("pk",),
            },
        ),
    ]
