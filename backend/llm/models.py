"""Pydantic schemas for the OpenRouter LLM explanation and verification layer."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class NarratorKeyDriver(BaseModel):
    factor: str
    plain_language: str
    evidence_ref: str


class NarratorOutput(BaseModel):
    headline: str
    summary: str = Field(..., max_length=1000)
    key_drivers: list[NarratorKeyDriver]
    caveats: list[str] = Field(default_factory=list)
    hotel_comparison: str


class OfficialAuthority(BaseModel):
    name: str
    url: str | None = None
    helpline: str | None = None


class CuratedAdviceItem(BaseModel):
    hazard_type: str
    hazard_name: str
    tips: list[str]
    authorities: list[OfficialAuthority]


class VerifierOutput(BaseModel):
    supported: bool
    unsupported_claims: list[str] = Field(default_factory=list)


class NarrativeResult(BaseModel):
    narrative_status: Literal["verified", "unverified", "fallback_template", "unavailable"]
    narrative: NarratorOutput
    curated_advice: list[CuratedAdviceItem]
    verification_details: dict[str, Any] = Field(default_factory=dict)
    model_used: str | None = None
    cached: bool = False
    config_version: str
