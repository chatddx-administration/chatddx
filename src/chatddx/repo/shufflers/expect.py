# src/chatddx/repo/shufflers/expect.py

from __future__ import annotations

from pathlib import Path

from django.db.models import QuerySet

from chatddx.repo.branch_models import CaseBranchModel, ExpectBranchModel
from chatddx.repo.shufflers.main import ensure_identity, qs_canon
from chatddx.repo.trail_models import CaseTrailModel, ExpectTrailModel, ScorerTrailModel
from chatddx.repo.trail_schemas import CaseSchema, ExpectSchema, ScorerSchema
from chatddx.utils import make_async


def expect_branch_name(case_id: int, scorer: ScorerTrailModel | None) -> str:
    return f"{case_id}:{scorer.name if scorer else ''}"


def dump_expect(
    case: CaseTrailModel,
    scorer: ScorerTrailModel | None,
    payload: str,
    owner_name: str,
) -> tuple[ExpectBranchModel, bool]:
    schema = ExpectSchema(
        payload=payload,
        scorer=ScorerSchema.model_validate(scorer) if scorer else None,
        case=CaseSchema.model_validate(case),
    )

    owner = ensure_identity(owner_name)
    branch_name = expect_branch_name(case.pk, scorer)

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
            "scorer": scorer,
            "case": case,
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
    scorer: ScorerTrailModel | None = None,
) -> dict[int, ExpectBranchModel]:
    owner = ensure_identity(owner_name)

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
            scorer=scorer,
            payload=payload,
            owner_name=owner_name,
        )

        dumped_expects[branch.pk] = branch

    return dumped_expects


dump_expects_async = make_async(dump_expects)


def load_expects(case: CaseTrailModel, owner_name: str) -> QuerySet[ExpectBranchModel]:
    return qs_canon(
        ExpectBranchModel.objects.filter(target__case_id=case.pk),
        owner_name,
    ).select_related("target")


load_expects_async = make_async(load_expects)
