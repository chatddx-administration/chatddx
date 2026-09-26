from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from django.db.models import Model, QuerySet
from pydantic import ValidationError

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identities, ensure_identity, ensure_tags
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel, TrailModel
from chatddx.repo.families.pydantic import (
    BranchDetails,
    BranchOut,
    TrailIn,
    dump_details,
    relation_fields,
)
from chatddx.repo.names import closure_branch_name
from chatddx.repo.queries import (
    deleted,
    head_of,
    live_first,
    qs_head,
    qs_head_visible,
    qs_with_relations,
)
from chatddx.repo.store.trail import dump_trail
from chatddx.repo.utils import (
    resolve_trail,
    resolve_trails,
    trail_closure,
    trail_relations,
)
from chatddx.utils import make_async


class BranchNotFoundError(Exception):
    pass


class AmbiguousBranchError(Exception):
    pass


def get_branch_model(
    entity_name: EntityName,
    owner_name: str,
    branch_name: str | None = None,
    fingerprint: str | None = None,
    qs: QuerySet[Any] | None = None,
) -> BranchModel:
    """
    Get latest branch model of `entity_name` owned by `owner_name` (its head).

    `branch_name`: Choose which name to select from
    `fingerprint`: Look-up the branch by it's trail's fingerprint
    `qs`: Start from custom queryset (default: all)
    """

    assert branch_name or fingerprint

    if not qs:
        model_cls = entity_of(entity_name).branch_model
        qs = model_cls.objects.all()

    if fingerprint:
        qs = qs.filter(trail__fingerprint=fingerprint)

    if branch_name:
        qs = qs.filter(name=branch_name)

    model = qs_head(qs, owner_name).first()

    if model is None:
        raise BranchNotFoundError(
            f"No branch '{entity_name}:{branch_name}' with owner {owner_name}"
        )

    model.trail = resolve_trail(model.trail)

    return model


def select_branch_models(
    entity_name: EntityName,
    owner_name: str,
    qs: QuerySet[Any] | None = None,
) -> list[BranchModel]:
    """
    Find all branch models of `entity_name` directly owned by `owner_name`
    `qs`: Start from custom queryset (default: all)
    """
    if qs is None:
        model_cls = entity_of(entity_name).branch_model
        qs = qs_with_relations(qs_head(model_cls.objects.all(), owner_name))

    models = list(qs)

    _ = resolve_trails([model.trail for model in models])

    return models


get_branch_model_async = make_async(get_branch_model)


def select_visible_branch_models(
    entity_name: EntityName,
    identity_name: str,
    shared_by: str | None = None,
) -> list[BranchModel]:
    """
    The head of every branch of `entity_name` that `identity_name` can use,
    by name: its own, and those shared with it, by `shared_by` alone where
    it is given. Its own shadows a shared one of the same name, and a
    deleted one is as if it weren't.
    """
    model_cls = entity_of(entity_name).branch_model
    qs = _shared_by(model_cls.objects.all(), identity_name, shared_by)
    heads = [
        model for model in qs_head_visible(qs, identity_name) if not deleted(model)
    ]
    visible = _prefer_own(heads, identity_name)
    models = sorted(visible, key=lambda model: (model.name, model.owner.name))

    _ = resolve_trails([model.trail for model in models])

    return models


def get_visible_branch_model(
    entity_name: EntityName,
    identity_name: str,
    branch_name: str | None = None,
    trail: TrailModel | int | None = None,
    shared_by: str | None = None,
) -> BranchModel:
    """
    The head of the branch of `entity_name` that `identity_name` means by
    `branch_name`, or the newest version holding `trail`: its own if it has
    one, else the one shared with it, by `shared_by` alone where it is given.
    A deleted branch is as if it weren't, but for holding a trail no other
    branch of its owner's holds.
    """
    assert branch_name or trail

    qs = entity_of(entity_name).branch_model.objects.all()
    qs = _shared_by(qs, identity_name, shared_by)

    if branch_name:
        qs = qs.filter(name=branch_name)

    if trail:
        qs = qs.filter(trail=trail)

    found = list(qs_head_visible(qs, identity_name))

    if trail:
        # the newest version of each branch holding it, the head or not
        held = live_first(found) if _deletable(entity_name) else found
        candidates = _prefer_own(held, identity_name)
    else:
        candidates = _prefer_own(
            [model for model in found if not deleted(model)], identity_name
        )

    what = f"{entity_name} '{branch_name}'" if branch_name else f"{entity_name} branch"

    if not candidates:
        raise BranchNotFoundError(f"no {what} for {identity_name}")

    if len(candidates) > 1:
        owners = ", ".join(sorted(model.owner.name for model in candidates))
        raise AmbiguousBranchError(f"{what} is shared by more than one: {owners}")

    model = candidates[0]
    model.trail = resolve_trail(model.trail)

    return model


