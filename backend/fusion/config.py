"""Configuration loader and schema models for the fusion scoring engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
import yaml
from pydantic import BaseModel, Field


class ScoreBand(BaseModel):
    min: float
    max: float
    label: str
    code: str
    description: str


class HotelRankingConfig(BaseModel):
    default_alpha: float = 0.7
    same_area_epsilon: float = 2.5


class FusionConfig(BaseModel):
    config_version: str
    hazard_layers: dict[str, Literal["static", "dynamic"]]
    base_weights: dict[str, float]
    source_confidence_defaults: dict[str, float]
    resolution_multipliers: dict[str, float]
    spatial_kernel_sigma_km: dict[str, float]
    temporal_decay_half_life_hours: dict[str, float | None]
    conflict_decay_by_event_type: dict[str, float] = Field(default_factory=dict)
    normalization: dict[str, Any]
    score_bands: list[ScoreBand]
    hotel_ranking: HotelRankingConfig = Field(default_factory=HotelRankingConfig)


_CACHE: tuple[str, FusionConfig] | None = None


def load_fusion_config(config_path: str | Path | None = None) -> FusionConfig:
    global _CACHE
    if config_path is None:
        # Search relative to current directory or monorepo root
        candidates = [
            Path("config/fusion_config.yaml"),
            Path("../config/fusion_config.yaml"),
            Path(__file__).resolve().parent.parent.parent / "config" / "fusion_config.yaml",
        ]
        path = next((p for p in candidates if p.exists()), candidates[0])
    else:
        path = Path(config_path)

    path_str = str(path.resolve()) if path.exists() else str(path)
    if _CACHE and _CACHE[0] == path_str:
        return _CACHE[1]

    if not path.exists():
        raise FileNotFoundError(f"Fusion config not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cfg = FusionConfig.model_validate(data)
    _CACHE = (path_str, cfg)
    return cfg
