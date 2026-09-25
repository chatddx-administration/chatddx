from pathlib import Path
from textwrap import dedent
from uuid import UUID

import pytest

from chatddx.core import settings
from chatddx.repo.entities.llm.pydantic import Refusal
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.families.pydantic import BranchDetailsPatch
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.parsers.inventory import ParseError, parse

INVENTORY = settings.INVENTORY_PATH / "inventory.toml"

MACHINE_ID = "00000000-0000-4000-8000-000000000001"

STACK = f"""
[machine.box]
machine_id = "{MACHINE_ID}"

[os.box]
toplevel = "/nix/store/00000000000000000000000000000000-nixos-system-box"

[llm.m]
snapshot = "/nix/store/11111111111111111111111111111111-m"

[serving.vllm]
engine = "/nix/store/22222222222222222222222222222222-vllm"

[stack.m-on-box]
machine = "box"
os = "box"
llm = "m"
serving = "vllm"
"""

SLICES = """
[instruction.i]
user = "{{case}}"
variables = ["case"]

[output.o]

[coercion.c]
mode = "native"

[reasoning.r]
effort = "default"

[sampling.s]
defaults = "generation_config"

[configuration.k]
instruction = "i"
output = "o"
coercion = "c"
reasoning = "r"
sampling = "s"
"""


