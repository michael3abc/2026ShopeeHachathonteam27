"""Public Python start/resume API for the compiled graph."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import TypeAdapter
from return_agent_contracts.enums import UserRole
from return_agent_contracts.models import (
    ManualEscalationHandoff,
    MemoryDistillationInput,
    ResolutionHandoff,
    UserTurn,
)
from return_agent_contracts.runtime import (
    AgentInterruptKind,
    AgentResumeRequest,
    AgentRunResult,
    AgentRunStatus,
    AgentStartRequest,
    InterruptedAgentRunResult,
    ManualEscalationAgentRunResult,
    NodeExecutionObservation,
    ResolutionAgentRunResult,
    ResumePayload,
)

from .assembly import build_human_review_dossier
from .dependencies import AgentDependencies
from .errors import (
    InvalidGraphResultError,
    ResumeMismatchError,
    ThreadAlreadyExistsError,
    ThreadNotFoundError,
)
from .graph import GRAPH_RECURSION_LIMIT, build_graph, initial_state

RESUME_ADAPTER = TypeAdapter(ResumePayload)
RESOLUTION_ADAPTER = TypeAdapter(ResolutionHandoff)
ESCALATION_ADAPTER = TypeAdapter(ManualEscalationHandoff)
MEMORY_INPUT_ADAPTER = TypeAdapter(MemoryDistillationInput)
LOGGER = logging.getLogger(__name__)

NodeObserver = Callable[[NodeExecutionObservation], Awaitable[None] | None]


@dataclass(slots=True)
class ReturnAgentRuntime:
    """A graph instance bound to providers, a model, and a checkpointer."""

    dependencies: AgentDependencies
    checkpointer: BaseCheckpointSaver[Any]
    graph: CompiledStateGraph = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.graph = build_graph(
            dependencies=self.dependencies,
            checkpointer=self.checkpointer,
        )

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        normalized = thread_id.strip()
        if not normalized:
            raise ValueError("thread_id must be non-empty")
        return {
            "configurable": {"thread_id": normalized},
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }

    def start(
        self,
        *,
        thread_id: str,
        case_ref: str,
        order_ref: str | None = None,
        initial_turn: UserTurn,
    ) -> AgentRunResult:
        """Start a new case and run until an interrupt or terminal handoff."""

        request = AgentStartRequest(
            thread_id=thread_id,
            case_ref=case_ref,
            order_ref=order_ref,
            initial_turn=initial_turn,
        )
        config = self._config(request.thread_id)
        if self.checkpointer.get_tuple(config) is not None:
            raise ThreadAlreadyExistsError(
                f"thread_id {thread_id!r} already has persisted state"
            )
        if request.initial_turn.role is not UserRole.USER:
            raise ValueError("initial_turn.role must be USER")
        output = self.graph.invoke(
            initial_state(
                thread_id=request.thread_id,
                case_ref=request.case_ref,
                order_ref=request.order_ref,
                initial_turn=request.initial_turn,
            ),
            config=config,
        )
        return self._result(output)

    def resume(self, *, thread_id: str, payload: ResumePayload) -> AgentRunResult:
        """Resume the currently active interrupt with a matching typed payload."""

        request = AgentResumeRequest(thread_id=thread_id, payload=payload)
        config = self._config(request.thread_id)
        if self.checkpointer.get_tuple(config) is None:
            raise ThreadNotFoundError(f"thread_id {thread_id!r} does not exist")
        validated = RESUME_ADAPTER.validate_python(request.payload)
        active_kind = self._active_interrupt_kind(config)
        if active_kind is not validated.kind:
            raise ResumeMismatchError(
                f"active interrupt is {active_kind.value}, got {validated.kind.value}"
            )
        output = self.graph.invoke(
            Command(resume=validated.model_dump(mode="json")),
            config=config,
        )
        return self._result(output)

    async def astart(
        self,
        *,
        thread_id: str,
        case_ref: str,
        order_ref: str | None = None,
        initial_turn: UserTurn,
        observer: NodeObserver | None = None,
        activity_observer=None,
        run_id: str | None = None,
    ) -> AgentRunResult:
        """Start a run while reporting framework-neutral node observations."""

        request = AgentStartRequest(
            thread_id=thread_id,
            case_ref=case_ref,
            order_ref=order_ref,
            initial_turn=initial_turn,
        )
        config = self._config(request.thread_id)
        config["configurable"]["activity_run_id"] = run_id or uuid4().hex
        if await self.checkpointer.aget_tuple(config) is not None:
            raise ThreadAlreadyExistsError(
                f"thread_id {thread_id!r} already has persisted state"
            )
        if request.initial_turn.role is not UserRole.USER:
            raise ValueError("initial_turn.role must be USER")
        return await self._ainvoke_observed(
            initial_state(
                thread_id=request.thread_id,
                case_ref=request.case_ref,
                order_ref=request.order_ref,
                initial_turn=request.initial_turn,
            ),
            config=config,
            observer=observer,
            activity_observer=activity_observer,
        )

    async def aresume(
        self,
        *,
        thread_id: str,
        payload: ResumePayload,
        observer: NodeObserver | None = None,
        activity_observer=None,
        run_id: str | None = None,
    ) -> AgentRunResult:
        """Resume a run while reporting framework-neutral node observations."""

        request = AgentResumeRequest(thread_id=thread_id, payload=payload)
        config = self._config(request.thread_id)
        config["configurable"]["activity_run_id"] = run_id or uuid4().hex
        if await self.checkpointer.aget_tuple(config) is None:
            raise ThreadNotFoundError(f"thread_id {thread_id!r} does not exist")
        validated = RESUME_ADAPTER.validate_python(request.payload)
        active_kind = await self._active_interrupt_kind_async(config)
        if active_kind is not validated.kind:
            raise ResumeMismatchError(
                f"active interrupt is {active_kind.value}, got {validated.kind.value}"
            )
        return await self._ainvoke_observed(
            Command(resume=validated.model_dump(mode="json")),
            config=config,
            observer=observer,
            activity_observer=activity_observer,
        )

    async def aget_memory_distillation_input(
        self, *, thread_id: str
    ) -> MemoryDistillationInput | None:
        """Read the prepared async-memory payload from a completed checkpoint."""

        config = self._config(thread_id)
        snapshot = await self.graph.aget_state(config)
        value = snapshot.values.get("memory_distillation_input")
        if value is None:
            return None
        return MEMORY_INPUT_ADAPTER.validate_python(value)

    async def _ainvoke_observed(
        self,
        graph_input: dict[str, Any] | Command,
        *,
        config: dict[str, Any],
        observer: NodeObserver | None,
        activity_observer=None,
    ) -> AgentRunResult:
        latest_values: dict[str, Any] | None = None
        active_tasks: dict[str, str] = {}
        try:
            async for part in self.graph.astream(
                graph_input,
                config=config,
                stream_mode=["tasks", "values", "custom"],
                version="v2",
            ):
                if part["type"] == "custom":
                    if activity_observer is not None:
                        try:
                            emitted = activity_observer(part["data"])
                            if inspect.isawaitable(emitted):
                                await emitted
                        except Exception:  # noqa: BLE001 - arbitrary telemetry sink must not affect graph
                            LOGGER.error("activity observer failed; trace incomplete")
                    continue
                if part["type"] == "values":
                    latest_values = part["data"]
                    continue
                if part["type"] != "tasks":
                    continue
                task = part["data"]
                task_ref = task["id"]
                node = task["name"]
                if "input" in task:
                    active_tasks[task_ref] = node
                    await self._notify_observer(
                        observer,
                        phase="ENTER",
                        node=node,
                        task_ref=task_ref,
                    )
                    continue
                active_tasks.pop(task_ref, None)
                error_message = task.get("error")
                if isinstance(error_message, BaseException):
                    error_message = f"{type(error_message).__name__}: {error_message}"
                await self._notify_observer(
                    observer,
                    phase="ERROR" if error_message else "EXIT",
                    node=node,
                    task_ref=task_ref,
                    error_message=error_message,
                    memory_retrieval=(task.get("result") or {}).get("memory_retrieval"),
                    review_gate=(task.get("result") or {}).get("review_gate"),
                )
        except Exception as error:
            message = f"{type(error).__name__}: {error}"
            for task_ref, node in active_tasks.items():
                await self._notify_observer(
                    observer,
                    phase="ERROR",
                    node=node,
                    task_ref=task_ref,
                    error_message=message,
                )
            raise

        snapshot = await self.graph.aget_state(config)
        if latest_values is None and not snapshot.values:
            raise InvalidGraphResultError("graph stream produced no state values")
        output = dict(snapshot.values)
        if snapshot.interrupts:
            output["__interrupt__"] = snapshot.interrupts
        return self._result(output)

    @staticmethod
    async def _notify_observer(
        observer: NodeObserver | None,
        *,
        phase: str,
        node: str,
        task_ref: str,
        error_message: str | None = None,
        memory_retrieval: Any = None,
        review_gate: Any = None,
    ) -> None:
        if observer is None:
            return
        try:
            observation = NodeExecutionObservation(
                phase=phase,
                node=node,
                task_ref=task_ref,
                error_message=error_message,
                memory_retrieval=memory_retrieval,
                review_gate=review_gate,
            )
            outcome = observer(observation)
            if inspect.isawaitable(outcome):
                await outcome
        except Exception:  # Telemetry must not alter graph execution.
            LOGGER.exception("node observer failed for %s (%s)", node, phase)

    def _active_interrupt_kind(self, config: dict[str, Any]) -> AgentInterruptKind:
        snapshot = self.graph.get_state(config)
        if not snapshot.interrupts:
            raise ResumeMismatchError("thread has no active interrupt")
        value = snapshot.interrupts[0].value
        if not isinstance(value, dict) or "kind" not in value:
            raise InvalidGraphResultError("interrupt payload has no kind")
        try:
            return AgentInterruptKind(value["kind"])
        except ValueError as error:
            raise InvalidGraphResultError("unknown interrupt kind") from error

    async def _active_interrupt_kind_async(
        self, config: dict[str, Any]
    ) -> AgentInterruptKind:
        snapshot = await self.graph.aget_state(config)
        return self._interrupt_kind_from_snapshot(snapshot)

    @staticmethod
    def _interrupt_kind_from_snapshot(snapshot: Any) -> AgentInterruptKind:
        if not snapshot.interrupts:
            raise ResumeMismatchError("thread has no active interrupt")
        value = snapshot.interrupts[0].value
        if not isinstance(value, dict) or "kind" not in value:
            raise InvalidGraphResultError("interrupt payload has no kind")
        try:
            return AgentInterruptKind(value["kind"])
        except ValueError as error:
            raise InvalidGraphResultError("unknown interrupt kind") from error

    @staticmethod
    def _result(output: dict[str, Any]) -> AgentRunResult:
        interrupts = output.get("__interrupt__", ())
        if interrupts:
            value = interrupts[0].value
            if not isinstance(value, dict) or "kind" not in value:
                raise InvalidGraphResultError("interrupt payload has no kind")
            if value["kind"] == AgentInterruptKind.HUMAN_REVIEW:
                value = ReturnAgentRuntime._human_review_interrupt(value, output)
            return InterruptedAgentRunResult(
                result_type="INTERRUPTED",
                status=AgentRunStatus.INTERRUPTED,
                interrupt_payload=value,
            )
        if output.get("resolution_handoff") is not None:
            return ResolutionAgentRunResult(
                result_type="RESOLUTION",
                status=AgentRunStatus.COMPLETED,
                resolution_handoff=RESOLUTION_ADAPTER.validate_python(
                    output["resolution_handoff"]
                ),
            )
        if output.get("manual_escalation") is not None:
            return ManualEscalationAgentRunResult(
                result_type="MANUAL_ESCALATION",
                status=AgentRunStatus.COMPLETED,
                manual_escalation=ESCALATION_ADAPTER.validate_python(
                    output["manual_escalation"]
                ),
            )
        raise InvalidGraphResultError(
            "graph reached neither an interrupt nor a terminal handoff"
        )

    @staticmethod
    def _human_review_interrupt(
        value: dict[str, Any], output: dict[str, Any]
    ) -> dict[str, Any]:
        """Add typed UI projection inputs outside the graph node boundary."""

        return {
            **value,
            "handoff": output.get("current_handoff"),
            "review_result": output["review_history"][-1],
            "dossier": build_human_review_dossier(output),
            "policy_bundle": output.get("policy_bundle"),
            "memory_ids": [
                memory.memory_id for memory in output.get("operational_memory", ())
            ],
        }
