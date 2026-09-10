# src/chatddx/main.py
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import django
import typer

django.setup()
from chatddx.experiment import worker as run_worker
from chatddx.repl import app as repl_app
from chatddx.repo.shufflers.cases import (
    dump_cases,
)
from chatddx.repo.shufflers.expect import dump_expect, dump_expects
from chatddx.repo.shufflers.experiment import dump_experiments
from chatddx.repo.shufflers.main import (
    dump_trail_registry,
    ensure_archive,
    ensure_identity,
)
from chatddx.repo.shufflers.scorer import DEFAULT_SCORER_NAMES, dump_scorers
from chatddx.repo.shufflers.tags import dump_case_tags
from chatddx.repo.shufflers.wipe import wipe_data

CURRENT_DIR = Path(__file__).resolve().parent
app = typer.Typer()

init_data = typer.Typer(invoke_without_command=True)
worker = typer.Typer()

app.add_typer(init_data, name="init-data")
app.add_typer(repl_app, name="repl")
app.add_typer(worker, name="worker")


@dataclass
class Context:
    pass


@app.callback()
def main():
    pass


@init_data.callback()
def init_data_(
    owner: Annotated[str, typer.Argument()],
    registry: Annotated[
        Path,
        typer.Option(
            "--registry",
            file_okay=True,
            dir_okay=False,
            exists=True,
            help="location of registry",
        ),
    ] = CURRENT_DIR / "data/registry.toml",
    cases_dir: Annotated[
        Path,
        typer.Option(
            "--cases-dir",
            file_okay=False,
            dir_okay=True,
            exists=True,
            help="location of case files",
        ),
    ] = CURRENT_DIR / "data/cases",
    expects_dir: Annotated[
        Path,
        typer.Option(
            "--expects-dir",
            file_okay=False,
            dir_okay=True,
            exists=True,
            help="location of expect files",
        ),
    ] = CURRENT_DIR / "data/expects",
    tags_path: Annotated[
        Path,
        typer.Option(
            "--tags-path",
            file_okay=True,
            dir_okay=False,
            exists=True,
            help="location of case tag data",
        ),
    ] = CURRENT_DIR / "data/tags.toml",
    experiments_dir: Annotated[
        Path,
        typer.Option(
            "--experiments-dir",
            file_okay=False,
            dir_okay=True,
            exists=True,
            help="location of sample experiment files",
        ),
    ] = CURRENT_DIR / "data/experiments",
    with_giftbag: Annotated[
        bool,
        typer.Option(
            "--with-giftbag",
            help=(
                "Also dump --giftbag-registry and add it to OWNER. archive "
                "responds to this flag too: pass it when OWNER is archive "
                "to give the giftbag to archive itself."
            ),
        ),
    ] = False,
    giftbag_registry: Annotated[
        Path,
        typer.Option(
            "--giftbag-registry",
            file_okay=True,
            dir_okay=False,
            exists=True,
            help="location of the giftbag registry",
        ),
    ] = CURRENT_DIR / "data/giftbag-registry.toml",
):
    """
    `archive` owns everything this dumps -- creating it first if this is
    the very first `init-data` run. OWNER is added as a collaborator on
    all of it (unless OWNER *is* archive, which already owns it outright).
    """
    archive = ensure_archive()
    collaborator = None if owner == archive.name else ensure_identity(owner)

    def share(dumped) -> None:
        """Add `collaborator` (OWNER, unless OWNER is archive) to every
        Branch/Experiment `dumped` -- a model instance, or a dict of them
        as returned by the various `dump_*` helpers above."""
        if collaborator is None:
            return
        targets = dumped.values() if isinstance(dumped, dict) else [dumped]
        for target in targets:
            target.collaborators.add(collaborator)

    scorer_branches = {
        branch.name: branch
        for branch in dump_scorers(DEFAULT_SCORER_NAMES, archive.name).values()
    }
    share(scorer_branches)
    for branch in scorer_branches.values():
        print(f"{branch.target.fingerprint}: {branch.pk} scorer {branch.name}:")

    for bundle, branches in dump_trail_registry(registry, archive.name).items():
        share(branches)
        for branch_idx, branch in branches.items():
            print(f"{branch.target.fingerprint}: {branch_idx} {bundle} {branch.name}:")

    case_branches = dump_cases(cases_dir, archive.name)
    share(case_branches)
    for branch_idx, branch in case_branches.items():
        print(f"{branch.target.fingerprint}: {branch_idx} case {branch.name}:")

    for case_name, tags in dump_case_tags(
        tags_path, case_branches, archive.name
    ).items():
        tag_names = ", ".join(tag.name for tag in tags)
        print(f"tags: case {case_name}: {tag_names}")

    # The bundled Expect payloads (src/chatddx/data/expects) are all written
    # in the row-pattern grammar `regex_match` understands (see
    # chatddx.experiment.scorers) -- so that's the scorer they're dumped
    # against by default.
    regex_match = scorer_branches["chatddx.experiment.scorers.regex_match"].target
    expect_branches = dump_expects(expects_dir, archive.name, scorer=regex_match)
    share(expect_branches)
    for branch_idx, branch in expect_branches.items():
        print(f"{branch.target.fingerprint}: {branch_idx} expect {branch.name}:")

    # A small demo of the other bundled scorer, `exact_match`: a second,
    # plain-text Expect on the same case, paired against exact_match instead
    # of regex_match (see the "openxddx-exact-match-demo" sample Experiment
    # in data/experiments/samples.toml).
    exact_match = scorer_branches["chatddx.experiment.scorers.exact_match"].target
    demo_case = next(
        branch.target
        for branch in case_branches.values()
        if branch.name == "openxddx-case_1"
    )
    demo_branch, _ = dump_expect(
        case=demo_case,
        scorer=exact_match,
        payload="acute kidney injury",
        owner_name=archive.name,
    )
    share(demo_branch)
    print(
        f"{demo_branch.target.fingerprint}: {demo_branch.pk} expect {demo_branch.name}:"
    )

    experiments = dump_experiments(experiments_dir, archive.name)
    share(experiments)
    for experiment_idx, experiment in experiments.items():
        print(f"{experiment.uuid}: {experiment_idx} experiment {experiment.tags}")

    if with_giftbag:
        for bundle, branches in dump_trail_registry(
            giftbag_registry, archive.name
        ).items():
            share(branches)
            for branch_idx, branch in branches.items():
                print(
                    f"{branch.target.fingerprint}: {branch_idx} giftbag {bundle} "
                    f"{branch.name}:"
                )


@app.command("wipe-data")
def wipe_data_(
    owner: Annotated[str, typer.Argument()],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
):
    """
    Wipe all data owned by OWNER: every Session, Run, Experiment, and
    Branch of every kind (agents, connections, cases, expects, scorers,
    ...), then the identity itself. This is the migration strategy for
    changes that reshape owned data -- wipe, then re-run `chatddx
    init-data`.
    """
    if not yes:
        typer.confirm(
            f"This will permanently delete all data owned by {owner!r}. Continue?",
            abort=True,
        )

    if wipe_data(owner):
        typer.echo(f"wiped all data owned by {owner!r}")
    else:
        typer.echo(f"no data owned by {owner!r}: nothing to wipe")


@worker.command("run")
def worker_run():
    """
    Trigger one worker pass: run every currently queued Run, oldest first,
    storing the resulting session and status on each, then exit.
    """
    asyncio.run(run_worker.trigger())