def write(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(dedent(text))

    return tmp_path / next(iter(files))


def parse_text(tmp_path: Path, text: str) -> ParsedInventory:
    return parse(write(tmp_path, {"inventory.toml": text}))


@pytest.fixture(scope="module")
def inventory() -> ParsedInventory:
    return parse(INVENTORY, BranchDetailsPatch(owner="archive"))


def test_every_record_of_the_inventory_parses(inventory: ParsedInventory):
    assert {entity: len(getattr(inventory, entity)) for entity in ENTITY_NAMES} == {
        "machine": 3,
        "os": 3,
        "llm": 2,
        "serving": 5,
        "client": 2,
        "stack": 5,
        "tool": 3,
        "toolset": 2,
        "instruction": 3,
        "output": 5,
        "coercion": 5,
        "reasoning": 9,
        "sampling": 5,
        "configuration": 12,
        "case": 99,
        "scorer": 4,
    }


def test_every_branch_is_the_record_s_name_and_the_caller_s(
    inventory: ParsedInventory,
):
    for entity in ENTITY_NAMES:
        for name, (_, details) in getattr(inventory, entity).items():
            assert (details.name, details.owner) == (name, "archive")


def test_a_stack_is_the_things_it_names(inventory: ParsedInventory):
    stack, details = inventory.stack["qwen3-8b-awq@pelle"]

    assert stack.machine == inventory.machine["pelle"][0]
    assert stack.os == inventory.os["pelle"][0]
    assert stack.host_os is None
    assert stack.llm == inventory.llm["qwen3-8b-awq"][0]
    assert stack.serving == inventory.serving["qwen3-8b-awq@pelle"][0]

    assert str(details.endpoint) == "http://pelle.km:12009/v1/"
    assert details.served_name == "Qwen/Qwen3-8B-AWQ"
    assert details.api == "vllm"
    assert details.credential is None
    assert details.tags == ["rtx-3070"]


def test_a_container_s_stack_names_its_host_s_system(inventory: ParsedInventory):
    stack, _ = inventory.stack["qwen3-8b-awq@malborg"]

    assert stack.os == inventory.os["vllm-qwen3"][0]
    assert stack.host_os == inventory.os["malborg"][0]


def test_one_llm_in_two_stacks_is_one_trail(inventory: ParsedInventory):
    pelle, _ = inventory.stack["qwen3-8b-awq@pelle"]
    malborg, _ = inventory.stack["qwen3-8b-awq@malborg"]

    assert pelle.llm.fingerprint == malborg.llm.fingerprint
    assert pelle.fingerprint != malborg.fingerprint


def test_a_thing_is_its_one_identifying_field(inventory: ParsedInventory):
    machine, details = inventory.machine["malborg"]

    assert machine.model_dump(exclude={"fingerprint"}) == {
        "machine_id": UUID("ce634da7-f312-4b47-b70a-862c83a30e5e")
    }

    assert details.unreliable is False
    assert details.specs is not None
    assert [gpu.model for gpu in details.specs.gpus] == ["NVIDIA GeForce RTX 5090"]


def test_an_llm_s_facts_reach_its_details_typed(inventory: ParsedInventory):
    _, qwen3 = inventory.llm["qwen3-8b-awq"]
    _, gpt_oss = inventory.llm["gpt-oss-20b"]

    thinking = {"chat_template_kwargs": {"enable_thinking": True}}

    assert qwen3.facts.reasoning.resolve("minimal") == ("on", thinking)
    assert qwen3.facts.reasoning.resolve("default") == ("on", thinking)
    assert qwen3.facts.sampling.recommended["off"].temperature == 0.7

    match gpt_oss.facts.reasoning.resolve("off"):
        case ("off", Refusal(refused=reason)):
            assert "always reasons" in reason
        case other:
            pytest.fail(f"off is not refused on gpt-oss: {other}")

    assert gpt_oss.facts.reasoning.resolve("on") == (
        "medium",
        {"reasoning_effort": "medium"},
    )
    assert gpt_oss.facts.profile["supports_thinking"] is True


def test_a_serving_s_arguments_are_content_and_its_speed_is_not(
    inventory: ParsedInventory,
):
    serving, details = inventory.serving["gpt-oss-20b@malborg"]

    assert serving.args["reasoning-parser"] == "openai_gptoss"
    assert serving.env["VLLM_BATCH_INVARIANT"] == "1"
    assert serving.provides() == {"reasoning_parser", "tool_call_parser"}
    assert details.performance["port"] == 12009


def test_a_schema_keeps_the_order_it_was_written_in(inventory: ParsedInventory):
    output, _ = inventory.output["management-plan"]

    assert output.json_schema is not None
    assert list(output.json_schema) == [
        "$defs",
        "properties",
        "required",
        "title",
        "type",
    ]
    assert list(output.json_schema["properties"]) == [  # pyright: ignore[reportArgumentType]
        "acute_warning",
        "diagnoses",
        "management",
        "sources",
    ]


def test_a_case_s_vignette_is_read_from_its_file(inventory: ParsedInventory):
    case, details = inventory.case["DutchFall10w"]

    vignette = settings.INVENTORY_PATH / "cases/DutchFall10w.txt"

    assert case.vignette == vignette.read_bytes().decode().rstrip("\n")
    assert "\r\n" in case.vignette
    assert details.tags == ["dutch-fall"]


def test_every_case_says_its_language_and_edn_s_are_swedish(
    inventory: ParsedInventory,
):
    cases = {name: details for name, (_, details) in inventory.case.items()}

    assert all(details.language for details in cases.values())
    assert {name for name, details in cases.items() if details.language == "sv"} == {
        name for name, details in cases.items() if "edn" in (details.tags or [])
    }


def test_a_configuration_extends_another(inventory: ParsedInventory):
    plan, _ = inventory.configuration["plan"]
    shown, details = inventory.configuration["plan-shown"]

    assert shown.coercion == inventory.coercion["native-shown"][0]
    assert shown.model_copy(update={"coercion": plan.coercion}) == plan

    assert details.tags == ["ddx"]


def test_a_configuration_names_a_toolset_or_none(inventory: ParsedInventory):
    assert inventory.configuration["plan"][0].toolset is None

    toolset = inventory.configuration["plan-web"][0].toolset

    assert toolset is not None
    assert toolset == inventory.toolset["web"][0]
    assert [tool.name for tool in toolset.tools] == ["web_search"]


def test_a_dev_shell_s_client_has_no_build(inventory: ParsedInventory):
    client, details = inventory.client["chatddx-dev"]

    assert client.build is None
    assert details.packages["pydantic-ai-slim"] == "2.41.0"


def test_a_record_is_split_into_content_and_details(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        f"""
        [machine.box]
        machine_id = "{MACHINE_ID}"
        unreliable = true
        tags = ["cloud"]
        specs.location = "somewhere"
        """,
    )

    machine, details = parsed.machine["box"]

    assert machine.machine_id == UUID(MACHINE_ID)
    assert details.unreliable is True
    assert details.tags == ["cloud"]
    assert details.specs is not None
    assert details.specs.location == "somewhere"


def test_details_are_not_fingerprinted(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        f"""
        [machine.plain]
        machine_id = "{MACHINE_ID}"

        [machine.described]
        machine_id = "{MACHINE_ID}"
        unreliable = true
        specs.cpu = "a CPU"
        tags = ["a tag"]
        """,
    )

    plain, _ = parsed.machine["plain"]
    described, _ = parsed.machine["described"]

    assert plain.fingerprint == described.fingerprint


def test_a_key_that_is_neither_content_nor_detail_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"machine 'box': unknown key 'spec'"):
        _ = parse_text(
            tmp_path,
            f"""
            [machine.box]
            machine_id = "{MACHINE_ID}"
            spec = {{}}
            """,
        )


