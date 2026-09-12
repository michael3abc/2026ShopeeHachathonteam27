from __future__ import annotations

import filecmp
from pathlib import Path

from return_agent_contracts.export_operations_schemas import (
    export_operations_schemas,
)
from return_agent_contracts.operations import OPERATIONS_SCHEMA_MODELS


def test_exported_operation_schemas_match_committed_v1(tmp_path) -> None:
    generated = tmp_path / "v1"
    export_operations_schemas(generated)
    contracts_root = Path(__file__).resolve().parents[2]
    committed = contracts_root / "schemas/operations/v1"
    expected_names = {*OPERATIONS_SCHEMA_MODELS.keys(), "manifest.json"}

    assert {path.name for path in generated.iterdir()} == expected_names
    assert {path.name for path in committed.iterdir()} == expected_names
    for filename in expected_names:
        assert filecmp.cmp(generated / filename, committed / filename, shallow=False)
