"""
Which entity a class belongs to, and which view a proxy is rendered through.

Both indexes are built with a collision check rather than a precedence rule:
once views are not entities, no class belongs to two entities, so there is
nothing left for declaration order to decide.
"""

from typing import cast, overload

from chatddx.repo.registry import *


class RegistryCollisionError(Exception):
    pass


ALL_ENTITIES: tuple[AnyEntity, ...] = (
    AGENT,
    CONNECTION,
    SAMPLING_PARAMS,
    OUTPUT_TYPE,
    TOOL,
    TOOL_GROUP,
    SCORER,
    EXPECT,
    CASE,
)

ALL_VIEWS: tuple[AnyView, ...] = (
    AGENT_VIEW,
    SUPER_AGENT_VIEW,
    CONNECTION_VIEW,
    SAMPLING_PARAMS_VIEW,
    OUTPUT_TYPE_VIEW,
    TOOL_VIEW,
    TOOL_GROUP_VIEW,
    SCORER_VIEW,
    EXPECT_VIEW,
    CASE_VIEW,
)


def _index_by_class[T: AnyEntity | AnyView](
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
_ENTITY_BY_CLASS: dict[type, AnyEntity] = _index_by_class(ALL_ENTITIES, "members", "entity")

_VIEW_BY_NAME: dict[ViewName, AnyView] = {v.name: v for v in ALL_VIEWS}
_VIEW_BY_CLASS: dict[type, AnyView] = _index_by_class(ALL_VIEWS, "proxies", "view")


# Every entity is presented through a view of its own name, so an
# `EntityName` is always a `ViewName`.
for _entity in ALL_ENTITIES:
    assert _entity.name in _VIEW_BY_NAME, f"'{_entity.name}' has no view of its name"


def _by_mro[T](index: dict[type, T], x: object) -> T | None:
    cls = x if isinstance(x, type) else type(x)

    for ancestor in cls.__mro__:
        found = index.get(ancestor)
        if found is not None:
            return found

    return None


@overload
def entity_of(
    x: AgentMember | type[AgentMember] | Literal["agent"],
) -> AgentEntity: ...


@overload
def entity_of(
    x: ConnectionMember | type[ConnectionMember] | Literal["connection"],
) -> ConnectionEntity: ...


@overload
def entity_of(
    x: SamplingParamsMember | type[SamplingParamsMember] | Literal["sampling_params"],
) -> SamplingParamsEntity: ...


@overload
def entity_of(
    x: OutputTypeMember | type[OutputTypeMember] | Literal["output_type"],
) -> OutputTypeEntity: ...


@overload
def entity_of(
    x: ToolMember | type[ToolMember] | Literal["tool"],
) -> ToolEntity: ...


@overload
def entity_of(
    x: ToolGroupMember | type[ToolGroupMember] | Literal["tool_group"],
) -> ToolGroupEntity: ...


@overload
def entity_of(
    x: ScorerMember | type[ScorerMember] | Literal["scorer"],
) -> ScorerEntity: ...


@overload
def entity_of(
    x: ExpectMember | type[ExpectMember] | Literal["expect"],
) -> ExpectEntity: ...


@overload
def entity_of(
    x: CaseMember | type[CaseMember] | Literal["case"],
) -> CaseEntity: ...


@overload
def entity_of(
    x: AnyEntityMember | type[AnyEntityMember] | EntityName,
) -> AnyEntity: ...


def entity_of(
    x: AnyEntityMember | type[AnyEntityMember] | EntityName,
) -> AnyEntity:
    """
    The entity a name, class or instance belongs to.

    A proxy resolves through its branch model, so `entity_of(SuperAgent(...))`
    and `entity_of(SharedSuperAgent(...))` both answer `agent`.
    """
    if isinstance(x, str):
        return _ENTITY_BY_NAME[x]

    entity = _by_mro(_ENTITY_BY_CLASS, x)

    if entity is None:
        cls = x if isinstance(x, type) else type(x)
        raise KeyError(f"No entity registered for {cls.__qualname__}")

    return entity


def view_of(
    x: BranchProxy | AnyEntityMember | type[BranchProxy | AnyEntityMember] | ViewName,
) -> AnyView:
    """
    The view a name, proxy or branch is rendered through.

    Every entity has a view of its own name, so an `EntityName` is a
    `ViewName` and reaches the entity's default view. A proxy is rendered
    through the view that registered it -- which is how `SuperAgent` gets
    the flat agent form while a plain `AgentBranchModel` gets the default
    one -- and anything else falls back to its entity's default view.
    """
    if isinstance(x, str):
        return _VIEW_BY_NAME[x]

    view = _by_mro(_VIEW_BY_CLASS, x)

    if view is not None:
        return view

    # not a registered proxy, so it is an entity class and has a default view
    return _VIEW_BY_NAME[entity_of(cast(AnyEntityMember, x)).name]
