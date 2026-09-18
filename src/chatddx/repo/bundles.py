from typing import overload

from chatddx.repo.registry import *

# bundle_of searches this from first to last and picks first match
ALL_BUNDLES: tuple[AnyBundle, ...] = (
    AGENT,
    CONNECTION,
    SAMPLING_PARAMS,
    OUTPUT_TYPE,
    TOOL,
    TOOL_GROUP,
    CASE,
    SCORER,
    EXPECT,
    SUPER_AGENT,
)
_BY_NAME: dict[EntityName, AnyBundle] = {b.name: b for b in ALL_BUNDLES}

_BY_CLASS: dict[type, AnyBundle] = {}
for b in ALL_BUNDLES:
    for cls in b.members():
        _ = _BY_CLASS.setdefault(cls, b)


@overload
def bundle_of(
    x: AgentMember | type[AgentMember] | Literal["agent"],
) -> AgentBundle: ...


@overload
def bundle_of(
    x: ConnectionMember | type[ConnectionMember] | Literal["connection"],
) -> ConnectionBundle: ...


@overload
def bundle_of(
    x: SamplingParamsMember | type[SamplingParamsMember] | Literal["sampling_params"],
) -> SamplingParamsBundle: ...


@overload
def bundle_of(
    x: OutputTypeMember | type[OutputTypeMember] | Literal["output_type"],
) -> OutputTypeBundle: ...


@overload
def bundle_of(
    x: ToolMember | type[ToolMember] | Literal["tool"],
) -> ToolBundle: ...


@overload
def bundle_of(
    x: ToolGroupMember | type[ToolGroupMember] | Literal["tool_group"],
) -> ToolGroupBundle: ...


@overload
def bundle_of(
    x: AnyMember | type[AnyMember] | EntityName,
) -> AnyBundle: ...


def bundle_of(
    x: AnyMember | type[AnyMember] | EntityName,
) -> AnyBundle:
    if isinstance(x, str):
        return _BY_NAME[x]

    cls = x if isinstance(x, type) else type(x)
    return next(_BY_CLASS[k] for k in cls.__mro__ if k in _BY_CLASS)
