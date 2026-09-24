import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from rich.console import Console
from typer.testing import CliRunner

from chatddx.core.repl import Repl, complete
from chatddx.dx.fake_vllm import FakeTransport, stream
from chatddx.manage import app
from chatddx.repo.entities.tool.django import ToolBranchModel

pytestmark = pytest.mark.django_db

# the inventory without its case corpus, and two cases: case-1 and case-2
INVENTORY = Path(__file__).parents[2] / "repo/tests/data/test-inventory.toml"

type Say = Callable[..., str]


def provision(*options: str) -> None:
    result = CliRunner().invoke(
        app, ["init-data", "alex", "--inventory", str(INVENTORY), *options]
    )
    assert result.exit_code == 0, result.output


@pytest.fixture
def fake() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def repl(fake: FakeTransport) -> Repl:
    provision()
    return Repl("alex", Console(record=True, width=200), transport=fake)


@pytest.fixture
def say(repl: Repl) -> Say:
    """Hand the repl its lines, and answer with what it wrote back."""

    def say(*lines: str) -> str:
        for line in lines:
            assert repl.handle(line)

        return repl.console.export_text()

    return say


def test_the_prompt_shows_the_cell(repl: Repl, say: Say):
    assert repl.prompt == "alex> "

    _ = say("use free-text")
    assert repl.prompt == "alex free-text> "

    _ = say("on qwen3-8b-awq@fake")
    assert repl.prompt == "alex free-text×qwen3-8b-awq@fake> "


def test_stacks_are_listed_with_whose_they_are(say: Say):
    written = say("stacks")

    for stack in (
        "qwen3-8b-awq@pelle",
        "gpt-oss-20b@malborg",
        "qwen3-8b-awq@malborg",
        "qwen3-8b-awq@fake",
        "gpt-oss-20b@fake",
    ):
        assert stack in written

    assert "http://localhost:12099/v1/" in written
    assert "archive" in written


def test_configurations_are_listed_with_their_variations(say: Say):
    row = next(
        line for line in say("configurations").splitlines() if "free-text" in line
    )

    assert row.split() == [
        "free-text",
        "ddx",
        "free-text",
        "auto",
        "default",
        "recommended",
        "—",
        "archive",
    ]


def test_show_sets_each_variation_beside_what_it_resolves_to(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "show")

    assert "cell: free-text × qwen3-8b-awq@fake" in written
    assert (
        "the model's default, 'on': chat_template_kwargs.enable_thinking=true"
        in written
    )
    assert "recommended for 'on'" in written
    assert "List the plausible diagnoses, one per line, most likely first." in written


def test_show_reports_a_refused_cell_slice_by_slice(say: Say):
    written = say("cell plan-web gpt-oss-20b@fake", "set reasoning off", "show")

    # the reasoning is refused; the rest resolves regardless
    assert written.count("refused:") == 1
    assert "refused: always reasons" in written
    assert "response_format: guided decoding holds the answer" in written
    assert "offered: web_search" in written


def test_run_streams_a_trial_of_the_cell(say: Say, fake: FakeTransport):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "trial: free-text × qwen3-8b-awq@fake × case-1" in written
    assert "[thinking] I am the fake vLLM" in written
    assert "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C" in written

    [request] = fake.requests
    assert request["messages"][-1] == {"role": "user", "content": "case payload 1"}


def test_run_sends_nothing_for_a_refused_cell(say: Say, fake: FakeTransport):
    written = say("cell baseline gpt-oss-20b@fake", "set reasoning off", "run case-1")

    assert "refused: reasoning: always reasons" in written
    assert fake.requests == []


def test_run_needs_a_whole_cell(say: Say, fake: FakeTransport):
    written = say("use free-text", "run case-1")

    assert "the cell needs a configuration and a stack" in written
    assert fake.requests == []


def test_what_it_doesn_t_know_is_said_and_nothing_changes(repl: Repl, say: Say):
    written = say("use nope", "cell free-text nope", "on", "frobnicate")

    assert "no configuration 'nope' for alex" in written
    assert "no stack 'nope' for alex" in written
    assert "usage: on STACK" in written
    assert "no command 'frobnicate': try help" in written
    assert repl.configuration is None


