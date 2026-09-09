# src/chatddx/repo/shufflers/main.py
from pathlib import Path
from typing import Any, Literal, overload

from django.db.models import QuerySet

from chatddx.core.django_fields import resolve_related_array_fields
from chatddx.core.models import IdentityModel
from chatddx.django.orm.qs import qs_canon
from chatddx.registry.main import parse_registry
from chatddx.repo.base import (
    BranchModel,
    BranchSpec,
    TrailModel,
    TrailSchema,
    TrailSpec,
)
from chatddx.repo.branch_models import BranchModelRegistry
from chatddx.repo.main import BundleName, Repo
from chatddx.repo.trail_schemas import CaseSchema, TrailRegistry
from chatddx.repo.trail_specs import (
    AgentSpec,
    CaseSpec,
    ConnectionSpec,
    OutputTypeSpec,
    SamplingParamsSpec,
    ToolGroupSpec,
    ToolSpec,
)
from chatddx.utils import ListOf, OneOf, make_async, one_or_list_of


def ensure_identity(name: str) -> IdentityModel:
    owner, _ = IdentityModel.objects.get_or_create(name=name)
    return owner


ensure_identity_async = make_async(ensure_identity)


def dump_trail_registry(registry_path: Path, owner_name: str):
    registry = parse_registry(
        path=registry_path,
        schema=TrailRegistry,
    )

    dumped_registry: BranchModelRegistry = {}

    for bundle_name, record in registry:
        dumped_registry[bundle_name] = {}

        for branch_name, schema in record.items():
            branch_model, _ = dump_branch(
                bundle_name=bundle_name,
                branch_name=branch_name,
                owner_name=owner_name,
                trail=schema,
            )

            dumped_registry[bundle_name][branch_model.pk] = branch_model

    return dumped_registry


dump_trail_registry_async = make_async(dump_trail_registry)


def dump_cases(cases_dir: Path, owner_name: str) -> dict[int, BranchModel]:
    dumped_cases: dict[int, BranchModel] = {}

    for case_path in sorted(cases_dir.iterdir()):
        if not case_path.is_file():
            continue

        payload = case_path.read_text(encoding="utf-8").rstrip("\n")

        branch_model, _ = dump_branch(
            bundle_name="case",
            branch_name=case_path.stem,
            owner_name=owner_name,
            trail=CaseSchema(payload=payload),
        )

        dumped_cases[branch_model.pk] = branch_model

    return dumped_cases


dump_cases_async = make_async(dump_cases)


def load_agents(
    owner_name: str,
    output_type: str | None = None,
):

    model_cls = Repo("agent", BranchModel)
    qs = qs_canon(model_cls.objects.all(), owner_name)

    qs = qs.filter(target__output_type__definition__title=output_type)

    return load_branches(
        bundle_name="agent",
        owner_name=owner_name,
        qs=qs,
    )


load_agents_async = make_async(load_agents)


def load_branches(
    bundle_name: str,
    owner_name: str,
    qs: QuerySet | None = None,
) -> list[BranchSpec[TrailSpec]]:
    if qs is None:
        model_cls = Repo(bundle_name, BranchModel)
        qs = qs_canon(
            model_cls.objects.all(),
            owner_name,
        )

    spec_cls = Repo(bundle_name, BranchSpec)

    specs: list[BranchSpec[TrailSpec]] = []
    for model in qs:
        model.target = resolve_related_array_fields(model.target)
        specs.append(spec_cls.model_validate(model))

    return specs


def load_agent(
    owner_name: str,
    branch_name: str,
    output_type: str | None = None,
):
    model_cls = Repo("agent", BranchModel)
    qs = model_cls.objects.all()
    if output_type:
        qs = qs.filter(target__output_type__fingerprint=output_type)

    return load_branch(
        bundle_name="agent",
        owner_name=owner_name,
        qs=qs,
    )


load_agent_async = make_async(load_agent)


