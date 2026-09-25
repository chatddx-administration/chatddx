"""
What each entity holds itself to, whoever writes it: the parser, a form or
code.
"""

from typing import Any

import pytest
from pydantic import JsonValue, ValidationError

from chatddx.repo.entities.case.pydantic import CaseDetails
from chatddx.repo.entities.coercion.pydantic import CoercionTrailIn
from chatddx.repo.entities.instruction.pydantic import InstructionTrailIn
from chatddx.repo.entities.llm.pydantic import (
    LLMDetails,
    LLMFacts,
    LLMTrailIn,
    ModeFact,
    ReasoningFacts,
    Refusal,
)
from chatddx.repo.entities.machine.pydantic import MachineTrailIn
from chatddx.repo.entities.os.pydantic import OsTrailIn
from chatddx.repo.entities.output.pydantic import OutputTrailIn
from chatddx.repo.entities.reasoning.pydantic import ReasoningTrailIn
from chatddx.repo.entities.sampling.pydantic import SamplingTrailIn
from chatddx.repo.entities.serving.pydantic import ServingDetails, ServingTrailIn
from chatddx.repo.entities.stack.pydantic import StackTrailIn
from chatddx.repo.entities.tool.pydantic import ToolTrailIn
from chatddx.repo.entities.toolset.pydantic import ToolsetTrailIn
from chatddx.repo.templates import TemplateError, placements

ENGINE = "/nix/store/22222222222222222222222222222222-vllm"
MACHINE = MachineTrailIn(machine_id="00000000-0000-4000-8000-000000000001")  # pyright: ignore[reportArgumentType]
LLM = LLMTrailIn(snapshot="/nix/store/11111111111111111111111111111111-m")


def os(name: str) -> OsTrailIn:
    return OsTrailIn(toplevel=f"/nix/store/{'0' * 32}-nixos-system-{name}")


# ------------------------------------------------------------------- things


@pytest.mark.parametrize(
    "snapshot",
    [
        "/nix/store/0v4qhx8a2c5m7l1d9rbs6fzjkg3ywpin-Qwen3-8B-AWQ",
        # a cloud provider's dated model name stands in, unverified
        "gpt-5-mini-2025-08-07",
    ],
)
def test_an_llm_is_its_snapshot(snapshot: str):
    assert LLMTrailIn(snapshot=snapshot).snapshot == snapshot


@pytest.mark.parametrize(
    "snapshot, problem",
    [
        # vLLM would resolve the revision when it starts
        ("Qwen/Qwen3-8B-AWQ", "names a repository"),
        ("/models/qwen3-8b-awq", "store path"),
        # nix base32 has no e, o, t or u
        ("/nix/store/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee-m", "store path"),
    ],
)
def test_a_snapshot_is_a_store_path_or_a_cloud_name(snapshot: str, problem: str):
    with pytest.raises(ValidationError, match=problem):
        _ = LLMTrailIn(snapshot=snapshot)


def test_a_source_pins_a_commit():
    assert LLMDetails(source=f"Qwen/Qwen3-8B-AWQ@{'a' * 40}").source

    with pytest.raises(ValidationError, match="not a pinned source"):
        _ = LLMDetails(source="Qwen/Qwen3-8B-AWQ@main")


def test_an_os_is_its_system_s_store_path():
    with pytest.raises(ValidationError, match="not a Nix store path"):
        _ = OsTrailIn(toplevel="/run/current-system")


# ---------------------------------------------------------------- servings


def test_serving_arguments_are_held_in_one_spelling():
    serving = ServingTrailIn(
        engine=ENGINE,
        args={"--max_model_len": 8192, "reasoning-parser": "qwen3"},
    )

    assert list(serving.args) == ["max-model-len", "reasoning-parser"]


