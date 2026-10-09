#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
PROMPT="${*:-good job}"
mlx_lm.generate \
  --model Qwen/Qwen3-1.7B-MLX-bf16 \
  --adapter-path adapters/sage-1.7b \
  --prompt "$PROMPT"
