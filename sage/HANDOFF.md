# SAGE — project handoff

Point Claude Code at this folder and have it read this file first. Everything
below is context accumulated from a planning conversation elsewhere; the code
in this repo reflects it, but the *reasoning* is only here.

## What this is

A cross-platform (Windows/macOS/Linux) desktop chat app for a personality
named "Sage," running Qwen3 locally with a custom LoRA adapter, no external
runtime dependencies (no Ollama, no Python) in the shipped app.

## Hard constraints — do not violate these

- **No model router.** Model size (1.7b / 4b / 8b) is always chosen
  manually by the user, never picked automatically based on prompt content
  or complexity. This was stated explicitly and repeatedly upstream — if
  you find yourself writing logic that infers which size to use from the
  message itself, stop, that's a router.
- **No Ollama or Python dependency at runtime.** Ollama was the original
  serving method during development; the shipped app must not require the
  end user to have it (or Python) installed. Inference runs through a
  bundled `llama-server` (llama.cpp) sidecar instead.

## Architecture decisions and why

- **Tauri, not Electron.** Chosen for smaller bundle size — the app
  already ships multi-GB model weights, so not adding a ~150MB Chromium
  runtime on top mattered.
- **The UI shell was originally native SwiftUI/Combine (macOS-only).**
  That code is fully retired — SwiftUI cannot target Windows/Linux, there
  was no salvage path once "all platforms" was confirmed to mean
  Windows+macOS+Linux. Its *behavioral spec* (see below) is what carried
  forward, not its code.
- **No separate Python backend.** Originally assumed one would exist;
  once "run on its own" was clarified to mean no external runtime
  dependency at all, hardware detection and model management moved into
  Rust directly, and llama.cpp is bundled as a Tauri sidecar rather than
  wrapped in a Python service.
- **Frontend is plain HTML/CSS/JS, no framework.** Matches the
  lightweight-Tauri rationale; revisit only if the Phase 2 UI genuinely
  outgrows it.
- **Qwen3's `<think>...</think>` tags are parsed in Rust** (in
  `commands.rs`) to split "thinking" from "final answer" content for the
  UI. This assumes the model actually emits those literal markers in the
  stream — if the Modelfile's chat template reformats or strips them,
  this logic needs revisiting against real output.

## Model / adapter provenance

- Qwen3, three sizes: 1.7b, 4b, 8b.
- A custom LoRA adapter ("Sage" personality) is applied on top of base
  Qwen3. It was originally set up and working through Ollama (Modelfile
  `FROM` + `ADAPTER`).
- Base GGUF weights need extracting from Ollama's blob store —
  `tools/extract_from_ollama.py` does this (reads Ollama's manifest/blob
  format directly, no Ollama daemon needs to be running).
- The adapter file's format was **unconfirmed as of handoff** — could be
  already-converted GGUF LoRA, or still the original PEFT/safetensors
  format from training. Check with:
  ```
  python -c "print(open('PATH_TO_ADAPTER', 'rb').read(4))"
  ```
  `b'GGUF'` → ready to use as-is with `--lora`. Anything else → needs a
  pass through llama.cpp's `convert_lora_to_gguf.py` before it'll work
  with `llama-server`. **This conversion step has not been written yet.**

## Status: Phase 1 (done) vs Phase 2 (not started)

**Phase 1 — working, in this repo:**
- Tauri app skeleton, hardware detection (`hardware.rs`), sidecar
  lifecycle management (`sidecar.rs`), streaming chat with thinking-tag
  splitting (`commands.rs`).
- Plain dark chat UI, functional but not styled per spec.
- Not yet verified to actually compile/run — see README "known rough
  edges." Treat the first `cargo build` as the real first test.

**Phase 2 — the original UX spec, not yet built:**
- Visual theme: green-and-yellow, Gemini-style.
- An animated icon/sphere (textured/noisy, like a voice-assistant orb)
  that visually reacts to how hard the model is "thinking" and which
  model is active — speeds up/slows down, including while the user is
  typing (not just during generation).
- A search bar (black background) for finding previous chats, with a
  small button beside it that opens a dropdown listing all chats.
- **Chats are not persisted by default.** Only saved when the user
  explicitly runs `/save chat <name>`. Name limit: 6 characters. (The
  original Swift implementation restricted this to letters only with no
  digits — that was likely an unintended side effect of the validation
  regex, not a deliberate spec point; worth just allowing alphanumeric
  when Phase 2 implements this.)
- Response styling: a bordered dialogue-box look with "Sage" labeled at
  the bottom, and the border highlights (green/yellow) once the response
  finishes generating. `style.css` already has a `.bubble.assistant.done`
  hook for this — currently just a plain border-color change, not the
  full styled treatment.
- A "thinking" toggle: while generating, clicking it shows the live
  reasoning stream (already flowing as `thinking`-flagged token events
  from Rust). Once the response completes, the thinking content should
  collapse into a bash/terminal-styled box rather than disappearing.
  `thinking-box` element and `.collapsed` class already exist as a
  starting point — the collapse currently just shrinks/dims it, doesn't
  yet restyle it as a terminal block.
- Below the search bar: per-response metrics — time taken and tokens/sec.
  Currently rendered in `#metrics` after each response; needs
  repositioning/styling to match "below the search bar" specifically.
- Hardware suitability check surfaces on launch (`check_environment` →
  `HardwareReport.fits`), currently as a plain system-style chat bubble;
  Phase 2 should give this a real status treatment.

## Known bugs from the original Swift version — already addressed in the
## Rust rewrite, listed here only so they don't get silently reintroduced

- `isThinking`-equivalent state getting stuck `true` after an error and
  never resetting (Rust emits explicit `error` events; make sure any UI
  state machine built on top always clears "thinking" on that event).
- Save-chat logic split across two disconnected notifications with no
  feedback path if the connecting piece was missing — when Phase 2
  implements `/save chat`, keep it a single direct call, not an
  event/notification round-trip.
- Model warmup hardcoded to one size regardless of which size was
  actually about to be used — `prepare_model` in this repo already keys
  off the requested size correctly; don't regress this.
- Two separate, drifting sources of truth for "which model is active" —
  this repo tracks it in one place (`SidecarState.loaded_size`); keep it
  that way rather than duplicating into a separate UI-side field.

## Suggested order of operations from here

1. Get Phase 1 actually compiling and running (`README.md` has the
   setup steps) — confirm hardware detection, model loading, and
   streaming chat all work before touching any visual design.
2. Resolve the adapter format question and wire up conversion if needed.
3. Build Phase 2 UI on top of the working Phase 1 plumbing, in roughly
   this order: theme + layout → response border/highlight → thinking
   box collapse styling → search bar + chat history dropdown → save/load
   commands → animated sphere last, since it's the most self-contained
   and purely cosmetic piece.
