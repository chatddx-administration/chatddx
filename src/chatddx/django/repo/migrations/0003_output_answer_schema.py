from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("repo", "0002_target_text_and_pattern")]

    operations = [
        migrations.RenameField(
            model_name="outputtrailmodel",
            old_name="json_schema",
            new_name="answer_schema",
        )
    ]
