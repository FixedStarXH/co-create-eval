"""Server-side configuration."""

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def database_url() -> str:
    return os.environ.get("DATABASE_URL", f"sqlite:///{(BACKEND_ROOT / 'data' / 'app.sqlite3').as_posix()}")
