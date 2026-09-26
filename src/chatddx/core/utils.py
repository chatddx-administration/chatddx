from collections.abc import Sequence

from chatddx.core.models import IdentityModel, TagModel
from chatddx.repo.entity_names import EntityName
from chatddx.utils import make_async


def ensure_identity(name: str) -> IdentityModel:
    identity, _ = IdentityModel.objects.get_or_create(name=name)
    return identity


def ensure_tag(owner: IdentityModel, entity: EntityName, name: str) -> TagModel:
    tag, _ = TagModel.objects.get_or_create(
        name=name,
        entity=entity,
        owner=owner,
    )
    return tag


def ensure_identities(names: Sequence[str]) -> list[IdentityModel]:
    """The identities of `names`, in their order: those there read at once."""
    there = {
        identity.name: identity
        for identity in IdentityModel.objects.filter(name__in=names)
    }
    return [there.get(name) or ensure_identity(name) for name in names]


def ensure_tags(
    owner: IdentityModel, entity: EntityName, names: Sequence[str]
) -> list[TagModel]:
    """The tags of `names`, in their order: those there read at once."""
    there = {
        tag.name: tag
        for tag in TagModel.objects.filter(owner=owner, entity=entity, name__in=names)
    }
    return [there.get(name) or ensure_tag(owner, entity, name) for name in names]


ensure_identity_async = make_async(ensure_identity)
