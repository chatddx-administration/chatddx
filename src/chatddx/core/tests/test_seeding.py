"""
An owner seeded with the registry (test-registry-inventory.toml): everything
the portal shows them outside the Shared tab, their own before they start;
and what of the archive's changes, once they have (test-later-inventory.toml),
comes to them.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from chatddx.bench.bench import Bench, Trial
from chatddx.bench.plan import Plan
from chatddx.bench.sending import Handed, Sending
from chatddx.conftest import TEST_LATER, TEST_REGISTRY, Provision, Recommit
from chatddx.core import settings
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.history.models import ConversationContext, RunModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchDetails, CaseTrailIn
from chatddx.repo.entities.llm.pydantic import LLMFacts
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.names import short_fingerprint
from chatddx.repo.parsers.inventory import ParseError, parse
from chatddx.repo.queries import head_of
from chatddx.repo.store.branch import commit
from chatddx.scoring.score import Scoring
from chatddx.worker import control, queue, worker

pytestmark = pytest.mark.django_db

FAKE = "qwen3-8b-awq@fake"


@pytest.fixture(scope="module")
def registry() -> ParsedInventory:
    return parse(TEST_REGISTRY)


def seeded(provision: Provision, user: str = "alice") -> None:
    """`user` given the registry as their own, as init-data's giftbag gives it."""
    _ = provision(
        "--with-giftbag", "--giftbag-inventory", str(TEST_REGISTRY), user=user
    )


def owned(owner: str) -> dict[str, set[str]]:
    return {
        entity: set(
            entity_of(entity)
            .branch_model.objects.filter(owner__name=owner)
            .values_list("name", flat=True)
        )
        for entity in ENTITY_NAMES
    }


def sent(owner: str) -> RunModel:
    """free-text on case-1 under seed 42, sent as the owner's bench has it."""
    bench = Bench(owner, FakeTransport())
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


def test_the_registry_as_a_giftbag_gives_everything_but_the_cases(
    provision: Provision, registry: ParsedInventory
):
    seeded(provision)
    mine = owned("alice")

    assert mine == {entity: set(getattr(registry, entity)) for entity in ENTITY_NAMES}
    assert mine["case"] == set()

    # the archive's content, under the archive's names: none named by fingerprint
    for entity in ENTITY_NAMES:
        branches = entity_of(entity).branch_model.objects.all()

        for name in mine[entity]:
            own, archived = (
                head_of(branches, owner, name) for owner in ("alice", "archive")
            )
            assert own is not None and archived is not None
            assert own.trail_id == archived.trail_id


def test_what_an_owner_is_given_stands_in_for_the_archive_s_wherever_it_is_read(
    provision: Provision,
):
    seeded(provision)
    bench = Bench("alice")
    stack = next(stack for stack in bench.stacks() if stack.name == FAKE)
    ready = bench.ready(bench.cell_of("test-tools", FAKE))
    _, llm = bench.llm_of(stack)

    assert {stack.owner.name for stack in bench.stacks()} == {"alice"}
    assert bench.configuration_named("test-tools").owner.name == "alice"
    assert llm is not None
    assert {tool.owner.name for tool in ready.tools.values()} == {"alice"}
    assert {scorer.owner for scorer in Scoring("alice").scorers} == {"alice"}


def test_runs_on_owners_copies_record_the_copies_and_share_their_trial(
    provision: Provision,
):
    seeded(provision)
    seeded(provision, "bob")
    runs = [sent(owner) for owner in ("alice", "bob")]

    assert [
        (run.stack_branch.owner.name, run.llm_branch.owner.name)
        for run in runs
        if run.stack_branch and run.llm_branch
    ] == [("alice", "alice"), ("bob", "bob")]
    assert runs[0].trial_id == runs[1].trial_id


def test_what_the_archive_changes_later_stays_the_archive_s(provision: Provision):
    seeded(provision)
    # init-data again, on the archive's inventory as it stands later, for bob
    _ = provision("--inventory", str(TEST_LATER), user="bob")
    alice = Bench("alice")
    stack = next(stack for stack in alice.stacks() if stack.name == FAKE)

    assert (str(stack.details.endpoint), alice.max_jobs(FAKE)) == (
        "http://localhost:12099/v1/",
        4,
    )
    assert Bench("archive").max_jobs(FAKE) == 8
    assert "dont_miss_mentions" not in {s.name for s in Scoring("alice").scorers}


def test_what_is_shared_with_an_owner_later_scores_their_runs_at_once(
    provision: Provision,
):
    seeded(provision)
    # init-data again for alice, on the archive's inventory as it stands later
    _ = provision("--inventory", str(TEST_LATER))

    assert ("dont_miss_mentions", "archive") in {
        (scorer.name, scorer.owner) for scorer in Scoring("alice").scorers
    }
    # the stack shared with her anew stays behind her own of its name
    assert Bench("alice").max_jobs(FAKE) == 4


def test_a_stack_takes_as_many_jobs_as_the_copy_of_whoever_is_queued_first(
    provision: Provision, recommit: Recommit
):
    seeded(provision)
    seeded(provision, "bob")
    recommit("stack", FAKE, owner="bob", max_jobs=1)
    queued("bob")
    queued("alice")
    at = worker.Worker()

    assert at._max_jobs(FAKE, []) == 1  # pyright: ignore[reportPrivateUsage]

    _ = control.stop("bob")

    assert at._max_jobs(FAKE, []) == 4  # pyright: ignore[reportPrivateUsage]


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


def test_two_names_of_an_owner_s_on_one_llm_leave_its_facts_unfound(
    provision: Provision, recommit: Recommit
):
    seeded(provision)
    recommit("llm", "qwen3-8b-awq", name="qwen3-renamed", owner="alice")
    bench = Bench("alice")
    stack = next(stack for stack in bench.stacks() if stack.name == FAKE)

    assert bench.llm_of(stack) == (LLMFacts(), None)
