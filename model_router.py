"""SAGE model selection.

Only the 1.7B writer uses a SAGE LoRA adapter.
The 4B and 8B models use their untouched base weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

SAGE_HOME = Path(__file__).resolve().parent
USER_SAGE_HOME = Path.home() / "SAGE"
MANAGED_MODEL_HOME = Path.home() / "SAGE Models"

HF_BASE_MODELS = {
    "1.7b": "mlx-community/Qwen3-1.7B-4bit",
    "4b": "mlx-community/Qwen3-4B-4bit",
    "8b": "mlx-community/Qwen3-8B-4bit",
}

LOCAL_DIRS = {
    "1.7b": MANAGED_MODEL_HOME / "qwen3-1.7b-4bit",
    "4b": MANAGED_MODEL_HOME / "qwen3-4b-4bit",
    "8b": MANAGED_MODEL_HOME / "qwen3-8b-4bit",
}

DISPLAY_NAMES = {
    "1.7b": "SAGE-1.7B Writer",
    "4b": "SAGE-4B",
    "8b": "SAGE-8B",
}


def _adapter_candidates(size: str) -> list[Path]:
    return [
        MANAGED_MODEL_HOME / "adapters" / f"sage-{size}",
        USER_SAGE_HOME / "sage_finetune" / "adapters" / f"sage-{size}",
        USER_SAGE_HOME / "adapters" / f"sage-{size}",
        SAGE_HOME / "adapters" / f"sage-{size}",
    ]


@dataclass(frozen=True)
class ModelSpec:
    size: str
    display_name: str
    base_repo: str
    adapter_path: Optional[Path]
    thinking: bool
    temperature: float
    top_p: float
    top_k: int
    max_tokens: int

    def base_model(self) -> str:
        local = LOCAL_DIRS[self.size]
        if (
            (local / "config.json").exists()
            and any(local.glob("*.safetensors"))
        ):
            return str(local)
        return self.base_repo

    @property
    def adapter_ready(self) -> bool:
        return bool(
            self.adapter_path
            and (self.adapter_path / "adapters.safetensors").exists()
        )

    @property
    def model(self) -> str:
        return self.display_name

    @property
    def use_thinking(self) -> bool:
        return self.thinking

    @property
    def tier(self) -> str:
        return self.size

    @property
    def use_model(self) -> bool:
        # Compatibility for older callers. Whether a request needs AI
        # should normally come from FunctionDecision.requires_ai.
        return True


ModelDecision = ModelSpec


def resolve_adapter(size: str) -> Optional[Path]:
    for path in _adapter_candidates(size):
        if path.is_dir():
            return path
    return None


def _spec(
    size: str,
    *,
    thinking: bool = True,
    use_adapter: bool = False,
) -> ModelSpec:
    return ModelSpec(
        size=size,
        display_name=DISPLAY_NAMES[size],
        base_repo=HF_BASE_MODELS[size],
        adapter_path=resolve_adapter(size) if use_adapter else None,
        thinking=thinking,
        temperature=0.6 if thinking else 0.7,
        top_p=0.95 if thinking else 0.8,
        top_k=20,
        max_tokens=8192 if size == "8b" else 4096,
    )


def select_model(request: Any, function: Any = None) -> ModelSpec:
    """Select the reasoning model or the dedicated phrasing model."""

    # Support both InterpretedRequest and the compatibility Request.
    kind = str(
        getattr(request, "intent", getattr(request, "kind", ""))
    )
    complexity = str(getattr(request, "complexity", "normal"))

    requires_web = bool(
        getattr(request, "explicit_web", False)
        or getattr(request, "requires_web", False)
        or getattr(function, "requires_web", False)
    )

    # Only explicit wording/transformation tasks use the trained writer.
    if kind == "phrasing" or complexity == "phrasing":
        return _spec(
            "1.7b",
            thinking=False,
            use_adapter=True,
        )

    # Keep web research on the larger base model.
    if requires_web or kind == "research":
        return _spec("8b", thinking=True)

    # Actual reasoning and task-solving use the unmodified base models.
    if complexity in ("hard", "very_hard", "complex"):
        return _spec("8b", thinking=True)

    return _spec("4b", thinking=True)


__all__ = [
    "HF_BASE_MODELS",
    "DISPLAY_NAMES",
    "ModelSpec",
    "ModelDecision",
    "resolve_adapter",
    "select_model",
]

