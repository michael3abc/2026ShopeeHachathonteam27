"""Documentation-only checks; no services, credentials, or live models."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs/reconstruction"


def verify(package, *, schemas=False):
    command = [sys.executable, "-I", str(package / "tools/verify_package.py")]
    if schemas:
        command.append("--schemas")
    return subprocess.run(command, cwd=package, text=True, capture_output=True, timeout=60)


def update_hash(package, name):
    manifest = json.loads((package / "manifest.json").read_text())
    manifest["files"][name] = sha256((package / name).read_bytes()).hexdigest()
    (package / "manifest.json").write_text(json.dumps(manifest))


def test_package_integrity_and_schemas():
    result = verify(PACKAGE, schemas=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_fixtures_validated"] >= 45


def test_independent_zip_and_reproducibility(tmp_path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    for target in (first, second):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/package_reconstruction.py"), "--output", str(target)], cwd=ROOT, text=True, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert all(name.startswith("reconstruction/") and ".." not in Path(name).parts for name in archive.namelist())
        archive.extractall(tmp_path / "isolated")
    extracted = tmp_path / "isolated/reconstruction"
    result = verify(extracted, schemas=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"] == "PASS"


@pytest.mark.parametrize("mutation", ["hash", "missing", "external_link", "bad_schema_ref", "task_cycle", "invalid_fixture", "application_code"])
def test_rejects_corruption(tmp_path, mutation):
    package = tmp_path / "package"
    shutil.copytree(PACKAGE, package)
    if mutation == "hash":
        (package / "README.md").write_text("corrupted")
    elif mutation == "missing":
        (package / "assets/prompts/reviewer.txt").unlink()
    elif mutation == "external_link":
        path = package / "README.md"
        path.write_text(path.read_text() + "\n[forbidden](../../outside.md)\n")
        update_hash(package, "README.md")
    elif mutation == "bad_schema_ref":
        path = package / "assets/schemas/model/NarrationText.schema.json"
        path.write_text(json.dumps({"$ref": "#/$defs/Missing"}))
        update_hash(package, str(path.relative_to(package)))
    elif mutation == "task_cycle":
        path = package / "tasks.json"
        value = json.loads(path.read_text())
        value["tasks"][0]["depends_on"] = ["T10"]
        path.write_text(json.dumps(value))
        update_hash(package, "tasks.json")
    elif mutation == "invalid_fixture":
        path = package / "examples/semantic-fixtures.json"
        value = json.loads(path.read_text())
        value["review"]["verdict"] = "NOT_A_VERDICT"
        path.write_text(json.dumps(value))
        update_hash(package, str(path.relative_to(package)))
    else:
        (package / "application.py").write_text("pass\n")
        update_hash(package, "application.py")
    result = verify(package, schemas=True)
    assert result.returncode != 0, f"accepted {mutation}"


def test_preserved_baseline_semantics():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_reconstruction_semantics.py")], cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("missing,changed,untracked,error", [
    (True, b"", b"", "baseline source unavailable"),
    (False, b"apps/api/src/example.py\n", b"", "baseline code drift"),
    (False, b"", b"apps/api/src/new.py\n", "baseline has untracked source"),
    (False, b"", b"", None),
])
def test_export_requires_exact_baseline_source(monkeypatch, missing, changed, untracked, error):
    import importlib.util

    spec = importlib.util.spec_from_file_location("snapshot_exporter", ROOT / "scripts/export_reconstruction.py")
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    monkeypatch.setattr(exporter.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a[0], int(missing)))
    outputs = iter((changed, untracked))
    monkeypatch.setattr(exporter.subprocess, "check_output", lambda *a, **kw: next(outputs))
    if error:
        with pytest.raises(SystemExit, match=error):
            exporter.require_baseline_workspace()
    else:
        exporter.require_baseline_workspace()
