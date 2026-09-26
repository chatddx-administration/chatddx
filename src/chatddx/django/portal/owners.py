# pyright: basic
"""Whom a request to the portal acts as, and the bench they have there."""

from django.http import HttpRequest

from chatddx.bench.bench import Bench
from chatddx.bench.cell import SLICES
from chatddx.core.utils import ensure_identity
from chatddx.repo.entity_names import EntityName

# what the portal shows of the owner's own alone: what is asked, and the
# cases; what answers, the stacks, is the archive's, a class of record apart
OWN: tuple[EntityName, ...] = ("configuration", *SLICES, "case")


def identity_of(request: HttpRequest) -> str:
    """The identity a request acts as: its user's, by name."""
    return ensure_identity(request.user.get_username()).name


def bench_of(request: HttpRequest) -> Bench:
    """The request's identity's bench, as the portal has it: its own, bar the stacks."""
    return Bench(identity_of(request), own=OWN)
