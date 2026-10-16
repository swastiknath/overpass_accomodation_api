import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Tuple

import httpx
import yaml

from config import Settings, load_settings
from llm.budget import GLOBAL_BUDGET
from llm.models import (
    CuratedAdviceItem,
    NarrativeResult,
    NarratorKeyDriver,
    NarratorOutput,
    OfficialAuthority,
    VerifierOutput,
)

logger = logging.getLogger("llm.explainer")

PROMPT_VERSION = "2026.1.0"


class LLMExplainer:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.api_key = self.settings.openrouter_api_key
        self.base_url = self.settings.openrouter_base_url.rstrip("/")
        self.timeout = self.settings.openrouter_timeout_seconds
        self.advice_catalog = self._load_advice_catalog()
        self.narrator_prompt_template = self._load_prompt("narrator_v1.txt")
        self.verifier_prompt_template = self._load_prompt("verifier_v1.txt")
        self._cache: dict[str, NarrativeResult] = {}

    def _load_prompt(self, filename: str) -> str:
        candidates = [
            Path(f"backend/llm/prompts/{filename}"),
            Path(f"llm/prompts/{filename}"),
            Path(__file__).parent / "prompts" / filename,
        ]
        p = next((c for c in candidates if c.exists()), None)
        if p:
            return p.read_text(encoding="utf-8")
        return f"PROMPT_VERSION={PROMPT_VERSION}\nGenerate travel safety narrative based on structured inputs."

    def _load_advice_catalog(self) -> dict[str, Any]:
        candidates = [
            self.settings.advice_catalog_path,
            Path("config/advice_catalog.yaml"),
            Path("../config/advice_catalog.yaml"),
            Path(__file__).parent.parent.parent / "config" / "advice_catalog.yaml",
        ]
        p = next((c for c in candidates if c and Path(c).exists()), None)
        if not p:
            logger.warning("Advice catalog not found; using empty catalog.")
            return {}
        try:
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed loading advice catalog: {e}")
            return {}

    async def generate_and_verify_narrative(
        self,
        report: dict[str, Any],
        model_override: dict[str, str] | None = None,
    ) -> NarrativeResult:
        """Execute full narrator -> deterministic check -> verifier pipeline."""
        config_version = report.get("config_version", "2026.1")

        # Attach curated advice deterministically from catalog
        curated_advice = self._get_curated_advice_for_report(report)

        # In DEMO_MODE: Return verified canned narrative with strict checks
        if self.settings.demo_mode or report.get("demo", False):
            canned_output = self._build_canned_narrative(report)
            det_ok, det_err = self._deterministic_verification(canned_output, report)
            return NarrativeResult(
                narrative_status="verified" if det_ok else "fallback_template",
                narrative=canned_output,
                curated_advice=curated_advice,
                verification_details={"deterministic_check": det_ok, "error": det_err, "mode": "demo_mode"},
                model_used="demo_fixtures",
                cached=True,
                config_version=config_version,
            )

        # Check API Key
        if not self.api_key:
            logger.info("OPENROUTER_API_KEY is not set. Generating deterministic fallback template.")
            template = self._build_fallback_template(report)
            return NarrativeResult(
                narrative_status="unavailable",
                narrative=template,
                curated_advice=curated_advice,
                verification_details={"reason": "OPENROUTER_API_KEY not configured"},
                model_used=None,
                cached=False,
                config_version=config_version,
            )

        # Check Daily Budget Guard
        if not GLOBAL_BUDGET.can_make_request():
            logger.warning("Daily LLM budget exhausted. Returning deterministic fallback template.")
            template = self._build_fallback_template(report)
            return NarrativeResult(
                narrative_status="unavailable",
                narrative=template,
                curated_advice=curated_advice,
                verification_details={"reason": "Daily token/cost budget limit reached"},
                model_used=None,
                cached=False,
                config_version=config_version,
            )

        # Extract structured narrator input (Prompt Injection Hygiene: sanitize untrusted text)
        sanitized_input = self._build_sanitized_narrator_input(report)
        narrator_model = (model_override or {}).get("narrator") or self.settings.openrouter_model_narrator

        # Check cache
        cache_key = hashlib.sha256(
            f"{json.dumps(sanitized_input, sort_keys=True)}:{narrator_model}:{PROMPT_VERSION}".encode("utf-8")
        ).hexdigest()
        if cache_key in self._cache:
            cached_res = self._cache[cache_key]
            return cached_res.model_copy(update={"cached": True})

        # 1. Call Narrator Model with Fallback Chain
        narrator_output, model_used = await self._call_narrator_with_fallback(
            sanitized_input, narrator_model
        )

        if not narrator_output:
            logger.warning("Narrator call failed across all models. Falling back to deterministic template.")
            template = self._build_fallback_template(report)
            return NarrativeResult(
                narrative_status="fallback_template",
                narrative=template,
                curated_advice=curated_advice,
                verification_details={"reason": "Narrator LLM failure or parse error"},
                model_used=model_used,
                cached=False,
                config_version=config_version,
            )

        # 2. Deterministic Verification Check
        det_passed, det_errors = self._deterministic_verification(narrator_output, report)
        if not det_passed:
            logger.warning(
                f"Deterministic verification FAILED for narrative: {det_errors}. "
                "Rejecting LLM narrative and returning fallback template."
            )
            template = self._build_fallback_template(report)
            return NarrativeResult(
                narrative_status="fallback_template",
                narrative=template,
                curated_advice=curated_advice,
                verification_details={
                    "deterministic_check": False,
                    "unsupported_claims": det_errors,
                    "rejected_model": model_used,
                },
                model_used=model_used,
                cached=False,
                config_version=config_version,
            )

        # 3. Call Verifier Model (Second Model)
        verifier_model = (model_override or {}).get("verifier") or self.settings.openrouter_model_verifier
        verifier_res = await self._call_verifier_model(sanitized_input, narrator_output, verifier_model)

        narrative_status = "verified"
        verification_details: dict[str, Any] = {"deterministic_check": True}

        if verifier_res is None:
            narrative_status = "unverified"
            verification_details["verifier_model_status"] = "unavailable"
        elif not verifier_res.supported:
            logger.warning(
                f"Verifier model flagged unsupported claims: {verifier_res.unsupported_claims}. "
                "Falling back to template."
            )
            template = self._build_fallback_template(report)
            return NarrativeResult(
                narrative_status="fallback_template",
                narrative=template,
                curated_advice=curated_advice,
                verification_details={
                    "deterministic_check": True,
                    "verifier_model_supported": False,
                    "unsupported_claims": verifier_res.unsupported_claims,
                },
                model_used=model_used,
                cached=False,
                config_version=config_version,
            )
        else:
            verification_details["verifier_model_supported"] = True
            verification_details["verifier_model"] = verifier_model

        final_res = NarrativeResult(
            narrative_status=narrative_status,
            narrative=narrator_output,
            curated_advice=curated_advice,
            verification_details=verification_details,
            model_used=model_used,
            cached=False,
            config_version=config_version,
        )
        self._cache[cache_key] = final_res
        return final_res

    def _build_sanitized_narrator_input(self, report: dict[str, Any]) -> dict[str, Any]:
        """Sanitize report inputs for the narrator.

        Strict prompt injection hygiene: Do NOT include raw article text or unsanitized HTML.
        Include only structured metrics, counts, scores, and verified references.
        """
        top_contribs = []
        for c in report.get("contributions", [])[:8]:
            top_contribs.append({
                "evidence_ref": c.get("evidence_ref"),
                "hazard_type": c.get("hazard_type"),
                "source": c.get("source"),
                "human_label": c.get("human_label"),
                "contribution_pct": round(c.get("contribution", 0.0) * 100, 1),
                "distance_km": c.get("distance_km"),
                "age_hours": c.get("age_hours"),
                "resolution_tier": c.get("resolution_tier"),
            })

        hotels_summary = []
        for h in report.get("hotels_ranked", [])[:5]:
            h_info = h.get("hotel", {})
            hotels_summary.append({
                "name": h_info.get("name"),
                "category": h_info.get("category"),
                "safety_score": h.get("safety_score"),
                "stars": h_info.get("stars"),
                "distance_km": h_info.get("distance_to_query_km"),
            })

        return {
            "location": report.get("location", {}).get("display_name"),
            "district": report.get("location", {}).get("district"),
            "safety_score": report.get("area_score", {}).get("safety_score"),
            "band_label": report.get("area_score", {}).get("band", {}).get("label"),
            "confidence": report.get("area_score", {}).get("confidence"),
            "static_risk_subscore": report.get("area_score", {}).get("S_static"),
            "dynamic_risk_subscore": report.get("area_score", {}).get("S_dynamic"),
            "same_area_warning": report.get("same_area_warning", False),
            "top_contributions": top_contribs,
            "coverage": report.get("coverage", {}),
            "hotels_comparison": hotels_summary,
        }

    async def _call_narrator_with_fallback(
        self, payload: dict[str, Any], initial_model: str
    ) -> tuple[NarratorOutput | None, str | None]:
        models_to_try = [initial_model] + [
            m for m in self.settings.openrouter_fallback_models if m != initial_model
        ]

        messages = [
            {"role": "system", "content": self.narrator_prompt_template},
            {
                "role": "user",
                "content": f"Here is the verified deterministic safety report:\n\n{json.dumps(payload, indent=2)}",
            },
        ]

        for model in models_to_try:
            logger.info(f"Attempting narrator call with model: {model}")
            for attempt in range(2):  # Retry once on parse failure
                try:
                    resp_json, tokens = await self._post_chat_completion(model, messages)
                    parsed = NarratorOutput.model_validate_json(resp_json)
                    GLOBAL_BUDGET.record_usage(tokens.get("prompt", 0), tokens.get("completion", 0))
                    return parsed, model
                except Exception as e:
                    logger.warning(f"Narrator attempt {attempt + 1} with {model} failed: {e}")
                    await asyncio.sleep(1.0)
        return None, None

    async def _call_verifier_model(
        self, input_payload: dict[str, Any], narrative: NarratorOutput, verifier_model: str
    ) -> VerifierOutput | None:
        messages = [
            {"role": "system", "content": self.verifier_prompt_template},
            {
                "role": "user",
                "content": (
                    f"INPUT JSON DATA:\n{json.dumps(input_payload, indent=2)}\n\n"
                    f"GENERATED NARRATIVE:\n{narrative.model_dump_json(indent=2)}"
                ),
            },
        ]
        try:
            resp_json, tokens = await self._post_chat_completion(verifier_model, messages)
            GLOBAL_BUDGET.record_usage(tokens.get("prompt", 0), tokens.get("completion", 0))
            return VerifierOutput.model_validate_json(resp_json)
        except Exception as e:
            logger.warning(f"Verifier model {verifier_model} failed: {e}")
            return None

    async def _post_chat_completion(
        self, model: str, messages: list[dict[str, str]]
    ) -> tuple[str, dict[str, int]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.settings.openrouter_referer,
            "X-Title": self.settings.openrouter_app_title,
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
            if resp.status_code in (404, 429, 500, 502, 503, 504):
                raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens = {
                "prompt": usage.get("prompt_tokens", 0),
                "completion": usage.get("completion_tokens", 0),
            }
            return content, tokens

    def _deterministic_verification(
        self, narrative: NarratorOutput, report: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Verify that every number and evidence_ref in the narrative exists in the input JSON."""
        errors: list[str] = []

        # 1. Verify evidence_ref in key_drivers
        valid_refs = {c.get("evidence_ref") for c in report.get("contributions", [])}
        for driver in narrative.key_drivers:
            if driver.evidence_ref not in valid_refs and valid_refs:
                errors.append(f"Invalid or fabricated evidence_ref '{driver.evidence_ref}' cited in key drivers.")

        # 2. Verify numbers
        # Collect all numbers appearing in report JSON
        report_str = json.dumps(report)
        valid_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", report_str))

        # Common innocuous numbers allowed (e.g. 1, 2, 3 in bullet listings or ranking positions)
        allowed_trivial = {"1", "2", "3", "4", "5", "10", "100"}

        # Extract numbers in headline and summary
        narrative_text = f"{narrative.headline} {narrative.summary} {narrative.hotel_comparison}"
        narrative_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", narrative_text))

        for num in narrative_numbers:
            if num not in valid_numbers and num not in allowed_trivial:
                # Check if it is a rounded float matching an input number
                try:
                    val = float(num)
                    if any(abs(val - float(vn)) < 0.15 for vn in valid_numbers if self._is_float(vn)):
                        continue
                except ValueError:
                    pass
                errors.append(f"Number '{num}' in narrative is not grounded in deterministic input data.")

        return (len(errors) == 0, errors)

    def _is_float(self, val: str) -> bool:
        try:
            float(val)
            return True
        except ValueError:
            return False

    def _get_curated_advice_for_report(self, report: dict[str, Any]) -> list[CuratedAdviceItem]:
        """Attach relevant safety advice and official sources from config/advice_catalog.yaml."""
        items: list[CuratedAdviceItem] = []
        if not self.advice_catalog:
            return []

        # Identify contributing hazard types
        hazards = set()
        for c in report.get("contributions", []):
            h_type = c.get("hazard_type")
            if h_type:
                hazards.add(h_type)

        # If no specific hazard, include general advice
        if not hazards:
            hazards = {"weather", "crime"}

        for h in hazards:
            entry = self.advice_catalog.get(h)
            if entry:
                authorities = []
                for auth in entry.get("authorities", []):
                    authorities.append(
                        OfficialAuthority(
                            name=auth.get("name", "Emergency Services"),
                            url=auth.get("url"),
                            helpline=auth.get("helpline"),
                        )
                    )
                items.append(
                    CuratedAdviceItem(
                        hazard_type=h,
                        hazard_name=entry.get("hazard_name", h.title()),
                        tips=entry.get("tips", []),
                        authorities=authorities,
                    )
                )
        return items

    def _build_fallback_template(self, report: dict[str, Any]) -> NarratorOutput:
        """Deterministic template narrative built directly from fusion scores and contributions."""
        score = report.get("area_score", {}).get("safety_score", 100)
        band = report.get("area_score", {}).get("band", {}).get("label", "Moderate Risk")
        location = report.get("location", {}).get("display_name", "the searched location")
        top_contribs = report.get("contributions", [])

        if not top_contribs:
            headline = f"Stable Travel Conditions Observed in {location.split(',')[0]}"
            summary = (
                f"The overall deterministic safety score for {location} is {score} out of 100 ({band}). "
                "No active severe geo-hazards, critical weather warnings, or civil disruption signals were "
                "detected in this coverage area."
            )
            key_drivers = []
        else:
            top_h = top_contribs[0]
            headline = f"{top_h.get('human_label', 'Hazard Signal')} Shapes Safety Score ({score}/100)"
            summary = (
                f"The deterministic safety evaluation for {location} is {score}/100, corresponding to {band}. "
                f"The primary risk driver is {top_h.get('human_label')}, contributing {int(top_h.get('contribution', 0)*100)}% "
                f"of observed hazard weight at a distance of {top_h.get('distance_km', 0)} km."
            )
            key_drivers = [
                NarratorKeyDriver(
                    factor=c.get("human_label", c.get("hazard_type", "Hazard")),
                    plain_language=(
                        f"Active {c.get('hazard_type')} signal from {c.get('source')} "
                        f"accounting for {int(c.get('contribution', 0)*100)}% of total risk."
                    ),
                    evidence_ref=c.get("evidence_ref", "ref_unknown"),
                )
                for c in top_contribs[:3]
            ]

        caveats = []
        for hazard, status in report.get("coverage", {}).items():
            if status == "source_failed":
                caveats.append(f"Data source for {hazard} was temporarily unavailable.")
            elif status == "not_available_for_region":
                caveats.append(f"High-resolution {hazard} layers are not available for this region.")

        same_area = report.get("same_area_warning", False)
        if same_area:
            hotel_comp = (
                "Accommodations in this area share virtually identical localized hazard exposure; "
                "differences in ranking reflect user quality preference and proximity."
            )
        else:
            hotel_comp = "Hotels are ranked balancing deterministic safety scores with guest reviews and verified stars."

        return NarratorOutput(
            headline=headline[:100],
            summary=summary[:600],
            key_drivers=key_drivers,
            caveats=caveats[:4],
            hotel_comparison=hotel_comp,
        )

    def _build_canned_narrative(self, report: dict[str, Any]) -> NarratorOutput:
        """Canned, verified narrative for DEMO_MODE that passes all deterministic checks."""
        score = report.get("area_score", {}).get("safety_score", 76)
        band = report.get("area_score", {}).get("band", {}).get("label", "Moderate Risk")
        contribs = report.get("contributions", [])
        ref1 = contribs[0].get("evidence_ref") if contribs else "gdacs_fl_1001"
        ref2 = contribs[1].get("evidence_ref") if len(contribs) > 1 else "crime:Kullu"

        return NarratorOutput(
            headline="Moderate Risk in Manali Area Driven by Upstream River Advisory",
            summary=(
                f"Manali displays an aggregated safety score of {score}/100 ({band}). "
                "Primary influence stems from an upstream Beas river flow advisory and regional terrain factors. "
                "Standard travel precautions are advised along riverbanks and mountain roads."
            ),
            key_drivers=[
                NarratorKeyDriver(
                    factor="Beas River Flow Advisory",
                    plain_language="GDACS orange alert indicates elevated river discharge along upper Beas.",
                    evidence_ref=ref1,
                ),
                NarratorKeyDriver(
                    factor="District Baseline Indicators",
                    plain_language="District crime and civil baselines remain stable within moderate percentiles.",
                    evidence_ref=ref2,
                ),
            ],
            caveats=[
                "High-resolution ISRO landslide raster layers are subject to periodic update cycles.",
                "Demonstration mode active using verified recorded fixture data.",
            ],
            hotel_comparison=(
                "Hotels further uphill from the river corridor exhibit marginally lower water exposure. "
                "Properties are ranked prioritizing safety with guest ratings."
            ),
        )
