from typing import Any

import pytest

from chatddx.core import settings
from chatddx.repo.entities.coercion.pydantic import CoercionTrailSchema
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailSchema
from chatddx.repo.entities.instruction.pydantic import InstructionTrailSchema
from chatddx.repo.entities.model.pydantic import ModelFacts
from chatddx.repo.entities.output.pydantic import OutputTrailSchema
from chatddx.repo.entities.reasoning.pydantic import ReasoningTrailSchema
from chatddx.repo.entities.sampling.pydantic import SamplingTrailSchema
from chatddx.repo.entities.serving.pydantic import ServingTrailSchema
from chatddx.repo.entities.stack.pydantic import StackDetails
from chatddx.repo.entities.tool.pydantic import ToolTrailSchema
from chatddx.repo.entities.toolset.pydantic import ToolsetTrailSchema
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.parsers.inventory import parse
from chatddx.runtime.resolution import (
    CellRefused,
    SliceRefusal,
    Slices,
    realize,
    resolve,
)

ENGINE = "/nix/store/5nxjf9n4gzgajv67rd4fb1kdssql7g51-python3.13-vllm-0.13.0"

FACTS = ModelFacts.model_validate(
    {
        "reasoning": {
            "default": "on",
            "off": {"chat_template_kwargs": {"enable_thinking": False}},
            "on": {"chat_template_kwargs": {"enable_thinking": True}},
            "high": "on",
            "low": {"refused": "no effort levels"},
            "xhigh": "low",
            "budget": {"field": "thinking_token_budget", "needs": "reasoning_parser"},
        },
        "sampling": {
            "recommended": {
                "on": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
                "off": {"temperature": 0.7, "top_p": 0.8, "top_k": 20},
            },
            "generation_config": {"temperature": 0.6, "top_p": 0.95},
        },
        "profile": {"supports_json_schema_output": True},
    }
)

STACK = StackDetails.model_validate(
    {
        "endpoint": "http://gpu:8000/v1/",
        "served_name": "Qwen/Qwen3-8B-AWQ",
        "api": "vllm",
    }
)

SERVING = ServingTrailSchema(engine=ENGINE, args={"reasoning-parser": "qwen3"})

INSTRUCTION = InstructionTrailSchema(
    system="{{output_guidance}}{{#if schema_prompt}}\n{{schema_prompt}}{{/if}}",
    user="{{case}}",
    variables=["case", "output_guidance", "schema_prompt"],
)


def cell(**slices: Any) -> ConfigurationTrailSchema:
    return ConfigurationTrailSchema.model_validate(
        {
            "instruction": INSTRUCTION,
            "output": OutputTrailSchema(guidance="List the diagnoses."),
            "coercion": CoercionTrailSchema(mode="auto"),
            "reasoning": ReasoningTrailSchema(effort="default"),
            "sampling": SamplingTrailSchema(defaults="recommended"),
        }
        | slices
    )


def refusals(
    configuration: ConfigurationTrailSchema, **kwargs: Any
) -> list[SliceRefusal]:
    with pytest.raises(CellRefused) as refused:
        _ = resolve(
            configuration,
            kwargs.get("stack", STACK),
            kwargs.get("facts", FACTS),
            kwargs.get("serving", SERVING),
        )

    return refused.value.refusals


# ------------------------------------------------------------------ realized


def test_a_cell_resolves_to_what_the_facts_write():
    resolution = resolve(cell(), STACK, FACTS, SERVING)

    assert resolution.endpoint == "http://gpu:8000/v1/"
    assert resolution.served_name == "Qwen/Qwen3-8B-AWQ"
    assert resolution.profile == {"supports_json_schema_output": True}

    # the model's own effort, and its recommendation for the mode it is
    assert resolution.reasoning.effort == "default"
    assert resolution.reasoning.intent == "on"
    assert resolution.sampling.source == "recommended for 'on'"
    assert resolution.fields == {
        "chat_template_kwargs": {"enable_thinking": True},
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
    }


