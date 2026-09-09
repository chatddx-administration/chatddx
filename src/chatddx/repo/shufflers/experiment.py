# src/chatddx/repo/shufflers/experiment.py

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
    data = tomllib.loads(experiments_path.read_text(encoding="utf-8"))
    return data.get("experiment", {})


def dump_experiments(
    experiments_dir: Path,
    owner_name: str,
) -> dict[int, ExperimentModel]:
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