def test_another_entity_s_detail_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"machine 'box': unknown key 'endpoint'"):
        _ = parse_text(
            tmp_path,
            f"""
            [machine.box]
            machine_id = "{MACHINE_ID}"
            endpoint = "http://box:8000/v1"
            """,
        )


@pytest.mark.parametrize("key", ["name", "owner"])
def test_a_record_names_neither_itself_nor_its_owner(tmp_path: Path, key: str):
    with pytest.raises(ParseError, match=rf"case 'c': .*'{key}'"):
        _ = parse_text(
            tmp_path,
            f"""
            [case.c]
            vignette = "a case"
            {key} = "someone else"
            """,
        )


def test_a_tool_s_name_is_the_one_the_llm_sees(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [tool.search]
        name = "web_search"
        """,
    )

    tool, details = parsed.tool["search"]

    assert tool.name == "web_search"
    assert details.name == "search"


def test_an_entity_the_registry_does_not_have_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"unknown entity 'agent'"):
        _ = parse_text(
            tmp_path,
            """
            [agent.a]
            instructions = "hello"
            """,
        )


def test_an_empty_record_is_one_with_every_field_at_its_default(tmp_path: Path):
    parsed = parse_text(tmp_path, "[output.raw]\n")

    output, _ = parsed.output["raw"]

    assert (output.json_schema, output.guidance, output.views) == (None, None, {})


def test_the_caller_s_details_reach_every_branch(tmp_path: Path):
    parsed = parse(
        write(tmp_path, {"inventory.toml": STACK}),
        BranchDetailsPatch(owner="someone", collaborators=["someone else"]),
    )

    for entity in ("machine", "os", "llm", "serving", "stack"):
        for _, details in getattr(parsed, entity).values():
            assert details.owner == "someone"
            assert details.collaborators == ["someone else"]


def test_a_relation_names_a_record(tmp_path: Path):
    parsed = parse_text(tmp_path, STACK)

    stack, _ = parsed.stack["m-on-box"]

    assert stack.machine == parsed.machine["box"][0]
    assert stack.os == parsed.os["box"][0]
    assert stack.llm == parsed.llm["m"][0]
    assert stack.serving == parsed.serving["vllm"][0]


def test_a_relation_to_no_record_is_an_error(tmp_path: Path):
    with pytest.raises(
        ParseError, match=r"stack 'm-on-box': .*unknown machine 'nowhere'"
    ):
        _ = parse_text(
            tmp_path, STACK.replace('machine = "box"', 'machine = "nowhere"')
        )


def test_an_optional_relation_left_out_is_none(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        STACK
        + """
        [stack.cloud]
        machine = "box"
        llm = "m"
        """,
    )

    stack, _ = parsed.stack["cloud"]

    assert (stack.os, stack.host_os, stack.serving) == (None, None, None)


def test_a_relation_is_a_name_not_a_record_of_its_own(tmp_path: Path):
    with pytest.raises(
        ParseError, match=r"stack 'm-on-box': 'machine' names a machine"
    ):
        _ = parse_text(
            tmp_path,
            STACK.replace(
                'machine = "box"', f'machine = {{ machine_id = "{MACHINE_ID}" }}'
            ),
        )


def test_a_relation_names_one_record_not_several_to_merge(tmp_path: Path):
    with pytest.raises(
        ParseError, match=r"configuration 'k': 'sampling' names a sampling"
    ):
        _ = parse_text(
            tmp_path,
            SLICES.replace('sampling = "s"', 'sampling = ["s", "t"]')
            + """
            [sampling.t]
            defaults = "recommended"
            """,
        )


def test_a_list_relation_keeps_the_order_it_was_written_in(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [tool.a]
        name = "a"

        [tool.b]
        name = "b"

        [toolset.ba]
        tools = ["b", "a"]
        """,
    )

    toolset, _ = parsed.toolset["ba"]

    assert [tool.name for tool in toolset.tools] == ["b", "a"]


