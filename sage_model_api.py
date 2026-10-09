"""High-level integration layer for the existing SAGE Python core.

Use this from sage.py after deterministic routing and local/web retrieval
have already happened. It deliberately leaves knowledge.py, research_v3.py,
request_router.py and memory handling in the existing SAGE system.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, Optional

from model_router import ModelSpec, select_model
from sage_model_runtime import GenerationEvent, GenerationResult, SAGEModelRuntime
from sage_runtime_prompt import build_runtime_system_prompt


@dataclass
class SAGEResponse:
    text: str
    model: str
    route: str
    thinking: bool
    elapsed_s: float
    generation_tokens: int
    generation_tps: float
    prompt_tokens: int
    prompt_tps: float
    peak_memory_gb: float
    hidden_thinking_chars: int


class SAGEAI:
    def __init__(self) -> None:
        self.runtime = SAGEModelRuntime()

    def select(self, request, function=None) -> ModelSpec:
        return select_model(request, function)

    def stream(
        self,
        request,
        messages: list[dict],
        *,
        identity: dict,
        memory: dict,
        settings: dict,
        research_context: str = "",
        route_name: str = "model",
    ) -> Generator[GenerationEvent, None, SAGEResponse]:
        spec = self.select(request)
        system = build_runtime_system_prompt(
            identity=identity,
            memory=memory,
            settings=settings,
            research_context=research_context,
        )
        final_messages = [{"role": "system", "content": system}] + messages

        generator = self.runtime.stream(spec, final_messages)
        while True:
            try:
                event = next(generator)
            except StopIteration as stop:
                result: GenerationResult = stop.value
                return SAGEResponse(
                    text=result.response,
                    model=result.model,
                    route=route_name,
                    thinking=result.thinking_used,
                    elapsed_s=result.elapsed_s,
                    generation_tokens=result.generation_tokens,
                    generation_tps=result.generation_tps,
                    prompt_tokens=result.prompt_tokens,
                    prompt_tps=result.prompt_tps,
                    peak_memory_gb=result.peak_memory_gb,
                    hidden_thinking_chars=result.internal_thinking_chars,
                )
            yield event


__all__ = ["SAGEResponse", "SAGEAI"]
