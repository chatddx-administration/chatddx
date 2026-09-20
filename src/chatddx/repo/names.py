"""
What a branch is called when nobody named it.

A branch nobody asked for still needs a name. `commit_closure` makes one for
every trail an owner holds only through another trail -- an agent's
connection, a tool group's tools -- and there is no form, no inventory file
and no user to take the name from.

The answer here is deliberately plain: the entity, then the head of the
fingerprint. There is room for a better one -- "connection of agent-1", a
slug of the payload, a counter per entity -- and this is the single place it
would be written, so no caller has to be revisited when it is.
"""

from chatddx.repo.registry import EntityName

SHORT_FINGERPRINT_LENGTH = 6


def short_fingerprint(fingerprint: str) -> str:
    """
    How a fingerprint is shown to a person: the head of it, the same length
    the change form and the branch `__str__` use.
    """
    return fingerprint[:SHORT_FINGERPRINT_LENGTH]


def resolve_branch_name(entity_name: EntityName, fingerprint: str) -> str:
    """
    A name for a branch of `entity_name` on `fingerprint`.

    Legible enough that a person meeting it in a dropdown can tell what it
    is and rename it, and unique enough for the natural key it becomes -- a
    branch is `(owner, name)`. "Enough" is doing work there: two trails of
    one entity whose fingerprints agree in the head would be handed the same
    name, and the second would be committed as a new version of the first's
    branch. A better resolver is where that stops being a bet.
    """
    return f"{entity_name} {short_fingerprint(fingerprint)}"
