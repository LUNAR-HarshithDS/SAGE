# SAGE Qwen3-1.7B LoRA Training Pack

This is a starter behavioral fine-tuning pack for teaching Qwen3-1.7B the SAGE personality and communication style without retraining its original pretraining corpus.

## Contents

- `data/train.jsonl` — training set
- `data/valid.jsonl` — validation set
- `data/test.jsonl` — held-out test set
- `lora_config.yaml` — MLX-LM LoRA configuration
- `train_sage.sh` — first training run
- `test_sage.sh` — evaluate the adapter
- `generate_sage.sh` — generate responses with the adapter
- `requirements.txt` — training dependency
- `build_dataset.py` — regenerates the dataset

## Base model

`Qwen/Qwen3-1.7B-MLX-bf16`

## First run

```bash
cd sage_finetune
python3 -m pip install -U "mlx-lm[train]"
./train_sage.sh
```

MLX-LM's current LoRA trainer accepts a local dataset directory containing `train.jsonl`, optional `valid.jsonl`, and `test.jsonl` for evaluation; it also supports YAML configuration and LoRA adapters. See the official documentation for the current CLI and format. 

## Test

```bash
./test_sage.sh
./generate_sage.sh "good job"
./generate_sage.sh "My program crashed"
./generate_sage.sh "How do wings generate lift?"
```

## Important

This is a deliberately small first experiment. Validate that SAGE behavior improves without degrading general knowledge, coding, math, or technical explanations before increasing the dataset or training duration.
