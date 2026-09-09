# src/chatddx/repo/shufflers/experiment.py
"""
Persistence for Experiment: a frozen (owner, agent, case, expect) record,
generated -- never hand-authored -- when a Batch is saved. Batch is not
implemented yet, so for now this module offers:

* `create_experiment()`, the construction logic a future Batch will call
  once per (agent, case) pair it wants scored, and
* `dump_experiments()`, which seeds the sample Experiments recorded under
  `data/experiments/*.toml` for `chatddx init-data`.

Like Expect (see chatddx.repo.shufflers.expect), Experiment sits outside
the RepoBundle/BundleName registry: it has no admin page of its own and
isn't itself a Trail/Branch pair, so it can't reuse the generic
`dump_branch()` machinery. Unlike Expect, an Experiment isn't
content-addressed either -- there's no single fingerprint identifying "the"
experiment for a given (agent, case) pair, since re-running the same pair
is a legitimate, separate Experiment. Only the sample-seeding path below
needs idempotency (so re-running `init-data` doesn't pile up duplicates),
and gets it by checking for an existing (owner, agent, case) row itself.
"""

from __future__ import annotations

import tomllib
import warnings
from pathlib import Path
from typing import Any

from chatddx.experiment.models import ExperimentModel
from chatddx.repo.branch_models import (
    AgentBranchModel,
    CaseBranchModel,
    ExpectBranchModel,
)
from chatddx.repo.shufflers.main import ensure_identity, qs_canon
from chatddx.repo.trail_models import AgentTrailModel, CaseTrailModel, ExpectTrailModel
from chatddx.utils import make_async


def find_expect(
    case: CaseTrailModel,
    scorer: str,
    owner_name: str,
) -> ExpectTrailModel | None:
    """The Expect trail currently paired with `case` for `scorer`."""
    branch = qs_canon(
        ExpectBranchModel.objects.filter(
            target__case_id=case.pk,
            target__scorer=scorer,
        ),
        owner_name,
    ).first()

    return branch.target if branch else None


find_expect_async = make_async(find_expect)


def create_experiment(
    owner_name: str,
    agent: AgentTrailModel,
    case: CaseTrailModel,
    tags: list[str] | None = None,
    scorer: str = "",
) -> ExperimentModel:
    """
    Freeze one (agent, case) pair into a runnable, scoreable Experiment.

    `expect` isn't supplied by the caller: it's looked up from the
    currently canonical Expect for `case` against `scorer`, per
    ExperimentModel's contract -- the same `scorer` this Experiment is
    itself built with, since that's what will grade its completed Runs.
    There's no substitute for it -- an Expect is what scoring the result
    *means* -- so when none exists yet for this exact pairing, this refuses
    to fabricate an Experiment that could never be scored, rather than
    leaving that gap for whoever runs it later to discover.

    A missing deterministic seed is a softer gap: the Experiment can still
    be built (its inputs -- agent, case, expect -- are all pinned trails,
    so it stays perfectly reproducible as *input*), but re-running an agent
    with no fixed seed is not guaranteed to reproduce the same *output*
    a year from now. That gets a warning rather than a hard failure.

    `scorer` is a dotted import path to the function that will score this
    Experiment's completed Runs (see ExperimentModel.scorer and
    chatddx.experiment.worker.score_run). It's optional -- left blank, the
    Experiment is paired with the default Expect for `case` and can still
    be run, just never scored.
    """
    owner = ensure_identity(owner_name)

    expect = find_expect(case, scorer, owner.name)
    if expect is None:
        raise ValueError(
            f"no Expect for case {case.pk} against scorer {scorer!r}: cannot "
            "build a scoreable Experiment. Add an Expect for this (case, "
            "scorer) pair first -- see chatddx.repo.shufflers.expect.dump_expect."
        )

    if agent.sampling_params.seed is None:
        warnings.warn(
            f"agent {agent.pk} has no fixed sampling seed: this Experiment's "
            "inputs (agent, case, expect) are pinned and will never change, "
            "but re-running the agent is not guaranteed to reproduce the "
            "same output a year from now.",
            stacklevel=2,
        )

    return ExperimentModel.objects.create(
        owner=owner,
        agent=agent,
        case=case,
        expect=expect,
        tags=", ".join(tags or []),
        scorer=scorer,
    )


create_experiment_async = make_async(create_experiment)


def parse_experiments(experiments_path: Path) -> dict[str, dict[str, Any]]:
    """Read the `[experiment.<name>]` tables out of one experiments TOML file."""
    data = tomllib.loads(experiments_path.read_text(encoding="utf-8"))
    return data.get("experiment", {})


def dump_experiments(
    experiments_dir: Path,
    owner_name: str,
) -> dict[int, ExperimentModel]:
    """
    Build the sample Experiments recorded under `experiments_dir`: every
    `[experiment.<name>]` table in every file there names an `agent` branch
    and a `case` branch, both expected to already be dumped (by
    `dump_trail_registry` and `dump_cases` respectively) before this runs.

    An entry naming a branch that doesn't exist for `owner_name` is
    skipped, as is one whose case has no Expect yet for its (optional)
    `scorer` -- both logged rather than raised, so one bad sample doesn't
    block the rest.
    Re-running this against an (owner, agent, case) pair that already has
    an Experiment is a no-op, so `chatddx init-data` stays safe to re-run.
    """
    owner = ensure_identity(owner_name)

    dumped: dict[int, ExperimentModel] = {}

    for experiments_path in sorted(experiments_dir.iterdir()):
        if not experiments_path.is_file():
            continue

        for name, entry in parse_experiments(experiments_path).items():
            agent_branch = qs_canon(
                AgentBranchModel.objects.filter(name=entry["agent"]),
                owner.name,
            ).first()
            case_branch = qs_canon(
                CaseBranchModel.objects.filter(name=entry["case"]),
                owner.name,
            ).first()

            if agent_branch is None or case_branch is None:
                print(
                    f"experiment {name}: skipped (agent {entry['agent']!r} or "
                    f"case {entry['case']!r} not found for owner {owner.name!r})"
                )
                continue

            existing = ExperimentModel.objects.filter(
                owner=owner,
                agent=agent_branch.target,
                case=case_branch.target,
            ).first()

            if existing is not None:
                dumped[existing.pk] = existing
                continue

            try:
                experiment = create_experiment(
                    owner_name=owner.name,
                    agent=agent_branch.target,
                    case=case_branch.target,
                    tags=list(entry.get("tags", [])),
                    scorer=entry.get("scorer", ""),
                )
            except ValueError as exc:
                print(f"experiment {name}: skipped ({exc})")
                continue

            dumped[experiment.pk] = experiment

    return dumped


dump_experiments_async = make_async(dump_experiments)
