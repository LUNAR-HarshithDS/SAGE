"""Native MLX runtime for trained SAGE adapters.

Loads one Qwen3 base model plus the corresponding SAGE LoRA adapter,
streams generation, tracks performance, and keeps model internals out of the
UI layer.

Qwen3 thinking output is deliberately NOT exposed as raw chain-of-thought.
The runtime emits thinking-state events so the UI can show that SAGE is
reasoning without revealing private internal reasoning text.
"""
from __future__ import annotations

import gc
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Generator, Optional

# MLX is available on Apple silicon, but not on native Windows. Keep the
# module importable so the cross-platform llama-server bridge can reuse the
# shared GenerationEvent/GenerationResult data classes.
try:
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler
    MLX_AVAILABLE = True
    MLX_IMPORT_ERROR = None
except ImportError as exc:
    mx = None
    load = None
    stream_generate = None
    make_sampler = None
    MLX_AVAILABLE = False
    MLX_IMPORT_ERROR = exc
from model_router import ModelSpec


@dataclass
class GenerationEvent:
    type: str
    text: str = ""
    model: str = ""
    thinking: bool = False
    prompt_tokens: int = 0
    generation_tokens: int = 0
    prompt_tps: float = 0.0
    generation_tps: float = 0.0
    peak_memory_gb: float = 0.0
    elapsed_s: float = 0.0


@dataclass
class GenerationResult:
    response: str
    model: str
    thinking_used: bool
    prompt_tokens: int
    generation_tokens: int
    prompt_tps: float
    generation_tps: float
    peak_memory_gb: float
    elapsed_s: float
    internal_thinking_chars: int = 0
    metadata: dict = field(default_factory=dict)


