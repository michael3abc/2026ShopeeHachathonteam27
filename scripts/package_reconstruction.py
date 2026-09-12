"""Build generated field appendix, fixture index, manifest and deterministic ZIP."""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs/reconstruction"
BASELINE = "485048cc73dc5c8f64d08034f49e318827418f80"


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def generate():
    lines = ["# 生成欄位字典（baseline固定）", "", "每個JSON property的required、形狀／限制均由schema生成；巢狀ref到同檔$defs，enum/oneOf/anyOf完整保留。schema以外的驗證見M01及semantic-validation-inventory。資料庫所有約束另見fresh SQL。", ""]
    catalog = json.loads((PACKAGE / "assets/contract-catalog.json").read_text())
    for name, info in sorted(catalog.items()):
        schema = json.loads((PACKAGE / "assets" / info["schema"]).read_text())
        lines += [f"## {name}", "", f"[完整巢狀Schema](assets/{info['schema']})", "", "| 欄位 | 必填 | 形狀／限制 |", "| --- | --- | --- |"]
        for field, definition in schema.get("properties", {}).items():
            shape = json.dumps({k: v for k, v in definition.items() if k not in {"title", "description"}}, ensure_ascii=False, separators=(",", ":")).replace("|", "&#124;")
            lines.append(f"| {field} | {'是' if field in schema.get('required', []) else '否'} | {shape} |")
        lines.append("")
    for table, info in json.loads((PACKAGE / "assets/db/dictionary.json").read_text()).items():
        lines += [f"## DB {table}", "", f"owner: {info['owner']}。完整check/unique/index見assets/db中的SQL與dictionary.json。", "", "| 欄位 | SQL型別 | NULL | PK | FK | default（server/application） |", "| --- | --- | --- | --- | --- | --- |"]
        for c in info["columns"]:
            lines.append(f"| {c['name']} | {c['type']} | {c['nullable']} | {c['primary_key']} | {','.join(c['foreign_keys'])} | {c['server_default']} / {c['application_default']} |")
        lines.append("")
    (PACKAGE / "reference-fields.md").write_text("\n".join(lines))
    index = []
    def add(file, pointer, schema, binding=None):
        item = {"file": file, "pointer": pointer, "schema": "assets/schemas/" + schema}
        if binding:
            item["runtime_binding"] = binding
        index.append(item)
    names = {"case_context": "CaseContext", "order_snapshot": "OrderSnapshot", "policy_bundle": "PolicyBundle", "assessment": "ApprovalEvidenceAssessment", "draft": "FullRefundProposedDecisionDraft", "handoff": "ProposedDecisionHandoff", "review": "ApprovedReviewResult", "revision_dossier": "HumanReviewDossier", "amount_dossier": "HumanReviewDossier", "candidate": "MemoryCandidate"}
    for field, model in names.items():
        add("examples/semantic-fixtures.json", "/"+field, f"types/{model}.schema.json")
    for i in range(4):
        add("examples/semantic-fixtures.json", f"/activities/{i}", "types/ActivityEvent.schema.json")
    for letter in "abc":
        file = f"assets/demo/case-{letter}.json.example"
        for key, model in (("case_context", "CaseContext"), ("order_snapshot", "OrderSnapshot"), ("initial_user_turn", "UserTurn"), ("create_case_request", "CreateCaseRequest")):
            add(file, "/"+key, f"types/{model}.schema.json")
        for i in range(len(json.loads((PACKAGE / file).read_text())["followup_messages"])):
            add(file, f"/followup_messages/{i}", "types/SendMessageRequest.schema.json")
    for filename, schema in (("evidence", "EvidenceFixture"), ("policy", "PolicyDocumentFixture")):
        file = f"assets/demo/{filename}.json.example"
        for i in range(len(json.loads((PACKAGE / file).read_text()))):
            add(file, f"/{i}", f"fixtures/{schema}.schema.json")
    add("assets/demo/memory-preload.json.example", "/candidate", "types/MemoryCandidate.schema.json")
    for i in range(2):
        add("assets/demo/human-review.json.example", f"/{i}/request", "ui/ReviewDecision.schema.json", {"handoff_id": "synthetic-bound-handoff"})
    dump(PACKAGE / "examples/fixture-index.json", index)
    # Capture machine-readable acceptance mapping from the hand-authored specification.
    rows = []
    for line in (PACKAGE / "acceptance.md").read_text().splitlines():
        match = re.match(r"\| (C\d{2}) / ([^|]+)\| ([^|]+)\| ([^|]+)\|", line)
        if match:
            rows.append(dict(zip(("id", "rules", "arrange_act", "assert"), (s.strip() for s in match.groups()))))
    assert len(rows) == 36
    dump(PACKAGE / "examples/conformance-cases.json", rows)


def package(output):
    generate()
    files = sorted(p for p in PACKAGE.rglob("*") if p.is_file() and p.name != "manifest.json")
    for file in files:
        assert not file.is_symlink()
        assert "__pycache__" not in file.parts
    hashes = {p.relative_to(PACKAGE).as_posix(): sha256(p.read_bytes()).hexdigest() for p in files}
    dump(PACKAGE / "manifest.json", {"baseline": BASELINE, "format_version": "1.0", "hash_algorithm": "sha256", "files": hashes})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted([*files, PACKAGE / "manifest.json"]):
            info = zipfile.ZipInfo("reconstruction/" + path.relative_to(PACKAGE).as_posix(), date_time=(2026, 9, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(json.dumps({"zip": str(output), "files": len(files)+1, "bytes": output.stat().st_size, "sha256": digest}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".artifacts/reconstruction/reconstruction-485048c.zip")
    args = parser.parse_args()
    package(args.output.resolve())
