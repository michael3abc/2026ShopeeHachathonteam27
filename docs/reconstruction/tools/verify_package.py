"""Offline package integrity check. Standard library; --schemas adds jsonschema."""
from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def pointer(value, fragment):
    if not fragment:
        return value
    assert fragment.startswith("/"), f"unsupported pointer {fragment}"
    for part in fragment[1:].split("/"):
        part = unquote(part).replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def in_package(path):
    resolved = path.resolve()
    assert resolved.is_relative_to(ROOT), f"external file dependency: {path}"
    assert resolved.is_file(), f"missing {path}"
    return resolved


def visit_refs(value, file):
    count = 0
    if isinstance(value, dict):
        if "$ref" in value:
            ref = value["$ref"]
            path, _, fragment = ref.partition("#")
            assert not re.match(r"[a-zA-Z]+:", path), f"network schema ref: {ref}"
            target = in_package(file.parent / path) if path else file
            pointer(json.loads(target.read_text()), fragment)
            count += 1
        for child in value.values():
            count += visit_refs(child, file)
    elif isinstance(value, list):
        for child in value:
            count += visit_refs(child, file)
    return count


def verify(schemas=False):
    manifest = json.loads((ROOT / "manifest.json").read_text())
    files = {p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob("*") if p.is_file() and p.name != "manifest.json"}
    assert set(files) == set(manifest["files"]), "manifest file-set mismatch"
    links = references = 0
    for name, file in files.items():
        assert not file.is_symlink(), f"symlink: {name}"
        assert sha256(file.read_bytes()).hexdigest() == manifest["files"][name], f"hash mismatch: {name}"
        assert not any(part in {".git", "__pycache__", "node_modules", ".secrets"} for part in file.parts)
        assert file.name not in {".env", ".env.local", "id_rsa", "id_ed25519"}, f"secret file: {name}"
        if file.suffix not in {".png", ".jpg"}:
            content = file.read_text()
            for pattern in (r"sk-[A-Za-z0-9_-]{24,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "/home/" + "michael/", r"https?://(?:compass|qwen)\.yoyoserver\.com"):
                assert not re.search(pattern, content), f"private material pattern: {name}"
        if file.suffix in {".py", ".ts", ".tsx", ".js", ".mjs"}:
            assert name == "tools/verify_package.py", f"application source in package: {name}"
        if file.suffix == ".md":
            for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", file.read_text()):
                link = link.strip("<>")
                if re.match(r"[a-zA-Z]+:", link) or link.startswith("#"):
                    continue
                in_package(file.parent / unquote(link.split("#", 1)[0]))
                links += 1
        if file.name.endswith(".schema.json") or file.name == "openapi.json":
            references += visit_refs(json.loads(file.read_text()), file)
    required_sections = ("責任與非責任", "依賴", "輸入輸出", "資料與演算法", "正常／失敗流程", "驗收條件")
    for index in range(1, 9):
        module = next(ROOT.glob(f"M{index:02d}-*.md"))
        body = module.read_text()
        assert all(section in body for section in required_sections), module
        assert f"M{index:02d}-R01" in body
    tasks = json.loads((ROOT / "tasks.json").read_text())["tasks"]
    seen = set()
    modules = set()
    for task in tasks:
        assert task["id"] not in seen
        assert set(task["depends_on"]) <= seen, f"task order/cycle: {task}"
        seen.add(task["id"])
        modules.update(task["modules"])
    assert modules == {f"M{i:02d}" for i in range(1, 9)}
    assert set(re.findall(r"C\d{2}", (ROOT / "acceptance.md").read_text())) >= {f"C{i:02d}" for i in range(1, 37)}
    for name in ("intake", "resolver", "reviewer", "memory-query", "memory-distiller", "narration"):
        assert (ROOT / f"assets/prompts/{name}.txt").stat().st_size > 0
    gate = json.loads((ROOT / "assets/reviewer-gates.json").read_text())
    assert gate == {"version": "reviewer-gates:1.0", "thresholds": {"TWD": "5000", "SGD": "200"}}
    assets = json.loads((ROOT / "assets/demo/assets-manifest.json.example").read_text())
    images = 0
    for item in assets["assets"]:
        if item.get("required"):
            in_package(ROOT / "assets/demo" / item["local_path"])
            images += 1
    assert images == 12
    fixture_count = 0
    if schemas:
        from jsonschema import Draft202012Validator, FormatChecker
        for path in (ROOT / "assets/schemas").rglob("*.schema.json"):
            Draft202012Validator.check_schema(json.loads(path.read_text()))
        for example in json.loads((ROOT / "examples/fixture-index.json").read_text()):
            raw = json.loads(in_package(ROOT / example["file"]).read_text())
            raw = pointer(raw, example.get("pointer", ""))
            raw = {**raw, **example.get("runtime_binding", {})} if example.get("runtime_binding") else raw
            schema = json.loads(in_package(ROOT / example["schema"]).read_text())
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(raw)
            fixture_count += 1
    return {"baseline": manifest["baseline"], "files": len(files), "links": links, "schema_refs": references, "modules": 8, "tasks": len(tasks), "required_images": images, "schema_fixtures_validated": fixture_count, "result": "PASS"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schemas", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.schemas), ensure_ascii=False))
