"""Build both static targets exclusively from a pinned committed source snapshot.

No application import, service connection, dependency installation or secret read.
The AST inventory is checked against a reviewed routing catalogue; it is not a
general proof of dynamic reachability. Updating the baseline requires review.
"""
from __future__ import annotations

import ast
import hashlib
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASELINE = json.loads((HERE / "baseline.json").read_text())
SHA = BASELINE["commit"]
CACHE: dict[str, str] = {}
SOURCES: dict[str, dict[str, Any]] = {}


def committed(path: str) -> str:
    if path not in CACHE:
        CACHE[path] = subprocess.check_output(
            ["git", "show", f"{SHA}:{path}"], cwd=ROOT, text=True
        )
    return CACHE[path]


def reference(path: str, symbol: str = "") -> str:
    key = f"{path}::{symbol}"
    if key in SOURCES:
        return key
    source = committed(path)
    lines = source.splitlines()
    start, end = 1, min(len(lines), 55)
    if symbol:
        if path.endswith(".py"):
            candidates = [n for n in ast.walk(ast.parse(source))
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                          and n.name == symbol]
        else:
            candidates = []
        if candidates:
            start = candidates[0].lineno
            end = candidates[0].end_lineno or start
        else:
            matches = [i + 1 for i, line in enumerate(lines) if symbol in line]
            if not matches:
                raise ValueError(f"Source symbol not found: {key}")
            start = matches[0]
            end = min(len(lines), start + 35)
    SOURCES[key] = {
        "id": key, "path": path, "symbol": symbol or "file", "line": start,
        "endLine": end, "sha256": hashlib.sha256(source.encode()).hexdigest(),
        "url": f"{BASELINE['repository']}/blob/{SHA}/{path}#L{start}-L{end}",
        "excerpt": "\n".join(f"{i + 1:4}  {lines[i]}" for i in range(start - 1, end)),
        "evidence": "Source verified",
    }
    return key


def graph_inventory() -> dict[str, Any]:
    path = "packages/agent_runtime/src/return_agent_runtime/graph.py"
    tree = ast.parse(committed(path))
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    builder = functions["build_graph"]
    names = []
    for node in ast.walk(builder):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add_node":
            names.append(ast.literal_eval(node.args[0]))
    # Keep source registration order.  Some real nodes are supplied by focused
    # modules (for example Policy v2), not graph.py private helpers.
    known = set(names) | {"__end__"}

    def local_functions(name: str, seen: set[str]) -> list[ast.FunctionDef]:
        if name in seen or name not in functions or name == "build_graph":
            return []
        seen.add(name)
        fn = functions[name]
        result = [fn]
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                result.extend(local_functions(node.func.id, seen))
        return result

    external_nodes = {
        "evaluate_policy": ("packages/agent_runtime/src/return_agent_runtime/policy.py", "evaluate_policy_node"),
        "confirm_policy_path": ("packages/agent_runtime/src/return_agent_runtime/policy.py", "confirm_policy_path_node"),
    }
    inventory = {}
    for name in names:
        routes: dict[str, list[int]] = {}
        reads = set()
        if name in external_nodes:
            node_path, node_symbol = external_nodes[name]
            node_tree = ast.parse(committed(node_path))
            node_functions = {n.name: n for n in node_tree.body if isinstance(n, ast.FunctionDef)}

            def external_functions(function_name: str, seen: set[str]) -> list[ast.FunctionDef]:
                if function_name in seen or function_name not in node_functions:
                    return []
                seen.add(function_name)
                function = node_functions[function_name]
                result = [function]
                for call in ast.walk(function):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                        result.extend(external_functions(call.func.id, seen))
                return result

            node_functions_to_scan = external_functions(node_symbol, set())
            node_source = reference(node_path, node_symbol)
        else:
            node_functions_to_scan = local_functions(f"_{name}_node", set())
            node_source = reference(path, f"_{name}_node")
        for fn in node_functions_to_scan:
            for node in ast.walk(fn):
                expressions = []
                if isinstance(node, ast.Dict):
                    expressions = [value for key, value in zip(node.keys, node.values)
                                   if isinstance(key, ast.Constant) and key.value == "_route"]
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) and target.slice.value == "_route":
                            expressions.append(node.value)
                for expression in expressions:
                    for value in ast.walk(expression):
                        if isinstance(value, ast.Constant) and value.value in known:
                            routes.setdefault(value.value, []).append(value.lineno)
                if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "state" and isinstance(node.ctx, ast.Load) and isinstance(node.slice, ast.Constant):
                    reads.add(node.slice.value)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "state" and node.func.attr == "get" and node.args and isinstance(node.args[0], ast.Constant):
                    reads.add(node.args[0].value)
        if name == "terminate_automation":
            routes["__end__"] = [next(n.lineno for n in ast.walk(builder)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "add_edge" and isinstance(n.args[0], ast.Constant)
                and n.args[0].value == "terminate_automation")]
        inventory[name] = {"routes": {k: sorted(set(v)) for k, v in routes.items()},
                           "reads": sorted(reads), "source": node_source}
    return {"nodes": inventory, "source": reference(path, "build_graph"),
            "registration": "每個 conditional source 共用 destinations；註冊允許不等於業務可達。"}


