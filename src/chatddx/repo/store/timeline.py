from dataclasses import dataclass

from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.queries import deleted, head_of, visible_to
from chatddx.repo.utils import resolve_trails


def select_versions(
    entity_name: EntityName,
    owner_name: str,
    branch_name: str,
    identity_name: str | None = None,
    model: type[BranchModel] | None = None,
) -> list[BranchModel]:
    qs = (model or entity_of(entity_name).branch_model).objects.filter(
        owner__name=owner_name, name=branch_name
    )

    if identity_name is not None:
        qs = qs.filter(visible_to(identity_name)).distinct()

    models = list(
        qs.select_related("owner", "trail")
        .prefetch_related("tags")
        .order_by("timestamp", "id")
    )

    _ = resolve_trails([model.trail for model in models])

    return models


@dataclass(frozen=True)
class Save:
    name: str
    head: BranchModel | None
    versions: int
    unchanged: bool

    @property
    def version(self) -> int:
        return self.versions + 1

    @property
    def deleted(self) -> bool:
        return self.head is not None and deleted(self.head)


def saving(
    entity_name: EntityName,
    owner_name: str,
    branch_name: str,
    fingerprint: str | None = None,
) -> Save:
    branches = entity_of(entity_name).branch_model.objects.all()
    versions = branches.filter(owner__name=owner_name, name=branch_name).count()
    head = head_of(branches, owner_name, branch_name) if versions else None
    unchanged = (
        head is not None
        and fingerprint is not None
        and head.trail.fingerprint == fingerprint
    )

    return Save(branch_name, head, versions, unchanged)


def alike(entity_name: EntityName, owner_name: str, branch_name: str) -> list[str]:
    branches = entity_of(entity_name).branch_model.objects.all()
    names = set(
        branches.filter(owner__name=owner_name, name__iexact=branch_name)
        .exclude(name=branch_name)
        .values_list("name", flat=True)
    )

    return sorted(
        name
        for name in names
        if (head := head_of(branches, owner_name, name)) is not None
        and not deleted(head)
    )
