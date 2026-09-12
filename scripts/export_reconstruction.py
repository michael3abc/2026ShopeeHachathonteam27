"""Deterministically export non-application reconstruction assets from the fixed baseline."""
from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import io
import json
import os
import subprocess
import tomllib
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

BASELINE = "485048cc73dc5c8f64d08034f49e318827418f80"
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/reconstruction/assets"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n").encode()


def collect():
    from pydantic import BaseModel, TypeAdapter
    from sqlalchemy.schema import CreateIndex, CreateTable
    from sqlalchemy.dialects import postgresql
    from return_agent_contracts import registry, service, activity
    from return_agent_contracts.export_schemas import SCHEMA_MODELS as agent
    from return_agent_contracts.export_ui_schemas import UI_SCHEMA_MODELS as ui
    from return_agent_contracts.export_operations_schemas import OPERATIONS_SCHEMA_MODELS as operations
    from return_agent.app import app
    from return_agent.db.models import Base
    from return_agent.db import case, activity as db_activity, agent_bridge  # noqa: F401
    from return_agent.store import ALLOWED_TRANSITIONS
    from return_agent_service.memory_replay import METADATA
    from return_agent_service.activity_workers import NARRATION_PROMPT, NarrationText
    from return_agent_runtime import prompts, graph

    outputs = {}
    sources = {}

    def put(path, value):
        if path.endswith(".sql") and isinstance(value, bytes):
            value = ("\n".join(line.rstrip() for line in value.decode().splitlines()).rstrip() + "\n").encode()
        outputs[path] = value if isinstance(value, bytes) else encode(value)

    def copy(source, destination):
        raw = subprocess.check_output(["git", "show", f"{BASELINE}:{source}"], cwd=ROOT)
        put(destination, raw)
        sources[destination] = {"path": source, "sha256": sha256(raw).hexdigest()}

    for group, models in (("agent", agent), ("ui", ui), ("operations", operations)):
        for filename, model in models.items():
            put(f"schemas/{group}/{filename}", TypeAdapter(model).json_schema())
    catalog = {}
    for module_name in ("models", "runtime", "ui", "service", "transport", "operations", "activity", "review_gates", "registry"):
        module = importlib.import_module("return_agent_contracts." + module_name)
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            if inspect.isclass(value) and issubclass(value, BaseModel) and value.__module__ == module.__name__:
                path = f"schemas/types/{name}.schema.json"
                put(path, value.model_json_schema())
                catalog[name] = {"schema": path, "description": inspect.getdoc(value) or "", "source": f"apps/contracts/src/return_agent_contracts/{module_name}.py"}
    for name in ("INTAKE_SCHEMA", "ASSESSMENT_SCHEMA", "RESOLVER_SCHEMA", "REVIEW_SCHEMA", "MEMORY_QUERY_SCHEMA"):
        schema = getattr(graph, name)
        put(f"schemas/model/{schema.name}.schema.json", schema.adapter.json_schema())
    put("schemas/model/NarrationText.schema.json", NarrationText.model_json_schema())
    from return_agent.capabilities.policy import PolicyDocumentFixture
    from return_agent.capabilities.evidence import EvidenceFixture
    put("schemas/fixtures/PolicyDocumentFixture.schema.json", PolicyDocumentFixture.model_json_schema())
    put("schemas/fixtures/EvidenceFixture.schema.json", EvidenceFixture.model_json_schema())
    put("contract-catalog.json", catalog)
    put("openapi.json", app.openapi())
    put("registry.json", {"version": registry.CLAIM_REGISTRY_VERSION, "major": registry.CLAIM_REGISTRY_MAJOR, "claims": [v.model_dump(mode="json") for v in registry.CLAIM_REGISTRY_V1.values()]})
    put("case-transitions.json", {k.value: sorted(v.value for v in values) for k, values in ALLOWED_TRANSITIONS.items()})
    put("redis-constants.json", {k: v for module in (service, activity) for k, v in vars(module).items() if isinstance(v, str) and ("STREAM" in k or "GROUP" in k)})
    put("budgets.json", {name: getattr(graph, name) for name in ("CLARIFICATION_LIMIT", "EVIDENCE_LIMIT", "VERIFICATION_LIMIT", "REVISION_LIMIT", "PROPOSE_LIMIT", "GRAPH_RECURSION_LIMIT")})
    for name in ("intake", "resolver", "reviewer", "memory-distiller", "memory-query"):
        copy(f"packages/agent_runtime/src/return_agent_runtime/prompt_text/{name}.txt", f"prompts/{name}.txt")
    put("prompts/narration.txt", (NARRATION_PROMPT + "\n").encode())
    put("prompts/versions.json", {**{k: v for k, v in vars(prompts).items() if k.endswith("_VERSION")}, "NARRATION_PROMPT_VERSION": "unversioned-inline@485048c"})
    copy("config/reviewer-gates.json", "reviewer-gates.json")
    for path in sorted((ROOT / "data/demo-case-study").rglob("*")):
        if path.is_file() and (path.name.endswith(".json.example") or path.suffix in {".png", ".jpg"}):
            copy(path.relative_to(ROOT).as_posix(), "demo/" + path.relative_to(ROOT / "data/demo-case-study").as_posix())
    image_prompt = subprocess.check_output(["git", "show", f"{BASELINE}:data/demo-case-study/prompt.md"], cwd=ROOT)
    put("demo/prompt.md", image_prompt.rstrip() + b"\n")
    # Export model metadata, not Python ORM/application code. PostgreSQL-specific types preserved.
    dialect = postgresql.dialect()
    dictionary = {}
    for owner, metadata in (("api", Base.metadata), ("agent-memory", METADATA)):
        ddl = ["-- Generated baseline DDL; fresh database only.", "CREATE EXTENSION IF NOT EXISTS vector;"]
        for table in metadata.sorted_tables:
            ddl.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
            indices = sorted(table.indexes, key=lambda i: str(i.name))
            ddl.extend(str(CreateIndex(index).compile(dialect=dialect)) + ";" for index in indices)
            dictionary[table.name] = {
                "owner": owner,
                "columns": [{"name": c.name, "type": str(c.type.compile(dialect=dialect)), "nullable": c.nullable, "primary_key": c.primary_key, "server_default": str(c.server_default.arg) if c.server_default else None, "application_default": str(c.default.arg) if c.default and c.default.is_scalar else None, "foreign_keys": sorted(f.target_fullname for f in c.foreign_keys)} for c in table.columns],
                "constraints": sorted(str(CreateTable(table).compile(dialect=dialect)).strip().splitlines()[1:-1]),
                "indexes": [{"name": i.name, "unique": i.unique, "sql": str(CreateIndex(i).compile(dialect=dialect))} for i in indices],
            }
        put(f"db/{owner}-fresh.sql", ("\n\n".join(ddl) + "\n").encode())
    put("db/dictionary.json", dictionary)
    # SQL-only journal and checkpoint storage contracts are not original app code.
    tree = ast.parse((ROOT / "apps/agent_service/src/return_agent_service/journal.py").read_text())
    journal = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "CREATE TABLE" in n.value)
    put("db/agent-journal-fresh.sql", (inspect.cleandoc(journal) + ";\n").encode())
    from langgraph.checkpoint.postgres.base import BasePostgresSaver
    put("db/checkpoint-migrations.json", {"library": "langgraph-checkpoint-postgres", "ordered_sql": BasePostgresSaver.MIGRATIONS})
    # Inventory all config access expressions, retaining declarative defaults, never process env.
    env = []
    provider_methods = []
    validators = []
    migrations = []
    for top in ("apps/api/src", "apps/agent_service/src", "packages/agent_runtime/src", "apps/contracts/src"):
        for file in sorted((ROOT / top).rglob("*.py")):
            tree = ast.parse(file.read_text())
            rel = file.relative_to(ROOT).as_posix()
            literal_constants = {}
            for assignment in tree.body:
                if isinstance(assignment, (ast.Assign, ast.AnnAssign)):
                    target = assignment.targets[0] if isinstance(assignment, ast.Assign) else assignment.target
                    if isinstance(target, ast.Name):
                        try:
                            literal_constants[target.id] = ast.literal_eval(assignment.value)
                        except (ValueError, TypeError):
                            pass
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and ast.unparse(node.func) in {"os.getenv", "os.environ.get"} and node.args and isinstance(node.args[0], ast.Constant):
                    default = ast.unparse(node.args[1]) if len(node.args) > 1 else "None"
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Name) and node.args[1].id in literal_constants:
                        default = repr(literal_constants[node.args[1].id])
                    env.append({"name": node.args[0].value, "default_expression": default, "source": rel})
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (node.name.startswith("validate_") or any("validator" in ast.unparse(d) for d in node.decorator_list)):
                    validators.append({"symbol": node.name, "source": rel, "description": ast.get_docstring(node) or "", "rejections": [ast.unparse(n.exc.args[0]) for n in ast.walk(node) if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and n.exc.args]})
            if file.name == "interfaces.py":
                for cls in tree.body:
                    if isinstance(cls, ast.ClassDef):
                        for method in cls.body:
                            if isinstance(method, ast.FunctionDef):
                                provider_methods.append({"provider": cls.name, "operation": method.name, "description": ast.get_docstring(cls), "parameters": [{"name": a.arg, "type": ast.unparse(a.annotation) if a.annotation else ""} for a in method.args.args if a.arg != "self"], "returns": ast.unparse(method.returns)})
    for file in sorted((ROOT / "apps/api/alembic/versions").glob("*.py")):
        tree = ast.parse(file.read_text())
        entry = {"source": file.relative_to(ROOT).as_posix(), "description": ast.get_docstring(tree)}
        for n in tree.body:
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                target = n.targets[0] if isinstance(n, ast.Assign) else n.target
                if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                    entry[target.id] = ast.literal_eval(n.value)
        migrations.append(entry)
    # Sanitize baseline's site-specific public endpoint defaults, explicitly documented.
    for entry in env:
        if "compass.yoyoserver.com" in entry["default_expression"]:
            entry["default_expression"] = "'https://embedding.example.invalid/v1' (portable substitution)"
    put("environment-inventory.json", env)
    put("providers.json", provider_methods)
    put("semantic-validation-inventory.json", validators)
    put("db/migration-history.json", migrations)
    # Historical SQL is portable data, not application source. Never open a DB.
    from alembic import command
    from alembic.config import Config
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql+psycopg://demo:demo@localhost/reconstruction"}):
        for entry in migrations:
            buffer = io.StringIO()
            config = Config(str(ROOT / "apps/api/alembic.ini"), output_buffer=buffer)
            config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
            command.upgrade(config, f"{entry['down_revision'] or 'base'}:{entry['revision']}", sql=True)
            put(f"db/migrations/{entry['revision']}.sql", buffer.getvalue().encode())
        buffer = io.StringIO()
        config = Config(str(ROOT / "apps/api/alembic.ini"), output_buffer=buffer)
        config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
        command.downgrade(config, "0012_human_review_dossier:0011_memory_vectors", sql=True)
        put("db/migrations/0012-protected-downgrade.sql", buffer.getvalue().encode())
    dependencies = tomllib.loads((ROOT / "uv.lock").read_text())
    put("dependencies/python-resolved.json", [{"name": p["name"], "version": p["version"]} for p in dependencies["package"]])
    npm = json.loads((ROOT / "apps/web/package-lock.json").read_text())
    put("dependencies/node-resolved.json", {path: {k: v for k, v in info.items() if k in {"version", "integrity", "engines"}} for path, info in npm["packages"].items()})
    for source in ("pyproject.toml", "apps/api/pyproject.toml", "apps/contracts/pyproject.toml", "apps/agent_service/pyproject.toml", "packages/agent_runtime/pyproject.toml", "apps/web/package.json"):
        copy(source, "dependencies/" + source.replace("/", "--"))
    # Snapshot deployment configuration is reference material, not a runnable original app.
    compose = subprocess.check_output(["git", "show", f"{BASELINE}:docker-compose.yml"], cwd=ROOT).decode()
    compose = compose.replace("https://compass.yoyoserver.com/v1", "https://embedding.example.invalid/v1")
    put("deployment/compose.reference.yml", compose.encode())
    for app_name in ("api", "agent_service", "web"):
        copy(f"apps/{app_name}/Dockerfile", f"deployment/{app_name}.Dockerfile.reference")
    copy("docs/spec/01-agent-graph.png", "diagrams/agent-graph.png")
    doc = subprocess.check_output(["git", "show", f"{BASELINE}:docs/spec/01-agent-graph.md"], cwd=ROOT).decode()
    put("diagrams/agent-graph.mmd", (doc.split("```mermaid\n", 1)[1].split("```", 1)[0]).encode())
    put("source-assets.json", {"baseline": BASELINE, "exact_copies": sources, "transforms": ["Python introspection exports schema, registry, database metadata and declarative inventories; no source implementation distributed", "Inline narration extracted unchanged, no original version constant", "Private deployment endpoint default replaced by example.invalid; no environment values read", "Generated SQL trailing whitespace normalized", {"source": "data/demo-case-study/prompt.md", "source_sha256": sha256(image_prompt).hexdigest(), "destination": "demo/prompt.md", "transform": "Trim trailing blank lines only; preserve synthetic image prompt content"}]})
    return outputs


