import json
from typing import Any

import pytest

from chatddx.repo.entities.coercion.pydantic import CoercionTrailIn
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.instruction.pydantic import InstructionTrailIn
from chatddx.repo.entities.llm.pydantic import LLMFacts
from chatddx.repo.entities.output.pydantic import OutputTrailIn
from chatddx.repo.entities.reasoning.pydantic import ReasoningTrailIn
from chatddx.repo.entities.sampling.pydantic import SamplingTrailIn
from chatddx.repo.entities.serving.pydantic import ServingTrailIn
from chatddx.repo.entities.stack.pydantic import StackDetails
from chatddx.repo.entities.tool.pydantic import ToolTrailIn
from chatddx.repo.entities.toolset.pydantic import ToolsetTrailIn
from chatddx.repo.inventories import ParsedInventory
from chatddx.runtime.resolution import (
    CellRefused,
    Coercion,
    SliceRefusal,
    Slices,
    Tool,
    realize,
    resolve,
)

ENGINE = "/nix/store/5nxjf9n4gzgajv67rd4fb1kdssql7g51-python3.13-vllm-0.13.0"

FACTS = LLMFacts.model_validate(
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
        "coercion": {
            "default": "native",
            "native": {"needs": "reasoning_parser"},
            "tool": {"needs": "tool_call_parser", "note": "tool_choice is ignored"},
            "prompted": {"refused": "never tried"},
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

SERVING = ServingTrailIn(engine=ENGINE, args={"reasoning-parser": "qwen3"})

INSTRUCTION = InstructionTrailIn(
    system="{{output_guidance}}{{#if schema_prompt}}\n{{schema_prompt}}{{/if}}",
    user="{{case}}",
    variables=["case", "output_guidance", "schema_prompt"],
)


def cell(**slices: Any) -> ConfigurationTrailIn:
    return ConfigurationTrailIn.model_validate(
        {
            "instruction": INSTRUCTION,
            "output": OutputTrailIn(guidance="List the diagnoses."),
            "coercion": CoercionTrailIn(mode="auto"),
            "reasoning": ReasoningTrailIn(effort="default"),
            "sampling": SamplingTrailIn(defaults="recommended"),
        }
        | slices
    )


def refusals(configuration: ConfigurationTrailIn, **kwargs: Any) -> list[SliceRefusal]:
    with pytest.raises(CellRefused) as refused:
        _ = resolve(
            configuration,
            kwargs.get("stack", STACK),
            kwargs.get("facts", FACTS),
            kwargs.get("serving", SERVING),
        )

    return refused.value.refusals


def test_a_cell_resolves_to_what_the_facts_write():
    resolution = resolve(cell(), STACK, FACTS, SERVING)

    assert resolution.endpoint == "http://gpu:8000/v1/"
    assert resolution.served_name == "Qwen/Qwen3-8B-AWQ"
    assert resolution.profile == {"supports_json_schema_output": True}

    assert resolution.reasoning.effort == "default"
    assert resolution.reasoning.intent == "on"
    assert resolution.sampling.source == "recommended for 'on'"
    assert resolution.fields == {
        "chat_template_kwargs": {"enable_thinking": True},
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
    }


def test_the_case_is_placed_when_a_run_renders_the_cell():
    resolution = resolve(cell(), STACK, FACTS, SERVING)

    assert resolution.render("a cough") == ("List the diagnoses.", "a cough")


def test_an_effort_collapses_into_the_intent_the_facts_name():
    resolution = resolve(
        cell(reasoning=ReasoningTrailIn(effort="high")), STACK, FACTS, SERVING
    )

    assert (resolution.reasoning.effort, resolution.reasoning.intent) == ("high", "on")
    assert resolution.reasoning.writes == {
        "chat_template_kwargs": {"enable_thinking": True}
    }


def test_recommended_sampling_follows_the_mode_reasoning_resolves_to():
    resolution = resolve(
        cell(reasoning=ReasoningTrailIn(effort="off")), STACK, FACTS, SERVING
    )

    assert resolution.sampling.source == "recommended for 'off'"
    assert resolution.sampling.writes == {"temperature": 0.7, "top_p": 0.8, "top_k": 20}


def test_the_llm_s_sampling_is_its_generation_config_and_explicit_values_win():
    sampling = SamplingTrailIn(
        defaults="generation_config", temperature=0, max_tokens=512
    )
    resolution = resolve(cell(sampling=sampling), STACK, FACTS, SERVING)

    assert resolution.sampling.source == "the LLM's generation config"
    assert resolution.sampling.writes == {
        "temperature": 0,
        "top_p": 0.95,
        "max_tokens": 512,
    }


def test_a_budget_goes_where_the_facts_say():
    reasoning = ReasoningTrailIn(effort="on", budget=512)
    resolution = resolve(cell(reasoning=reasoning), STACK, FACTS, SERVING)

    assert resolution.reasoning.writes["thinking_token_budget"] == 512


def test_free_text_places_no_schema_whatever_the_coercion():
    resolution = resolve(
        cell(coercion=CoercionTrailIn(mode="prompted", schema_prompt="{{schema}}")),
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
        reasoning=ReasoningTrailIn(effort="off"),
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
        ReasoningTrailIn(effort="high"), None, FACTS, SERVING
    )

    assert reasoning is not None
    assert (reasoning.intent, sampling, refusals) == ("on", None, [])


def test_an_effort_the_facts_refuse_is_refused_with_their_reason():
    assert refusals(cell(reasoning=ReasoningTrailIn(effort="low"))) == [
        SliceRefusal("reasoning", "no effort levels")
    ]


def test_an_effort_that_collapses_into_a_refused_one_says_where_it_ended():
    assert refusals(cell(reasoning=ReasoningTrailIn(effort="xhigh"))) == [
        SliceRefusal("reasoning", "it ends at 'low': no effort levels")
    ]


def test_an_effort_the_facts_say_nothing_on_is_refused():
    assert refusals(cell(reasoning=ReasoningTrailIn(effort="minimal"))) == [
        SliceRefusal("reasoning", "the LLM's facts say nothing on 'minimal'")
    ]


def test_without_a_default_in_the_facts_the_default_is_refused():
    facts = FACTS.model_copy(
        update={"reasoning": FACTS.reasoning.model_copy(update={"default": None})}
    )

    assert refusals(cell(), facts=facts) == [
        SliceRefusal("reasoning", "the LLM's facts say no default effort")
    ]


def test_a_mode_with_no_recommendation_is_refused():
    facts = FACTS.model_copy(
        update={"sampling": FACTS.sampling.model_copy(update={"recommended": {}})}
    )

    assert refusals(cell(), facts=facts) == [
        SliceRefusal("sampling", "the LLM's facts recommend nothing for 'on'")
    ]


def test_a_budget_needs_a_serving_with_a_reasoning_parser():
    reasoning = ReasoningTrailIn(effort="on", budget=512)

    assert refusals(
        cell(reasoning=reasoning), serving=ServingTrailIn(engine=ENGINE)
    ) == [
        SliceRefusal(
            "reasoning",
            "a budget needs a reasoning parser, which the serving doesn't provide",
        )
    ]


def test_a_budget_has_to_fit_in_max_tokens():
    reasoning = ReasoningTrailIn(effort="on", budget=512)
    sampling = SamplingTrailIn(defaults="recommended", max_tokens=512)

    assert refusals(cell(reasoning=reasoning, sampling=sampling)) == [
        SliceRefusal("reasoning", "a budget of 512 doesn't fit in max_tokens 512")
    ]


def test_a_slot_the_instruction_doesn_t_place_is_refused():
    bare = InstructionTrailIn(user="{{case}}", variables=["case"])

    assert refusals(cell(instruction=bare)) == [
        SliceRefusal(
            "instruction", "it doesn't place 'output_guidance', which the output fills"
        )
    ]


def test_a_stack_the_repl_can_t_send_to_is_refused():
    stack = StackDetails(api="anthropic")

    assert refusals(cell(), stack=stack) == [
        SliceRefusal("stack", "the repl sends to vLLM only, not anthropic", "later"),
        SliceRefusal("stack", "the stack names no endpoint"),
        SliceRefusal("stack", "the stack names no served name"),
    ]


SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"urgent": {"type": "boolean"}, "diagnoses": {"type": "array"}},
    "required": ["urgent", "diagnoses"],
}

