"""Export versioned JSON Schema files for trusted operations boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from .operations import OPERATIONS_SCHEMA_MODELS


def export_operations_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in OPERATIONS_SCHEMA_MODELS.items():
        path = output_dir / filename
        path.write_text(
            json.dumps(
                TypeAdapter(model).json_schema(mode="validation"),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        written.append(path)

    manifest = output_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "operations_contract_version": "v1",
                "schemas": [path.name for path in written],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return [*written, manifest]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apps/contracts/schemas/operations/v1"),
        help="directory for versioned operations schemas",
    )
    args = parser.parse_args()
    for path in export_operations_schemas(args.output):
        print(path)


if __name__ == "__main__":
    main()
