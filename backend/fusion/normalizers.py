"""Per-signal normalization functions registry for hazard types.

Each normalization function takes raw signal payload and configuration,
and produces a normalized hazard severity sigma_i in [0.0, 1.0].
Unknown hazard types raise ValueError.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from fusion.config import FusionConfig


NormalizerFn = Callable[[Any, FusionConfig], float]
NORMALIZER_REGISTRY: dict[str, NormalizerFn] = {}


def register_normalizer(hazard_type: str) -> Callable[[NormalizerFn], NormalizerFn]:
    def decorator(fn: NormalizerFn) -> NormalizerFn:
        NORMALIZER_REGISTRY[hazard_type] = fn
        return fn
    return decorator


@register_normalizer("landslide")
def normalize_landslide(raw: Any, config: FusionConfig) -> float:
    """Landslide susceptibility: model probability used directly in [0, 1]."""
    if raw is None:
        return 0.0
    try:
        val = float(raw)
        return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        return 0.0


@register_normalizer("terrain")
def normalize_terrain(raw: Any, config: FusionConfig) -> float:
    """Terrain hazard / slope instability factor in [0, 1]."""
    if raw is None:
        return 0.0
    try:
        val = float(raw)
        return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        return 0.0


@register_normalizer("flood_susceptibility")
def normalize_flood_susceptibility(raw: Any, config: FusionConfig) -> float:
    """Flood susceptibility model probability in [0, 1]."""
    if raw is None:
        return 0.0
    try:
        val = float(raw)
        return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        return 0.0


@register_normalizer("flood")
def normalize_flood_alert(raw: Any, config: FusionConfig) -> float:
    """Flood alert (GDACS/FEWS): ordinal anchors (green 0.2, orange 0.55, red 0.9)."""
    anchors = config.normalization.get("flood_gdacs_anchors", {"green": 0.2, "orange": 0.55, "red": 0.9})
    if isinstance(raw, str):
        cleaned = raw.strip().lower()
        if "red" in cleaned:
            return float(anchors.get("red", 0.9))
        if "orange" in cleaned or "amber" in cleaned:
            return float(anchors.get("orange", 0.55))
        if "green" in cleaned:
            return float(anchors.get("green", 0.2))
    elif isinstance(raw, (int, float)):
        # If passed as numeric severity
        if raw >= 0.8:
            return float(anchors.get("red", 0.9))
        if raw >= 0.5:
            return float(anchors.get("orange", 0.55))
        return float(anchors.get("green", 0.2))
    return float(anchors.get("green", 0.2))


@register_normalizer("cyclone")
def normalize_cyclone_alert(raw: Any, config: FusionConfig) -> float:
    """Cyclone alert (GDACS/FEWS): ordinal anchors (green 0.2, orange 0.55, red 0.9)."""
    anchors = config.normalization.get("cyclone_gdacs_anchors", {"green": 0.2, "orange": 0.55, "red": 0.9})
    if isinstance(raw, str):
        cleaned = raw.strip().lower()
        if "red" in cleaned:
            return float(anchors.get("red", 0.9))
        if "orange" in cleaned or "amber" in cleaned:
            return float(anchors.get("orange", 0.55))
        if "green" in cleaned:
            return float(anchors.get("green", 0.2))
    elif isinstance(raw, (int, float)):
        if raw >= 0.8:
            return float(anchors.get("red", 0.9))
        if raw >= 0.5:
            return float(anchors.get("orange", 0.55))
        return float(anchors.get("green", 0.2))
    return float(anchors.get("green", 0.2))


@register_normalizer("earthquake")
def normalize_earthquake(raw: Any, config: FusionConfig) -> float:
    """Earthquake (USGS): sigmoid on magnitude, inflection at config value (default 5.0)."""
    eq_cfg = config.normalization.get("earthquake_sigmoid", {})
    inflection = float(eq_cfg.get("inflection_magnitude", 5.0))
    k = float(eq_cfg.get("steepness_k", 1.2))

    mag = 0.0
    if isinstance(raw, (int, float)):
        mag = float(raw)
    elif isinstance(raw, dict):
        mag = float(raw.get("mag", raw.get("magnitude", 0.0)))
    elif isinstance(raw, str):
        try:
            mag = float(raw)
        except ValueError:
            mag = 0.0

    # Sigmoid: 1 / (1 + exp(-k * (mag - inflection)))
    sigma = 1.0 / (1.0 + math.exp(-k * (mag - inflection)))
    return max(0.0, min(1.0, sigma))


@register_normalizer("fire")
def normalize_fire(raw: Any, config: FusionConfig) -> float:
    """Fire (FIRMS): source confidence field mapped to [0, 1]."""
    if raw is None:
        return 0.5
    if isinstance(raw, (int, float)):
        # FIRMS confidence is often 0-100 or already normalized 0.0-1.0
        val = float(raw)
        if val > 1.0:
            val = val / 100.0
        return max(0.0, min(1.0, val))
    if isinstance(raw, str):
        cleaned = raw.strip().lower()
        if cleaned == "h" or "high" in cleaned:
            return 0.9
        if cleaned == "n" or "nominal" in cleaned:
            return 0.6
        if cleaned == "l" or "low" in cleaned:
            return 0.3
        try:
            val = float(cleaned)
            return max(0.0, min(1.0, val / 100.0 if val > 1.0 else val))
        except ValueError:
            pass
    return 0.5


@register_normalizer("conflict")
def normalize_conflict(raw: Any, config: FusionConfig) -> float:
    """Conflict (ACLED): sigma = (1 - exp(-lambda * fatalities)) * event-type multiplier lookup.

    (protest < riot < armed clash). If fatalities == 0, applies base event presence factor.
    """
    lambda_val = float(config.normalization.get("conflict_fatalities_lambda", 0.25))
    multipliers = config.normalization.get(
        "conflict_event_multiplier",
        {
            "protest": 0.35,
            "riot": 0.65,
            "armed_clash": 1.00,
            "violence_against_civilians": 0.90,
        },
    )

    fatalities = 0.0
    event_type = "protest"

    if isinstance(raw, dict):
        fatalities = float(raw.get("fatalities", 0.0))
        event_type = str(raw.get("event_type", "protest")).lower().replace(" ", "_")
    elif isinstance(raw, (int, float)):
        fatalities = float(raw)
    elif isinstance(raw, str):
        event_type = raw.lower().replace(" ", "_")

    # Match event type multiplier
    multiplier = 0.35
    for key, mult in multipliers.items():
        if key in event_type:
            multiplier = float(mult)
            break

    # If fatalities > 0, use exponential curve. If 0 fatalities, presence of protest/riot has baseline
    if fatalities > 0:
        intensity = 1.0 - math.exp(-lambda_val * fatalities)
    else:
        # Baseline presence for events without reported fatalities
        intensity = 0.30

    sigma = intensity * multiplier
    return max(0.0, min(1.0, sigma))


@register_normalizer("crime")
def normalize_crime(raw: Any, config: FusionConfig) -> float:
    """Crime (district): percentile rank across all districts for the same year in [0, 1]."""
    if raw is None:
        return 0.0
    if isinstance(raw, dict):
        rank = raw.get("percentile_rank", raw.get("crime_rate_percentile", raw.get("severity_normalized")))
        if rank is not None:
            return max(0.0, min(1.0, float(rank)))
    try:
        val = float(raw)
        # If passed as 0-100 percentile rank, convert to 0-1
        if val > 1.0:
            val = val / 100.0
        return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        return 0.0


@register_normalizer("weather")
def normalize_weather(raw: Any, config: FusionConfig) -> float:
    """Weather: threshold-based on rainfall_mm_24h and wind vs configured trigger thresholds."""
    w_cfg = config.normalization.get("weather_thresholds", {})
    rain_heavy = float(w_cfg.get("rain_heavy_mm", 50.0))
    rain_extreme = float(w_cfg.get("rain_extreme_mm", 120.0))
    wind_high = float(w_cfg.get("wind_high_kmh", 40.0))
    wind_extreme = float(w_cfg.get("wind_extreme_kmh", 80.0))

    rain_mm = 0.0
    wind_kmh = 0.0

    if isinstance(raw, dict):
        rain_mm = float(raw.get("rainfall_mm_24h", raw.get("rain_mm", 0.0)))
        wind_kmh = float(raw.get("wind_speed_kmh", raw.get("wind_kmh", 0.0)))
    elif isinstance(raw, (int, float)):
        # If single normalized value passed directly
        return max(0.0, min(1.0, float(raw)))

    # Compute rain score
    rain_score = 0.0
    if rain_mm >= rain_extreme:
        rain_score = 1.0
    elif rain_mm >= rain_heavy:
        rain_score = 0.6 + 0.4 * ((rain_mm - rain_heavy) / max(1.0, rain_extreme - rain_heavy))
    elif rain_mm > 15.0:
        rain_score = 0.3 * (rain_mm / rain_heavy)

    # Compute wind score
    wind_score = 0.0
    if wind_kmh >= wind_extreme:
        wind_score = 1.0
    elif wind_kmh >= wind_high:
        wind_score = 0.6 + 0.4 * ((wind_kmh - wind_high) / max(1.0, wind_extreme - wind_high))
    elif wind_kmh > 20.0:
        wind_score = 0.3 * (wind_kmh / wind_high)

    sigma = max(rain_score, wind_score)
    return max(0.0, min(1.0, sigma))


@register_normalizer("news")
def normalize_news(raw: Any, config: FusionConfig) -> float:
    """Local news: classifier_confidence * tone_severity * recency_decay * log(1 + count) / norm, capped at 1.0."""
    news_cfg = config.normalization.get("news", {})
    count_norm = float(news_cfg.get("count_norm", 10.0))

    conf = 0.8
    tone_severity = 0.5
    recency_decay = 1.0
    count = 1

    if isinstance(raw, dict):
        conf = float(raw.get("classifier_confidence", raw.get("confidence", 0.8)))
        tone_severity = float(raw.get("tone_severity", raw.get("severity", 0.5)))
        recency_decay = float(raw.get("recency_decay", 1.0))
        count = int(raw.get("count", raw.get("article_count", 1)))
    elif isinstance(raw, (int, float)):
        return max(0.0, min(1.0, float(raw)))

    raw_calc = conf * tone_severity * recency_decay * (math.log(1.0 + max(0, count)) / math.log(1.0 + count_norm))
    return max(0.0, min(1.0, raw_calc))


def normalize_signal(hazard_type: str, raw_value: Any, config: FusionConfig) -> float:
    """Normalize a raw hazard signal using the registered normalizer for hazard_type.

    Raises ValueError if hazard_type is not registered.
    """
    if hazard_type not in NORMALIZER_REGISTRY:
        raise ValueError(
            f"Unknown hazard_type '{hazard_type}'. Must be one of registered hazard types: "
            f"{sorted(NORMALIZER_REGISTRY.keys())}"
        )
    return NORMALIZER_REGISTRY[hazard_type](raw_value, config)