@pytest.mark.parametrize(
    "args, problem",
    [
        ({"max-model-len": 1, "max_model_len": 2}, "given twice"),
        ({"model": "/nix/store/x"}, "LLM's identity"),
        ({"served-model-name": "qwen3"}, "served_name"),
        ({"api-key": "secret"}, "credential"),
        ({"gpu-memory-utilization": 0.9}, "belongs to performance"),
        ({"port": 8000}, "belongs to performance"),
    ],
)
def test_an_argument_that_isn_t_content_is_refused(args: dict[str, Any], problem: str):
    with pytest.raises(ValidationError, match=problem):
        _ = ServingTrailIn(engine=ENGINE, args=args)


@pytest.mark.parametrize(
    "performance",
    [{"max-model-len": 8192}, {"enforce-eager": True}, {"reasoning-parser": "qwen3"}],
)
def test_what_changes_the_output_is_not_performance(performance: dict[str, Any]):
    with pytest.raises(ValidationError, match="belongs to args"):
        _ = ServingDetails(performance=performance)


def test_a_serving_provides_what_its_arguments_set_up():
    assert ServingTrailIn(engine=ENGINE).provides() == frozenset()

    serving = ServingTrailIn(
        engine=ENGINE,
        args={"reasoning-parser": "qwen3", "tool-call-parser": "hermes"},
    )

    # a tool-call parser does nothing without auto tool choice
    assert serving.provides() == {"reasoning_parser"}

    serving.args["enable-auto-tool-choice"] = True

    assert serving.provides() == {"reasoning_parser", "tool_call_parser"}


# ------------------------------------------------------------------- stacks


def test_a_container_s_stack_names_both_systems():
    stack = StackTrailIn(
        machine=MACHINE,
        os=os("container"),
        host_os=os("host"),
        llm=LLM,
    )

    assert stack.host_os == os("host")


def test_a_host_os_is_for_a_container():
    with pytest.raises(ValidationError, match="name the container's OS too"):
        _ = StackTrailIn(machine=MACHINE, host_os=os("host"), llm=LLM)

    with pytest.raises(ValidationError, match="not its host's"):
        _ = StackTrailIn(machine=MACHINE, os=os("a"), host_os=os("a"), llm=LLM)


# ------------------------------------------------------------------- facts


def test_a_fact_is_a_fragment_a_collapse_or_a_refusal():
    facts = ReasoningFacts.model_validate(
        {
            "default": "on",
            "off": {"chat_template_kwargs": {"enable_thinking": False}},
            "on": {"chat_template_kwargs": {"enable_thinking": True}},
            "low": "on",
            "high": {"refused": "no"},
        }
    )

    assert facts.resolve("low") == (
        "on",
        {"chat_template_kwargs": {"enable_thinking": True}},
    )
    assert facts.resolve("default") == facts.resolve("on")
    assert facts.resolve("high") == ("high", Refusal(refused="no"))
    # no fact at all: refused for want of one
    assert facts.resolve("xhigh") is None
    assert facts.realized() == {"off", "on"}


@pytest.mark.parametrize(
    "facts, problem",
    [
        ({"on": "medium"}, "collapses into 'medium', which ends in no fact"),
        ({"default": "on"}, "collapses into 'on', which ends in no fact"),
        ({"on": "medium", "medium": "on"}, "the collapses go round"),
        ({"low": "maximal"}, "low"),
        # the reasoning slice writes these, and a fact can't write others
        ({"on": {"temperature": 0.6}}, "not \\['temperature'\\]"),
        ({"budget": {"field": "max_tokens"}}, "not \\['max_tokens'\\]"),
        ({"off": {"refused": ""}}, "refused"),
        ({"off": {"refused": "why", "reasoning_effort": "low"}}, "Extra inputs"),
    ],
)
def test_facts_that_don_t_resolve_are_refused(facts: dict[str, Any], problem: str):
    with pytest.raises(ValidationError, match=problem):
        _ = ReasoningFacts.model_validate(facts)


