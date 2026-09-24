"""What goes in the cell, and keeping what is in it as one's own."""

from collections.abc import Callable

import pytest
from rich.console import Console

from chatddx.core.models import IdentityModel
from chatddx.core.repl.commands import handle
from chatddx.core.repl.shell import Repl
from chatddx.dx.fake_vllm import FakeTransport
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.reasoning.django import ReasoningBranchModel

type Say = Callable[..., str]
type Provision = Callable[..., None]

pytestmark = pytest.mark.django_db


@pytest.fixture
def bobs(repl: Repl, provision: Provision) -> None:
    """
    bob's configurations, shared with the repl's identity, bob's plan under
    a name the archive doesn't have.
    """
    provision("--with-giftbag", user="bob")
    alex = IdentityModel.objects.get(name=repl.identity)

    _ = ConfigurationBranchModel.objects.filter(owner__name="bob", name="plan").update(
        name="bobs-plan"
    )
    for branch in ConfigurationBranchModel.objects.filter(owner__name="bob"):
        branch.collaborators.add(alex)


def test_set_puts_another_variation_in_the_cell(
    repl: Repl, say: Say, fake: FakeTransport
):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "run case-1")

    assert repl.prompt == "alex free-text+reasoning=off×qwen3-8b-awq@fake> "
    assert "trial: free-text+reasoning=off × qwen3-8b-awq@fake × case-1" in written

    [request] = fake.requests
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert "[thinking]" not in written


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

    _ = say("set toolset sentinel")
    assert repl.prompt == "alex test-tools×qwen3-8b-awq@fake> "


def test_none_of_a_toolset_it_has_none_of_is_nothing_set(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set toolset none")

    assert repl.prompt == "alex free-text×qwen3-8b-awq@fake> "


def test_use_puts_a_configuration_in_as_it_is(repl: Repl, say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "use free-text")

    assert repl.prompt == "alex free-text×qwen3-8b-awq@fake> "


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


def test_save_keeps_the_cell_as_a_configuration_of_one_s_own(repl: Repl, say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "save quiet")

    assert "saved as quiet: created" in written
    assert repl.prompt == "alex quiet×qwen3-8b-awq@fake> "

    saved = ConfigurationBranchModel.objects.get(owner__name="alex", name="quiet")
    off = ReasoningBranchModel.objects.get(owner__name="archive", name="off")
    assert saved.target.reasoning_id == off.target_id

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
    assert ConfigurationBranchModel.objects.filter(owner__name="alex").count() == 2


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


def test_a_configuration_of_one_s_own_shadows_the_archive_s(provision: Provision):
    provision("--with-giftbag")
    repl = Repl("alex", Console(record=True, width=200))

    assert handle(repl, "use plan")
    assert repl.cell.configuration is not None
    assert repl.cell.configuration.owner.name == "alex"

    assert handle(repl, "use archive/plan")
    assert repl.cell.configuration.owner.name == "archive"
    assert repl.prompt == "alex archive/plan> "


@pytest.mark.usefixtures("bobs")
def test_only_the_archive_s_configurations_run_beside_one_s_own(repl: Repl, say: Say):
    _ = say("use free-text")
    assert repl.cell.configuration is not None
    assert repl.cell.configuration.owner.name == "archive"

    assert "no configuration 'bobs-plan' for alex" in say("use bobs-plan")
    assert "bob" not in say("configurations")
    assert "bobs-plan" not in repl.names("configuration")


@pytest.mark.usefixtures("bobs")
def test_another_s_configuration_is_put_in_by_its_owner_and_saved_to_run(
    repl: Repl, say: Say, fake: FakeTransport
):
    written = say("cell bob/bobs-plan qwen3-8b-awq@fake", "show")

    assert repl.prompt == "alex bob/bobs-plan×qwen3-8b-awq@fake> "
    assert "a schema; views: differential, warning, disposition" in written

    written = say("run case-1")

    assert "bob/bobs-plan is bob's: save it as your own first: save NAME" in written
    assert fake.requests == []

    written = say("save my-plan", "run case-1")

    assert "saved as my-plan: created" in written
    assert "recorded as run 1 of trial" in written
    assert repl.prompt == "alex my-plan×qwen3-8b-awq@fake> "


@pytest.mark.usefixtures("bobs")
def test_another_s_configuration_is_found_only_where_it_is_shared(say: Say):
    alex = IdentityModel.objects.get(name="alex")
    for branch in ConfigurationBranchModel.objects.filter(
        owner__name="bob", name="free-text"
    ):
        branch.collaborators.remove(alex)

    written = say("use bob/free-text", "use bob/nope")

    assert "no configuration 'bob/free-text' for alex" in written
    assert "no configuration 'bob/nope' for alex" in written


def test_one_s_own_configuration_goes_by_one_s_own_name_too(repl: Repl, say: Say):
    _ = say("use free-text", "save mine", "use alex/mine")

    assert repl.prompt == "alex mine> "
    assert "no configuration 'alex/free-text' for alex" in say("use alex/free-text")
