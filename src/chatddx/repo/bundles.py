from typing import Literal, cast, overload

from chatddx.repo.registry import *


class RegistryCollisionError(Exception):
    pass


# in commit order, as `EntityName` lists them
ALL_ENTITIES: tuple[AnyEntity, ...] = (
    MACHINE,
    OS,
    MODEL,
    SERVING,
    CLIENT,
    STACK,
    TOOL,
    TOOLSET,
    INSTRUCTION,
    OUTPUT,
    COERCION,
    REASONING,
    SAMPLING,
    CONFIGURATION,
    CASE,
    SCORER,
)

ALL_PRESENTATIONS: tuple[AnyPresentation, ...] = (
    MACHINE_PRESENTATION,
    OS_PRESENTATION,
    MODEL_PRESENTATION,
    SERVING_PRESENTATION,
    CLIENT_PRESENTATION,
    STACK_PRESENTATION,
    TOOL_PRESENTATION,
    TOOLSET_PRESENTATION,
    INSTRUCTION_PRESENTATION,
    OUTPUT_PRESENTATION,
    COERCION_PRESENTATION,
    REASONING_PRESENTATION,
    SAMPLING_PRESENTATION,
    CONFIGURATION_PRESENTATION,
    CASE_PRESENTATION,
    SCORER_PRESENTATION,
)


def _index_by_class[T: AnyEntity | AnyPresentation](
    owners: tuple[T, ...],
    members: str,
    label: str,
) -> dict[type, T]:
    index: dict[type, T] = {}

    for owner in owners:
        classes: tuple[type, ...] = getattr(owner, members)()

        for cls in classes:
            claimed = index.get(cls)

            if claimed is not None:
                raise RegistryCollisionError(
                    f"{cls.__qualname__} is claimed by two {label}s, "
                    + f"'{claimed.name}' and '{owner.name}'. A class belongs "
                    + "to exactly one, so that the class of a thing is "
                    + "enough to say which."
                )

            index[cls] = owner

    return index


_ENTITY_BY_NAME: dict[EntityName, AnyEntity] = {e.name: e for e in ALL_ENTITIES}
_ENTITY_BY_CLASS: dict[type, AnyEntity] = _index_by_class(
    ALL_ENTITIES, "members", "entity"
)

_PRESENTATION_BY_NAME: dict[PresentationName, AnyPresentation] = {
    v.name: v for v in ALL_PRESENTATIONS
}
_PRESENTATION_BY_CLASS: dict[type, AnyPresentation] = _index_by_class(
    ALL_PRESENTATIONS, "proxies", "presentation"
)


# Every entity is presented through a presentation of its own name, so an
# `EntityName` is always a `PresentationName`.
for _entity in ALL_ENTITIES:
    assert _entity.name in _PRESENTATION_BY_NAME, (
        f"'{_entity.name}' has no presentation of its name"
    )


def _by_mro[T](index: dict[type, T], x: object) -> T | None:
    cls = x if isinstance(x, type) else type(x)

    for ancestor in cls.__mro__:
        found = index.get(ancestor)
        if found is not None:
            return found

    return None


@overload
def entity_of(
    x: MachineMember | type[MachineMember] | Literal["machine"],
) -> MachineEntity: ...


@overload
def entity_of(
    x: OsMember | type[OsMember] | Literal["os"],
) -> OsEntity: ...


@overload
def entity_of(
    x: ModelMember | type[ModelMember] | Literal["model"],
) -> ModelEntity: ...


@overload
def entity_of(
    x: ServingMember | type[ServingMember] | Literal["serving"],
) -> ServingEntity: ...


@overload
def entity_of(
    x: ClientMember | type[ClientMember] | Literal["client"],
) -> ClientEntity: ...


@overload
def entity_of(
    x: StackMember | type[StackMember] | Literal["stack"],
) -> StackEntity: ...


@overload
def entity_of(
    x: ToolMember | type[ToolMember] | Literal["tool"],
) -> ToolEntity: ...


@overload
def entity_of(
    x: ToolsetMember | type[ToolsetMember] | Literal["toolset"],
) -> ToolsetEntity: ...


@overload
def entity_of(
    x: InstructionMember | type[InstructionMember] | Literal["instruction"],
) -> InstructionEntity: ...


@overload
def entity_of(
    x: OutputMember | type[OutputMember] | Literal["output"],
) -> OutputEntity: ...


@overload
def entity_of(
    x: CoercionMember | type[CoercionMember] | Literal["coercion"],
) -> CoercionEntity: ...


@overload
def entity_of(
    x: ReasoningMember | type[ReasoningMember] | Literal["reasoning"],
) -> ReasoningEntity: ...


@overload
def entity_of(
    x: SamplingMember | type[SamplingMember] | Literal["sampling"],
) -> SamplingEntity: ...


@overload
def entity_of(
    x: ConfigurationMember | type[ConfigurationMember] | Literal["configuration"],
) -> ConfigurationEntity: ...


@overload
def entity_of(
    x: CaseMember | type[CaseMember] | Literal["case"],
) -> CaseEntity: ...


@overload
def entity_of(
    x: ScorerMember | type[ScorerMember] | Literal["scorer"],
) -> ScorerEntity: ...


@overload
def entity_of(
    x: AnyEntityMember | type[AnyEntityMember] | EntityName,
) -> AnyEntity: ...


def entity_of(
    x: AnyEntityMember | type[AnyEntityMember] | EntityName,
) -> AnyEntity:
    """
    The entity a name, class or instance belongs to.

    A proxy resolves through its branch model, so `entity_of(Configuration(...))`
    and `entity_of(SharedConfiguration(...))` both answer `configuration`.
    """
    if isinstance(x, str):
        return _ENTITY_BY_NAME[x]

    entity = _by_mro(_ENTITY_BY_CLASS, x)

    if entity is None:
        cls = x if isinstance(x, type) else type(x)
        raise KeyError(f"No entity registered for {cls.__qualname__}")

    return entity


def presentation_of(
    x: BranchProxy
    | AnyEntityMember
    | type[BranchProxy | AnyEntityMember]
    | PresentationName,
) -> AnyPresentation:
    """
    The presentation a name, proxy or branch is rendered through.

    Every entity has a presentation of its own name, so an `EntityName` is a
    `PresentationName` and reaches the entity's presentation. A proxy is
    rendered through the presentation that registered it, and anything else
    through its entity's.
    """
    if isinstance(x, str):
        return _PRESENTATION_BY_NAME[x]

    presentation = _by_mro(_PRESENTATION_BY_CLASS, x)

    if presentation is not None:
        return presentation

    # not a registered proxy, so it is an entity class and has a presentation
    return _PRESENTATION_BY_NAME[entity_of(cast(AnyEntityMember, x)).name]