# `bundle_name` picks the concrete Trail*Spec at runtime via `Repo()`, which
# pyright can't see through; these overloads let callers that pass a literal
# bundle name (the common case) get the narrowed `target` type back instead
# of the base `TrailSpec`.
@overload
def load_branch(
    bundle_name: Literal["agent"],
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[AgentSpec] | None: ...
@overload
def load_branch(
    bundle_name: Literal["connection"],
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[ConnectionSpec] | None: ...
@overload
def load_branch(
    bundle_name: Literal["sampling_params"],
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[SamplingParamsSpec] | None: ...
@overload
def load_branch(
    bundle_name: Literal["output_type"],
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[OutputTypeSpec] | None: ...
@overload
def load_branch(
    bundle_name: Literal["tool_group"],
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[ToolGroupSpec] | None: ...
@overload
def load_branch(
    bundle_name: Literal["tool"],
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[ToolSpec] | None: ...
@overload
def load_branch(
    bundle_name: Literal["case"],
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[CaseSpec] | None: ...
def load_branch(
    bundle_name: BundleName,
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> (
    BranchSpec[AgentSpec]
    | BranchSpec[ConnectionSpec]
    | BranchSpec[SamplingParamsSpec]
    | BranchSpec[OutputTypeSpec]
    | BranchSpec[ToolGroupSpec]
    | BranchSpec[ToolSpec]
    | BranchSpec[CaseSpec]
    | None
):
    spec_cls = Repo(bundle_name, BranchSpec)

    if qs is None:
        model_cls = Repo(bundle_name, BranchModel)
        qs = model_cls.objects.all()

    if trail:
        qs = qs.filter(target__fingerprint=trail.fingerprint)
    if branch_name:
        qs = qs.filter(name=branch_name)

    qs = qs_canon(qs, owner_name)

    if (branch := qs.first()) is None:
        return branch

    branch.target = resolve_related_array_fields(branch.target)

    return spec_cls.model_validate(branch)


load_branch_async = make_async(load_branch)


def dump_branch(
    bundle_name: str,
    branch_name: str,
    owner_name: str,
    trail: TrailSchema | TrailModel,
) -> tuple[BranchModel, bool]:
    branch_model_cls = Repo(bundle_name, BranchModel)
    trail_model_cls = Repo(bundle_name, TrailModel)

    owner = ensure_identity(owner_name)

    canon = qs_canon(
        branch_model_cls.objects.filter(name=branch_name),
        owner.name,
    ).first()

    if canon and trail.fingerprint == canon.target.fingerprint:
        return canon, False

    match trail:
        case TrailSchema():
            trail_model = dump_trail(trail_model_cls, trail)
        case TrailModel():
            trail_model = trail

    branch_instance = branch_model_cls(
        target_id=trail_model.pk,
        owner=owner,
        name=branch_name,
    )

    branch_instance.save()

    return branch_instance, True


dump_branch_async = make_async(dump_branch)


@overload
def load_trail(
    bundle: Any,
    fingerprint: str,
    as_schema: type[TrailModel],
) -> TrailModel: ...
@overload
def load_trail[T: TrailSpec](
    bundle: Any,
    fingerprint: str,
    as_schema: type[T],
) -> T: ...
def load_trail(
    bundle: Any,
    fingerprint: str,
    as_schema: type[TrailModel] | type[TrailSpec],
) -> TrailModel | TrailSpec:
    trail_model_cls = Repo(bundle, TrailModel)
    trail_model = trail_model_cls.objects.get(fingerprint=fingerprint)

    trail_model = resolve_related_array_fields(trail_model)

    if issubclass(as_schema, TrailModel):
        return trail_model

    return as_schema.model_validate(trail_model)


load_trail_async = make_async(load_trail)


def dump_trail[T: TrailModel](
    model_cls: type[T],
    schema: TrailSchema,
) -> T:
    new_values: dict[str, Any] = {}

    for field_name, field_value in schema:
        field = model_cls._meta.get_field(field_name)
        associated_model = (
            getattr(field, "associated_model", None) or field.related_model
        )

        match one_or_list_of(TrailSchema, field_value):
            case OneOf(value) if associated_model:
                new_values[field_name + "_id"] = dump_trail(
                    associated_model,
                    value,
                ).pk

            case ListOf(values) if associated_model:
                new_values[field_name] = [
                    dump_trail(
                        associated_model,
                        value,
                    ).pk
                    for value in values
                ]

            case _:
                new_values[field_name] = field_value

    model, _ = model_cls.objects.get_or_create(
        fingerprint=schema.fingerprint,
        defaults=new_values,
    )

    return model


dump_trail_async = make_async(dump_trail)