def test_the_case_is_placed_when_a_trial_renders_the_cell():
    resolution = resolve(cell(), STACK, FACTS, SERVING)

    # an unfilled slot the instruction branches on is left out
    assert resolution.render("a cough") == ("List the diagnoses.", "a cough")


def test_an_effort_collapses_into_the_intent_the_facts_name():
    resolution = resolve(
        cell(reasoning=ReasoningTrailSchema(effort="high")), STACK, FACTS, SERVING
    )

    assert (resolution.reasoning.effort, resolution.reasoning.intent) == ("high", "on")
    assert resolution.reasoning.writes == {
        "chat_template_kwargs": {"enable_thinking": True}
    }


def test_recommended_sampling_follows_the_mode_reasoning_resolves_to():
    resolution = resolve(
        cell(reasoning=ReasoningTrailSchema(effort="off")), STACK, FACTS, SERVING
    )

    assert resolution.sampling.source == "recommended for 'off'"
    assert resolution.sampling.writes == {"temperature": 0.7, "top_p": 0.8, "top_k": 20}


def test_the_model_s_sampling_is_its_generation_config_and_explicit_values_win():
    sampling = SamplingTrailSchema(defaults="model", temperature=0, max_tokens=512)
    resolution = resolve(cell(sampling=sampling), STACK, FACTS, SERVING)

    assert resolution.sampling.source == "the model's generation config"
    assert resolution.sampling.writes == {
        "temperature": 0,
        "top_p": 0.95,
        "max_tokens": 512,
    }


def test_a_budget_goes_where_the_facts_say():
    reasoning = ReasoningTrailSchema(effort="on", budget=512)
    resolution = resolve(cell(reasoning=reasoning), STACK, FACTS, SERVING)

    assert resolution.reasoning.writes["thinking_token_budget"] == 512


def test_free_text_places_no_schema_whatever_the_coercion():
    resolution = resolve(
        cell(coercion=CoercionTrailSchema(mode="prompted", schema_prompt="{{schema}}")),
        STACK,
        FACTS,
        SERVING,
    )

    assert resolution.slots == {"output_guidance": "List the diagnoses."}


def test_a_variation_set_in_a_configuration_s_place_resolves_there():
    configuration = cell()
    slices = Slices(
        instruction=configuration.instruction,
        output=configuration.output,
        coercion=configuration.coercion,
        reasoning=ReasoningTrailSchema(effort="off"),
        sampling=configuration.sampling,
        toolset=configuration.toolset,
    )

    resolution = resolve(slices, STACK, FACTS, SERVING)

    assert resolution.reasoning.writes == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert resolution.sampling.source == "recommended for 'off'"


def test_reasoning_realizes_without_a_sampling_to_pull_in():
    reasoning, sampling, refusals = realize(
        ReasoningTrailSchema(effort="high"), None, FACTS, SERVING
    )

    assert reasoning is not None
    assert (reasoning.intent, sampling, refusals) == ("on", None, [])


# ------------------------------------------------------------------- refused


def test_an_effort_the_facts_refuse_is_refused_with_their_reason():
    assert refusals(cell(reasoning=ReasoningTrailSchema(effort="low"))) == [
        SliceRefusal("reasoning", "no effort levels")
    ]


def test_an_effort_that_collapses_into_a_refused_one_says_where_it_ended():
    assert refusals(cell(reasoning=ReasoningTrailSchema(effort="xhigh"))) == [
        SliceRefusal("reasoning", "it ends at 'low': no effort levels")
    ]


def test_an_effort_the_facts_say_nothing_on_is_refused():
    assert refusals(cell(reasoning=ReasoningTrailSchema(effort="minimal"))) == [
        SliceRefusal("reasoning", "the model's facts say nothing on 'minimal'")
    ]


def test_without_a_default_in_the_facts_the_default_is_refused():
    facts = FACTS.model_copy(
        update={"reasoning": FACTS.reasoning.model_copy(update={"default": None})}
    )

    assert refusals(cell(), facts=facts) == [
        SliceRefusal("reasoning", "the model's facts say no default effort")
    ]


