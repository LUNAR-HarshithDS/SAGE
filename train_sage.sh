#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -U "mlx-lm[train]"
mkdir -p adapters
mlx_lm.lora --config lora_config.yaml
