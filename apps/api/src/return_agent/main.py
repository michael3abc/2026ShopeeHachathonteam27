"""Container entrypoint: migrate the API database, then serve FastAPI."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config


def main() -> None:
    api_root = Path(__file__).resolve().parents[2]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    command.upgrade(config, "head")
    uvicorn.run("return_agent.app:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