STRUCTURED = OutputTrailIn.model_validate(
    {"answer_schema": SCHEMA, "guidance": "List the diagnoses."}
)


def test_a_schema_is_held_by_the_mode_the_coercion_asks_for():
    resolution = resolve(
        cell(output=STRUCTURED, coercion=CoercionTrailIn(mode="native")),
        STACK,
        FACTS,
        SERVING,
    )

    assert resolution.coercion == Coercion(
        "native", "native", SCHEMA, SCHEMA, None, None
    )
    assert resolution.slots == {"output_guidance": "List the diagnoses."}


def test_auto_is_the_mode_the_facts_name():
    resolution = resolve(cell(output=STRUCTURED), STACK, FACTS, SERVING)

    assert resolution.coercion == Coercion("auto", "native", SCHEMA, SCHEMA, None, None)


def test_the_schema_prompt_fills_its_slot_with_the_schema_as_written():
    coercion = CoercionTrailIn(mode="native", schema_prompt="Schema:\n{{schema}}")
    resolution = resolve(
        cell(output=STRUCTURED, coercion=coercion), STACK, FACTS, SERVING
    )

    assert resolution.slots["schema_prompt"] == "Schema:\n" + json.dumps(
        SCHEMA, indent=2
    )
    assert resolution.render("a cough")[0] == (
        "List the diagnoses.\n" + resolution.slots["schema_prompt"]
    )