def get_shared_branch_model(
    entity_name: EntityName,
    identity_name: str,
    owner_name: str,
    branch_name: str,
) -> BranchModel:
    """
    The head of `owner_name`'s branch `branch_name` of `entity_name`, as
    `identity_name` sees it: its own, or shared with it.
    """
    qs = entity_of(entity_name).branch_model.objects.filter(
        owner__name=owner_name, name=branch_name
    )
    model = qs_head_visible(qs, identity_name).first()

    if model is None or deleted(model):
        raise BranchNotFoundError(
            f"no {entity_name} '{owner_name}/{branch_name}' for {identity_name}"
        )

    model.trail = resolve_trail(model.trail)

    return model


def _shared_by(
    qs: QuerySet[Any], identity_name: str, shared_by: str | None
) -> QuerySet[Any]:
    if shared_by is None:
        return qs

    return qs.filter(owner__name__in=(identity_name, shared_by))


def _deletable(entity_name: EntityName) -> bool:
    """Whether a branch of the kind can be deleted: taken out of sight, kept."""
    return "deleted" in entity_of(entity_name).branch_details.model_fields


def _prefer_own(models: list[BranchModel], identity_name: str) -> list[BranchModel]:
    own = {model.name for model in models if model.owner.name == identity_name}

    return [
        model
        for model in models
        if model.owner.name == identity_name or model.name not in own
    ]


def get_branch_out(
    entity_name: EntityName,
    owner_name: str,
    branch_name: str | None = None,
    fingerprint: str | None = None,
    qs: QuerySet[Any] | None = None,
) -> BranchOut[Any, Any]:
    """
    Get latest branch spec of `entity_name` owned by `owner_name` (its head).

    `branch_name`: Choose which name to select from
    `fingerprint`: Look-up the branch by it's trail's fingerprint
    `qs`: Start from custom queryset (default: all)
    """

    model = get_branch_model(
        entity_name,
        owner_name,
        branch_name,
        fingerprint,
        qs,
    )

    spec_cls = entity_of(entity_name).branch_out

    try:
        return spec_cls.model_validate(model)
    except ValidationError as e:
        if settings.MODE == "dev":
            from chatddx.dev.error_handling import print_pydantic_errors

            print_pydantic_errors(e)
        raise


get_branch_async = make_async(get_branch_out)


def select_branch_outs(
    entity_name: EntityName,
    owner_name: str,
    qs: QuerySet[Any] | None = None,
) -> list[BranchOut[Any, Any]]:
    """
    Find all branch specs of `entity_name` directly owned by `owner_name`
    `qs`: Start from custom queryset (default: all)
    """

    models = select_branch_models(entity_name, owner_name, qs)
    spec_cls = entity_of(entity_name).branch_out

    specs: list[BranchOut[Any, Any]] = []
    for model in models:
        specs.append(spec_cls.model_validate(model))

    return specs


select_branch_async = make_async(select_branch_outs)


def commit(
    trail: TrailIn | TrailModel,
    branch_details: BranchDetails,
    owner: IdentityModel | None = None,
) -> bool:
    """
    Embed trail in a branch and make it the head
    True: the head changed
    False: the head didn't, the trail was already the branch's head
    `owner`: the identity the details name, where the caller has it
    """
    return _commit(trail, branch_details, owner, closure=True)


commit_async = make_async(commit)


