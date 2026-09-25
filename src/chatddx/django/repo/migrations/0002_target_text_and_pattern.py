"""A case's target, once a bare pattern, is its text and its pattern."""

from typing import Any

from django.db import migrations


def _each_target(apps: Any, reshape: Any) -> None:
    """Reshape each target of each case branch; a target reshaped to None goes."""
    CaseBranchModel = apps.get_model("repo", "CaseBranchModel")

    for branch in CaseBranchModel.objects.all():
        targets = branch.details.get("targets") or {}
        reshaped = {
            kind: reshape(target)
            for kind, target in targets.items()
            if reshape(target) is not None
        }

        if reshaped != targets:
            branch.details = {**branch.details, "targets": reshaped}
            branch.save(update_fields=["details"])


def forwards(apps: Any, _schema_editor: Any) -> None:
    _each_target(
        apps,
        lambda target: (
            {"text": None, "pattern": target} if isinstance(target, str) else target
        ),
    )


def backwards(apps: Any, _schema_editor: Any) -> None:
    _each_target(
        apps,
        lambda target: target.get("pattern") if isinstance(target, dict) else target,
    )


class Migration(migrations.Migration):
    dependencies = [("repo", "0001_initial")]

    operations = [migrations.RunPython(forwards, backwards)]
