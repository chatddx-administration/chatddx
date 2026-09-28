from typing import Literal, overload

from chatddx.repo.registry import *


class RegistryCollisionError(Exception):
    pass


ALL_ENTITIES: tuple[AnyEntity, ...] = (
    MACHINE,
    OS,
    LLM,
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


def _index_by_class(entities: tuple[AnyEntity, ...]) -> dict[type, AnyEntity]:
    index: dict[type, AnyEntity] = {}

    for entity in entities:
        for cls in entity.members():
            claimed = index.get(cls)

            if claimed is not None:
                raise RegistryCollisionError(
                    f"{cls.__qualname__} is claimed by two entities, "
                    + f"'{claimed.name}' and '{entity.name}'. A class belongs "
                    + "to exactly one, so that the class of a thing is "
                    + "enough to say which."
                )

            index[cls] = entity

    return index


_ENTITY_BY_NAME: dict[EntityName, AnyEntity] = {e.name: e for e in ALL_ENTITIES}
_ENTITY_BY_CLASS: dict[type, AnyEntity] = _index_by_class(ALL_ENTITIES)


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
    x: LLMMember | type[LLMMember] | Literal["llm"],
) -> LLMEntity: ...


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
    if isinstance(x, str):
        return _ENTITY_BY_NAME[x]

    entity = _by_mro(_ENTITY_BY_CLASS, x)

    if entity is None:
        cls = x if isinstance(x, type) else type(x)
        raise KeyError(f"No entity registered for {cls.__qualname__}")

    return entity
