"""Fail when source-backed architecture changed after the Explorer baseline."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


manifest = json.loads((HERE / "source-manifest.json").read_text())
baseline = manifest["baseline"]["commit"]
scope = set(manifest["architecturePaths"])

if subprocess.run(
    ["git", "merge-base", "--is-ancestor", baseline, "HEAD"], cwd=ROOT
).returncode:
    raise SystemExit(
        f"Architecture Explorer baseline {baseline} is not an ancestor of HEAD. "
        "Choose and review a new committed baseline."
    )

changed = set(filter(None, git("diff", "--name-only", f"{baseline}..HEAD").splitlines()))
drift = sorted(changed & scope)
if drift:
    joined = "\n  - ".join(drift)
    raise SystemExit(
        "Architecture Explorer is stale. These manifest-covered architecture sources "
        f"changed after baseline {baseline[:7]}:\n  - {joined}\n"
        "Review the new implementation, update presentation/baseline.json and content.py, "
        "then rebuild the Explorer."
    )

print(
    f"Architecture sync passed: {len(scope)} manifest-covered sources unchanged "
    f"after {baseline[:7]}."
)
