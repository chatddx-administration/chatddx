from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from chatddx.factors.base import resolve
from chatddx.factors.bundle import Registry
from chatddx.factors.gatherer import gather
from chatddx.factors.gathering import (
    REVIEW,
    Center,
    Gathered,
    Gathering,
    Seeding,
)
from chatddx.factors.kinds import BY_KIND, parse_component
from chatddx.factors.request import Skeleton
from chatddx.factors.test.sample import world
from chatddx.factors.trial import Trial
from chatddx.test.helpers import registry

__all__ = ["registry"]


def seeded(reg: Registry, *seeds: int, **more: object) -> str:
    made = resolve(reg.get, world(reg)["trial"], Trial)
    return reg.add(made.model_copy(update={"seeds": seeds, **more}))


def center(reg: Registry) -> Center:
    return Center(component=resolve(reg.get, world(reg)["trial"], Trial).cases[0])


def gathered(reg: Registry, *groups: tuple[str, ...]) -> Gathering:
    return Gathering(
        center=center(reg),
        seedings=REVIEW,
        gathered=tuple(
            Gathered(group=g, seeding=s.name, run=uuid4(), trial=trial)
            for g, trials in enumerate(groups)
            for s, trial in zip(REVIEW, trials, strict=False)
        ),
    )


def test_a_gathering_binds_each_group_s_seedings_to_runs(reg: Registry) -> None:
    held = gathered(
        reg, (seeded(reg, 11, 12, 13), seeded(reg, 13)), (seeded(reg, 21, 22, 23),)
    )
    assert held.cross_check(reg.get) == []
    assert [list(g) for g in held.groups()] == [
        ["original", "repeat"],
        ["original"],
    ]
    assert parse_component(held.canonical) == held
    assert {s.path for s in held.refs()} >= {"/center/component", "/gathered/2/trial"}


def test_a_center_is_any_component_but_a_gathering_or_a_seed(reg: Registry) -> None:
    kinds = {s.kinds for s in gathered(reg, (seeded(reg, 1, 2, 3),)).refs()}
    assert set(BY_KIND) - {"gathering"} in [set(k) for k in kinds]
    assert Center(seed=7).seed == 7
    for wrong in ({}, {"seed": 7, "component": "sha256:" + "0" * 64}):
        with pytest.raises(ValidationError, match="a component or a seed"):
            _ = Center.model_validate(wrong)


@pytest.mark.parametrize(
    ("seedings", "refused"),
    [
        ((Seeding(name="a", seeds=1), Seeding(name="a", seeds=1)), "named twice"),
        (
            (Seeding(name="a", seeds=1, repeats="b"), Seeding(name="b", seeds=1)),
            "isn't before",
        ),
        (
            (Seeding(name="a", seeds=1), Seeding(name="b", seeds=2, repeats="a")),
            "more seeds",
        ),
    ],
)
def test_seedings_are_named_once_and_repeat_what_comes_before(
    reg: Registry, seedings: tuple[Seeding, ...], refused: str
) -> None:
    with pytest.raises(ValidationError, match=refused):
        _ = Gathering(
            center=center(reg),
            seedings=seedings,
            gathered=(
                Gathered(group=0, seeding="a", run=uuid4(), trial=seeded(reg, 1)),
            ),
        )


def test_runs_go_in_order_once_each(reg: Registry) -> None:
    three, one = seeded(reg, 11, 12, 13), seeded(reg, 13)
    held = gathered(reg, (three, one), (three, one))
    runs = held.gathered

    def refused(changed: tuple[Gathered, ...], why: str) -> None:
        with pytest.raises(ValidationError, match=why):
            _ = held.model_copy(update={"gathered": changed})

    refused((runs[1], runs[0], *runs[2:]), "by group, then by seeding")
    refused((runs[0], runs[0], *runs[2:]), "by group, then by seeding")
    refused(tuple(r.model_copy(update={"group": r.group * 2}) for r in runs), "gaps")
    refused((runs[0], runs[1].model_copy(update={"run": runs[0].run})), "once")
    refused((runs[0].model_copy(update={"seeding": "spare"}),), "no seeding spare")


