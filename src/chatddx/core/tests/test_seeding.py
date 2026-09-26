"""
An owner seeded as init-data's giftbag seeds them: what is asked, their own
before they start; the rest the archive's, shared with them: what answers, a
class of record no owner is given, and the cases and scorers. And what of
the archive's changes, once they have started (test-later-inventory.toml),
comes to them.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from chatddx.bench.bench import Bench, Trial
from chatddx.bench.plan import Plan
from chatddx.bench.sending import Handed, Sending
from chatddx.conftest import TEST_LATER, Provision, SayAs
from chatddx.core import settings
from chatddx.history.models import ConversationContext, RunModel
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchDetails, CaseTrailIn
from chatddx.repo.entities.llm.django import LLMBranchModel
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.names import short_fingerprint
from chatddx.repo.parsers.inventory import ParseError, parse
from chatddx.repo.store.branch import commit
from chatddx.scoring.score import Scoring
from chatddx.worker import queue, worker

pytestmark = pytest.mark.django_db

FAKE = "qwen3-8b-awq@fake"

# the archive's alone (datamodel.md §1): what answers, and what is asked
# about and how it is judged
KEPT = ("machine", "os", "llm", "serving", "client", "stack", "case", "scorer")


def seeded(provision: Provision, user: str = "alice") -> None:
    """`user` given the giftbag as their own, as a new owner is."""
    _ = provision("--with-giftbag", user=user)


def sent(owner: str) -> RunModel:
    """free-text on case-1 under seed 42, sent as the owner's bench has it."""
    bench = Bench(owner)
    ready = bench.ready(bench.cell_of("free-text", FAKE))
    [case] = [case for case in bench.cases() if case.name == "case-1"]
    sending = Sending(bench, Trial.on(ready, case, 42), ConversationContext.WORKER)

    with Handed(sending.events()) as handed:
        for _ in handed:
            pass

    recorded = sending.written().run
    assert recorded is not None

    return recorded


def queued(owner: str) -> None:
    bench = Bench(owner)
    plan = Plan.of(bench, [bench.cell_of("free-text", FAKE)], ["tag-2"], 42)
    _ = queue.put(owner, uuid4(), plan.kept, plan.cases)


def test_the_giftbag_gives_what_is_asked_and_nothing_else():
    giftbag = parse(settings.INVENTORY_PATH / "giftbag-inventory.toml")

    assert {entity for entity in ENTITY_NAMES if getattr(giftbag, entity)} == (
        set(ENTITY_NAMES) - set(KEPT)
    )


def test_an_owner_uses_their_own_configuration_on_the_archive_s_stack(
    provision: Provision,
):
    seeded(provision)
    bench = Bench("alice")
    stack = next(stack for stack in bench.stacks() if stack.name == FAKE)
    ready = bench.ready(bench.cell_of("test-tools", FAKE))
    _, llm = bench.llm_of(stack)

    assert bench.configuration_named("test-tools").owner.name == "alice"
    assert {tool.owner.name for tool in ready.tools.values()} == {"alice"}
    assert {stack.owner.name for stack in bench.stacks()} == {"archive"}
    assert LLMBranchModel.objects.get(pk=llm).owner.name == "archive"
    assert {case.owner.name for case in bench.cases()} == {"archive"}
    assert {scorer.owner for scorer in Scoring("alice").scorers} == {"archive"}


def test_owners_runs_record_the_archive_s_stack_and_share_their_trial(
    provision: Provision,
):
    seeded(provision)
    seeded(provision, "bob")
    runs = [sent(owner) for owner in ("alice", "bob")]

    assert [
        (run.stack_branch.owner.name, run.llm_branch.owner.name)
        for run in runs
        if run.stack_branch and run.llm_branch
    ] == [("archive", "archive")] * 2
    assert runs[0].trial_id == runs[1].trial_id


def test_a_seeded_owner_s_repl_runs_the_archive_s_cases(
    provision: Provision, say_as: SayAs
):
    seeded(provision)
    say = say_as()

    assert "case-1  case-2" in say("cases")

    written = say("cell free-text qwen3-8b-awq@fake", "run case-1", "batch tag-2")

    assert "recorded as run 1" in written
    assert "2 cases tagged tag-2" in written
    assert set(
        RunModel.objects.filter(owner__name="alice").values_list(
            "trial__case__branches__name", flat=True
        )
    ) == {"case-1", "case-2"}


def test_what_the_archive_changes_later_reaches_its_owners_at_once(
    provision: Provision,
):
    seeded(provision)
    queued("alice")
    # init-data again, on the archive's inventory as it stands later, for bob
    _ = provision("--inventory", str(TEST_LATER), user="bob")
    stack = next(stack for stack in Bench("alice").stacks() if stack.name == FAKE)

    assert str(stack.details.endpoint) == "http://localhost:12100/v1/"
    # the worker's slots on it are its one branch's, whoever is queued
    assert worker.Worker()._max_jobs(FAKE, []) == 8  # pyright: ignore[reportPrivateUsage]
    # what the archive adds is shared with whom init-data is run for alone
    assert "dont_miss_mentions" not in {s.name for s in Scoring("alice").scorers}


def test_what_the_archive_adds_later_is_shared_by_init_data_run_again(
    provision: Provision,
):
    seeded(provision)
    # init-data again for alice, on the archive's inventory as it stands later
    _ = provision("--inventory", str(TEST_LATER))

    assert ("dont_miss_mentions", "archive") in {
        (scorer.name, scorer.owner) for scorer in Scoring("alice").scorers
    }


def test_an_owner_s_case_on_an_archive_vignette_under_another_name_is_unnamed():
    vignette = CaseBranchModel.objects.filter(name="case-1").latest("pk").trail.vignette

    for name in ("mine", "case-1"):
        owner = "alice" if name == "mine" else "bob"
        _ = commit(
            CaseTrailIn(vignette=vignette),
            CaseBranchDetails.model_validate({"name": name, "owner": owner}),
        )

    trail = CaseBranchModel.objects.filter(name="mine").latest("pk").trail

    # beside the archive's case-1, shared with alice, hers is one of two names
    assert Bench("alice").name_of("case", trail) == short_fingerprint(trail.fingerprint)
    # named as the archive names it, bob's shadows the archive's
    assert Bench("bob").name_of("case", trail) == "case-1"


def test_a_giftbag_can_t_give_a_part_without_what_it_names(tmp_path: Path):
    giftbag = tmp_path / "giftbag.toml"
    fake = settings.INVENTORY_PATH / "inventory" / "fake.toml"
    _ = giftbag.write_text(f'extends = ["{fake}"]\n')

    with pytest.raises(ParseError, match="unknown llm 'qwen3-8b-awq'"):
        _ = parse(giftbag)
