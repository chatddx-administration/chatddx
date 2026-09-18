import django.db.models.deletion
from django.db import migrations, models


def link_case_branches(apps, schema_editor):
    """
    Move every case/expect link from the case trail to the case branches of
    the owners that have a branch for the linked expect.
    """
    CaseExpect = apps.get_model("orm", "CaseExpect")
    CaseBranchModel = apps.get_model("orm", "CaseBranchModel")
    ExpectBranchModel = apps.get_model("orm", "ExpectBranchModel")

    for link in CaseExpect.objects.all():
        owners = set(
            ExpectBranchModel.objects.filter(
                target_id=link.expect_id,
            ).values_list("owner_id", flat=True)
        )

        branches = [
            branch
            for branch in CaseBranchModel.objects.filter(target_id=link.case_id)
            if branch.owner_id in owners
        ]

        if not branches:
            link.delete()
            continue

        link.case_branch_id = branches[0].pk
        link.save(update_fields=["case_branch"])

        for branch in branches[1:]:
            CaseExpect.objects.create(
                case_id=link.case_id,
                expect_id=link.expect_id,
                case_branch_id=branch.pk,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("orm", "0012_remove_casetrailmodel_expects_and_more"),
    ]

    operations = [
        # 0012 dropped `expects` from the case trail's state but kept the link
        # table it was built on, so there is no trail-side field to remove.
        migrations.AddField(
            model_name="caseexpect",
            name="case_branch",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="orm.casebranchmodel",
            ),
        ),
        migrations.RunPython(link_case_branches, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="caseexpect",
            name="case",
        ),
        migrations.RenameField(
            model_name="caseexpect",
            old_name="case_branch",
            new_name="case",
        ),
        migrations.AlterField(
            model_name="caseexpect",
            name="case",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="orm.casebranchmodel",
            ),
        ),
        migrations.AddField(
            model_name="casebranchmodel",
            name="expects",
            field=models.ManyToManyField(
                related_name="cases",
                through="orm.CaseExpect",
                through_fields=("case", "expect"),
                to="orm.expecttrailmodel",
            ),
        ),
    ]