def test_sampling_is_recommended_for_a_mode_the_facts_resolve_to():
    reasoning = {"on": {"chat_template_kwargs": {"enable_thinking": True}}, "low": "on"}

    assert LLMFacts.model_validate(
        {
            "reasoning": reasoning,
            "sampling": {"recommended": {"on": {"temperature": 0.6}}},
        }
    )

    with pytest.raises(ValidationError, match=r"recommended for \['low'\]"):
        _ = LLMFacts.model_validate(
            {
                "reasoning": reasoning,
                "sampling": {"recommended": {"low": {"temperature": 0.6}}},
            }
        )


def test_auto_resolves_to_a_mode_the_facts_say_works():
    assert LLMFacts.model_validate({"coercion": {"default": "native", "native": {}}})

    for coercion in (
        {"default": "tool"},
        {"default": "tool", "tool": {"refused": "vLLM ignores it"}},
    ):
        with pytest.raises(ValidationError, match="`auto` resolves to 'tool'"):
            _ = LLMFacts.model_validate({"coercion": coercion})


def test_a_mode_names_what_it_needs_one_or_several():
    facts = LLMFacts.model_validate(
        {"coercion": {"native": {"needs": "reasoning_parser"}, "tool": {"needs": []}}}
    )

    native = facts.coercion.native

    assert isinstance(native, ModeFact)
    assert native.needs == ["reasoning_parser"]

    with pytest.raises(ValidationError, match="reasoning_parser"):
        _ = LLMFacts.model_validate({"coercion": {"native": {"needs": "a_parser"}}})


# -------------------------------------------------------------- templates


def test_a_template_places_values_and_branches_on_conditions():
    placed = placements(
        "{{a}}{{#if b}}{{{c}}}{{else}}{{d.e}}{{/if}}{{^f}}x{{/f}}{{!-- g --}}"
    )

    assert placed.values == {"a", "c", "d"}
    assert placed.conditions == {"b", "f"}


@pytest.mark.parametrize(
    "template",
    ["{{#if a}}", "{{/if}}", "{{> partial}}", "{{lookup a b}}", "{{#foo a}}{{/foo}}"],
)
def test_a_template_is_plain_handlebars(template: str):
    with pytest.raises(TemplateError):
        _ = placements(template)


def test_an_instruction_declares_what_it_places():
    instruction = InstructionTrailIn(
        system="{{output_guidance}}{{#if schema_prompt}}\n\n{{schema_prompt}}{{/if}}",
        user="{{case}}",
        variables=["schema_prompt", "output_guidance", "case"],
    )

    # one order for one set
    assert instruction.variables == ["case", "output_guidance", "schema_prompt"]


@pytest.mark.parametrize(
    "system, user, variables, problem",
    [
        ("{{output_guidance}}", "{{case}}", ["case"], "placed but not declared"),
        ("", "{{case}}", ["case", "output_guidance"], "declared but never placed"),
        ("", "", ["case"], "declared but never placed"),
        ("", "{{output_guidance}}", ["output_guidance"], "declare `case`"),
        ("{{#if case}}x{{/if}}", "{{case}}", ["case"], "never a condition"),
        ("", "{{case}}", ["case", "case"], "declared twice"),
        ("", "{{case}}", ["case", "reasoning_guidance"], "reasoning_guidance"),
    ],
)
def test_an_instruction_that_doesn_t_declare_what_it_places_is_refused(
    system: str, user: str, variables: list[str], problem: str
):
    with pytest.raises(ValidationError, match=problem):
        _ = InstructionTrailIn(system=system, user=user, variables=variables)  # pyright: ignore[reportArgumentType]


# ----------------------------------------------------------------- coercion


def test_prompted_mode_needs_a_schema_prompt():
    with pytest.raises(ValidationError, match="needs a schema_prompt"):
        _ = CoercionTrailIn(mode="prompted")


