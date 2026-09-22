from chatddx.repo.entity_names import EntityName

SHORT_FINGERPRINT_LENGTH = 6


def short_fingerprint(fingerprint: str) -> str:
    return fingerprint[:SHORT_FINGERPRINT_LENGTH]


def resolve_branch_name(entity_name: EntityName, fingerprint: str) -> str:
    return f"{entity_name} {short_fingerprint(fingerprint)}"
