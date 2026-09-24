# pyright: basic
"""What goes in the cell, and keeping what is in it as one's own."""

from django.db import transaction
from rich.text import Text

from chatddx.core import settings
from chatddx.core.repl.cell import NONE, OPTIONAL, SLICES
from chatddx.core.repl.render import LABEL
from chatddx.core.repl.shell import Repl
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailSchema
from chatddx.repo.entities.stack.pydantic import StackBranchSpec
from chatddx.repo.names import short_fingerprint
from chatddx.repo.shufflers.branch import (
    commit,
    commit_copies,
    get_branch_model,
    get_visible_branch_model,
)
from chatddx.repo.shufflers.trail import dump_trail


def use(repl: Repl, name: str) -> None:
    repl.cell.put(repl.configuration_named(name), _called(repl, name))
    repl.say_cell()


def on(repl: Repl, name: str) -> None:
    model = get_visible_branch_model("stack", repl.identity, name)
    repl.cell.stack = StackBranchSpec.model_validate(model)
    repl.say_cell()


def cell(repl: Repl, configuration: str, stack: str) -> None:
    """Both, each looked up before either is put in the cell."""
    configuration_model = repl.configuration_named(configuration)
    stack_model = get_visible_branch_model("stack", repl.identity, stack)

    repl.cell.put(configuration_model, _called(repl, configuration))
    repl.cell.stack = StackBranchSpec.model_validate(stack_model)
    repl.say_cell()


def set_(repl: Repl, entity: str, name: str) -> None:
    cell = repl.cell

    if entity not in SLICES:
        repl.error(f"no slice '{entity}': {', '.join(SLICES)}")
        return

    if not cell.configuration:
        repl.error("the cell has no configuration to set it in: use CONFIGURATION")
        return

    own = getattr(cell.configuration.target, entity)

    if name == NONE:
        if entity not in OPTIONAL:
            repl.error(
                f"a configuration always has a {entity}: only a toolset can be none"
            )
            return

        if own is None:
            _ = cell.variations.pop(entity, None)
        else:
            cell.variations[entity] = None

        repl.say_cell()
        return

    model = get_visible_branch_model(entity, repl.identity, name)
    spec = entity_of(entity).branch_spec.model_validate(model)

    if own is not None and own.fingerprint == spec.target.fingerprint:
        _ = cell.variations.pop(entity, None)
    else:
        cell.variations[entity] = spec

    repl.say_cell()


def save(repl: Repl, name: str) -> None:
    """
    Keep the cell's configuration, what is set in it included, as the
    identity's own. What it reaches becomes the identity's too, as the
    archive has it: a tool keeps what it runs.
    """
    cell = repl.cell

    if not cell.configuration:
        repl.error("the cell has no configuration to save: use CONFIGURATION")
        return

    if "/" in name:
        repl.error(f"a name can't hold '/', which parts an owner from a name: {name}")
        return

    entity = entity_of("configuration")
    schema = ConfigurationTrailSchema.model_validate(cell.slices, from_attributes=True)
    had = entity.branch_model.objects.filter(
        owner__name=repl.identity, name=name
    ).exists()

    with transaction.atomic():
        trail = dump_trail(ConfigurationTrailModel, schema)
        copied = commit_copies(trail, repl.identity, settings.ARCHIVE_IDENTITY_NAME)
        changed = commit(
            trail,
            entity.branch_details.model_validate(
                {"name": name, "owner": repl.identity, "tags": cell.configuration.tags}
            ),
        )

    what = "a new version" if had and changed else "unchanged" if had else "created"
    repl.console.print(
        f"saved as {name}: {what} {short_fingerprint(trail.fingerprint)}"
    )

    if copied:
        repl.console.print(Text(f"yours now too: {', '.join(copied)}", style=LABEL))

    repl.forget()
    cell.put(get_branch_model("configuration", repl.identity, name), name)
    repl.say_cell()


def _called(repl: Repl, name: str) -> str:
    """What the cell calls a configuration: what it was named, one's own bare."""
    return name.removeprefix(f"{repl.identity}/")
