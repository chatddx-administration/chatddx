# src/chatddx/repo/shufflers/main.py
from collections import defaultdict
from pathlib import Path
from typing import Any, cast, get_args

from django.db.models import (
    Count,
    F,
    ForeignKey,
    OneToOneField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)

from chatddx.core.django_fields import RelatedArrayField
from chatddx.core.models import IdentityModel
from chatddx.registry.main import parse_registry
from chatddx.repo.base import (
    BaseFormDataOut,
    BranchModel,
    BranchSpec,
    TrailModel,
    TrailSchema,
    TrailSpec,
)
from chatddx.repo.branch_models import BranchModelRegistry, OutputTypeBranchModel
from chatddx.repo.form_data_out import TemplateData
from chatddx.repo.main import BundleName, Repo
from chatddx.repo.trail_schemas import TrailRegistry
from chatddx.utils import ListOf, OneOf, make_async, one_or_list_of

agent_relations: list[BundleName] = [
    "connection",
    "sampling_params",
    "output_type",
    "tool_group",
]


def ensure_identity(name: str) -> IdentityModel:
    owner, _ = IdentityModel.objects.get_or_create(name=name)
    return owner


ensure_identity_async = make_async(ensure_identity)


def qs_super_agent[T: TrailModel](qs: QuerySet[T], owner_name: str):
    def subquery(owner_name: str, model: str, column: str):
        branch_model_cls = Repo(model, BranchModel)

        return branch_model_cls.objects.filter(
            target=OuterRef(f"target__{model}"),
            owner__name=owner_name,
        ).values(column)[:1]

    branch_annotations = {
        f"{model}_{field}": Subquery(subquery(owner_name, model, field))
        for field in ("name", "id")
        for model in agent_relations
    }
    return qs.select_related(
        *[f"target__{model}" for model in agent_relations]
    ).annotate(**branch_annotations)


def qs_owned_trails[T: TrailModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return (
        qs.filter(branches__owner__name=owner_name)
        .annotate(branch_name=F("branches__name"))
        .order_by("id")
        .distinct("id")
    )


def qs_canon[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    owned_qs = qs.filter(owner__name=owner_name)

    count_subquery = (
        qs.filter(owner_id=OuterRef("owner_id"), name=OuterRef("name"))
        .values("owner_id", "name")
        .annotate(total=Count("id"))
        .values("total")
    )

    canonical_ids = (
        owned_qs.order_by("owner_id", "name", "-timestamp")
        .distinct("owner_id", "name")
        .values_list("id", flat=True)
    )

    return (
        owned_qs.filter(id__in=canonical_ids)
        .annotate(_version_count=Subquery(count_subquery))
        .order_by("-timestamp")
    )


def qs_canon_col[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    owned_qs = qs.filter(Q(owner__name=owner_name) | Q(collaborators__name=owner_name))

    count_subquery = (
        qs.filter(owner_id=OuterRef("owner_id"), name=OuterRef("name"))
        .values("owner_id", "name")
        .annotate(total=Count("id"))
        .values("total")
    )

    canonical_ids = (
        owned_qs.order_by("owner_id", "name", "-timestamp")
        .distinct("owner_id", "name")
        .values_list("id", flat=True)
    )

    return (
        owned_qs.filter(id__in=canonical_ids)
        .annotate(_version_count=Subquery(count_subquery))
        .order_by("-timestamp")
    )


def qs_owned[T: BranchModel](qs: QuerySet[T], owner_name: str) -> QuerySet[T]:
    return qs.filter(owner__name=owner_name)


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


def load_template_data(owner_name: str):

    payload: dict[BundleName, dict[str, BaseFormDataOut]] = defaultdict(dict)

    for bundle in get_args(BundleName):
        form_data_cls = Repo(bundle, BaseFormDataOut)
        branch_specs = load_branches(bundle, owner_name)

        for branch_spec in branch_specs:
            branch_dict = branch_spec.model_dump()
            form_data = branch_dict | branch_dict["target"]
            payload[bundle][str(form_data["id"])] = form_data_cls.model_validate(
                form_data
            )

    return TemplateData.model_validate(payload)


def load_form_data(
    branch: BranchModel | BranchSpec,
) -> BaseFormDataOut:

    match branch:
        case BranchModel():
            branch.target = resolve_related_array_fields(branch.target)
            branch_spec = Repo(branch, BranchSpec).model_validate(branch)
        case BranchSpec():
            branch_spec = branch

    branch_dict = branch_spec.model_dump()
    form_data = Repo(branch, BaseFormDataOut).model_validate(
        branch_dict | branch_dict["target"]
    )
    return form_data


dump_trail_registry_async = make_async(dump_trail_registry)


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


def load_branch(
    bundle_name: str,
    owner_name: str,
    branch_name: str | None = None,
    trail: TrailModel | TrailSchema | None = None,
    qs: QuerySet | None = None,
) -> BranchSpec[TrailSpec] | None:
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


def load_trail[T: (TrailSpec, TrailModel)](
    bundle: Any,
    fingerprint: str,
    as_schema: type[T],
) -> T:
    trail_model_cls = Repo(bundle, TrailModel)
    trail_model = trail_model_cls.objects.get(fingerprint=fingerprint)

    trail_model = resolve_related_array_fields(trail_model)

    if as_schema == TrailModel:
        return cast(T, trail_model)

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


def resolve_related_array_fields(model: TrailModel):
    for field in model._meta.concrete_fields:
        if isinstance(field, RelatedArrayField):
            value = getattr(model, field.name)

            if not value:
                setattr(model, field.name, [])
                continue

            queryset = field.associated_model.objects.filter(pk__in=value)
            resolved_value = list(queryset)

            for obj in resolved_value:
                _ = resolve_related_array_fields(obj)

            setattr(model, field.name, resolved_value)

        elif isinstance(field, (ForeignKey, OneToOneField)):
            associated_model = getattr(model, field.name, None)
            if associated_model is not None:
                _ = resolve_related_array_fields(associated_model)

    return model


resolve_related_array_fields_async = make_async(resolve_related_array_fields)