def schema_inventory() -> dict[str, Any]:
    state_path = "packages/agent_runtime/src/return_agent_runtime/state.py"
    tree = ast.parse(committed(state_path))
    state = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AgentState")
    fields = {n.target.id: ast.unparse(n.annotation) for n in state.body
              if isinstance(n, ast.AnnAssign)}
    paths = ["apps/api/src/return_agent/db/models.py", "apps/api/src/return_agent/db/case.py",
             "apps/api/src/return_agent/db/activity.py", "apps/api/src/return_agent/db/agent_bridge.py"]
    tables = []
    for path in paths:
        for node in ast.parse(committed(path)).body:
            if not isinstance(node, ast.ClassDef):
                continue
            tablename = next((ast.literal_eval(n.value) for n in node.body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in n.targets)), None)
            if not tablename:
                continue
            columns, foreign_keys = [], []
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    columns.append(item.target.id)
                    for call in ast.walk(item):
                        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "ForeignKey":
                            foreign_keys.append({"column": item.target.id, "target": ast.unparse(call.args[0]), "kind": "DB foreign key"})
            tables.append({"name": tablename, "columns": columns, "foreignKeys": foreign_keys,
                           "owner": "api", "source": reference(path, node.name)})
    return {"fields": fields, "source": reference(state_path, "AgentState"), "tables": tables}


def validate(data: dict[str, Any]) -> dict[str, Any]:
    ids = [e["id"] for e in data["entities"]]
    assert len(ids) == len(set(ids)), "Duplicate entity ID"
    edge_ids = [e["id"] for e in data["edges"]]
    assert len(edge_ids) == len(set(edge_ids)), "Duplicate edge ID"
    entities = {e["id"]: e for e in data["entities"]}
    actual = data["graph"]["nodes"]
    edges = {(e["from"], e["to"]) for e in data["edges"] if e["kind"] == "graph"}
    expected = {(a, b) for a, node in actual.items() for b in node["routes"]} | {("__start__", "parse_request")}
    assert edges == expected, f"Routing catalogue drift: missing={expected - edges}, extra={edges - expected}"
    for entity in data["entities"]:
        assert entity["refs"], f"Missing evidence: {entity['id']}"
        for ref in entity["refs"]:
            assert ref in SOURCES, ref
        if entity["type"] == "node":
            for field in entity["writes"]:
                assert field in data["schema"]["fields"], field
    for edge in data["edges"]:
        assert edge["from"] in entities and edge["to"] in entities, edge
        assert edge["refs"] and all(ref in SOURCES for ref in edge["refs"])
    for group in data["groups"]:
        assert group["nodes"] and all(n in actual for n in group["nodes"])
    grouped = [n for group in data["groups"] for n in group["nodes"]]
    assert sorted(grouped) == sorted(actual), "Graph grouping must be an exact partition"
    for scenario in data["scenarios"]:
        assert scenario["provenance"] in {"Recorded execution", "Test fixture", "Illustrative"}
        last_node = None
        for step in scenario["steps"]:
            assert all(i in entities for i in step["entities"]), step
            assert step["refs"] and all(r in SOURCES for r in step["refs"])
            assert step["status"] in data["statuses"]
            assert all(field in data["schema"]["fields"] for field in step.get("patch", {}))
            if step.get("node"):
                assert step["node"] in entities
                assert set(step.get("patch", {})) <= set(entities[step["node"]].get("writes", [])), (scenario["id"], step["node"], "patch does not belong to node")
                # Non-node timeline steps may occur between graph transitions.
                if last_node and last_node != step["node"]:
                    assert (last_node, step["node"]) in edges, (scenario["id"], last_node, step["node"])
                last_node = step["node"]
    return {"sourceCommit": SHA, "entities": len(ids), "graphNodes": len(actual),
            "graphEdges": len(expected), "sources": len(SOURCES), "scenarios": len(data["scenarios"]),
            "checks": ["fixed-commit source references", "unique entity and edge IDs", "reviewed routes match AST inventory",
                       "state fields exist", "high-level groups partition real nodes", "trace node transitions exist",
                       "scenario references and statuses resolve", "illustrative patches belong to their node"],
            "limits": "Source catalogue checks; not a runtime reachability proof or a business E2E test."}


def build() -> None:
    namespace = runpy.run_path(str(HERE / "content.py"))
    data = namespace["create_content"](reference, committed, graph_inventory(), schema_inventory())
    data["baseline"] = BASELINE
    data["sources"] = SOURCES
    report = validate(data)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    shell = (HERE / "src/index.html").read_text()
    html = shell.replace("/* STYLES */", (HERE / "src/style.css").read_text()).replace(
        "/* DATA */", f"window.EXPLORER_DATA = {payload};").replace(
        "/* APP */", (HERE / "src/app.js").read_text())
    for folder in ("dist", "offline"):
        target = HERE / folder
        target.mkdir(exist_ok=True)
        (target / "index.html").write_text(html)
    (HERE / "dist/.nojekyll").write_text("")
    architecture_prefixes = (
        "packages/agent_runtime/src/", "apps/api/src/", "apps/api/alembic/",
        "apps/agent_service/src/", "apps/contracts/src/", "apps/web/src/",
    )
    architecture_paths = sorted({source["path"] for source in SOURCES.values()
        if source["path"].startswith(architecture_prefixes)
        or source["path"] in {"docker-compose.yml", "apps/web/next.config.ts",
                              "config/reviewer-gates.json", "config/user-risk.json"}})
    (HERE / "source-manifest.json").write_text(json.dumps({
        "baseline": BASELINE,
        "architecturePaths": architecture_paths,
        "syncRule": "CI fails when a manifest-covered architecture source changes after baseline.",
        "sources": SOURCES,
    }, ensure_ascii=False, indent=2) + "\n")
    (HERE / "architecture-data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    (HERE / "content-checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({**report, "htmlBytes": len(html.encode()), "targets": ["dist/index.html", "offline/index.html"]}, ensure_ascii=False))


if __name__ == "__main__":
    build()
