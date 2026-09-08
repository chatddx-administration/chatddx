# src/chatddx/main.py
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import django
import typer

django.setup()
from chatddx.repl import app as repl_app
from chatddx.repo.shufflers.main import (
    dump_cases,
    dump_trail_registry,
    ensure_identity,
)

CURRENT_DIR = Path(__file__).resolve().parent
app = typer.Typer()

init_data = typer.Typer(invoke_without_command=True)

app.add_typer(init_data, name="init-data")
app.add_typer(repl_app, name="repl")


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
):
    _ = ensure_identity(owner)

    for bundle, branches in dump_trail_registry(registry, owner).items():
        for branch_idx, branch in branches.items():
            print(f"{branch.target.fingerprint}: {branch_idx} {bundle} {branch.name}:")

    for branch_idx, branch in dump_cases(cases_dir, owner).items():
        print(f"{branch.target.fingerprint}: {branch_idx} case {branch.name}:")
