# pyright: basic
from pathlib import Path

from django.apps import AppConfig
from django.db.models.signals import post_migrate

SQL = Path(__file__).parent / "sql"


class RepoConfig(AppConfig):
    name = "chatddx.repo"
    label = "repo"

    def ready(self):
        post_migrate.connect(install_trail_triggers, sender=self)


def install_trail_triggers(sender, **kwargs):
    """Make every trail table refuse an update or a delete: a trail is immutable."""
    from django.db import connections

    from chatddx.repo.families.django import TrailModel

    functions_tpl = (SQL / "trail_functions.sql").read_text()
    triggers_tpl = (SQL / "trail_triggers.sql").read_text()
    connection = connections[kwargs.get("using", "default")]

    for model in sender.get_models():
        if issubclass(model, TrailModel):
            context = {"table_name": model._meta.db_table}

            with connection.cursor() as cursor:
                cursor.execute(functions_tpl.format(**context))
                cursor.execute(triggers_tpl.format(**context))
                print(f"Applied immutability trigger to {context['table_name']}")
