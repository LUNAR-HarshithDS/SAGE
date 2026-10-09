# SAGE model runtime integration

This package integrates the native MLX SAGE model runtime into the supplied `sage.py`.

## Files added beside `sage.py`

- `model_router.py` — deterministic 1.7B/4B/8B selector
- `sage_model_runtime.py` — MLX model loader/streamer
- `sage_model_api.py` — high-level SAGE model API
- `sage_runtime_prompt.py` — dynamic runtime context prompt
- `request_router_model_notes.py` — routing notes
- `requirements-models.txt` — model-runtime dependencies

## Adapter locations

The runtime checks these locations, in order:

1. `~/SAGE Models/adapters/sage-<size>/`
2. `~/SAGE/sage_finetune/adapters/sage-<size>/`
3. `~/SAGE/adapters/sage-<size>/`
4. beside the runtime source

Each adapter directory must contain `adapters.safetensors` and `adapter_config.json`.

## Runtime behavior

- Deterministic requests do not load an AI model.
- Local-knowledge requests route to SAGE-1.7B with thinking off.
- Simple general conversation routes to SAGE-4B with thinking off.
- Complex reasoning / explicit web research routes to SAGE-8B with thinking on.
- Only one model is kept resident at a time.
- Raw chain-of-thought is not emitted to the UI or CLI; only thinking state events are exposed.
- `ask_sage()` remains a text-returning compatibility API.
- `ask_sage_stream()` exposes structured streaming events for the future SwiftUI app.

## Important

Place these model-runtime Python files in the same directory as your working `sage.py` before running it.
