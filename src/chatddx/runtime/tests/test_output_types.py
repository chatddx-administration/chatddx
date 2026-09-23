import json
from typing import Any

import pytest
from pydantic_ai import ModelProfile, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from chatddx.core.choices import ValidationChoices
from chatddx.repo.entities.agent.pydantic import AgentTrailSpec
from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.builder import ENVELOPE, build_agent, build_output_type, unwrap
from chatddx.runtime.context import AgentContext

pytestmark = pytest.mark.django_db(transaction=True)

# an agent whose output type is a ranked list of diagnoses
AGENT = "gpt-oss-20b diagnoses-tool seed-locked low-reasoning"


class Replies:
    """A model that answers with each value in turn, the way `mode` carries it."""

    def __init__(self, *values: Any):
        self.values: list[Any] = list(values)
        self.seen: list[AgentInfo] = []

    def __call__(self, messages: Any, info: AgentInfo) -> ModelResponse:
        _ = messages
        self.seen.append(info)
        value = {ENVELOPE: self.values.pop(0)}

        if info.output_tools:
            tool = info.output_tools[0].name
            return ModelResponse(parts=[ToolCallPart(tool, value)])

        return ModelResponse(parts=[TextPart(json.dumps(value))])

    def schema_shown(self) -> dict[str, Any]:
        info = self.seen[0]

        if info.output_tools:
            return info.output_tools[0].parameters_json_schema

        output_object = info.model_request_parameters.output_object
        assert output_object is not None
        return output_object.json_schema


async def run(spec: AgentTrailSpec, replies: Replies, mode: str = "tool") -> Any:
    output_type = build_output_type(spec)
    agent = build_agent(spec, output_type)

    model = FunctionModel(
        replies,
        profile=ModelProfile(
            default_structured_output_mode=mode,  # pyright: ignore[reportArgumentType]
            supports_json_schema_output=True,
        ),
    )

    with agent.override(model=model):
        result = await agent.run(
            "a case",
            deps=AgentContext(agent=spec, output_type=output_type),
        )

    return result.output


def with_output_type(spec: AgentTrailSpec, **changes: Any) -> AgentTrailSpec:
    return spec.model_copy(
        update={"output_type": spec.output_type.model_copy(update=changes)},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["tool", "native", "prompted"])
async def test_a_list_comes_back_as_the_list_whichever_mode_carries_it(
    inventory_fixture_bs: InventoryBranchSpec,
    mode: str,
):
    spec = inventory_fixture_bs.agent[AGENT].target
    replies = Replies(["pneumonia", "copd"])

    assert await run(spec, replies, mode) == ["pneumonia", "copd"]

    # and the model was shown the definition, items and all
    shown = replies.schema_shown()["properties"][ENVELOPE]
    assert shown["type"] == "array"
    assert shown["items"]["type"] == "string"


@pytest.mark.asyncio
async def test_a_list_that_breaks_its_definition_is_retried_when_asked_to_be(
    inventory_fixture_bs: InventoryBranchSpec,
):
    spec = with_output_type(
        inventory_fixture_bs.agent[AGENT].target,
        validation_strategy=ValidationChoices.RETRY,
    )
    replies = Replies([{"diagnosis": "copd"}], ["copd"])

    assert await run(spec, replies) == ["copd"]
    assert len(replies.seen) == 2


@pytest.mark.asyncio
async def test_a_list_that_breaks_its_definition_crashes_when_asked_to(
    inventory_fixture_bs: InventoryBranchSpec,
):
    spec = with_output_type(
        inventory_fixture_bs.agent[AGENT].target,
        validation_strategy=ValidationChoices.CRASH,
    )

    with pytest.raises(RuntimeError, match="Validation failed"):
        _ = await run(spec, Replies([1, 2]))


@pytest.mark.asyncio
async def test_a_list_informed_of_its_error_goes_on_unmarked(
    inventory_fixture_bs: InventoryBranchSpec,
):
    # nowhere in a list for an `__error__`, so the scorer's check catches it
    spec = with_output_type(
        inventory_fixture_bs.agent[AGENT].target,
        validation_strategy=ValidationChoices.INFORM,
    )

    assert await run(spec, Replies([1, 2])) == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "definition, value",
    [
        ({"type": "boolean"}, True),
        ({"type": "integer"}, 42),
        ({"type": "string", "enum": ["urgent", "routine"]}, "routine"),
        ({"type": ["string", "null"]}, None),
    ],
)
async def test_whatever_a_definition_names_is_what_comes_back(
    inventory_fixture_bs: InventoryBranchSpec,
    definition: dict[str, Any],
    value: Any,
):
    spec = with_output_type(
        inventory_fixture_bs.agent[AGENT].target,
        definition=definition,
    )

    assert await run(spec, Replies(value)) == value


def test_a_reply_is_unwrapped_where_its_output_was_asked_for_in_an_envelope():
    listing = {"type": "array", "items": {"type": "string"}}

    assert unwrap(listing, {ENVELOPE: ["copd"]}) == ["copd"]
    # an object is asked for as itself, even one with a field of that name
    assert unwrap({"type": "object"}, {ENVELOPE: ["copd"]}) == {ENVELOPE: ["copd"]}
    assert unwrap({}, "free text") == "free text"
