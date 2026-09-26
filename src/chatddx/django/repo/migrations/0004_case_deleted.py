"""A case can be deleted, its timeline kept: none is yet."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("repo", "0003_output_answer_schema")]

    operations = [
        migrations.RunSQL(
            "UPDATE repo_case_branch SET details = details || '{\"deleted\": false}' "
            + "WHERE NOT details ? 'deleted'",
            "UPDATE repo_case_branch SET details = details - 'deleted'",
        )
    ]
