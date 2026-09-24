from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orm", "0003_run_client"),
    ]

    operations = [
        migrations.AddField(
            model_name="runtoolbranchmodel",
            name="blob",
            field=models.CharField(default="", max_length=64),
            preserve_default=False,
        ),
    ]
