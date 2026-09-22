# pyright: basic
from pathlib import Path

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class OrmConfig(AppConfig):
    name = "chatddx.django.orm"
    verbose_name = "Database"

    def ready(self):
        post_migrate.connect(install_trail_triggers, sender=self)


def install_trail_triggers(sender, **kwargs):
    from django.db import connections

    from chatddx.repo.families.django import TrailModel

    functions_tpl = (
        Path(__file__).parent.parent.parent / "repo/sql/trail_functions.sql"
    ).read_text()
    triggers_tpl = (
        Path(__file__).parent.parent.parent / "repo/sql/trail_triggers.sql"
    ).read_text()

    connection = connections[kwargs.get("using", "default")]

    for model in sender.get_models():
        if issubclass(model, TrailModel):
            context = {
                "table_name": model._meta.db_table,
            }

            functions_sql = functions_tpl.format(**context)
            triggers_sql = triggers_tpl.format(**context)

            with connection.cursor() as cursor:
                cursor.execute(functions_sql)
                cursor.execute(triggers_sql)
                print(f"Applied immutability trigger to {context['table_name']}")
