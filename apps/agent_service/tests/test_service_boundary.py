from __future__ import annotations

import re
from pathlib import Path


def test_agent_service_does_not_import_api_package() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src"
    forbidden = re.compile(r"(?:from|import)\s+return_agent(?:\s|\.)")
    for path in source_root.rglob("*.py"):
        assert forbidden.search(path.read_text(encoding="utf-8")) is None, path


def test_runtime_package_contains_no_service_framework_imports() -> None:
    runtime_root = Path(__file__).resolve().parents[3] / "packages/agent_runtime/src"
    forbidden = ("fastapi", "redis", "sqlalchemy", "return_agent_service")
    for path in runtime_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(name in source for name in forbidden), path