def require_baseline_workspace():
    """Reject missing or changed source; never reinterpret an imported snapshot."""
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{BASELINE}^{{commit}}"], cwd=ROOT,
        capture_output=True, check=False,
    )
    if exists.returncode:
        raise SystemExit("baseline source unavailable; verify the preserved snapshot instead")
    # Code being imported must match baseline even after the docs commit.
    paths = ["apps", "packages", "uv.lock", "data/demo-case-study", "config", "docker-compose.yml"]
    changed = subprocess.check_output(["git", "diff", "--name-only", BASELINE, "--", *paths], cwd=ROOT).decode().splitlines()
    changed = [p for p in changed if not p.endswith("README.md")]
    if changed:
        raise SystemExit(f"baseline code drift: {changed}")
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *paths], cwd=ROOT
    ).decode().splitlines()
    if untracked:
        raise SystemExit(f"baseline has untracked source: {untracked}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    require_baseline_workspace()
    outputs = collect()
    existing_assets = {p.relative_to(TARGET).as_posix() for p in TARGET.rglob("*") if p.is_file()}
    unexpected = sorted(existing_assets - outputs.keys())
    if unexpected:
        raise SystemExit(f"unexpected assets; inspect before removing: {unexpected}")
    errors = []
    for name, raw in outputs.items():
        dest = TARGET / name
        if args.check:
            if not dest.exists() or dest.read_bytes() != raw:
                errors.append(name)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
    if errors:
        raise SystemExit(f"export drift: {errors}")
    print(json.dumps({"baseline": BASELINE, "exported_assets": len(outputs), "mode": "check" if args.check else "export"}))


if __name__ == "__main__":
    main()
