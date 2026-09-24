import os
from pathlib import Path

MODE = os.environ.get("CHATDDX_MODE")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ARCHIVE_IDENTITY_NAME = "archive"

INVENTORY_PATH = PROJECT_ROOT / "data"
