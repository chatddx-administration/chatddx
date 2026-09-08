# src/chatddx/repo/shufflers/expect.py
"""
Persistence for Expect: an immutable expectation (payload) pinned to an
exact (Case trail, OutputType trail) pair.

Expect deliberately sits outside the RepoBundle/BundleName registry (it has
no independent admin page or crispy-form UI -- it's only edited inline from
the Case form), so it can't reuse the generic `dump_branch()` machinery,
which resolves its models via `Repo(bundle_name, ...)`. This mirrors that
function's logic directly against the concrete Expect models instead.

Like every other TrailModel, ExpectTrailModel rows are enforced immutable
at the database level (see chatddx.django.orm.apps.install_trail_triggers):
editing an expectation never updates a row in place, it inserts a new
fingerprinted trail row and -- if the content actually changed -- points a
new ExpectBranchModel at it, exactly like editing a Case or a Connection.
"""

from __future__ import annotations

from pathlib import Path

from django.db.models import QuerySet

from chatddx.repo.branch_models import (
    CaseBranchModel,
    ExpectBranchModel,
    OutputTypeBranchModel,
)
from chatddx.repo.shufflers.main import ensure_identity, qs_canon
from chatddx.repo.trail_models import (
    CaseTrailModel,
    ExpectTrailModel,
    OutputTypeTrailModel,
)
from chatddx.repo.trail_schemas import CaseSchema, ExpectSchema, OutputTypeSchema
from chatddx.utils import make_async


def expect_branch_name(case_id: int, output_type_id: int) -> str:
    """
    Deterministic branch name for a (case trail, output_type trail) pair, so
    the same pair always canonicalizes to a single current ExpectBranchModel
    row (via `qs_canon`) regardless of how many times its payload changes.
    """
    return f"{case_id}:{output_type_id}"


def dump_expect(
    case: CaseTrailModel,
    output_type: OutputTypeTrailModel,
    payload: str,
    owner_name: str,
) -> tuple[ExpectBranchModel, bool]:
    """
    Get-or-create the immutable Expect trail row for this exact content, and
    point a branch at it -- a no-op if the current canonical branch for this
    (case, output_type) pair already has this exact payload.
    """
    schema = ExpectSchema(
        payload=payload,
        case=CaseSchema.model_validate(case),
        output_type=OutputTypeSchema.model_validate(output_type),
    )

    owner = ensure_identity(owner_name)
    branch_name = expect_branch_name(case.pk, output_type.pk)

    canon = qs_canon(
        ExpectBranchModel.objects.filter(name=branch_name),
        owner.name,
    ).first()

    if canon and schema.fingerprint == canon.target.fingerprint:
        return canon, False

    trail, _ = ExpectTrailModel.objects.get_or_create(
        fingerprint=schema.fingerprint,
        defaults={
            "payload": schema.payload,
            "case": case,
            "output_type": output_type,
        },
    )

    branch = ExpectBranchModel.objects.create(
        target=trail,
        owner=owner,
        name=branch_name,
    )

    return branch, True


dump_expect_async = make_async(dump_expect)


def dump_expects(
    expects_dir: Path,
    owner_name: str,
    output_type_name: str = "free-text",
) -> dict[int, ExpectBranchModel]:
    """
    Dump every file in `expects_dir` as an Expect, paired with the Case whose
    branch name matches the file's name -- mirroring `dump_cases` -- against
    the `output_type_name` OutputType branch (see the registry's
    `[output_type.free-text]` entry, dumped by `dump_trail_registry`).

    A file with no matching Case branch for `owner_name` is skipped.
    """
    owner = ensure_identity(owner_name)

    output_type_branch = qs_canon(
        OutputTypeBranchModel.objects.filter(name=output_type_name),
        owner.name,
    ).first()

    if output_type_branch is None:
        raise ValueError(
            f"Output type '{output_type_name}' not found for owner '{owner_name}'"
        )

    dumped_expects: dict[int, ExpectBranchModel] = {}

    for expect_path in sorted(expects_dir.iterdir()):
        if not expect_path.is_file():
            continue

        case_branch = qs_canon(
            CaseBranchModel.objects.filter(name=expect_path.stem),
            owner.name,
        ).first()

        if case_branch is None:
            continue

        payload = expect_path.read_text(encoding="utf-8").rstrip("\n")

        branch, _ = dump_expect(
            case=case_branch.target,
            output_type=output_type_branch.target,
            payload=payload,
            owner_name=owner_name,
        )

        dumped_expects[branch.pk] = branch

    return dumped_expects


dump_expects_async = make_async(dump_expects)


def load_expects(case: CaseTrailModel, owner_name: str) -> QuerySet[ExpectBranchModel]:
    """The current (canonical) Expect branches for every OutputType paired with `case`."""
    return qs_canon(
        ExpectBranchModel.objects.filter(target__case_id=case.pk),
        owner_name,
    ).select_related("target", "target__output_type")


load_expects_async = make_async(load_expects)
