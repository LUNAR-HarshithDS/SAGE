#!/usr/bin/env python3
"""
Extract GGUF model (and LoRA adapter, if attached via a Modelfile
ADAPTER instruction) blobs out of Ollama's local blob store, so they can
be used directly with llama.cpp / llama-server without Ollama running.

Usage:
    python extract_from_ollama.py sage:1.7b sage:4b sage:8b --out ./extracted

If auto-detection can't find your Ollama directory, pass it explicitly:
    python extract_from_ollama.py sage:1.7b --models-dir /path/to/.ollama/models
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

MODEL_MEDIA_TYPE = "application/vnd.ollama.image.model"
ADAPTER_MEDIA_TYPE = "application/vnd.ollama.image.adapter"


def candidate_ollama_dirs():
    env = os.environ.get("OLLAMA_MODELS")
    if env:
        yield Path(env)
    home = Path.home()
    yield home / ".ollama" / "models"
    yield Path("/usr/share/ollama/.ollama/models")  # Linux service install


def find_models_dir(explicit: Optional[str]) -> Path:
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        print(f"--models-dir {p} does not exist.")
        sys.exit(1)

    for candidate in candidate_ollama_dirs():
        if candidate.exists():
            return candidate

    print("Could not auto-detect Ollama's models directory.")
    print("Run `ollama list` to confirm Ollama is installed, then pass")
    print("--models-dir explicitly (check the OLLAMA_MODELS env var too).")
    sys.exit(1)


def parse_name_tag(spec: str):
    name, _, tag = spec.partition(":")
    return name, (tag or "latest")


def find_manifest(models_dir: Path, name: str, tag: str) -> Path:
    manifests_root = models_dir / "manifests"
    matches = [
        p for p in manifests_root.rglob(tag)
        if p.is_file() and p.parent.name == name
    ]
    if not matches:
        raise FileNotFoundError(
            f"No manifest found for '{name}:{tag}' under {manifests_root}. "
            f"Run `ollama list` to confirm the exact name and tag "
            f"(if you used a custom namespace, the manifest may be nested "
            f"differently — check {manifests_root} by hand)."
        )
    return matches[0]


def blob_path(models_dir: Path, digest: str) -> Path:
    algo, hexpart = digest.split(":", 1)
    return models_dir / "blobs" / f"{algo}-{hexpart}"


def extract_one(models_dir: Path, spec: str, out_dir: Path):
    name, tag = parse_name_tag(spec)
    manifest_path = find_manifest(models_dir, name, tag)
    manifest = json.loads(manifest_path.read_text())
    safe_name = f"{name}-{tag}".replace("/", "_")
    found = False

    for layer in manifest.get("layers", []):
        media_type = layer.get("mediaType", "")
        digest = layer.get("digest", "")
        if not digest:
            continue
        src = blob_path(models_dir, digest)

        if media_type == MODEL_MEDIA_TYPE:
            dst = out_dir / f"{safe_name}.gguf"
            shutil.copyfile(src, dst)
            print(f"  model   -> {dst.name}  ({src.stat().st_size / 1e9:.2f} GB)")
            found = True

        elif media_type == ADAPTER_MEDIA_TYPE:
            dst = out_dir / f"{safe_name}-adapter.gguf"
            shutil.copyfile(src, dst)
            print(f"  adapter -> {dst.name}  ({src.stat().st_size / 1e6:.2f} MB)")
            found = True

    if not found:
        print("  no model/adapter layers matched — inspect the manifest by hand:")
        print(f"  {manifest_path}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("models", nargs="+", help="model:tag entries, e.g. sage:1.7b")
    parser.add_argument("--out", default="./extracted", help="output directory (default: ./extracted)")
    parser.add_argument("--models-dir", default=None, help="override Ollama's models directory")
    args = parser.parse_args()

    models_dir = find_models_dir(args.models_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Using Ollama models dir: {models_dir}\n")

    for spec in args.models:
        print(f"Extracting {spec}...")
        try:
            extract_one(models_dir, spec, out_dir)
        except Exception as e:
            print(f"  failed: {e}")
        print()

    print(f"Done. Extracted files (if any) are in {out_dir.resolve()}")


if __name__ == "__main__":
    main()