@pytest.mark.parametrize(
    "schema_prompt",
    ["Answer as JSON.", "{{schema}} {{case}}", "{{#if schema}}{{schema}}{{/if}}"],
)
def test_a_schema_prompt_places_the_schema_and_nothing_else(schema_prompt: str):
    with pytest.raises(
        ValidationError, match=r"places \{\{schema\}\}, and nothing else"
    ):
        _ = CoercionTrailIn(mode="native", schema_prompt=schema_prompt)


def test_tool_mode_needs_a_tool_description():
    with pytest.raises(ValidationError, match="it needs a tool_description"):
        _ = CoercionTrailIn(mode="tool")

    tool = CoercionTrailIn(mode="tool", tool_description="Answer here.")
    auto = CoercionTrailIn(mode="auto", tool_description="Answer here.")

    assert (tool.tool_description, auto.tool_description) == ("Answer here.",) * 2


def test_a_tool_description_is_for_tool_mode_and_places_nothing():
    with pytest.raises(ValidationError, match="a tool description is for tool mode"):
        _ = CoercionTrailIn(mode="native", tool_description="Answer here.")

    with pytest.raises(ValidationError, match="a tool description places nothing"):
        _ = CoercionTrailIn(mode="tool", tool_description="Answer {{here}}.")


# ------------------------------------------------------------------ outputs