def test_the_cross_check_holds_each_run_to_its_seeding(reg: Registry) -> None:
    three, one = seeded(reg, 11, 12, 13), seeded(reg, 13)
    assert gathered(reg, (seeded(reg, 1, 2), one)).cross_check(reg.get) == [
        "group 0's original ran 2 seeds, not 3",
        "group 0's repeat ran other than original's trial on its last seeds",
    ]
    assert gathered(reg, (three, seeded(reg, 12))).cross_check(reg.get) == [
        "group 0's repeat ran other than original's trial on its last seeds"
    ]
    uncleaned = seeded(reg, 13, cleanup=())
    assert gathered(reg, (three, uncleaned)).cross_check(reg.get) == [
        "group 0's repeat ran other than original's trial on its last seeds"
    ]
    alone = gathered(reg, (three, one)).model_copy(
        update={"gathered": (gathered(reg, (three, one)).gathered[1],)}
    )
    assert alone.cross_check(reg.get) == ["group 0's repeat has no original to repeat"]


def test_a_greedy_repeat_names_its_replicate_by_position(reg: Registry) -> None:
    made = resolve(reg.get, world(reg)["trial"], Trial)
    skeleton = resolve(reg.get, made.skeleton, Skeleton)
    greedy = reg.add(
        skeleton.model_copy(update={"body": {**skeleton.body, "temperature": 0}})
    )
    assert resolve(reg.get, greedy, Skeleton).greedy
    three = seeded(reg, 0, 1, 2, skeleton=greedy)
    one = seeded(reg, 0, skeleton=greedy)
    assert gathered(reg, (three, one)).cross_check(reg.get) == []


def test_a_repeat_s_item_is_alike_the_item_it_repeats(reg: Registry) -> None:
    three, one = seeded(reg, 11, 12, 13), seeded(reg, 13)
    assert gathered(reg, (three, one)).cross_check(reg.get) == []
    made = resolve(reg.get, three, Trial)
    skeleton = resolve(reg.get, made.skeleton, Skeleton)
    case = made.cases[0]

    def single(trial: str, replicate: int) -> str:
        return resolve(reg.get, trial, Trial).single(skeleton, case, replicate).digest

    assert single(one, 0) == single(three, 2)
    assert single(one, 0) not in {single(three, 0), single(three, 1)}
    assert single(seeded(reg, 13, cleanup=()), 0) != single(three, 2)

    greedy = reg.add(
        skeleton.model_copy(update={"body": {**skeleton.body, "temperature": 0}})
    )
    held = resolve(reg.get, seeded(reg, 0, 1, 2, skeleton=greedy), Trial)
    shown = resolve(reg.get, greedy, Skeleton)
    assert len({held.single(shown, case, r).digest for r in range(3)}) == 1


def test_gather_fills_each_group_s_seedings_with_the_first_run_that_fits(
    reg: Registry,
) -> None:
    three, one = seeded(reg, 11, 12, 13), seeded(reg, 13)
    older, stray = seeded(reg, 1, 2, 3), seeded(reg, 2)
    runs = {name: uuid4() for name in ("one", "three", "older", "stray", "b")}
    found: list[tuple[str, UUID, str]] = [
        ("a", runs["one"], one),
        ("a", runs["stray"], stray),
        ("a", runs["three"], three),
        ("a", runs["older"], older),
        ("b", runs["b"], seeded(reg, 21, 22, 23)),
        ("c", uuid4(), seeded(reg, 5, 6)),
    ]
    held = gather(center(reg), REVIEW, found, reg.get)
    assert held is not None and held.cross_check(reg.get) == []
    by_run = {g.run: (g.group, g.seeding) for g in held.gathered}
    a = by_run[runs["three"]][0]
    assert by_run[runs["one"]] == (a, "repeat")
    assert runs["older"] not in by_run and runs["stray"] not in by_run
    assert by_run[runs["b"]] == (1 - a, "original")
    assert len(held.groups()) == 2

    again = gather(center(reg), REVIEW, reversed(found), reg.get)
    assert again is not None
    assert [g.trial for g in again.gathered] != [g.trial for g in held.gathered]
    shuffled = [found[4], *found[:4]]
    assert gather(center(reg), REVIEW, shuffled, reg.get) == held
    assert gather(center(reg), REVIEW, found[-1:], reg.get) is None
