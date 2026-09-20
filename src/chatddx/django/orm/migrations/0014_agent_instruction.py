from contextlib import contextmanager
from pathlib import Path

import django.db.models.deletion
from django.db import migrations, models

import chatddx.repo.families.django
from chatddx.utils import generate_fingerprint

SQL_DIR = Path(chatddx.repo.families.django.__file__).parent.parent / "sql"

AGENT_TABLE = "agents_agent"

SHORT_FINGERPRINT_LENGTH = 6


@contextmanager
def without_the_trigger(schema_editor, table_name: str):
    """
    Lift the immutability trigger off `table_name` for as long as the block
    runs, and put it back after.

    A trail is immutable by trigger (see `chatddx.django.orm.apps`), which
    is what a fingerprint is for -- and rewriting every one of them is the
    one thing a migration that changes what a fingerprint covers has to do.
    """
    context = {"table_name": table_name}

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"DROP TRIGGER IF EXISTS trg_protect_trail_{table_name} "
            + f'ON "{table_name}";'
        )

    yield

    with schema_editor.connection.cursor() as cursor:
        cursor.execute((SQL_DIR / "trail_functions.sql").read_text().format(**context))
        cursor.execute((SQL_DIR / "trail_triggers.sql").read_text().format(**context))


def agent_fingerprint(agent, instruction_fingerprint: str | None) -> str:
    """
    What an agent's fingerprint covers, on either side of this migration.

    Mirrors `TrailSchema.as_fingerprint`: an agent serializes to the
    fingerprints of the trails it points at, plus -- before this migration
    -- the instruction text it held itself.
    """
    covered = {
        "connection": agent.connection.fingerprint,
        "sampling_params": agent.sampling_params.fingerprint,
        "output_type": agent.output_type.fingerprint,
        "tool_group": agent.tool_group.fingerprint,
    }

    if instruction_fingerprint is None:
        return generate_fingerprint(covered | {"instructions": agent.instructions})

    return generate_fingerprint(covered | {"instruction": instruction_fingerprint})


def name_for(fingerprint: str) -> str:
    """
    What a branch nobody named is called -- the same answer
    `chatddx.repo.names.resolve_branch_name` gives.
    """
    return f"instruction {fingerprint[:SHORT_FINGERPRINT_LENGTH]}"


def agents(apps):
    return (
        apps.get_model("orm", "AgentTrailModel")
        .objects.select_related(
            "connection",
            "sampling_params",
            "output_type",
            "tool_group",
        )
        .iterator()
    )


def bundle_the_instructions(apps, schema_editor):
    """
    Give every agent's instructions a bundle of their own to live in.

    Agents saying the same thing end up pointing at one instruction, the
    way agents on one connection already do, and each owner is left with a
    branch on it -- the guarantee `commit_closure` keeps for everything an
    agent reaches.
    """
    instruction_model = apps.get_model("orm", "InstructionTrailModel")
    instruction_branch_model = apps.get_model("orm", "InstructionBranchModel")
    agent_branch_model = apps.get_model("orm", "AgentBranchModel")

    with without_the_trigger(schema_editor, AGENT_TABLE):
        for agent in agents(apps):
            definition = agent.instructions

            instruction, _ = instruction_model.objects.get_or_create(
                fingerprint=generate_fingerprint({"definition": definition}),
                defaults={"definition": definition},
            )

            agent.instruction = instruction
            agent.fingerprint = agent_fingerprint(agent, instruction.fingerprint)
            agent.save(update_fields=["instruction", "fingerprint"])

    fingerprints = dict(instruction_model.objects.values_list("pk", "fingerprint"))

    owners = (
        agent_branch_model.objects.values_list("target__instruction", "owner")
        .order_by()
        .distinct()
    )

    for instruction_id, owner_id in owners:
        _ = instruction_branch_model.objects.get_or_create(
            target_id=instruction_id,
            owner_id=owner_id,
            defaults={"name": name_for(fingerprints[instruction_id])},
        )


def unbundle_the_instructions(apps, schema_editor):
    """
    Put the text back on the agent, and the fingerprint back to what it
    covered while it was there.
    """
    with without_the_trigger(schema_editor, AGENT_TABLE):
        for agent in agents(apps):
            agent.instructions = agent.instruction.definition
            agent.fingerprint = agent_fingerprint(agent, None)
            agent.save(update_fields=["instructions", "fingerprint"])


class Migration(migrations.Migration):
    """
    Break an agent's instructions out into an instruction of their own.

    The text was the one value an agent held; it is an entity now, so an
    agent is nothing but the trails it points at. What a fingerprint covers
    changes with it -- the instruction's fingerprint in place of the text --
    so every agent's is rewritten here, with the immutability trigger lifted
    for exactly as long as that takes.
    """

    dependencies = [
        ("orm", "0013_batchmodel_batch_experimentmodel_batch"),
    ]

    operations = [
        migrations.CreateModel(
            name="InstructionTrailModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "fingerprint",
                    models.CharField(
                        db_index=True, editable=False, max_length=64, unique=True
                    ),
                ),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("definition", models.TextField()),
            ],
            options={
                "db_table": "agents_instruction",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="InstructionBranchModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                (
                    "collaborators",
                    models.ManyToManyField(
                        blank=True,
                        related_name="shared_%(class)s",
                        to="orm.identitymodel",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owned_%(class)s",
                        to="orm.identitymodel",
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(
                        blank=True, related_name="tagged_%(class)s", to="orm.tagmodel"
                    ),
                ),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="branches",
                        to="orm.instructiontrailmodel",
                    ),
                ),
            ],
            options={
                "db_table": "agents_instruction_branch",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Instruction",
            fields=[],
            options={
                "verbose_name": "Instruction",
                "verbose_name_plural": "Instructions",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=(
                chatddx.repo.families.django.BranchProxy,
                "orm.instructionbranchmodel",
            ),
        ),
        migrations.AddIndex(
            model_name="instructionbranchmodel",
            index=models.Index(
                fields=["owner", "name", "-timestamp"],
                name="agents_inst_owner_i_882f05_idx",
            ),
        ),
        # nullable while the agents that have no instruction yet are filled in
        migrations.AddField(
            model_name="agenttrailmodel",
            name="instruction",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="orm.instructiontrailmodel",
            ),
        ),
        # and the text it replaces nullable, so that going back the other
        # way can add the column before `unbundle_the_instructions` fills it
        migrations.AlterField(
            model_name="agenttrailmodel",
            name="instructions",
            field=models.TextField(null=True),
        ),
        migrations.RunPython(
            bundle_the_instructions,
            unbundle_the_instructions,
        ),
        migrations.AlterField(
            model_name="agenttrailmodel",
            name="instruction",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="orm.instructiontrailmodel",
            ),
        ),
        migrations.RemoveField(
            model_name="agenttrailmodel",
            name="instructions",
        ),
    ]