def _commit(
    trail: TrailIn | TrailModel,
    branch_details: BranchDetails,
    owner: IdentityModel | None,
    closure: bool,
) -> bool:
    entity = entity_of(trail)

    branch_details = entity.branch_details.model_validate(branch_details.model_dump())
    details = dump_details(branch_details)

    head = head_of(
        entity.branch_model.objects.all(), branch_details.owner, branch_details.name
    )

    if head and trail.fingerprint == head.trail.fingerprint and details == head.details:
        commit_relations(head, head, branch_details)

        if closure:
            _ = _commit_closure(head.trail, head.owner)

        return False

    match trail:
        case TrailIn():
            committed = dump_trail(entity.trail_model, trail)
        case TrailModel():
            committed = trail

    if head is not None:
        owner = head.owner
    elif owner is None:
        owner = ensure_identity(branch_details.owner)

    assert owner.name == branch_details.owner

    branch_model = entity.branch_model.objects.create(
        name=branch_details.name,
        owner=owner,
        trail=committed,
        details=details,
    )

    commit_relations(branch_model, head, branch_details)

    if closure:
        _ = _commit_closure(committed, owner)

    return True


def commit_closure(root: TrailModel, owner_name: str) -> list[str]:
    """
    A branch of `owner_name`'s on each trail `root` reaches that has none,
    named for it: the names, in the order the walk reached them.
    """
    return _commit_closure(root, ensure_identity(owner_name))


commit_closure_async = make_async(commit_closure)


def _commit_closure(root: TrailModel, owner: IdentityModel) -> list[str]:
    closure = trail_closure(root)
    by_entity: dict[EntityName, list[TrailModel]] = defaultdict(list)

    for trail in closure:
        by_entity[entity_of(trail).name].append(trail)

    # the whole closure is walked here: what a branch of it reaches, too
    branched = {
        (entity, trail_id)
        for entity, trails in by_entity.items()
        for trail_id in entity_of(entity)
        .branch_model.objects.filter(trail__in=trails, owner=owner)
        .values_list("trail_id", flat=True)
    }
    committed: list[str] = []

    for trail in closure:
        entity = entity_of(trail)

        if (entity.name, trail.pk) in branched:
            continue

        branch_name = closure_branch_name(entity.name, trail.fingerprint)

        _ = _commit(
            trail,
            BranchDetails(name=branch_name, owner=owner.name),
            owner,
            closure=False,
        )

        committed.append(branch_name)

    return committed


def commit_copies(root: TrailModel, owner_name: str, source_name: str) -> list[str]:
    copied: list[str] = []

    for trail in _reached(root):
        entity = entity_of(trail)
        branches = entity.branch_model.objects.all()

        if branches.filter(trail=trail, owner__name=owner_name).exists():
            continue

        source = qs_head(branches.filter(trail=trail), source_name).first()

        if source is None or (
            branches.filter(owner__name=owner_name, name=source.name).exists()
        ):
            continue

        _ = commit(
            trail=trail,
            branch_details=entity.branch_details.model_validate(
                {**source.details, "name": source.name, "owner": owner_name}
            ),
        )
        copied.append(f"{entity.name} {source.name}")

    return copied


def _reached(root: TrailModel) -> list[TrailModel]:
    seen: set[tuple[Any, Any]] = set()
    reached: list[TrailModel] = []

    def visit(trail: TrailModel) -> None:
        for related in trail_relations(trail):
            key = (related._meta.concrete_model, related.pk)

            if key not in seen:
                seen.add(key)
                visit(related)
                reached.append(related)

    visit(root)
    return reached


RELATION_RESOLVERS: dict[
    str,
    Callable[[IdentityModel, EntityName, list[str]], Sequence[Model]],
] = {
    "identity": lambda owner, entity, names: ensure_identities(names),
    "tag": ensure_tags,
}


def commit_relations(
    branch_model: BranchModel,
    previous: BranchModel | None,
    branch_details: BranchDetails,
) -> None:
    owner = branch_model.owner
    entity = entity_of(branch_model).name

    for field_name, resolver in relation_fields(type(branch_details)):
        names: list[str] | None = getattr(branch_details, field_name)
        _commit_relation(
            branch_model,
            previous,
            field_name,
            None
            if names is None
            else RELATION_RESOLVERS[resolver](owner, entity, names),
        )


def _commit_relation(
    branch_model: BranchModel,
    previous: BranchModel | None,
    field_name: str,
    related: Sequence[Model] | None,
) -> None:
    again = previous is not None and previous.pk == branch_model.pk

    if related is None:
        if previous is None or again:
            return
        related = list(getattr(previous, field_name).all())

    if again:
        getattr(branch_model, field_name).set(related)
    elif related:
        # a new version relates to nothing yet
        getattr(branch_model, field_name).add(*related)
