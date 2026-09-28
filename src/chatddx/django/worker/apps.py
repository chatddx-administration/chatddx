# pyright: basic
from django.apps import AppConfig


class WorkerConfig(AppConfig):
    name = "chatddx.django.worker"
    label = "worker"
