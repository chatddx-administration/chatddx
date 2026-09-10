from pathlib import Path

from chatddx.repo.base import BranchModel
from chatddx.repo.shufflers.main import dump_branch
from chatddx.repo.trail_schemas import CaseSchema
from chatddx.utils import make_async


def dump_cases(cases_dir: Path, owner_name: str) -> dict[int, BranchModel]:
    dumped_cases: dict[int, BranchModel] = {}

    for case_path in sorted(cases_dir.iterdir()):
        if not case_path.is_file():
            continue

        payload = case_path.read_text(encoding="utf-8").rstrip("\n")

        branch_model, _ = dump_branch(
            bundle_name="case",
            branch_name=case_path.stem,
            owner_name=owner_name,
            trail=CaseSchema(payload=payload),
        )

        dumped_cases[branch_model.pk] = branch_model

    return dumped_cases


dump_cases_async = make_async(dump_cases)