def test_a_list_relation_is_a_list_of_names(tmp_path: Path):
    with pytest.raises(ParseError, match=r"toolset 't': 'tools' names tools"):
        _ = parse_text(
            tmp_path,
            """
            [tool.a]
            name = "a"

            [toolset.t]
            tools = "a"
            """,
        )


def test_a_partial_record_cannot_be_named(tmp_path: Path):
    with pytest.raises(ParseError, match=r"stack 'm-on-box': machine 'box' is partial"):
        _ = parse_text(
            tmp_path,
            STACK.replace("[machine.box]", "[machine.box]\npartial = true"),
        )


def test_a_record_named_twice_is_one_trail(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        SLICES
        + """
        [configuration.k2]
        extends = "k"
        """,
    )

    k, _ = parsed.configuration["k"]
    k2, _ = parsed.configuration["k2"]

    assert k.fingerprint == k2.fingerprint


def test_a_record_extends_another(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [coercion.shown]
        mode = "native"
        schema_prompt = "The schema: {{schema}}"

        [coercion.prompted]
        extends = "shown"
        mode = "prompted"
        """,
    )

    shown, _ = parsed.coercion["shown"]
    prompted, _ = parsed.coercion["prompted"]

    assert prompted.mode == "prompted"
    assert prompted.schema_prompt == shown.schema_prompt


def test_what_a_record_extends_first_wins(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [sampling.cold]
        defaults = "generation_config"
        temperature = 0.1

        [sampling.hot]
        defaults = "recommended"
        temperature = 1.5
        top_p = 0.9

        [sampling.mixed]
        extends = ["cold", "hot"]
        max_tokens = 100
        """,
    )

    mixed, _ = parsed.sampling["mixed"]

    assert (mixed.defaults, mixed.temperature, mixed.top_p, mixed.max_tokens) == (
        "generation_config",
        0.1,
        0.9,
        100,
    )


def test_a_record_s_own_keys_win_over_what_it_extends(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [reasoning.on]
        effort = "on"

        [reasoning.on-budget]
        extends = "on"
        effort = "high"
        budget = 512
        """,
    )

    assert parsed.reasoning["on-budget"][0].effort == "high"


def test_extending_is_shallow(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [serving.base]
        engine = "/nix/store/22222222222222222222222222222222-vllm"
        args.max-model-len = 8192
        args.seed = 0

        [serving.long]
        extends = "base"
        args.max-model-len = 32768
        """,
    )

    assert parsed.serving["long"][0].args == {"max-model-len": 32768}


