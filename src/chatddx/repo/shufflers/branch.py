from collections.abc import Callable
from typing import Any

from django.db.models import Model, QuerySet
from pydantic import ValidationError

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity, ensure_tag
from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel, TrailModel
from chatddx.repo.families.pydantic import (
    BranchSchemaDetails,
    BranchSpec,
    TrailSchema,
    dump_details,
    relation_fields,
)
from chatddx.repo.names import resolve_branch_name
from chatddx.repo.queries import qs_canon, qs_canon_col, qs_with_details
from chatddx.repo.shufflers.trail import dump_trail
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
    Get latest branch model of `entity_name` owned by `owner_name` (aka canon).

    `branch_name`: Choose which name to select from
    `fingerprint`: Look-up the branch by it's trail's fingerprint
    `qs`: Start from custom queryset (default: all)
    """

    assert branch_name or fingerprint

    if not qs:
        model_cls = entity_of(entity_name).branch_model
        qs = model_cls.objects.all()

    if fingerprint:
        qs = qs.filter(target__fingerprint=fingerprint)

    if branch_name:
        qs = qs.filter(name=branch_name)

    model = qs_canon(qs, owner_name).first()

    if model is None:
        raise BranchNotFoundError(
            f"No branch '{entity_name}:{branch_name}' with owner {owner_name}"
        )

    model.target = resolve_trail(model.target)

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
        qs = qs_with_details(qs_canon(model_cls.objects.all(), owner_name))

    models = list(qs)

    # One walk for the whole selection: the trails come back a table at a
    # time rather than a row at a time (see `chatddx.repo.utils`).
    _ = resolve_trails([model.target for model in models])

    return models


get_branch_model_async = make_async(get_branch_model)


def select_visible_branch_models(
    entity_name: EntityName,
    identity_name: str,
    shared_by: str | None = None,
) -> list[BranchModel]:
    """
    The canon of every branch of `entity_name` that `identity_name` can use,
    by name: its own, and those shared with it, by `shared_by` alone where
    it is given. Its own shadows a shared one of the same name.
    """
    model_cls = entity_of(entity_name).branch_model
    qs = _shared_by(model_cls.objects.all(), identity_name, shared_by)
    visible = _prefer_own(list(qs_canon_col(qs, identity_name)), identity_name)
    models = sorted(visible, key=lambda model: (model.name, model.owner.name))

    _ = resolve_trails([model.target for model in models])

    return models


def get_visible_branch_model(
    entity_name: EntityName,
    identity_name: str,
    branch_name: str | None = None,
    trail: TrailModel | int | None = None,
    shared_by: str | None = None,
) -> BranchModel:
    """
    The canon of the branch of `entity_name` that `identity_name` means by
    `branch_name`, or that holds `trail`: its own if it has one, else the
    one shared with it, by `shared_by` alone where it is given.
    """
    assert branch_name or trail

    qs = entity_of(entity_name).branch_model.objects.all()
    qs = _shared_by(qs, identity_name, shared_by)

    if branch_name:
        qs = qs.filter(name=branch_name)

    if trail:
        qs = qs.filter(target=trail)

    candidates = _prefer_own(list(qs_canon_col(qs, identity_name)), identity_name)
    what = f"{entity_name} '{branch_name}'" if branch_name else f"{entity_name} branch"

    if not candidates:
        raise BranchNotFoundError(f"no {what} for {identity_name}")

    if len(candidates) > 1:
        owners = ", ".join(sorted(model.owner.name for model in candidates))
        raise AmbiguousBranchError(f"{what} is shared by more than one: {owners}")

    model = candidates[0]
    model.target = resolve_trail(model.target)

    return model


def _shared_by(
    qs: QuerySet[Any], identity_name: str, shared_by: str | None
) -> QuerySet[Any]:
    if shared_by is None:
        return qs

    return qs.filter(owner__name__in=(identity_name, shared_by))


def _prefer_own(models: list[BranchModel], identity_name: str) -> list[BranchModel]:
    own = {model.name for model in models if model.owner.name == identity_name}

    return [
        model
        for model in models
        if model.owner.name == identity_name or model.name not in own
    ]


def get_branch_spec(
    entity_name: EntityName,
    owner_name: str,
    branch_name: str | None = None,
    fingerprint: str | None = None,
    qs: QuerySet[Any] | None = None,
) -> BranchSpec[Any, Any]:
    """
    Get latest branch spec of `entity_name` owned by `owner_name` (aka canon).

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

    spec_cls = entity_of(entity_name).branch_spec

    try:
        return spec_cls.model_validate(model)
    except ValidationError as e:
        if settings.MODE == "dev":
            from chatddx.dx.error_handling import print_pydantic_errors

            print_pydantic_errors(e)
        raise