def test_a_mode_with_no_recommendation_is_refused():
    facts = FACTS.model_copy(
        update={"sampling": FACTS.sampling.model_copy(update={"recommended": {}})}
    )

    assert refusals(cell(), facts=facts) == [
        SliceRefusal("sampling", "the model's facts recommend nothing for 'on'")
    ]


def test_a_budget_needs_a_serving_with_a_reasoning_parser():
    reasoning = ReasoningTrailSchema(effort="on", budget=512)

    assert refusals(
        cell(reasoning=reasoning), serving=ServingTrailSchema(engine=ENGINE)
    ) == [
        SliceRefusal(
            "reasoning",
            "a budget needs a reasoning parser, which the serving doesn't provide",
        )
    ]


def test_a_budget_has_to_fit_in_max_tokens():
    reasoning = ReasoningTrailSchema(effort="on", budget=512)
    sampling = SamplingTrailSchema(defaults="recommended", max_tokens=512)

    assert refusals(cell(reasoning=reasoning, sampling=sampling)) == [
        SliceRefusal("reasoning", "a budget of 512 doesn't fit in max_tokens 512")
    ]


def test_a_slot_the_instruction_doesn_t_place_is_refused():
    bare = InstructionTrailSchema(user="{{case}}", variables=["case"])

    assert refusals(cell(instruction=bare)) == [
        SliceRefusal(
            "instruction", "it doesn't place 'output_guidance', which the output fills"
        )
    ]


def test_a_stack_the_repl_can_t_send_to_is_refused():
    stack = StackDetails(api="anthropic")

    assert refusals(cell(), stack=stack) == [
        SliceRefusal("model", "the repl sends to vLLM only, not anthropic", "later"),
        SliceRefusal("model", "the stack names no endpoint"),
        SliceRefusal("model", "the stack names no served name"),
    ]


def test_a_schema_and_a_toolset_wait_for_their_pieces():
    output = OutputTrailSchema.model_validate(
        {"schema": {"type": "object", "properties": {}}, "guidance": "Fill it in."}
    )
    toolset = ToolsetTrailSchema(tools=[ToolTrailSchema(name="lookup")])

    assert [r.kind for r in refusals(cell(output=output, toolset=toolset))] == [
        "later",
        "later",
    ]


def test_a_refused_cell_keeps_what_its_other_slices_resolve_to():
    toolset = ToolsetTrailSchema(tools=[ToolTrailSchema(name="lookup")])

    with pytest.raises(CellRefused) as refused:
        _ = resolve(cell(toolset=toolset), STACK, FACTS, SERVING)

    assert refused.value.reasoning is not None
    assert refused.value.reasoning.intent == "on"
    assert refused.value.sampling is not None
    assert refused.value.slots == {"output_guidance": "List the diagnoses."}


# ------------------------------------------------------------- the inventory


@pytest.fixture(scope="module")
def inventory() -> ParsedInventory:
    return parse(settings.INVENTORY_PATH / "inventory.toml")


@pytest.mark.parametrize(
    ("stack_name", "model_name"),
    [
        ("qwen3-8b-awq@pelle", "qwen3-8b-awq"),
        ("gpt-oss-20b@malborg", "gpt-oss-20b"),
        ("qwen3-8b-awq@fake", "qwen3-8b-awq"),
    ],
)
def test_free_text_resolves_on_every_model_with_its_facts(
    inventory: ParsedInventory, stack_name: str, model_name: str
):
    configuration, _ = inventory.configuration["free-text"]
    stack, stack_details = inventory.stack[stack_name]
    _, model_details = inventory.model[model_name]
    facts = model_details.facts

    resolution = resolve(configuration, stack_details, facts, stack.serving)

    resolved = facts.reasoning.resolve("default")
    assert resolved is not None
    intent, writes = resolved

    assert resolution.reasoning.writes == writes
    assert resolution.sampling.writes == facts.sampling.recommended[intent].model_dump(
        exclude_none=True
    )
