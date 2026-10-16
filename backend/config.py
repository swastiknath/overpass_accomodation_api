"""Runtime settings and environment configuration for India Travel Safety system."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Geographic envelope of India in EPSG:4326 (lon_min, lat_min, lon_max, lat_max)
INDIA_BBOX: tuple[float, float, float, float] = (68.0, 6.0, 97.5, 37.0)


class Settings(BaseSettings):
    """Runtime config loaded from environment variables / `.env`. Credentials are never hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── Operating Mode ────────────────────────────────────────────────────
    demo_mode: bool = Field(default=False, description="When True, serves fixtures without external network calls")
    config_dir: Path = Field(default=Path("config"), description="Path to config directory with YAML files")
    fixtures_dir: Path = Field(default=Path("fixtures"), description="Path to recorded connector responses")

    # ── Fusion & Advice Config Files ──────────────────────────────────────
    fusion_config_path: Path = Field(default=Path("config/fusion_config.yaml"))
    advice_catalog_path: Path = Field(default=Path("config/advice_catalog.yaml"))
    news_keywords_path: Path = Field(default=Path("config/news_keywords.yaml"))

    # ── Licensing and Data Redistribution ────────────────────────────────
    # If redistribution_allowed is False, public responses emit only aggregated / derived metrics
    redistribution_allowed: bool = Field(
        default=True,
        description="Whether commercial / public redistribution of raw records (e.g. ACLED) is permitted",
    )

    # ── Geocoding & Maps ──────────────────────────────────────────────────
    geocode_provider: Literal["nominatim", "photon", "mapbox"] = Field(default="nominatim")
    nominatim_user_agent: str = Field(
        default="IndiaTravelSafety/1.0 (safety-research@example.com)",
        description="Identifying User-Agent for Nominatim OSM geocoding",
    )
    nominatim_base_url: str = Field(default="https://nominatim.openstreetmap.org")
    mapbox_access_token: str | None = Field(default=None)
    map_style_url: str = Field(default="https://demotiles.maplibre.org/style.json")

    # ── Hotel Providers ───────────────────────────────────────────────────
    overpass_url: str = Field(default="https://overpass-api.de/api/interpreter")
    overpass_timeout_seconds: float = Field(default=45.0, gt=0)
    google_places_api_key: str | None = Field(default=None)
    foursquare_api_key: str | None = Field(default=None)
    amadeus_api_key: str | None = Field(default=None)
    amadeus_api_secret: str | None = Field(default=None)

    # ── OpenRouter LLM ────────────────────────────────────────────────────
    openrouter_api_key: str | None = Field(default=None)
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_model_narrator: str = Field(default="anthropic/claude-3.5-sonnet")
    openrouter_model_verifier: str = Field(default="openai/gpt-4o-mini")
    openrouter_fallback_models: list[str] = Field(
        default_factory=lambda: ["google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"]
    )
    openrouter_referer: str = Field(default="https://indiatravelsafety.org")
    openrouter_app_title: str = Field(default="India Travel Safety Intelligence")
    openrouter_timeout_seconds: float = Field(default=25.0, gt=0)
    openrouter_max_retries: int = Field(default=2, ge=0)
    llm_daily_budget_usd: float = Field(default=10.0, gt=0)
    llm_daily_token_limit: int = Field(default=500000, gt=0)

    # ── Bhuvan / NRSC (ISRO) ──────────────────────────────────────────────
    bhuvan_username: str | None = Field(default=None)
    bhuvan_password: str | None = Field(default=None)
    bhuvan_wms_base_url: str = Field(default="")
    bhuvan_wms_version: str = Field(default="1.3.0")
    bhuvan_wfs_base_url: str = Field(default="")
    bhuvan_wfs_version: str = Field(default="2.0.0")
    gis_landing_zone: Path = Field(default=Path("data/landing/private"))
    gis_public_zone: Path = Field(default=Path("data/public"))
    bhuvan_max_retries: int = Field(default=4, ge=0)
    bhuvan_retry_base_seconds: float = Field(default=1.5, gt=0)
    bhuvan_timeout_seconds: float = Field(default=60.0, gt=0)
    bhuvan_default_width: int = Field(default=1024, ge=1)
    bhuvan_default_height: int = Field(default=1024, ge=1)

    # ── ACLED — conflict & political violence ─────────────────────────────
    acled_email: str | None = Field(default=None)
    acled_password: str | None = Field(default=None)
    acled_api_url: str = Field(default="https://api.acleddata.com")

    # ── NASA FIRMS — active fire detections ───────────────────────────────
    firms_map_key: str | None = Field(default=None)

    # ── Weather ───────────────────────────────────────────────────────────
    weather_backend: Literal["open_meteo", "openweathermap"] = Field(default="open_meteo")
    openweathermap_api_key: str | None = Field(default=None)

    # ── data.gov.in — IPC crime data ──────────────────────────────────────
    datagov_api_key: str | None = Field(default=None)

    # ── GDELT DOC 2.0 — news article discovery ───────────────────────────
    gdelt_doc_api_url: str = Field(default="https://api.gdeltproject.org/api/v2/doc/doc")

    # ── Shared connector defaults ─────────────────────────────────────────
    connector_max_retries: int = Field(default=3, ge=0)
    connector_retry_base_seconds: float = Field(default=1.0, gt=0)
    connector_timeout_seconds: float = Field(default=30.0, gt=0)

    # ── Admin boundary layer (optional) ───────────────────────────────────
    admin_boundary_path: str | None = Field(default=None)
    admin_id_column: str = Field(default="district_id")
    admin_name_column: str = Field(default="district_name")

    # ── Web API & Security ────────────────────────────────────────────────
    allowed_origins: list[str] = Field(default_factory=lambda: ["*"])
    api_rate_limit_per_minute: int = Field(default=60, ge=1)

    @field_validator(
        "bhuvan_username",
        "bhuvan_password",
        "acled_email",
        "acled_password",
        "firms_map_key",
        "openweathermap_api_key",
        "datagov_api_key",
        "admin_boundary_path",
        "openrouter_api_key",
        "google_places_api_key",
        "foursquare_api_key",
        "amadeus_api_key",
        "amadeus_api_secret",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("openrouter_fallback_models", "allowed_origins", mode="before")
    @classmethod
    def _parse_list_from_str(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except Exception:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


_GLOBAL_SETTINGS: Settings | None = None


def load_settings() -> Settings:
    global _GLOBAL_SETTINGS
    if _GLOBAL_SETTINGS is None:
        _GLOBAL_SETTINGS = Settings()
    return _GLOBAL_SETTINGS
