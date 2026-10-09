"""HTTP-backed drop-in replacement for SAGEModelRuntime.

Matches sage_model_runtime.SAGEModelRuntime's public shape exactly
(stream() yields GenerationEvent, returns GenerationResult) but talks to
llama-server (GGUF, managed by the Tauri app as its own sidecar) over HTTP
instead of loading an MLX model in-process. This lets sage.py's real
ask_sage_stream() run unmodified on Windows/Linux, not just Apple Silicon.

Usage (see sage_router_server.py):
    import sage
    from llama_bridge import LlamaServerRuntime
    sage.sage_ai.runtime = LlamaServerRuntime(port=8721)

Thinking-tag handling mirrors sage_model_runtime.py's confirmed real
behavior: when thinking is on, Qwen3's chat template puts the opening
<think> into the PROMPT itself — it never appears in the generated
stream, only the closing </think> does. This assumes llama-server's
chat template handles Qwen3 the same way (it should — it's a property
of Qwen3's template, not the serving framework) — verify against real
output once this is actually running end-to-end.

NOTE: Rust (sidecar.rs) owns loading/switching which GGUF size is
resident in llama-server. This class assumes whatever's already loaded
matches the requested spec — it doesn't ask Rust to switch models itself.
"""
from __future__ import annotations

import json
import time
from typing import Generator, Optional

import requests

from sage_model_runtime import GenerationEvent, GenerationResult
from model_router import ModelSpec


class LlamaServerRuntime:
    def __init__(self, host: str = "127.0.0.1", port: int = 8721):
        self.base_url = f"http://{host}:{port}"
        self._loaded_key: Optional[str] = None

    @property
    def loaded_key(self):
        return self._loaded_key

    def unload(self) -> None:
        # No-op — llama-server's process lifecycle is owned by Rust.
        self._loaded_key = None

    def load_model(self, spec: ModelSpec) -> None:
        # No-op, kept for interface compatibility — see class docstring.
        self._loaded_key = spec.size

    def stream(
        self,
        spec: ModelSpec,
        messages: list[dict],
        *,
        thinking_visible: bool = False,
        on_event=None,
    ) -> Generator[GenerationEvent, None, GenerationResult]:
        del thinking_visible

        start = time.perf_counter()
        payload = {
            "model": "sage",
            "messages": messages,
            "stream": True,
            "temperature": spec.temperature,
            "top_p": spec.top_p,
        }

        response_text: list[str] = []
        hidden_thinking_chars = 0
        in_think = bool(spec.thinking)
        saw_think_end = not spec.thinking
        announced_thinking = False
        token_count = 0

        if spec.thinking:
            event = GenerationEvent(type="thinking_started", model=spec.display_name, thinking=True)
            if on_event:
                on_event(event)
            yield event
            announced_thinking = True

        with requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=300,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                    text = chunk["choices"][0]["delta"].get("content", "")
                except Exception:
                    continue
                if not text:
                    continue

                token_count += 1
                remaining = text

                while remaining:
                    if in_think:
                        if "</think>" in remaining:
                            before, remaining = remaining.split("</think>", 1)
                            hidden_thinking_chars += len(before)
                            in_think = False
                            saw_think_end = True
                            if announced_thinking:
                                event = GenerationEvent(type="thinking_finished", model=spec.display_name)
                                if on_event:
                                    on_event(event)
                                yield event
                            continue
                        hidden_thinking_chars += len(remaining)
                        remaining = ""
                    else:
                        response_text.append(remaining)
                        event = GenerationEvent(
                            type="token",
                            text=remaining,
                            model=spec.display_name,
                            thinking=False,
                            elapsed_s=time.perf_counter() - start,
                        )
                        if on_event:
                            on_event(event)
                        yield event
                        remaining = ""

        elapsed = time.perf_counter() - start
        if spec.thinking and not saw_think_end and announced_thinking:
            event = GenerationEvent(type="thinking_finished", model=spec.display_name, elapsed_s=elapsed)
            if on_event:
                on_event(event)
            yield event

        response = "".join(response_text).strip()
        generation_tps = token_count / elapsed if elapsed > 0 else 0.0

        result = GenerationResult(
            response=response,
            model=spec.display_name,
            thinking_used=spec.thinking,
            prompt_tokens=0,  # not exposed per-chunk by the streaming API; pull from
            generation_tokens=token_count,  # llama-server's final usage block to fill in properly
            prompt_tps=0.0,
            generation_tps=generation_tps,
            peak_memory_gb=0.0,  # tracked at the host level (hardware.rs), not here
            elapsed_s=elapsed,
            internal_thinking_chars=hidden_thinking_chars,
            metadata={"backend": "llama-server", "url": self.base_url},
        )

        complete = GenerationEvent(
            type="complete",
            text=response,
            model=spec.display_name,
            thinking=False,
            generation_tokens=token_count,
            generation_tps=generation_tps,
            elapsed_s=elapsed,
        )
        if on_event:
            on_event(complete)
        yield complete
        return result