get_branch_async = make_async(get_branch_spec)


def select_branch_specs(
    entity_name: EntityName,
    owner_name: str,
    qs: QuerySet[Any] | None = None,
) -> list[BranchSpec[Any, Any]]:
    """
    Find all branch specs of `entity_name` directly owned by `owner_name`
    `qs`: Start from custom queryset (default: all)
    """

    models = select_branch_models(entity_name, owner_name, qs)
    spec_cls = entity_of(entity_name).branch_spec

    specs: list[BranchSpec[Any, Any]] = []
    for model in models:
        specs.append(spec_cls.model_validate(model))

    return specs


select_branch_async = make_async(select_branch_specs)


def commit(
    trail: TrailSchema | TrailModel,
    branch_details: BranchSchemaDetails,
) -> bool:
    """
    Embed trail in a branch and make it canon
    True: Canon changed
    False: Canon not changed, the trail was already canon in the branch

    A version is its trail and its details: what the branch says about the
    content without being part of it, such as a model's facts or a stack's
    endpoint. Resolution reads details, and a trial has to be able to say
    which version it resolved against, so a change to them makes a new
    version as a change to the trail does (new-datamodel.md §1). What the
    branch is related to, its tags and collaborators, is not read by
    resolution, and changes in place.
    """
    entity = entity_of(trail)
    branch_model_cls = entity.branch_model
    trail_model_cls = entity.trail_model

    # A caller that says nothing about what this kind of branch carries hands
    # over the base details; widening it to the entity's own leaves every
    # relation at None, which still means "inherit from the superseded
    # version", and every detail at its default. A caller that names
    # something the entity does not carry is rejected here rather than
    # ignored.
    branch_details = entity.branch_details.model_validate(branch_details.model_dump())
    details = dump_details(branch_details)

    qs = branch_model_cls.objects.all()

    canon = qs_canon(
        qs.filter(name=branch_details.name),
        branch_details.owner,
    ).first()

    if (
        canon
        and trail.fingerprint == canon.target.fingerprint
        and details == canon.details
    ):
        # What a branch is related to is not part of its version, so it can
        # change while the canon stays put.
        commit_relations(canon, canon, branch_details)
        _ = commit_closure(canon.target, branch_details.owner)
        return False

    match trail:
        case TrailSchema():
            target = dump_trail(trail_model_cls, trail)
        case TrailModel():
            target = trail

    branch_model = branch_model_cls.objects.create(
        name=branch_details.name,
        owner=ensure_identity(branch_details.owner),
        target=target,
        details=details,
    )

    commit_relations(branch_model, canon, branch_details)
    _ = commit_closure(target, branch_details.owner)

    return True


commit_async = make_async(commit)


