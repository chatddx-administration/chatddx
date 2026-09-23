from django.db.models import TextChoices


class RoleChoices(TextChoices):
    SYSTEM = "system", "System"
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    TOOL = "tool", "Tool"
    UNKNOWN = "unknown", "Unknown"


class MessageKindChoices(TextChoices):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    PROMPT = "prompt"


class RunStatusChoices(TextChoices):
    STORED = "stored", "Stored"
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    ERRORED = "errored", "Errored"
    COMPLETED = "completed", "Completed"
    SCORED = "scored", "Scored"


class SessionContextChoices(TextChoices):
    CHAT = "chat", "Chat"
    REPL = "repl", "REPL"
    EXPERIMENT = "experiment", "Experiment"