def test_extends_goes_down_a_chain(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [sampling.a]
        defaults = "generation_config"
        temperature = 0.2

        [sampling.b]
        extends = "a"
        top_k = 20

        [sampling.c]
        extends = "b"
        max_tokens = 64
        """,
    )

    c, _ = parsed.sampling["c"]

    assert (c.defaults, c.temperature, c.top_k, c.max_tokens) == (
        "generation_config",
        0.2,
        20,
        64,
    )


def test_a_partial_record_is_a_template_and_nothing_more(tmp_path: Path):
    parsed = parse_text(
        tmp_path,
        """
        [reasoning.budgeted]
        partial = true
        budget = 1024

        [reasoning.on-budgeted]
        extends = "budgeted"
        effort = "on"
        """,
    )

    assert list(parsed.reasoning) == ["on-budgeted"]
    assert parsed.reasoning["on-budgeted"][0].budget == 1024


def test_a_record_that_extends_itself_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"sampling 'a' extends itself: a -> b -> a"):
        _ = parse_text(
            tmp_path,
            """
            [sampling.a]
            extends = "b"
            defaults = "generation_config"

            [sampling.b]
            extends = "a"
            defaults = "generation_config"
            """,
        )


def test_extending_no_record_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"sampling 'a': .*unknown sampling 'nothing'"):
        _ = parse_text(
            tmp_path,
            """
            [sampling.a]
            extends = "nothing"
            defaults = "generation_config"
            """,
        )


@pytest.mark.parametrize("value", ["true", '"yes"', "1"])
def test_extends_is_a_name_or_names_and_partial_is_a_flag(tmp_path: Path, value: str):
    with pytest.raises(ParseError, match=r"sampling 'a': "):
        _ = parse_text(
            tmp_path,
            f"""
            [sampling.a]
            defaults = "generation_config"
            {"extends" if value == "true" else "partial"} = {value}
            """,
        )


def test_an_inventory_extends_other_files(tmp_path: Path):
    parsed = parse(
        write(
            tmp_path,
            {
                "inventory.toml": 'extends = ["parts/stack.toml"]\n' + SLICES,
                "parts/stack.toml": STACK,
            },
        )
    )

    assert list(parsed.stack) == ["m-on-box"]
    assert list(parsed.configuration) == ["k"]


def test_the_extending_file_wins(tmp_path: Path):
    parsed = parse(
        write(
            tmp_path,
            {
                "inventory.toml": """
                extends = "base.toml"

                [case.c]
                vignette = "mine"
                """,
                "base.toml": """
                [case.c]
                vignette = "theirs"

                [case.d]
                vignette = "only theirs"
                """,
            },
        )
    )

    assert parsed.case["c"][0].vignette == "mine"
    assert parsed.case["d"][0].vignette == "only theirs"


def test_a_record_extends_one_in_another_file(tmp_path: Path):
    parsed = parse(
        write(
            tmp_path,
            {
                "inventory.toml": """
                extends = "base.toml"

                [sampling.capped]
                extends = "recommended"
                max_tokens = 4096
                """,
                "base.toml": """
                [sampling.recommended]
                defaults = "recommended"
                """,
            },
        )
    )

    capped, _ = parsed.sampling["capped"]

    assert (capped.defaults, capped.max_tokens) == ("recommended", 4096)


def test_an_inventory_that_extends_itself_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"a\.toml -> b\.toml -> a\.toml"):
        _ = parse(
            write(
                tmp_path,
                {
                    "a.toml": 'extends = "b.toml"',
                    "b.toml": 'extends = "a.toml"',
                },
            )
        )


def test_a_path_key_reads_a_file_next_to_the_file_that_names_it(tmp_path: Path):
    parsed = parse(
        write(
            tmp_path,
            {
                "inventory.toml": 'extends = "parts/slices.toml"',
                "parts/slices.toml": """
                [instruction.i]
                system_path = "templates/system.txt"
                user = "{{case}}"
                variables = ["case", "output_guidance"]

                [output.o]
                json_schema_path = "schemas/o.json"
                views.differential = "$.diagnoses[*]"
                """,
                "parts/templates/system.txt": "{{output_guidance}}\n",
                "parts/schemas/o.json": """
                {
                  "type": "object",
                  "properties": {
                    "diagnoses": {"type": "array", "items": {"type": "string"}},
                    "certainty": {"type": "number"}
                  }
                }
                """,
            },
        )
    )

    instruction, _ = parsed.instruction["i"]
    output, _ = parsed.output["o"]

    assert instruction.system == "{{output_guidance}}"
    assert output.json_schema is not None
    assert list(output.json_schema["properties"]) == ["diagnoses", "certainty"]  # pyright: ignore[reportArgumentType]


def test_a_toml_file_loads_as_a_table(tmp_path: Path):
    parsed = parse(
        write(
            tmp_path,
            {
                "inventory.toml": """
                [tool.t]
                name = "t"
                parameters_path = "t.toml"
                """,
                "t.toml": """
                type = "object"
                properties.query.type = "string"
                """,
            },
        )
    )

    assert parsed.tool["t"][0].parameters == {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }


def test_only_a_record_s_own_keys_read_files(tmp_path: Path):
    parsed = parse(
        write(
            tmp_path,
            {
                "inventory.toml": """
                [output.o]
                json_schema_path = "o.json"
                """,
                "o.json": """
                {"type": "object", "properties": {"image_path": {"type": "string"}}}
                """,
            },
        )
    )

    output, _ = parsed.output["o"]

    assert output.json_schema == {
        "type": "object",
        "properties": {"image_path": {"type": "string"}},
    }


def test_a_value_and_its_path_together_are_an_error(tmp_path: Path):
    with pytest.raises(
        ParseError, match=r"case 'c': both 'vignette' and 'vignette_path'"
    ):
        _ = parse(
            write(
                tmp_path,
                {
                    "inventory.toml": """
                    [case.c]
                    vignette = "here"
                    vignette_path = "c.txt"
                    """,
                    "c.txt": "there",
                },
            )
        )


def test_a_path_to_no_file_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"output 'o': .*nowhere\.json"):
        _ = parse_text(
            tmp_path,
            """
            [output.o]
            json_schema_path = "nowhere.json"
            """,
        )


def test_a_file_of_no_known_kind_is_an_error(tmp_path: Path):
    with pytest.raises(ParseError, match=r"no loader for '\.yaml'"):
        _ = parse(
            write(
                tmp_path,
                {
                    "inventory.toml": """
                    [output.o]
                    json_schema_path = "o.yaml"
                    """,
                    "o.yaml": "type: object",
                },
            )
        )


def test_a_case_s_vignette_is_its_file_unless_it_says_otherwise(tmp_path: Path):
    parsed = parse(
        write(
            tmp_path,
            {
                "inventory.toml": """
                [case.written]
                vignette = "written here"

                [case.filed]
                tags = ["a dataset"]
                """,
                "cases/filed.txt": "filed away\n",
            },
        )
    )

    assert parsed.case["written"][0].vignette == "written here"
    assert parsed.case["filed"][0].vignette == "filed away"


def test_an_entity_s_table_holds_tables(tmp_path: Path):
    with pytest.raises(ParseError, match=r"case 'c' must be a table"):
        _ = parse_text(
            tmp_path,
            """
            [case]
            c = "a case"
            """,
        )


def test_a_record_that_does_not_validate_says_which_it_is(tmp_path: Path):
    with pytest.raises(ParseError, match=r"coercion 'p': .*schema_prompt"):
        _ = parse_text(
            tmp_path,
            """
            [coercion.p]
            mode = "prompted"
            """,
        )


def test_an_invalid_record_is_reported_as_itself_not_as_what_names_it(
    tmp_path: Path,
):
    with pytest.raises(ParseError, match=r"coercion 'c': ") as raised:
        _ = parse_text(tmp_path, SLICES.replace('mode = "native"', 'mode = "nativ"'))

    assert "configuration" not in str(raised.value)


def test_invalid_details_say_which_record_they_are(tmp_path: Path):
    with pytest.raises(ParseError, match=r"llm 'm': .*source"):
        _ = parse_text(
            tmp_path,
            """
            [llm.m]
            snapshot = "/nix/store/11111111111111111111111111111111-m"
            source = "Qwen/Qwen3-8B-AWQ@main"
            """,
        )


def test_an_error_says_which_file_the_record_is_in(tmp_path: Path):
    with pytest.raises(ParseError, match=r"reasoning 'r': .* \(parts/slices\.toml\)$"):
        _ = parse(
            write(
                tmp_path,
                {
                    "inventory.toml": 'extends = "parts/slices.toml"',
                    "parts/slices.toml": """
                    [reasoning.r]
                    effort = "maximal"
                    """,
                },
            )
        )