PLAN: dict[str, JsonValue] = {
    "type": "object",
    "$defs": {
        "Diagnosis": {
            "type": "object",
            "properties": {
                "diagnosis": {"type": "string"},
                "probability": {"enum": ["high", "low"]},
                "maybe": {"type": ["string", "null"]},
                "either": {"anyOf": [{"type": "string"}, {"type": "number"}]},
                "critical": {"type": "boolean"},
            },
        }
    },
    "properties": {
        "diagnoses": {"type": "array", "items": {"$ref": "#/$defs/Diagnosis"}},
        "names": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
}


@pytest.mark.parametrize(
    "path",
    [
        "$.diagnoses[*].diagnosis",
        "$.names[*]",
        # one string is a list of one
        "$.summary",
        # an enum of strings is strings
        "$.diagnoses[*].probability",
        # the items whose boolean is true
        "$.diagnoses[?(@.critical)].diagnosis",
    ],
)
def test_a_view_is_a_path_the_schema_proves(path: str):
    output = OutputTrailIn(json_schema=PLAN, views={"differential": path})

    assert output.views == {"differential": path}


@pytest.mark.parametrize(
    "path, problem",
    [
        ("$.names", r"\$\.names is of type array, not a string"),
        ("$.diagnoses[*]", r"\$\.diagnoses\[\*\] is of type object"),
        ("$.nowhere[*]", r"\$ has no property 'nowhere'"),
        ("$.summary[*]", r"\$\.summary is of type string, not an array"),
        # a null is not a diagnosis
        ("$.diagnoses[*].maybe", r"of type \['string', 'null'\]"),
        ("$.diagnoses[*].either", r"a union \(anyOf\)"),
        ("diagnoses[*]", "not a path"),
        ("$..diagnosis", "not a path"),
        ("$.diagnoses[0]", "not a path"),
        # a filter needs a boolean the items declare
        (
            "$.diagnoses[?(@.diagnosis)].diagnosis",
            r"\$\.diagnoses\[\?\(@\.diagnosis\)\]\.diagnosis is of type string, not a boolean",
        ),
        ("$.diagnoses[?(@.nowhere)].diagnosis", "filters on 'nowhere'"),
        ("$.names[?(@.critical)]", r"\$\.names\[\?\(@\.critical\)\] is of type string"),
        ("$.diagnoses[?(@.critical == true)]", "not a path"),
    ],
)
def test_a_path_the_schema_doesn_t_prove_is_refused(path: str, problem: str):
    with pytest.raises(ValidationError, match=problem):
        _ = OutputTrailIn(json_schema=PLAN, views={"differential": path})


def test_free_text_gives_its_views_through_parsers():
    output = OutputTrailIn(guidance="One per line.", views={"differential": "lines"})

    assert output.json_schema is None

    with pytest.raises(ValidationError, match="through a parser"):
        _ = OutputTrailIn(views={"differential": "$.names[*]"})

    with pytest.raises(ValidationError, match="not a path"):
        _ = OutputTrailIn(json_schema=PLAN, views={"differential": "lines"})


def test_free_text_offers_its_text_whole():
    output = OutputTrailIn(views={"text": "whole", "differential": "lines"})

    assert output.view("text", "Pneumonia, most likely.\nCOPD") == [
        "Pneumonia, most likely.\nCOPD"
    ]
    assert output.view("text", "  \n") == []

    with pytest.raises(ValidationError, match="through a parser"):
        _ = OutputTrailIn(views={"text": "lines"})


def test_a_structured_output_offers_text_only_where_a_path_proves_a_string():
    output = OutputTrailIn(json_schema=PLAN, views={"text": "$.summary"})

    assert output.view("text", {"summary": "pneumonia"}) == ["pneumonia"]

    with pytest.raises(ValidationError, match="not a string"):
        _ = OutputTrailIn(json_schema=PLAN, views={"text": "$"})


def test_a_warning_may_be_null_and_reads_as_nothing():
    output = OutputTrailIn(json_schema=PLAN, views={"warning": "$.diagnoses[*].maybe"})
    answer: JsonValue = {"diagnoses": [{"maybe": "sepsis"}, {"maybe": None}]}

    assert output.view("warning", answer) == ["sepsis"]

    with pytest.raises(ValidationError, match=r"of type \['string', 'null'\]"):
        _ = OutputTrailIn(
            json_schema=PLAN, views={"disposition": "$.diagnoses[*].maybe"}
        )


def test_a_view_the_code_doesn_t_know_is_refused():
    with pytest.raises(ValidationError, match="views.plan"):
        _ = OutputTrailIn(json_schema=PLAN, views={"plan": "$"})  # pyright: ignore[reportArgumentType]


def test_a_view_reads_what_its_path_reaches_in_an_answer():
    output = OutputTrailIn(
        json_schema=PLAN, views={"differential": "$.diagnoses[*].diagnosis"}
    )
    answer: JsonValue = {
        "diagnoses": [
            {"diagnosis": "pneumonia"},
            {"diagnosis": "copd"},
            # an item the path doesn't reach is read as nothing
            {"probability": "low"},
        ]
    }

    assert output.view("differential", answer) == ["pneumonia", "copd"]


def test_a_filter_keeps_the_items_whose_boolean_is_true():
    output = OutputTrailIn(
        json_schema=PLAN, views={"critical": "$.diagnoses[?(@.critical)].diagnosis"}
    )
    answer: JsonValue = {
        "diagnoses": [
            {"diagnosis": "pneumonia", "critical": False},
            {"diagnosis": "sepsis", "critical": True},
            # an item that doesn't say is not critical
            {"diagnosis": "copd"},
        ]
    }

    assert output.view("critical", answer) == ["sepsis"]


def test_a_view_of_one_string_reads_a_list_of_one():
    output = OutputTrailIn(json_schema=PLAN, views={"differential": "$.summary"})

    assert output.view("differential", {"summary": "pneumonia"}) == ["pneumonia"]
    assert output.view("differential", {}) == []


def test_free_text_is_read_a_line_at_a_time_its_list_markers_stripped():
    output = OutputTrailIn(views={"differential": "lines"})
    answer = (
        "1. Pneumonia\n\n- COPD exacerbation\n* Asthma\n2) Heart failure\n  Embolism "
    )

    assert output.view("differential", answer) == [
        "Pneumonia",
        "COPD exacerbation",
        "Asthma",
        "Heart failure",
        "Embolism",
    ]


def test_a_schema_is_a_json_schema():
    with pytest.raises(ValidationError, match="not a valid JSON Schema"):
        _ = OutputTrailIn(json_schema={"type": "objet"})


# ---------------------------------------------------- reasoning, sampling


def test_a_budget_is_for_reasoning_that_is_on():
    assert ReasoningTrailIn(effort="on", budget=1024).budget == 1024

    with pytest.raises(ValidationError, match="budget for reasoning that is off"):
        _ = ReasoningTrailIn(effort="off", budget=1024)


@pytest.mark.parametrize(
    "values",
    [
        {"temperature": 2.1},
        {"temperature": -0.1},
        {"top_p": 0},
        {"top_p": 1.1},
        {"top_k": -2},
        {"max_tokens": 0},
        {"presence_penalty": 2.5},
        {"frequency_penalty": -2.5},
    ],
)
def test_sampling_holds_its_values_to_their_ranges(values: dict[str, Any]):
    with pytest.raises(ValidationError):
        _ = SamplingTrailIn(defaults="generation_config", **values)


def test_sampling_says_what_a_value_left_out_means():
    with pytest.raises(ValidationError, match="defaults"):
        _ = SamplingTrailIn.model_validate({"temperature": 0.7})


def test_what_sampling_params_held_that_isn_t_sampling_is_gone():
    """
    The seed is the trial's, one per replicate; `n` is scrapped; logit bias
    keys are token ids, which fit one tokenizer; and provider params were
    reasoning switches, which are the reasoning slice's now
    (new-datamodel.md §7).
    """
    fields = set(SamplingTrailIn.model_fields)

    assert fields.isdisjoint({"seed", "n", "logit_bias", "provider_params"})
    assert "stop" in fields and "stop_sequences" not in fields


# --------------------------------------------------------------- toolsets


def test_a_toolset_has_tools_of_different_names():
    def tool(name: str) -> ToolTrailIn:
        return ToolTrailIn(name=name)

    assert ToolsetTrailIn(tools=[tool("a"), tool("b")])

    with pytest.raises(ValidationError, match="'a' appears twice"):
        _ = ToolsetTrailIn(tools=[tool("a"), tool("a")])

    with pytest.raises(ValidationError, match="at least 1"):
        _ = ToolsetTrailIn(tools=[])


def test_a_tool_is_named_as_the_api_allows():
    with pytest.raises(ValidationError, match="name"):
        _ = ToolTrailIn(name="web search")


# --------------------------------------------------------------------- cases


def test_a_case_says_the_language_it_is_written_in():
    assert CaseDetails.model_validate({"language": "sv"}).language == "sv"
    assert CaseDetails().language is None

    with pytest.raises(ValidationError, match="language"):
        _ = CaseDetails.model_validate({"language": "se"})


def test_a_target_is_its_words_and_its_pattern_either_of_which_may_be_missing():
    details = CaseDetails.model_validate(
        {
            "targets": {
                "diagnosis": {"text": "Biliary colic", "pattern": "biliary & colic"},
                "warning": False,
                "disposition": {"text": "home"},
                "dont_miss": {"pattern": "pulmonary & embolism"},
            }
        }
    )

    assert details.targets["disposition"] is not False
    assert details.targets["disposition"].pattern is None

    with pytest.raises(ValidationError, match="its text, its pattern, or both"):
        _ = CaseDetails.model_validate({"targets": {"diagnosis": {}}})

    with pytest.raises(ValidationError, match="Extra inputs"):
        _ = CaseDetails.model_validate(
            {"targets": {"diagnosis": {"pattern": "copd", "why": "guessed"}}}
        )


def test_only_a_warning_can_be_expected_to_be_none():
    with pytest.raises(ValidationError, match="only warning can be false"):
        _ = CaseDetails.model_validate({"targets": {"dont_miss": False}})
