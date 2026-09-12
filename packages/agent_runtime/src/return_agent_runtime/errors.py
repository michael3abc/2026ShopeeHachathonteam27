"""Errors raised by the Python runtime boundary."""


class AgentRuntimeError(RuntimeError):
    """Base error for invalid runtime usage."""


class ThreadAlreadyExistsError(AgentRuntimeError):
    """Raised when a new case attempts to reuse an existing thread."""


class ThreadNotFoundError(AgentRuntimeError):
    """Raised when a resume targets an unknown thread."""


class ResumeMismatchError(AgentRuntimeError):
    """Raised when the resume payload does not match the active interrupt."""


class InvalidGraphResultError(AgentRuntimeError):
    """Raised when a graph run reaches neither an interrupt nor a terminal DTO."""
