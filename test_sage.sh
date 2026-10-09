#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mlx_lm.lora \
  --model Qwen/Qwen3-1.7B-MLX-bf16 \
  --test \
  --data data \
  --adapter-path adapters/sage-1.7b
