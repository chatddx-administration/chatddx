import pytest

from chatddx.api.standing import baseline_cases, configurations
from chatddx.bench import Bench
from chatddx.scripted import composed


@pytest.mark.slow
def test_a_configuration_s_baselines_are_broken_down_by_each_gathering_in_the_order_they_ran(
    bench: Bench,
) -> None:
    schema = bench.thread("targets", "expectation_schema")[0].digest
    made = composed(bench, schema, gatherings=8, versions=3, seed=5, days=14)
    cases = baseline_cases(bench)
    owned = configurations(bench)
    by_name = {t.name or t.title: t for t in owned}
    name = max(made.gatherings, key=lambda n: made.gatherings[n].get("baseline", 0))
    thread = by_name[name].id

    held = bench.breakdown(thread, cases, [t.id for t in owned])

    assert held.views and held.timeline
    ats = [g.point.at for g in held.timeline]
    assert ats == sorted(ats)
    assert len({g.point.started for g in held.timeline}) == len(held.timeline)
    for g in held.timeline:
        assert set(g.estimates) <= set(g.values) <= set(held.views)
        for v, e in g.estimates.items():
            assert e.n == len(g.values[v])
        point = g.point
        assert sum(point.languages.values()) == len(cases)
        assert 0 <= point.missing <= len(cases)
        alike, of = point.alike
        assert 0 <= alike <= of
        assert 0.0 <= point.failed <= 1.0
    assert held.timeline[0].paired == {}
    for at, g in enumerate(held.timeline):
        shown = bench.baseline(g.point.started, cases)
        assert (
            shown is not None and shown.gathered == g and shown.configuration == thread
        )
        assert shown.before == (held.timeline[at - 1] if at else None)
        assert {c.case for c in shown.cases} >= set(cases)
        assert (
            sum(not c.answered for c in shown.cases if c.case in cases)
            == g.point.missing
        )
        assert {r.repeat for r in shown.runs} <= {False, True}
    assert all(set(p.shared) <= set(held.views) for p in held.peers)
    assert {p.configuration for p in held.peers} <= {t.id for t in owned} - {thread}

    runs = bench.runs()
    first = bench.observed(runs)
    again = bench.observed(runs)
    assert first and all(a.ran is b.ran for a, b in zip(first, again, strict=True))
    assert bench.breakdown(thread, cases, [t.id for t in owned]) == held