def commit_closure(target: TrailModel, owner_name: str) -> list[str]:
    """
    Give every trail `target` reaches a branch of `owner_name`'s, and answer
    with the names of the ones that had to be made.

    A trail an owner holds only through another -- a stack's machine, a
    toolset's tools -- is as much in their possession as the one they named,
    and anything that offers to show or edit it needs a branch to say *which*
    one it is. So a commit is not finished until the closure of what it
    committed is committed too.

    Only a trail the owner has *no* branch of gets one. Where they already
    have one, which of their versions is canon and what it is called is
    theirs, and a save of something referencing it is not the place to
    revisit that.

    These branches are made on the owner's behalf rather than saved by them,
    so they carry nothing beside their content: no tags, no collaborators,
    and every detail at its default. A collaborator saving a shared
    configuration commits under the owner's name, and what the owner's
    version of an instruction is tagged with is not the collaborator's to
    write -- so it is dropped, silently and on purpose.
    """
    committed: list[str] = []

    for trail in trail_closure(target):
        entity = entity_of(trail)

        has_branch = entity.branch_model.objects.filter(
            target=trail,
            owner__name=owner_name,
        ).exists()

        if has_branch:
            # Skipped, not stepped over: what this trail reaches is still
            # walked, so an owner left holding a toolset whose tools have no
            # branches is repaired rather than kept out of reach.
            continue

        branch_name = resolve_branch_name(entity.name, trail.fingerprint)

        _ = commit(
            trail=trail,
            branch_details=BranchSchemaDetails(
                name=branch_name,
                owner=owner_name,
            ),
        )

        committed.append(branch_name)

    return committed


commit_closure_async = make_async(commit_closure)


def commit_copies(target: TrailModel, owner_name: str, source_name: str) -> list[str]:
    """
    Give every trail `target` reaches that `owner_name` has no branch of a
    copy of `source_name`'s branch of it, under its name and with its
    details, and answer with what was copied, as `entity name`.

    It goes before a commit of `target`, whose closure would otherwise give
    those trails branches under names of its own, with every detail at its
    default: a tool would lose what it runs. So a trail comes after what it
    reaches, which by then has a branch of the owner's. What `source_name`
    has no branch of, or holds under a name the owner already gives another
    trail, is left to that closure.
    """
    copied: list[str] = []

    for trail in _reached(target):
        entity = entity_of(trail)
        branches = entity.branch_model.objects.all()

        if branches.filter(target=trail, owner__name=owner_name).exists():
            continue

        source = qs_canon(branches.filter(target=trail), source_name).first()

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


def _reached(target: TrailModel) -> list[TrailModel]:
    """What `target` reaches, each trail after what it reaches in turn."""
    seen: set[tuple[Any, Any]] = set()
    reached: list[TrailModel] = []

    def visit(trail: TrailModel) -> None:
        for related in trail_relations(trail):
            key = (related._meta.concrete_model, related.pk)

            if key not in seen:
                seen.add(key)
                visit(related)
                reached.append(related)

    visit(target)
    return reached


# How a branch-details field turns each name it holds into the row that name
# stands for, keyed by the `relation` the field is tagged with; see
# `chatddx.repo.families.pydantic.RELATION`.
RELATION_RESOLVERS: dict[
    str,
    Callable[[IdentityModel, EntityName], Callable[[str], Model]],
] = {
    "identity": lambda owner, entity: ensure_identity,
    "tag": lambda owner, entity: lambda name: ensure_tag(owner, entity, name),
}


def commit_relations(
    branch_model: BranchModel,
    previous: BranchModel | None,
    branch_details: BranchSchemaDetails,
) -> None:
    """
    Give `branch_model` what `branch_details` names beside its content, and
    for everything it doesn't name, what the version it supersedes carried.

    None of this is part of the trail: collaborators and tags belong to the
    owner's version of the entity, not to its content, and every version
    keeps the set it was saved with.

    Which relations a branch has is the details model's to say -- every field
    it tags with a `relation` -- so an entity that carries something extra
    declares it there instead of being a special case here.
    """
    owner = branch_model.owner
    entity = entity_of(branch_model).name

    for field_name, resolver in relation_fields(type(branch_details)):
        _commit_relation(
            branch_model,
            previous,
            field_name,
            getattr(branch_details, field_name),
            RELATION_RESOLVERS[resolver](owner, entity),
        )


def _commit_relation(
    branch_model: BranchModel,
    previous: BranchModel | None,
    field_name: str,
    names: list[str] | None,
    resolve: Callable[[str], Model],
) -> None:
    if names is None:
        if previous is None or previous.pk == branch_model.pk:
            return
        related = list(getattr(previous, field_name).all())
    else:
        related = [resolve(name) for name in names]

    getattr(branch_model, field_name).set(related)
