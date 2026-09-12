"""Packaged canonical prompts and their versions."""

from importlib.resources import files

INTAKE_PROMPT_VERSION = "intake:1.2"
RESOLVER_PROMPT_VERSION = "resolver:1.1"
REVIEWER_PROMPT_VERSION = "reviewer:2.2"
MEMORY_DISTILLER_PROMPT_VERSION = "memory-distiller:2.1"
MEMORY_QUERY_PROMPT_VERSION = "memory-query:1.0"


def _read_prompt(name: str) -> str:
    return (
        files("return_agent_runtime.prompt_text")
        .joinpath(f"{name}.txt")
        .read_text(encoding="utf-8")
        .strip()
    )


INTAKE_SYSTEM_PROMPT = _read_prompt("intake")
RESOLVER_SYSTEM_PROMPT = _read_prompt("resolver")
REVIEWER_SYSTEM_PROMPT = _read_prompt("reviewer")
MEMORY_DISTILLER_SYSTEM_PROMPT = _read_prompt("memory-distiller")

MEMORY_QUERY_SYSTEM_PROMPT = _read_prompt("memory-query")
