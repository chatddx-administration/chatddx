from collections.abc import Callable

from django.db.models import Model, QuerySet
from pydantic import ValidationError

from chatddx.core import settings
from chatddx.core.utils import ensure_identity, ensure_tag
from chatddx.django.orm.qs import qs_canon
from chatddx.repo.bundles import bundle_of
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.families.django import BranchModel, TrailModel
from chatddx.repo.families.pydantic import (
    BranchSchemaDetails,
    BranchSpec,
    TrailSchema,
    TrailSpec,
)
from chatddx.repo.registry import EntityName
from chatddx.repo.shufflers.trail import dump_trail
from chatddx.repo.utils import resolve_trail
from chatddx.utils import make_async


class BranchNotFoundError(Exception):
    pass


def get_branch_model(
    entity_name: EntityName,
    owner_name: str,
    branch_name: str | None = None,
    fingerprint: str | None = None,
    qs: QuerySet[BranchModel] | None = None,
) -> BranchModel:
    """
    Get latest branch model of `entity_name` owned by `owner_name` (aka canon).

    `branch_name`: Choose which name to select from
    `fingerprint`: Look-up the branch by it's trail's fingerprint
    `qs`: Start from custom queryset (default: all)
    """

    assert branch_name or fingerprint

    if not qs:
        model_cls = bundle_of(entity_name).branch_model
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
    qs: QuerySet[BranchModel] | None = None,
) -> list[BranchModel]:
    """
    Find all branch models of `entity_name` directly owned by `owner_name`
    `qs`: Start from custom queryset (default: all)
    """
    if qs is None:
        model_cls = bundle_of(entity_name).branch_model
        qs = qs_canon(
            model_cls.objects.all(),
            owner_name,
        )

    models: list[BranchModel] = []
    for model in qs:
        model.target = resolve_trail(model.target)
        models.append(model)

    return models


def get_branch_spec(
    entity_name: EntityName,
    owner_name: str,
    branch_name: str | None = None,
    fingerprint: str | None = None,
    qs: QuerySet[BranchModel] | None = None,
) -> BranchSpec[TrailSpec]:
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

    spec_cls = bundle_of(entity_name).branch_spec

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
    qs: QuerySet[BranchModel] | None = None,
) -> list[BranchSpec[TrailSpec]]:
    """
    Find all branch specs of `entity_name` directly owned by `owner_name`
    `qs`: Start from custom queryset (default: all)
    """

    models = select_branch_models(entity_name, owner_name, qs)
    spec_cls = bundle_of(entity_name).branch_spec

    specs: list[BranchSpec[TrailSpec]] = []
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
    """
    branch_model_cls = bundle_of(trail).branch_model
    trail_model_cls = bundle_of(trail).trail_model

    qs = branch_model_cls.objects.all()

    canon = qs_canon(
        qs.filter(name=branch_details.name),
        branch_details.owner,
    ).first()

    if canon and trail.fingerprint == canon.target.fingerprint:
        # What a branch carries besides its content is not fingerprinted, so
        # it can change while the canon stays put.
        commit_relations(canon, canon, branch_details)
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
    )

    commit_relations(branch_model, canon, branch_details)

    return True


commit_async = make_async(commit)


def commit_relations(
    branch_model: BranchModel,
    previous: BranchModel | None,
    branch_details: BranchSchemaDetails,
) -> None:
    """
    Give `branch_model` what `branch_details` names beside its content, and
    for everything it doesn't name, what the version it supersedes carried.

    None of this is part of the trail: collaborators, tags and a case's
    expects belong to the owner's version of the entity, not to its payload,
    and every version keeps the set it was saved with.
    """
    owner = branch_model.owner
    entity = bundle_of(branch_model).name

    _commit_relation(
        branch_model,
        previous,
        "collaborators",
        branch_details.collaborators,
        ensure_identity,
    )

    _commit_relation(
        branch_model,
        previous,
        "tags",
        branch_details.tags,
        lambda name: ensure_tag(owner, entity, name),
    )

    if isinstance(branch_model, CaseBranchModel):
        _commit_relation(
            branch_model,
            previous,
            "expects",
            branch_details.expects,
            lambda name: get_branch_model(
                entity_name="expect",
                owner_name=owner.name,
                branch_name=name,
            ),
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
