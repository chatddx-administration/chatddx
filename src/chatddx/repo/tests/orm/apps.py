# pyright: basic
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class RepoOrmConfig(AppConfig):
    """The `orm` app, holding the registry's models and nothing else."""

    name = "chatddx.repo.tests.orm"
    label = "orm"

    def ready(self):
        from chatddx.django.orm.apps import install_trail_triggers

        post_migrate.connect(install_trail_triggers, sender=self)
