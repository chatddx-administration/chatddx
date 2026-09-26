import pytest

from chatddx.conftest import Say
from chatddx.repl.commands import COMMANDS, complete, handle
from chatddx.repl.shell import Repl

pytestmark = pytest.mark.django_db


def test_the_prompt_shows_the_cell(repl: Repl, say: Say):
    assert repl.prompt == "alex #none> "

    _ = say("use free-text")
    assert repl.prompt == "alex free-text #none> "

    _ = say("on qwen3-8b-awq@fake")
    assert repl.prompt == "alex free-text×qwen3-8b-awq@fake #none> "


def test_help_lists_every_command_with_the_words_it_takes(say: Say):
    written = say("help")

    for verb in COMMANDS:
        assert verb in written

    assert "set SLICE VARIATION" in written
    assert "run CASE [SEED]" in written
    assert "batch TAG..." in written


def test_what_it_doesn_t_know_is_said_and_nothing_changes(repl: Repl, say: Say):
    written = say("use nope", "cell free-text nope", "on", "frobnicate", "use 'x")

    assert "no configuration 'nope' for alex" in written
    assert "no stack 'nope' for alex" in written
    assert "usage: on STACK" in written
    assert "no command 'frobnicate': try help" in written
    assert "No closing quotation" in written
    assert repl.cell.configuration is None


def test_quit_leaves(repl: Repl):
    assert handle(repl, "quit") is False
    assert handle(repl, "exit") is False


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
    assert complete(names, "show c") == ["client", "coercion", "configuration", "case"]
    assert complete(names, "show case case-") == ["case-1", "case-2"]
    assert complete(names, "set r") == ["reasoning"]
    assert complete(names, "set reasoning o") == ["off", "on", "on-budget-2048"]
    assert complete(names, "set toolset ") == ["sentinel", "web", "none"]
    assert complete(names, "set reasoning n") == []
    assert complete(names, "frobnicate x") == []


def test_a_word_that_repeats_completes_each_time_but_as_it_was_given():
    names = {"batch:tag": ["dutch-fall", "edn", "openxddx"]}

    assert complete(names, "batch ") == ["dutch-fall", "edn", "openxddx"]
    assert complete(names, "batch e") == ["edn"]
    assert complete(names, "batch edn ") == ["dutch-fall", "openxddx"]
    assert complete(names, "batch edn openxddx d") == ["dutch-fall"]


def test_show_completes_tags_after_tag_and_one_name_after_an_entity():
    names = {"batch:tag": ["edn", "openxddx"], "case": ["case-1", "case-2"]}

    assert complete(names, "show t") == ["tag", "tool", "toolset"]
    assert complete(names, "show tag ") == ["edn", "openxddx"]
    assert complete(names, "show tag edn ") == ["openxddx"]
    assert complete(names, "show case case-1 ") == []


def test_the_tags_complete_as_the_cases_have_them(repl: Repl):
    assert repl.completions()["batch:tag"] == ["tag-1", "tag-2"]
