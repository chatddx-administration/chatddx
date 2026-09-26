import pytest

from chatddx.conftest import Recommit, Say
from chatddx.core.models import IdentityModel
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repl.commands import handle
from chatddx.repl.shell import Repl
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.reasoning.django import ReasoningBranchModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def bobs(repl: Repl, recommit: Recommit) -> None:
    """The archive's plan and free-text as bob's own, shared with alice."""
    shared = [repl.identity]
    recommit(
        "configuration", "plan", name="bobs-plan", owner="bob", collaborators=shared
    )
    recommit("configuration", "free-text", owner="bob", collaborators=shared)


def test_set_puts_another_variation_in_the_cell(
    repl: Repl, say: Say, fake: FakeTransport
):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "run case-1")

    assert repl.prompt == "alice free-text+reasoning=off×qwen3-8b-awq@fake #none> "
    assert "trial: free-text+reasoning=off × qwen3-8b-awq@fake × case-1" in written

    [request] = fake.requests
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert "[thinking]" not in written


def test_setting_the_configuration_s_own_variation_unsets_it(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set reasoning off")
    _ = say("set reasoning default")

    assert repl.prompt == "alice free-text×qwen3-8b-awq@fake #none> "


def test_none_takes_the_toolset_out(repl: Repl, say: Say, fake: FakeTransport):
    written = say("cell test-tools qwen3-8b-awq@fake", "set toolset none", "show")

    assert repl.prompt == "alice test-tools+toolset=none×qwen3-8b-awq@fake #none> "
    assert "none (set; test-tools has sentinel)" in written

    _ = say("run case-1")

    [request] = fake.requests
    assert "tools" not in request

    _ = say("set toolset sentinel")
    assert repl.prompt == "alice test-tools×qwen3-8b-awq@fake #none> "


def test_none_of_a_toolset_it_has_none_of_is_nothing_set(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set toolset none")

    assert repl.prompt == "alice free-text×qwen3-8b-awq@fake #none> "


def test_use_puts_a_configuration_in_as_it_is(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "use free-text")

    assert repl.prompt == "alice free-text×qwen3-8b-awq@fake #none> "


def test_set_says_what_it_can_t_set(say: Say):
    written = say("set reasoning off", "use free-text", "set colour red")
    written += say("set reasoning nope")

    assert "the cell has no configuration to set it in" in written
    assert (
        "no slice 'colour': instruction, output, coercion, reasoning, sampling, toolset"
        in written
    )
    assert "no reasoning 'nope' for alice" in written
    assert "a configuration always has a reasoning: only a toolset can be none" in say(
        "set reasoning none"
    )


def test_save_keeps_the_cell_as_a_configuration_of_one_s_own(repl: Repl, say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "save quiet")

    assert "saved as quiet: created" in written
    assert repl.prompt == "alice quiet×qwen3-8b-awq@fake #none> "

    saved = ConfigurationBranchModel.objects.get(owner__name="alice", name="quiet")
    off = ReasoningBranchModel.objects.get(owner__name="archive", name="off")
    assert saved.trail.reasoning_id == off.trail_id

    assert "quiet" in repl.completions()["configuration"]
    assert "cell: quiet × qwen3-8b-awq@fake" in say("use quiet")


def test_saving_again_is_a_new_version_or_nothing(say: Say):
    written = say(
        "cell free-text qwen3-8b-awq@fake",
        "save mine",
        "save mine",
        "set reasoning high",
        "save mine",
    )

    assert "saved as mine: created" in written
    assert "saved as mine: unchanged" in written
    assert "saved as mine: a new version" in written
    assert ConfigurationBranchModel.objects.filter(owner__name="alice").count() == 2


def test_a_saved_configuration_s_tools_still_run(say: Say, fake: FakeTransport):
    written = say("cell test-tools qwen3-8b-awq@fake", "save my-tools")

    assert "yours now too:" in written
    assert "tool sentinel_op" in written

    written = say("show", "run case-1")
    rows = {
        cells[0]: cells[1]
        for cells in (line.split() for line in written.splitlines())
        if len(cells) > 1
    }

    assert (rows["instruction"], rows["toolset"]) == ("bare", "sentinel")
    assert "[result] asdf" in written
    assert len(fake.requests) == 3


def test_save_says_what_it_can_t_save(say: Say):
    assert "the cell has no configuration to save" in say("save nothing")
    assert "a name can't hold '/'" in say("use free-text", "save bob/mine")


def test_a_configuration_of_one_s_own_shadows_the_archive_s(
    repl: Repl, recommit: Recommit
):
    recommit("configuration", "plan", owner="alice")

    assert handle(repl, "use plan")
    assert repl.cell.configuration is not None
    assert repl.cell.configuration.owner.name == "alice"

    assert handle(repl, "use archive/plan")
    assert repl.cell.configuration.owner.name == "archive"
    assert repl.prompt == "alice archive/plan #none> "


@pytest.mark.usefixtures("bobs")
def test_only_the_archive_s_configurations_run_beside_one_s_own(repl: Repl, say: Say):
    _ = say("use free-text")
    assert repl.cell.configuration is not None
    assert repl.cell.configuration.owner.name == "archive"

    assert "no configuration 'bobs-plan' for alice" in say("use bobs-plan")
    assert "bob" not in say("configurations")
    assert "bobs-plan" not in repl.names("configuration")


@pytest.mark.usefixtures("bobs")
def test_another_s_configuration_is_put_in_by_its_owner_and_saved_to_run(
    repl: Repl, say: Say, fake: FakeTransport
):
    written = say("cell bob/bobs-plan qwen3-8b-awq@fake", "show")

    assert repl.prompt == "alice bob/bobs-plan×qwen3-8b-awq@fake #none> "
    assert "a schema; views: differential, warning, disposition" in written

    written = say("run case-1")

    assert "bob/bobs-plan is bob's: save it as your own first: save NAME" in written
    assert fake.requests == []

    written = say("save my-plan", "run case-1")

    assert "saved as my-plan: created" in written
    assert "recorded as run 1 of trial" in written
    assert repl.prompt == "alice my-plan×qwen3-8b-awq@fake #none> "


@pytest.mark.usefixtures("bobs")
def test_another_s_configuration_is_found_only_where_it_is_shared(say: Say):
    alice = IdentityModel.objects.get(name="alice")
    for branch in ConfigurationBranchModel.objects.filter(
        owner__name="bob", name="free-text"
    ):
        branch.collaborators.remove(alice)

    written = say("use bob/free-text", "use bob/nope")

    assert "no configuration 'bob/free-text' for alice" in written
    assert "no configuration 'bob/nope' for alice" in written


def test_one_s_own_configuration_goes_by_one_s_own_name_too(repl: Repl, say: Say):
    _ = say("use free-text", "save mine", "use alice/mine")

    assert repl.prompt == "alice mine #none> "
    assert "no configuration 'alice/free-text' for alice" in say("use alice/free-text")
