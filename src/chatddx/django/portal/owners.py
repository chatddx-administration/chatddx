# pyright: basic

from django.http import HttpRequest

from chatddx.bench.bench import Bench
from chatddx.bench.cell import SLICES
from chatddx.core.utils import ensure_identity
from chatddx.repo.entity_names import EntityName

OWN: tuple[EntityName, ...] = ("configuration", *SLICES, "case")


def identity_of(request: HttpRequest) -> str:
    return ensure_identity(request.user.get_username()).name


def bench_of(request: HttpRequest) -> Bench:
    return Bench(identity_of(request), own=OWN)