def test_a_mode_needs_what_the_facts_say_it_needs():
    coercion = CoercionTrailIn(mode="tool", tool_description="Answer here.")

    assert refusals(cell(output=STRUCTURED, coercion=coercion)) == [
        SliceRefusal(
            "coercion",
            "'tool' needs a tool call parser, which the serving doesn't provide",
        )
    ]

    serving = ServingTrailIn(
        engine=ENGINE,
        args={"tool-call-parser": "hermes", "enable-auto-tool-choice": True},
    )
    resolution = resolve(
        cell(output=STRUCTURED, coercion=coercion), STACK, FACTS, serving
    )

    assert resolution.coercion == Coercion(
        "tool", "tool", SCHEMA, SCHEMA, "Answer here.", "tool_choice is ignored"
    )


def test_a_reasoning_parser_is_needed_only_while_the_llm_reasons():
    bare = ServingTrailIn(engine=ENGINE)
    native = CoercionTrailIn(mode="native")

    assert refusals(cell(output=STRUCTURED, coercion=native), serving=bare) == [
        SliceRefusal(
            "coercion",
            "'native' needs a reasoning parser while the LLM reasons, which the "
            + "serving doesn't provide",
        )
    ]

    off = ReasoningTrailIn(effort="off")
    resolution = resolve(
        cell(output=STRUCTURED, coercion=native, reasoning=off), STACK, FACTS, bare
    )

    assert resolution.coercion is not None
    assert resolution.coercion.mode == "native"


def test_auto_ending_at_tool_needs_a_tool_description():
    tooled = FACTS.model_copy(
        update={"coercion": FACTS.coercion.model_copy(update={"default": "tool"})}
    )
    serving = ServingTrailIn(
        engine=ENGINE,
        args={"tool-call-parser": "hermes", "enable-auto-tool-choice": True},
    )

    assert refusals(cell(output=STRUCTURED), facts=tooled, serving=serving) == [
        SliceRefusal(
            "coercion",
            "it ends at 'tool': 'tool' needs a tool description, which the coercion "
            + "doesn't give",
        )
    ]


