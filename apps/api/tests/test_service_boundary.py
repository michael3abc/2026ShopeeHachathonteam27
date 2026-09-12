from __future__ import annotations

from pathlib import Path


def test_api_does_not_import_agent_runtime() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    for path in source_root.rglob("*.py"):
        assert "return_agent_runtime" not in path.read_text(encoding="utf-8"), path
