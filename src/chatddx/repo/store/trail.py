from typing import Any

from django.db import transaction

from chatddx.repo.bundles import entity_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import TrailModel
from chatddx.repo.families.pydantic import TrailIn, TrailOut
from chatddx.repo.utils import resolve_trail
from chatddx.utils import make_async


def load_trail(
    bundle: EntityName,
    fingerprint: str,
    as_schema: type[TrailModel] | type[TrailOut],
) -> TrailModel | TrailOut:
    trail_model_cls = entity_of(bundle).trail_model
    trail_model = trail_model_cls.objects.get(fingerprint=fingerprint)

    trail_model = resolve_trail(trail_model)

    if issubclass(as_schema, TrailModel):
        return trail_model

    return as_schema.model_validate(trail_model)


load_trail_async = make_async(load_trail)


def dump_trail[T: TrailModel](
    model_cls: type[T],
    schema: TrailIn,
) -> T:
    new_values: dict[str, Any] = {}
    m2m_values: dict[str, list[Any]] = {}

    for field_name, field_value in schema:
        field = model_cls._meta.get_field(field_name)
        associated_model = (
            getattr(field, "associated_model", None) or field.related_model
        )

        # sibling in src/chatddx/repo/families/pydantic.py
        match field_value:
            case TrailIn() if associated_model:
                new_values[field.attname] = dump_trail(
                    associated_model,
                    field_value,
                ).pk

            case [*values] if associated_model and all(
                isinstance(value, TrailIn) for value in values
            ):
                pks = [dump_trail(associated_model, value).pk for value in values]

                if field.many_to_many:
                    m2m_values[field_name] = pks
                else:
                    new_values[field_name] = pks

            case _:
                new_values[field_name] = field_value

    with transaction.atomic():
        model, created = model_cls.objects.get_or_create(
            fingerprint=schema.fingerprint,
            defaults=new_values,
        )

        if created:
            for field_name, pks in m2m_values.items():
                getattr(model, field_name).set(pks)

    return model


dump_trail_async = make_async(dump_trail)