def test_references_are_inlined_as_the_request_carries_the_schema():
    schema: dict[str, Any] = {
        "$defs": {"Item": {"type": "object", "properties": {"z": {}, "a": {}}}},
        "type": "object",
        "properties": {
            "first": {"$ref": "#/$defs/Item", "description": "the first"},
            "all": {"type": "array", "items": {"$ref": "#/$defs/Item"}},
        },
    }
    output = OutputTrailIn.model_validate({"answer_schema": schema})

    resolution = resolve(cell(output=output), STACK, FACTS, SERVING)

    assert resolution.coercion is not None
    assert resolution.coercion.schema == schema
    assert resolution.coercion.sent == {
        "type": "object",
        "properties": {
            "first": {
                "type": "object",
                "properties": {"z": {}, "a": {}},
                "description": "the first",
            },
            "all": {
                "type": "array",
                "items": {"type": "object", "properties": {"z": {}, "a": {}}},
            },
        },
    }


def test_a_schema_that_refers_to_itself_can_t_be_sent():
    schema: dict[str, Any] = {
        "$defs": {
            "Node": {"type": "object", "properties": {"next": {"$ref": "#/$defs/Node"}}}
        },
        "$ref": "#/$defs/Node",
    }
    output = OutputTrailIn.model_validate({"answer_schema": schema})

    assert refusals(cell(output=output)) == [
        SliceRefusal(
            "coercion", "the schema can't be sent: #/$defs/Node refers to itself"
        )
    ]


def test_a_schema_whose_root_isn_t_an_object_can_t_be_sent():
    output = OutputTrailIn.model_validate(
        {"answer_schema": {"type": "array", "items": {"type": "string"}}}
    )

    assert refusals(cell(output=output)) == [
        SliceRefusal(
            "coercion",
            'the schema can\'t be sent: an answer is held to an object, not to "array"',
        )
    ]


def test_a_mode_the_facts_refuse_or_say_nothing_on_is_refused():
    prompted = CoercionTrailIn(mode="prompted", schema_prompt="{{schema}}")
    silent = FACTS.model_copy(
        update={"coercion": FACTS.coercion.model_copy(update={"default": None})}
    )

    assert refusals(cell(output=STRUCTURED, coercion=prompted)) == [
        SliceRefusal("coercion", "never tried")
    ]
    assert refusals(cell(output=STRUCTURED), facts=silent) == [
        SliceRefusal("coercion", "the LLM's facts name no mode for 'auto'")
    ]


def test_a_schema_prompt_the_instruction_doesn_t_place_is_refused():
    guidance_only = InstructionTrailIn(
        system="{{output_guidance}}",
        user="{{case}}",
        variables=["case", "output_guidance"],
    )
    coercion = CoercionTrailIn(mode="native", schema_prompt="{{schema}}")

    assert refusals(
        cell(instruction=guidance_only, output=STRUCTURED, coercion=coercion)
    ) == [
        SliceRefusal(
            "instruction", "it doesn't place 'schema_prompt', which the coercion fills"
        )
    ]


TOOLED = ServingTrailIn(
    engine=ENGINE,
    args={
        "reasoning-parser": "qwen3",
        "tool-call-parser": "hermes",
        "enable-auto-tool-choice": True,
    },
)

GUIDED = InstructionTrailIn(
    system="{{output_guidance}}{{#if tool_guidance}}\n{{tool_guidance}}{{/if}}",
    user="{{case}}",
    variables=["case", "output_guidance", "tool_guidance"],
)


def test_a_toolset_offers_its_tools_in_order_as_the_request_carries_them():
    lookup = ToolTrailIn.model_validate(
        {
            "name": "lookup",
            "description": "Look a term up.",
            "parameters": {
                "$defs": {"Term": {"type": "string"}},
                "type": "object",
                "properties": {"term": {"$ref": "#/$defs/Term"}},
            },
        }
    )
    toolset = ToolsetTrailIn(
        guidance="Look it up.", tools=[lookup, ToolTrailIn(name="now")]
    )

    resolution = resolve(
        cell(instruction=GUIDED, toolset=toolset), STACK, FACTS, TOOLED
    )

    assert resolution.tools == [
        Tool(
            "lookup",
            "Look a term up.",
            {"type": "object", "properties": {"term": {"type": "string"}}},
        ),
        Tool("now", "", {"type": "object", "properties": {}}),
    ]
    assert resolution.slots["tool_guidance"] == "Look it up."
    assert resolution.render("a cough")[0] == "List the diagnoses.\nLook it up."


