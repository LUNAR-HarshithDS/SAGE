# Sage — Phase 1 skeleton

This is the working plumbing: Tauri shell → bundled llama.cpp sidecar →
streaming chat with Qwen3's `<think>` tags split into a separate live feed.
No Ollama, no Python, at runtime — everything ships in one app.

**Not yet in this pass** (Phase 2): the Gemini-style green/yellow theme,
the animated thinking-sphere, the search bar + chat-history dropdown,
`/save chat <name>`, and the border-highlight-on-complete treatment.
The current UI is a plain dark chat window so the underlying wiring can be
verified first.

## 1. Prerequisites

- Rust + Cargo — https://rustup.rs
- Node.js 18+
- Tauri CLI — installed via `npm install` (see step 4)

## 2. Get `llama-server`

Build or download llama.cpp's `llama-server` binary for your platform,
then place it at:

```
src-tauri/binaries/llama-server-<target-triple>
```

Find your target triple with:

```
rustc -Vv | grep host
```

Examples: `llama-server-x86_64-pc-windows-msvc.exe` (Windows),
`llama-server-aarch64-apple-darwin` (Apple Silicon Mac),
`llama-server-x86_64-unknown-linux-gnu` (Linux). You'll need one binary per
platform you ship for — Tauri does not cross-compile the sidecar for you.

## 3. Get the model + adapter files

Run the extraction script against your Sage models in Ollama:

```
python tools/extract_from_ollama.py sage:1.7b sage:4b sage:8b --out ./models
```

This should produce, per size you have:

```
models/sage-1.7b.gguf
models/sage-1.7b-adapter.gguf   (if a LoRA adapter was attached via Modelfile)
```

Rename the outputs to match what `sidecar.rs` expects if they don't already:

```
models/sage-1.7b.gguf
models/sage-4b.gguf
models/sage-8b.gguf
models/sage-1.7b-adapter.gguf   (optional, per size)
models/sage-4b-adapter.gguf
models/sage-8b-adapter.gguf
```

If your standalone adapter copy turns out to be in the original
PEFT/safetensors format rather than GGUF (check with the one-liner from
earlier: read the first 4 bytes, `b'GGUF'` means it's ready) — let me know
and I'll add the `convert_lora_to_gguf.py` conversion step.

## 4. Run it

```
npm install
npm run tauri dev
```

First message will take a few seconds while `llama-server` loads the
model; `/health` polling in `sidecar.rs` waits for it before the request
goes through.

## Known rough edges in this pass

- GPU detection is best-effort (`nvidia-smi` on Linux, `wmic` on Windows,
  chip name only on macOS) — good enough to decide GPU-offload on/off, not
  precise VRAM accounting.
- No icons configured yet — fine for `tauri dev`, but run
  `npm run tauri icon <path-to-1024x1024.png>` before `tauri build`.
- The context window is hardcoded to 4096 tokens in `sidecar.rs` — adjust
  to whatever Qwen3 size/quant you're running.