class SAGEModelRuntime:
    """Thread-safe single-model MLX runtime.

    Only one model is kept resident. This prevents the 1.7B, 4B, and 8B
    models from simultaneously consuming the Mac's unified memory.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model = None
        self._tokenizer = None
        self._loaded_key: Optional[tuple[str, str, str]] = None

    @property
    def loaded_key(self) -> Optional[tuple[str, str, str]]:
        return self._loaded_key

    def unload(self) -> None:
        with self._lock:
            self._model = None
            self._tokenizer = None
            self._loaded_key = None
            gc.collect()
            try:
                mx.clear_cache()
            except Exception:
                pass


    def _validate_adapter(self, spec: ModelSpec) -> None:
        """Validate the adapter only when this model uses one."""
        if spec.adapter_path is None:
            return

        if not spec.adapter_path.is_dir():
            raise FileNotFoundError(
                f"Adapter directory not found: {spec.adapter_path}"
            )

        missing = [
            name
            for name in ("adapters.safetensors", "adapter_config.json")
            if not (spec.adapter_path / name).exists()
        ]

        if missing:
            raise FileNotFoundError(
                f"{spec.display_name} adapter is incomplete: "
                f"missing {', '.join(missing)}"
            )
            
    def load_model(self, spec: ModelSpec) -> None:
        """Load a base model, optionally with its LoRA adapter."""
        if not MLX_AVAILABLE:
            raise RuntimeError(
                "The native SAGE runtime requires MLX, which is not available "
                "on this platform. On Windows, start a compatible llama-server "
                "and use sage_router_server.py with llama_bridge.py instead."
            ) from MLX_IMPORT_ERROR
        with self._lock:
            self._validate_adapter(spec)

            base_model = spec.base_model()
            adapter_key = (
                str(spec.adapter_path)
                if spec.adapter_path is not None
                else ""
            )
            key = (spec.size, base_model, adapter_key)

            if self._loaded_key == key and self._model is not None:
                return

            self.unload()

            if spec.adapter_path is not None:
                self._model, self._tokenizer = load(
                    base_model,
                    adapter_path=str(spec.adapter_path),
                )
            else:
                self._model, self._tokenizer = load(base_model)

            self._loaded_key = key

    @staticmethod
    def _strip_think(text: str) -> str:
        text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S)
        text = text.replace("<think>", "").replace("</think>", "")
        return text.strip()

    @staticmethod
    def _build_prompt(tokenizer, messages: list[dict], thinking: bool) -> str:
        # Qwen3 supports an explicit thinking switch in its chat template.
        # enable_thinking=False prevents <think> content entirely.
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=thinking,
        )

    def stream(
        self,
        spec: ModelSpec,
        messages: list[dict],
        *,
        thinking_visible: bool = False,
        on_event: Optional[Callable[[GenerationEvent], None]] = None,
    ) -> Generator[GenerationEvent, None, GenerationResult]:
        """Stream safe UI events and return the final structured result.

        `thinking_visible` only controls whether thinking-state events are
        emitted. Raw model reasoning text is never emitted.
        """
        del thinking_visible  # kept for API compatibility with the UI layer

        start = time.perf_counter()
        with self._lock:
            self.load_model(spec)
            prompt = self._build_prompt(self._tokenizer, messages, spec.thinking)
            sampler = make_sampler(
                temp=spec.temperature,
                top_p=spec.top_p,
                top_k=spec.top_k,
            )

            response_text = []
            hidden_thinking_chars = 0
            in_think = bool(spec.thinking)
            saw_think_end = not spec.thinking
            announced_thinking = False
            last = None

            if spec.thinking and on_event is not None:
                event = GenerationEvent(
                    type="thinking_started",
                    model=spec.display_name,
                    thinking=True,
                )
                on_event(event)
                yield event
                announced_thinking = True

            for piece in stream_generate(
                self._model,
                self._tokenizer,
                prompt,
                max_tokens=spec.max_tokens,
                sampler=sampler,
            ):
                last = piece
                text = piece.text or ""

                # Qwen3 emits <think>...</think> in thinking mode. We consume
                # this content internally and only surface state changes.
                if spec.thinking:
                    if "<think>" in text:
                        in_think = True
                        text = text.replace("<think>", "")
                    if "</think>" in text:
                        before, after = text.split("</think>", 1)
                        hidden_thinking_chars += len(before)
                        in_think = False
                        saw_think_end = True
                        if announced_thinking and on_event is not None:
                            event = GenerationEvent(
                                type="thinking_finished",
                                model=spec.display_name,
                                thinking=False,
                            )
                            on_event(event)
                            yield event
                        text = after
                    elif in_think and not saw_think_end:
                        hidden_thinking_chars += len(text)
                        text = ""

                if text:
                    response_text.append(text)
                    event = GenerationEvent(
                        type="token",
                        text=text,
                        model=spec.display_name,
                        thinking=False,
                        prompt_tokens=piece.prompt_tokens,
                        generation_tokens=piece.generation_tokens,
                        prompt_tps=piece.prompt_tps,
                        generation_tps=piece.generation_tps,
                        peak_memory_gb=piece.peak_memory,
                        elapsed_s=time.perf_counter() - start,
                    )
                    if on_event is not None:
                        on_event(event)
                    yield event

            elapsed = time.perf_counter() - start
            if spec.thinking and not saw_think_end and announced_thinking and on_event is not None:
                event = GenerationEvent(
                    type="thinking_finished",
                    model=spec.display_name,
                    thinking=False,
                    elapsed_s=elapsed,
                )
                on_event(event)
                yield event

            response = self._strip_think("".join(response_text))
            generation_tokens = getattr(last, "generation_tokens", 0) if last else 0
            prompt_tokens = getattr(last, "prompt_tokens", 0) if last else 0
            prompt_tps = getattr(last, "prompt_tps", 0.0) if last else 0.0
            generation_tps = getattr(last, "generation_tps", 0.0) if last else 0.0
            peak_memory = getattr(last, "peak_memory", 0.0) if last else 0.0

            result = GenerationResult(
                response=response,
                model=spec.display_name,
                thinking_used=spec.thinking,
                prompt_tokens=prompt_tokens,
                generation_tokens=generation_tokens,
                prompt_tps=prompt_tps,
                generation_tps=generation_tps,
                peak_memory_gb=peak_memory,
                elapsed_s=elapsed,
                internal_thinking_chars=hidden_thinking_chars,
                metadata={
                    "base_model": spec.base_model(),
                    "adapter_path": (
                        str(spec.adapter_path)
                        if spec.adapter_path is not None
                        else None
                    ),
                },
            )

            complete = GenerationEvent(
                type="complete",
                text=response,
                model=spec.display_name,
                thinking=False,
                prompt_tokens=prompt_tokens,
                generation_tokens=generation_tokens,
                prompt_tps=prompt_tps,
                generation_tps=generation_tps,
                peak_memory_gb=peak_memory,
                elapsed_s=elapsed,
            )
            if on_event is not None:
                on_event(complete)
            yield complete
            return result

    def generate(self, spec: ModelSpec, messages: list[dict]) -> GenerationResult:
        # Deliberately unsupported: fails immediately rather than running a
        # full (and wasted) generation pass first. Use generate_blocking().
        raise RuntimeError("Use generate_blocking() for non-streaming generation.")

    def generate_blocking(self, spec: ModelSpec, messages: list[dict]) -> GenerationResult:
        generator = self.stream(spec, messages)
        while True:
            try:
                next(generator)
            except StopIteration as stop:
                return stop.value


__all__ = ["GenerationEvent", "GenerationResult", "SAGEModelRuntime"]