def test_no_toolset_offers_nothing():
    resolution = resolve(cell(instruction=GUIDED), STACK, FACTS, TOOLED)

    assert resolution.tools == []
    assert "tool_guidance" not in resolution.slots


def test_tools_need_a_serving_with_a_tool_call_parser():
    toolset = ToolsetTrailIn(tools=[ToolTrailIn(name="lookup")])

    assert refusals(cell(toolset=toolset)) == [
        SliceRefusal(
            "toolset",
            "tools need a tool call parser, which the serving doesn't provide",
        )
    ]


def test_a_tool_whose_parameters_refer_to_themselves_can_t_be_sent():
    walk = ToolTrailIn.model_validate(
        {
            "name": "walk",
            "parameters": {
                "$defs": {
                    "Node": {
                        "type": "object",
                        "properties": {"next": {"$ref": "#/$defs/Node"}},
                    }
                },
                "$ref": "#/$defs/Node",
            },
        }
    )
    toolset = ToolsetTrailIn(tools=[walk])

    assert refusals(cell(toolset=toolset), serving=TOOLED) == [
        SliceRefusal("toolset", "'walk' can't be sent: #/$defs/Node refers to itself")
    ]


def test_tool_guidance_the_instruction_doesn_t_place_is_refused():
    toolset = ToolsetTrailIn(guidance="Look it up.", tools=[ToolTrailIn(name="lookup")])

    assert refusals(cell(toolset=toolset), serving=TOOLED) == [
        SliceRefusal(
            "instruction", "it doesn't place 'tool_guidance', which the toolset fills"
        )
    ]


def test_a_refused_cell_keeps_what_its_other_slices_resolve_to():
    toolset = ToolsetTrailIn(tools=[ToolTrailIn(name="lookup")])

    with pytest.raises(CellRefused) as refused:
        _ = resolve(cell(toolset=toolset), STACK, FACTS, SERVING)

    assert refused.value.reasoning is not None
    assert refused.value.reasoning.intent == "on"
    assert refused.value.sampling is not None
    assert [tool.name for tool in refused.value.tools] == ["lookup"]
    assert refused.value.slots == {"output_guidance": "List the diagnoses."}


@pytest.mark.parametrize("configuration_name", ["diagnoses", "diagnoses-tool"])
def test_on_pelle_a_grammar_leaves_qwen3_no_room_to_think(
    test_inventory: ParsedInventory, configuration_name: str
):
    configuration, _ = test_inventory.configuration[configuration_name]
    stack, stack_details = test_inventory.stack["qwen3-8b-awq@pelle"]
    _, llm = test_inventory.llm["qwen3-8b-awq"]
    off, _ = test_inventory.reasoning["off"]

    with pytest.raises(CellRefused) as refused:
        _ = resolve(configuration, stack_details, llm.facts, stack.serving)

    assert [refusal.slice for refusal in refused.value.refusals] == ["coercion"]
    assert "needs a reasoning parser while the LLM reasons" in str(refused.value)

    thoughtless = configuration.model_copy(update={"reasoning": off})
    resolution = resolve(thoughtless, stack_details, llm.facts, stack.serving)

    assert resolution.reasoning.writes == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


@pytest.mark.parametrize(
    ("stack_name", "llm_name"),
    [
        ("qwen3-8b-awq@pelle", "qwen3-8b-awq"),
        ("gpt-oss-20b@malborg", "gpt-oss-20b"),
        ("qwen3-8b-awq@fake", "qwen3-8b-awq"),
    ],
)
def test_free_text_resolves_on_every_llm_with_its_facts(
    test_inventory: ParsedInventory, stack_name: str, llm_name: str
):
    configuration, _ = test_inventory.configuration["free-text"]
    stack, stack_details = test_inventory.stack[stack_name]
    _, llm_details = test_inventory.llm[llm_name]
    facts = llm_details.facts

    resolution = resolve(configuration, stack_details, facts, stack.serving)

    resolved = facts.reasoning.resolve("default")
    assert resolved is not None
    intent, writes = resolved

    assert resolution.reasoning.writes == writes
    assert resolution.sampling.writes == facts.sampling.recommended[intent].model_dump(
        exclude_none=True
    )