# ----------------------------------------------------------------------- set


def test_set_puts_another_variation_in_the_cell(
    repl: Repl, say: Say, fake: FakeTransport
):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "run case-1")

    assert repl.prompt == "alex free-text+reasoning=off×qwen3-8b-awq@fake> "
    assert "trial: free-text+reasoning=off × qwen3-8b-awq@fake × case-1" in written

    # Qwen3 with its thinking switched off, and nothing thought
    [request] = fake.requests
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert "[thinking]" not in written


def test_show_says_what_is_set_and_what_the_configuration_has(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "show")

    assert "off (set; free-text has default)" in written
    assert "chat_template_kwargs.enable_thinking=false" in written
    assert "recommended for 'off'" in written


def test_setting_the_configuration_s_own_variation_unsets_it(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set reasoning off")
    _ = say("set reasoning default")

    assert repl.prompt == "alex free-text×qwen3-8b-awq@fake> "


def test_none_takes_the_toolset_out(repl: Repl, say: Say, fake: FakeTransport):
    written = say("cell test-tools qwen3-8b-awq@fake", "set toolset none", "show")

    assert repl.prompt == "alex test-tools+toolset=none×qwen3-8b-awq@fake> "
    assert "none (set; test-tools has sentinel)" in written

    _ = say("run case-1")

    [request] = fake.requests
    assert "tools" not in request

    # and back: the configuration's own toolset unsets it
    _ = say("set toolset sentinel")
    assert repl.prompt == "alex test-tools×qwen3-8b-awq@fake> "


def test_none_of_a_toolset_it_has_none_of_is_nothing_set(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set toolset none")

    assert repl.prompt == "alex free-text×qwen3-8b-awq@fake> "


def test_use_puts_a_configuration_in_as_it_is(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "use free-text")

    assert repl.prompt == "alex free-text×qwen3-8b-awq@fake> "


def test_what_a_stack_refuses_is_said_before_anything_is_sent(
    say: Say, fake: FakeTransport
):
    written = say("cell free-text gpt-oss-20b@fake", "set reasoning off", "run case-1")

    assert "refused: reasoning: always reasons" in written
    assert fake.requests == []


def test_set_says_what_it_can_t_set(say: Say):
    written = say("set reasoning off", "use free-text", "set colour red")
    written += say("set reasoning nope")

    assert "the cell has no configuration to set it in" in written
    assert (
        "no slice 'colour': instruction, output, coercion, reasoning, sampling, toolset"
        in written
    )
    assert "no reasoning 'nope' for alex" in written
    assert "a configuration always has a reasoning: only a toolset can be none" in say(
        "set reasoning none"
    )


# ----------------------------------------------------------------- reasoning


REASONING = (
    "default",
    "off",
    "on",
    "on-budget-2048",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)


def row_names(table: str) -> list[str]:
    """A table's first column, where a row starts rather than wraps on."""
    cells = [
        line.split("│")[1].strip()
        for line in table.splitlines()
        if line.startswith("│")
    ]
    return [cell for cell in cells if cell]


def test_the_reasoning_table_sets_every_variation_on_every_stack(say: Say):
    written = say("reasoning")

    assert row_names(written) == list(REASONING)

    # every stack is named once; those alike share a column
    for stack in ("gpt-oss-20b@fake", "qwen3-8b-awq@pelle", "qwen3-8b-awq@fake"):
        assert written.count(stack) == 1

    assert "refused: always reasons" in written
    assert "thinking_token_budget=2048" in written
    # pelle has no reasoning parser to spend a budget
    assert "a budget needs a reasoning parser" in written
    assert "the cell has no configuration: no sampling is pulled in" in written


def test_the_reasoning_table_pulls_in_the_cell_s_sampling(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning high", "reasoning")

    assert "▸ high" in written
    assert "▸ qwen3-8b-awq@fake" in written
    assert "sampling as 'recommended' pulls it in" in written
    # Qwen3's recommendation with its thinking off
    assert "temperature=0.7 top_p=0.8" in written


# ------------------------------------------------------------------ answers


def test_a_structured_answer_is_judged_and_its_views_read(say: Say):
    written = say("cell plan qwen3-8b-awq@fake", "run case-1")

    assert '"acute_warning": "fake acute warning"' in written
    assert "valid" in written
    assert "differential\n  1. fake diagnosis 1\n  2. fake diagnosis 2" in written


def test_free_text_has_its_views_read_too(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "differential\n  1. Fake diagnosis A" in written
    assert "valid" not in written


def test_tool_mode_shows_the_call_the_answer_is_given_through(say: Say):
    written = say("cell diagnoses-tool qwen3-8b-awq@fake", "run case-1")

    assert '[final_result] {"diagnoses": ["fake diagnoses 1"' in written
    assert "valid" in written


def test_an_answer_that_doesn_t_hold_says_why():
    provision()

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        # any object at all, where the plan's schema wants its fields
        body["response_format"] = {"type": "json_object"}
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    repl = Repl("alex", Console(record=True, width=200), httpx2.MockTransport(handler))
    _ = repl.handle("cell plan qwen3-8b-awq@fake")
    _ = repl.handle("run case-1")

    written = repl.console.export_text()
    assert "invalid: $: 'acute_warning' is a required property" in written
    # its views read nothing from it
    assert "differential\n  nothing" in written


def test_an_answer_that_doesn_t_parse_says_so():
    provision()

    def handler(_request: httpx2.Request) -> httpx2.Response:
        # prose, where the schema wants a document
        body: dict[str, Any] = {"model": "Qwen/Qwen3-8B-AWQ", "messages": []}
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    repl = Repl("alex", Console(record=True, width=200), httpx2.MockTransport(handler))
    _ = repl.handle("cell challenge-coercion-prompted qwen3-8b-awq@fake")
    _ = repl.handle("run case-1")

    assert "invalid: the answer doesn't parse" in repl.console.export_text()


def test_a_run_says_when_no_thinking_came_back_though_it_was_asked_for():
    provision()

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        # as if the grammar had kept the model from thinking
        body["chat_template_kwargs"] = {"enable_thinking": False}
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    repl = Repl("alex", Console(record=True, width=200), httpx2.MockTransport(handler))
    _ = repl.handle("cell diagnoses qwen3-8b-awq@fake")
    _ = repl.handle("run case-1")

    written = repl.console.export_text()
    assert "no thinking came back, though reasoning resolved to 'on'" in written
    assert "valid" in written


def test_thinking_no_reasoning_parser_took_out_is_labelled_so():
    provision()
    fake = FakeTransport(reasoning_parser=False)

    repl = Repl("alex", Console(record=True, width=200), transport=fake)
    _ = repl.handle("cell free-text qwen3-8b-awq@fake")
    _ = repl.handle("run case-1")

    written = repl.console.export_text()
    assert "[thinking in content] I am the fake vLLM" in written
    assert "Fake diagnosis A" in written
    assert "no thinking came back" not in written


def test_run_takes_the_trial_s_seed(say: Say, fake: FakeTransport):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1 42", "run case-1 x")

    assert "trial: free-text × qwen3-8b-awq@fake × case-1 (seed 42)" in written
    assert fake.requests[0]["seed"] == 42
    assert "a seed is a whole number, not 'x'" in written
    assert len(fake.requests) == 1


# ------------------------------------------------------------------- toolset


def test_calls_and_what_they_returned_stream_as_they_come(
    say: Say, fake: FakeTransport
):
    written = say("cell test-tools qwen3-8b-awq@fake", "run case-1")

    assert "[sentinel_string] {}\n[result] asdf" in written
    assert '[sentinel_op] {"v1": 1, "v2": 1}\n[result] 0' in written
    assert "Fake diagnosis A" in written
    # a round for each tool, then the answer
    assert "3 requests)" in written
    assert len(fake.requests) == 3


def test_show_says_which_tools_the_model_is_offered(say: Say):
    written = say("cell plan-web qwen3-8b-awq@fake", "show")

    assert "offered: web_search" in written
    # and the guidance fills its slot
    assert "You have access to a web_search tool." in written


def test_a_toolset_can_be_set_in_any_configuration(say: Say, fake: FakeTransport):
    written = say(
        "cell baseline qwen3-8b-awq@fake", "set toolset sentinel", "run case-1"
    )

    assert "[result] asdf" in written
    assert [t["function"]["name"] for t in fake.requests[0]["tools"]] == [
        "sentinel_string",
        "sentinel_op",
    ]


def test_a_model_still_calling_tools_is_stopped():
    provision()

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        # as if nothing had been called yet: the fake calls on and on
        text = "".join(stream(body | {"messages": body["messages"][:1]}))
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=text.encode()
        )

    repl = Repl("alex", Console(record=True, width=200), httpx2.MockTransport(handler))
    _ = repl.handle("cell test-tools qwen3-8b-awq@fake")
    _ = repl.handle("run case-1")

    assert "stopped: still calling tools after 5 rounds" in repl.console.export_text()


def test_a_tool_with_nothing_to_run_is_said_before_anything_is_sent(
    say: Say, fake: FakeTransport
):
    _ = ToolBranchModel.objects.filter(name="sentinel_op").update(details={})

    written = say("cell test-tools qwen3-8b-awq@fake", "run case-1")

    assert "nothing to run for sentinel_op: no implementation" in written
    assert fake.requests == []


def test_show_says_how_the_answer_is_held_and_what_the_facts_note(say: Say):
    written = say("cell diagnoses-tool gpt-oss-20b@fake", "show")

    assert "a final_result tool holds the answer to the schema" in written
    assert "the model reads it as the tool's parameters" in written
    assert "vLLM ignores tool_choice = required for gpt-oss" in written


def test_show_shows_a_schema_prompt_and_clips_a_long_one(say: Say):
    written = say("cell plan-shown qwen3-8b-awq@fake", "show")

    assert "the model reads it through schema_prompt" in written
    assert "Answer with a JSON object that matches this JSON Schema" in written
    assert "more lines" in written


def test_quit_leaves(repl: Repl):
    assert repl.handle("quit") is False


def test_a_configuration_of_one_s_own_shadows_the_archive_s(fake: FakeTransport):
    provision("--with-giftbag")
    repl = Repl("alex", Console(record=True, width=200), transport=fake)

    assert repl.handle("use plan")
    assert repl.configuration is not None
    assert repl.configuration.owner.name == "alex"


def test_the_repl_needs_an_identity():
    result = CliRunner().invoke(app, ["repl", "nobody"])

    assert result.exit_code == 1
    assert "no identity 'nobody'" in result.stderr


def test_it_completes_a_command_and_then_its_names():
    names = {
        "configuration": ["free-text", "plan", "plan-web"],
        "stack": ["qwen3-8b-awq@fake", "qwen3-8b-awq@pelle"],
        "case": ["case-1", "case-2"],
        "reasoning": ["default", "high", "off", "on", "on-budget-2048"],
        "toolset": ["sentinel", "web"],
    }

    assert complete(names, "us") == ["use"]
    assert complete(names, "use pl") == ["plan", "plan-web"]
    assert complete(names, "cell plan qwen3-8b-awq@") == [
        "qwen3-8b-awq@fake",
        "qwen3-8b-awq@pelle",
    ]
    assert complete(names, "run case-") == ["case-1", "case-2"]
    assert complete(names, "show ") == []
    assert complete(names, "set r") == ["reasoning"]
    assert complete(names, "set reasoning o") == ["off", "on", "on-budget-2048"]
    # a toolset can be none
    assert complete(names, "set toolset ") == ["sentinel", "web", "none"]
    assert complete(names, "set reasoning n") == []


def test_a_session_can_be_piped_in(tmp_path: Path):
    provision()

    result = CliRunner().invoke(
        app,
        ["repl", "alex", "--history", str(tmp_path / "history")],
        input="cell free-text qwen3-8b-awq@fake\nshow\nquit\n",
    )

    assert result.exit_code == 0, result.output
    assert "alex> cell free-text qwen3-8b-awq@fake\n" in result.output
    assert "alex free-text×qwen3-8b-awq@fake> show\n" in result.output
    assert "the model's default, 'on'" in result.output
