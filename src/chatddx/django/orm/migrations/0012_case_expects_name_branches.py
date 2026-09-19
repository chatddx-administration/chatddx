import django.db.models.deletion
from django.db import migrations, models


def branch_for(expect_branch_model, case, trail_id):
    """
    The expect branch a case-to-trail link stood for.

    A trail is shared by every expectation with the same payload and scorer,
    so the link alone cannot say which one it was. The owner's branches of
    that trail are the candidates, and the one named after this case -- the
    `<case>|<scorer>` both the inventory parser and the expect inline write
    -- is the link's own; failing that, their latest branch of it.
    """
    candidates = expect_branch_model.objects.filter(
        target_id=trail_id,
        owner_id=case.owner_id,
    ).order_by("-timestamp")

    own = candidates.filter(name__startswith=f"{case.name}|").first()

    return own or candidates.first()


def name_the_expect_branches(apps, schema_editor):
    case_expect_model = apps.get_model("orm", "CaseExpect")
    expect_branch_model = apps.get_model("orm", "ExpectBranchModel")

    orphaned = []

    for link in case_expect_model.objects.select_related("case").iterator():
        branch = branch_for(expect_branch_model, link.case, link.expect_trail_id)

        if branch is None:
            orphaned.append(link.pk)
            continue

        link.expect_branch = branch
        link.save(update_fields=["expect_branch"])

    # A link whose owner has no branch of the trail names an expectation that
    # cannot be told apart from anyone else's, which is what this migration is
    # here to stop.
    _ = case_expect_model.objects.filter(pk__in=orphaned).delete()


def name_the_expect_trails(apps, schema_editor):
    case_expect_model = apps.get_model("orm", "CaseExpect")

    for link in case_expect_model.objects.select_related("expect_branch").iterator():
        link.expect_trail_id = link.expect_branch.target_id
        link.save(update_fields=["expect_trail"])


class Migration(migrations.Migration):
    """
    Let a case name the expect *branches* it carries instead of their trails.

    Expectations with the same payload and scorer share one content-addressed
    trail, so a link to a trail matched every case that expected the same
    thing. Which branch each link stood for is recovered by name, see
    `branch_for`.
    """

    dependencies = [
        ("orm", "0011_casetrailmodel_expecttrailmodel_scorertrailmodel_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="casebranchmodel",
            name="expects",
        ),
        migrations.AlterField(
            model_name="caseexpect",
            name="expect",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="orm.expecttrailmodel",
            ),
        ),
        migrations.RenameField(
            model_name="caseexpect",
            old_name="expect",
            new_name="expect_trail",
        ),
        migrations.AddField(
            model_name="caseexpect",
            name="expect_branch",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="orm.expectbranchmodel",
            ),
        ),
        migrations.RunPython(name_the_expect_branches, name_the_expect_trails),
        migrations.RemoveField(
            model_name="caseexpect",
            name="expect_trail",
        ),
        migrations.RenameField(
            model_name="caseexpect",
            old_name="expect_branch",
            new_name="expect",
        ),
        migrations.AlterField(
            model_name="caseexpect",
            name="expect",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to="orm.expectbranchmodel",
            ),
        ),
        migrations.AddField(
            model_name="casebranchmodel",
            name="expects",
            field=models.ManyToManyField(
                related_name="cases",
                through="orm.CaseExpect",
                through_fields=("case", "expect"),
                to="orm.expectbranchmodel",
            ),
        ),
    ]
