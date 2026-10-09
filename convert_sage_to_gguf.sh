#!/bin/bash
# Fuse each trained SAGE LoRA adapter into its base model, then convert to
# GGUF so llama.cpp / llama-server can run it on Windows and Linux too.
#
# Pipeline per size:
#   1. mlx_lm.fuse   — merge the LoRA adapter into the base MLX model
#                       (--dequantize ensures full-precision output even if
#                       the base checkpoint is quantized)
#   2. convert_hf_to_gguf.py (from llama.cpp) — convert the fused, HF-style
#                       model directory to an f16 GGUF. This is llama.cpp's
#                       own converter, not mlx_lm's built-in GGUF export —
#                       mlx_lm's exporter currently hardcodes "llama.*" GGUF
#                       architecture keys regardless of the source model,
#                       which would likely mistag a Qwen3 model. llama.cpp's
#                       own converter has had proper Qwen3 support since
#                       April 2025.
#   3. llama-quantize — shrink the f16 GGUF down to something practical to
#                       ship (Q4_K_M), also from llama.cpp.
#
# Prerequisites (not installed by this script):
#   - mlx-lm:      python3 -m pip install -U mlx-lm
#   - llama.cpp cloned and built, with its Python conversion deps installed:
#       git clone https://github.com/ggml-org/llama.cpp
#       cd llama.cpp && pip install -r requirements/requirements-convert_hf_to_gguf.txt
#       cmake -B build && cmake --build build --target llama-quantize -j
#
# IMPORTANT — verify before running:
#   Training (lora_config.yaml) used "Qwen/Qwen3-1.7B-MLX-bf16" as the base
#   for the 1.7b adapter. That's what this script fuses against by default
#   for 1.7b, NOT the 4-bit "mlx-community/Qwen3-1.7B-4bit" repo that
#   model_router.py uses at inference time — fusing against the same
#   precision the adapter was actually trained on gives a cleaner result;
#   GGUF-level quantization happens afterward in step 3 instead.
#
#   I only saw a training script/config for the 1.7b size. If you haven't
#   actually trained 4b/8b adapters yet, only run this for 1.7b — the
#   base-model repo names below for 4b/8b are a guess (following the same
#   "Qwen3-<size>-MLX-bf16" naming pattern) and need verifying against
#   what's actually on Hugging Face before you rely on them.

set -euo pipefail

LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-./llama.cpp}"
ADAPTERS_DIR="${ADAPTERS_DIR:-./adapters}"
OUT_DIR="${OUT_DIR:-./gguf_out}"
QUANT="${QUANT:-Q4_K_M}"

declare -A BASE_MODELS=(
  ["1.7b"]="Qwen/Qwen3-1.7B-MLX-bf16"
  ["4b"]="Qwen/Qwen3-4B-MLX-bf16"     # unverified — confirm this repo exists
  ["8b"]="Qwen/Qwen3-8B-MLX-bf16"     # unverified — confirm this repo exists
)

mkdir -p "$OUT_DIR"

convert_size() {
  local size="$1"
  local base="${BASE_MODELS[$size]}"
  local adapter="$ADAPTERS_DIR/sage-$size"
  local fused="$OUT_DIR/fused-$size"
  local f16_gguf="$OUT_DIR/sage-$size-f16.gguf"
  local quant_gguf="$OUT_DIR/sage-$size-${QUANT,,}.gguf"

  if [ ! -d "$adapter" ]; then
    echo "Skipping $size — no adapter found at $adapter"
    return
  fi

  echo "=== $size ==="
  echo "Fusing adapter into $base ..."
  python3 -m mlx_lm fuse \
    --model "$base" \
    --adapter-path "$adapter" \
    --save-path "$fused" \
    --dequantize

  echo "Converting to GGUF (f16) ..."
  python3 "$LLAMA_CPP_DIR/convert_hf_to_gguf.py" \
    "$fused" \
    --outfile "$f16_gguf" \
    --outtype f16

  echo "Quantizing to $QUANT ..."
  "$LLAMA_CPP_DIR/build/bin/llama-quantize" \
    "$f16_gguf" \
    "$quant_gguf" \
    "$QUANT"

  echo "Done: $quant_gguf"
  echo
}

for size in 1.7b 4b 8b; do
  convert_size "$size"
done

echo "All done. Quantized GGUF files (where adapters existed) are in $OUT_DIR/"
