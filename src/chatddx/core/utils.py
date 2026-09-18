from chatddx.core.models import IdentityModel, TagModel
from chatddx.repo.registry import EntityName
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


ensure_identity_async = make_async(ensure_identity)
