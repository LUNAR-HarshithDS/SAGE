"""SAGE function router.

Responsibility:
    Decide WHICH capability should handle an interpreted request.
    It does not execute that capability and never calls an LLM/web service.
"""

from __future__ import annotations

from dataclasses import dataclass
from input_interpreter import InterpretedRequest


@dataclass(frozen=True)
class FunctionDecision:
    name: str
    args: dict
    confidence: float
    deterministic: bool
    requires_web: bool = False
    requires_local_knowledge: bool = False
    requires_ai: bool = False


def route_function(request: InterpretedRequest) -> FunctionDecision:
    intent = request.intent

    mapping = {
        # Instant / deterministic
        "command": (
            "command",
            True,
            False,
            False,
            False,
        ),
        "casual": (
            "casual_response",
            True,
            False,
            False,
            False,
        ),
        "mathematics": (
            "math_engine",
            True,
            False,
            False,
            False,
        ),
        "data_analysis": (
            "analysis_engine",
            True,
            False,
            False,
            False,
        ),
        "phrasing": (
            "phrasing",
            False,
            False,
            True,
            False,
        ),
        "conversion": (
            "conversion_engine",
            True,
            False,
            False,
            False,
        ),
        "memory_write": (
            "remember",
            True,
            False,
            False,
            False,
        ),
        "memory_delete": (
            "forget",
            True,
            False,
            False,
            False,
        ),
        "empty": (
            "invalid_input",
            True,
            False,
            False,
            False,
        ),

        # Local knowledge first, then AI synthesis
        "knowledge": (
            "local_first",
            False,
            False,
            True,
            True,
        ),
        "history": (
            "local_first",
            False,
            False,
            True,
            True,
        ),

        # Web research, then AI synthesis
        "research": (
            "web_research",
            False,
            True,
            True,
            False,
        ),

        # General conversational AI
        "conversation": (
            "conversation",
            False,
            False,
            True,
            False,
        ),
    }

    (
        name,
        deterministic,
        requires_web,
        requires_ai,
        requires_local_knowledge,
    ) = mapping.get(
        intent,
        ("conversation", False, False, True, False),
    )

    if intent == "command":
        command = request.args.get("command")

        return FunctionDecision(
            name=command or "invalid_command",
            args=request.args,
            confidence=request.confidence,
            deterministic=True,
        )

    if intent == "research":
        name = (
            "web_research_url"
            if "urls" in request.args
            else "web_research"
        )

    return FunctionDecision(
        name=name,
        args=request.args,
        confidence=request.confidence,
        deterministic=deterministic,
        requires_web=requires_web,
        requires_local_knowledge=(
            requires_local_knowledge
            or request.requires_local_knowledge
        ),
        requires_ai=requires_ai,
    )


__all__ = ["FunctionDecision", "route_function"]
