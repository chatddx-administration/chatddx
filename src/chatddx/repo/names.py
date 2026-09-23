from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.canonical import fingerprint_digest

SHORT_FINGERPRINT_LENGTH = 6


def short_fingerprint(fingerprint: str) -> str:
    """The first hex digits of a fingerprint, past its scheme."""
    return fingerprint_digest(fingerprint)[:SHORT_FINGERPRINT_LENGTH]


def resolve_branch_name(entity_name: EntityName, fingerprint: str) -> str:
    return f"{entity_name} {short_fingerprint(fingerprint)}"
