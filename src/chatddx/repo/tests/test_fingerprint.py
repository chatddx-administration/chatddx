"""
What a fingerprint is a hash of: a trail's content, in canonical form
(data-generation.md §3.2), with a scheme and version in front of it.
"""

import hashlib
import math
import re

import pytest

from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.output.pydantic import OutputTrailIn
from chatddx.repo.entities.serving.pydantic import ServingTrailIn
from chatddx.repo.entities.tool.pydantic import ToolTrailIn
from chatddx.repo.families.canonical import (
    canonical_json,
    fingerprint,
    fingerprint_digest,
    ordered,
)
from chatddx.repo.inventories import InventoryTrailIn
from chatddx.repo.names import closure_branch_name, short_fingerprint

ENGINE = "/nix/store/22222222222222222222222222222222-vllm"


# ---------------------------------------------------------- canonical form


@pytest.mark.parametrize(
    "number, written",
    [
        (0, "0"),
        (-0.0, "0"),
        (20, "20"),
        (1.0, "1"),
        (0.6, "0.6"),
        (-2.5, "-2.5"),
        (0.1 + 0.2, "0.30000000000000004"),
        (0.000001, "0.000001"),
        (1e-7, "1e-7"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (1.5e21, "1.5e+21"),
        (5e-324, "5e-324"),
        (2**53, "9007199254740992"),
        # past 2^53 a JSON number is a double, as ECMAScript prints it
        (2**60, "1152921504606847000"),
    ],
)
def test_a_number_is_written_as_ecmascript_writes_it(number: float, written: str):
    assert canonical_json(number) == written


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
def test_a_number_json_has_no_form_for_is_an_error(number: float):
    with pytest.raises(ValueError, match="no JSON form"):
        _ = canonical_json(number)


def test_keys_are_sorted_by_their_utf16_code_units():
    # "😀" is a surrogate pair, D83D DE00: past "€" at 20AC in UTF-16, though
    # not in code points
    assert (
        canonical_json({"😀": 1, "€": 2, "b": 3, "a": 4})
        == '{"a":4,"b":3,"€":2,"😀":1}'
    )


def test_a_string_escapes_only_what_json_must():
    assert canonical_json('é"\\\n\u0001/') == '"é\\"\\\\\\n\\u0001/"'


def test_nothing_but_json_has_a_canonical_form():
    with pytest.raises(TypeError, match="not a JSON value"):
        _ = canonical_json({"a": {1, 2}})


def test_ordered_keeps_every_object_s_order_where_the_sort_cant_reach_it():
    assert canonical_json(
        ordered({"b": {"d": 1, "c": 2}, "a": [{"f": 3, "e": 4}]})
    ) == (
        '{"ordered":[["b",{"ordered":[["d",1],["c",2]]}],'
        + '["a",[{"ordered":[["f",3],["e",4]]}]]]}'
    )


def test_an_ordered_object_is_not_a_list_of_pairs():
    """A default that is an object and one that is a list are two schemas."""
    as_object = ordered({"default": {"a": 1}})
    as_pairs = ordered({"default": [["a", 1]]})

    assert canonical_json(as_object) != canonical_json(as_pairs)


# --------------------------------------------------------------- the scheme


def test_a_fingerprint_names_its_scheme_and_version():
    digest = hashlib.sha256(b'{"a":1}').hexdigest()

    assert fingerprint({"a": 1}) == f"cddx-trail/1:sha256:{digest}"
    assert fingerprint_digest(fingerprint({"a": 1})) == digest


def test_a_short_fingerprint_reads_the_hex_part():
    long = fingerprint({"a": 1})

    assert short_fingerprint(long) == fingerprint_digest(long)[:6]
    assert (
        closure_branch_name("sampling", long)
        == f"sampling {fingerprint_digest(long)[:6]}"
    )


def test_every_trail_of_the_inventory_has_a_fingerprint_of_the_scheme(
    trails: InventoryTrailIn,
):
    for entity, records in trails:
        for name, trail in records.items():
            assert re.fullmatch(
                r"cddx-trail/1:sha256:[0-9a-f]{64}", trail.fingerprint
            ), f"{entity} {name}"


# ------------------------------------------------------------- what counts


def test_a_schema_s_order_is_content():
    """
    A constrained decoder emits keys in the order `properties` gives them, so
    the model commits to its answer before or after its reasons by it.
    """
    reasons_first = OutputTrailIn(
        schema={
            "type": "object",
            "properties": {
                "rationale": {"type": "string"},
                "diagnosis": {"type": "string"},
            },
        }
    )
    answer_first = OutputTrailIn(
        schema={
            "type": "object",
            "properties": {
                "diagnosis": {"type": "string"},
                "rationale": {"type": "string"},
            },
        }
    )

    assert reasons_first.fingerprint != answer_first.fingerprint


def test_a_tool_s_parameters_keep_their_order_too():
    def tool(*names: str) -> ToolTrailIn:
        return ToolTrailIn(
            name="t",
            parameters={
                "type": "object",
                "properties": {n: {"type": "string"} for n in names},
            },
        )

    assert tool("a", "b").fingerprint != tool("b", "a").fingerprint


def test_what_is_read_as_a_set_is_not_ordered():
    """vLLM reads its arguments and environment as sets."""
    one = ServingTrailIn(engine=ENGINE, args={"seed": 0, "max-model-len": 8192})
    other = ServingTrailIn(engine=ENGINE, args={"max-model-len": 8192, "seed": 0})

    assert one.fingerprint == other.fingerprint


def test_two_spellings_of_one_argument_are_one_argument():
    one = ServingTrailIn(engine=ENGINE, args={"--max_model_len": 8192})
    other = ServingTrailIn(engine=ENGINE, args={"max-model-len": 8192})

    assert one.args == {"max-model-len": 8192}
    assert one.fingerprint == other.fingerprint


def test_a_relation_stands_in_as_its_fingerprint(
    trails: InventoryTrailIn,
):
    plan = trails.configuration["plan"]

    assert plan.canonical_input()["output"] == plan.output.fingerprint

    rewritten = plan.model_copy(
        update={"output": plan.output.model_copy(update={"guidance": "Rewritten."})}
    )

    assert rewritten.fingerprint != plan.fingerprint


def test_a_relation_left_out_is_null_in_the_canonical_input(
    trails: InventoryTrailIn,
):
    plan = trails.configuration["plan"]
    plan_web = trails.configuration["plan-web"]

    assert plan.canonical_input()["toolset"] is None
    assert plan_web.canonical_input()["toolset"] == plan_web.toolset.fingerprint  # pyright: ignore[reportOptionalMemberAccess]
    assert plan.fingerprint != plan_web.fingerprint


def test_the_fingerprint_is_computed_not_kept(
    trails: InventoryTrailIn,
):
    plan = trails.configuration["plan"]
    before = plan.fingerprint

    plan.output.guidance = (plan.output.guidance or "") + " Now."

    assert plan.fingerprint != before


def test_the_same_content_is_the_same_fingerprint_whoever_writes_it(
    trails: InventoryTrailIn,
):
    plan = trails.configuration["plan"]

    assert ConfigurationTrailIn.model_validate(plan.model_dump()).fingerprint == (
        plan.fingerprint
    )
