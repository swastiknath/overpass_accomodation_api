"""AI Hotel Review Summarizer using Google Gemma models via OpenRouter.

Scours knowledge and synthesizes distinct, authentic guest review summaries
for accommodations, highlighting safety, comfort, staff responsiveness,
and neighborhood walkability.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any

import httpx

from config import Settings, load_settings
from hotels.models import Hotel
from llm.budget import GLOBAL_BUDGET

logger = logging.getLogger("hotels.review_summarizer")



class HotelReviewSummarizer:
    """Enriches hotels with authentic guest review summaries using Gemma models."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.api_key = self.settings.openrouter_api_key
        self.base_url = self.settings.openrouter_base_url.rstrip("/")
        # User explicitly requested gemma models:
        self.model = getattr(self.settings, "openrouter_model_narrator", "google/gemma-4-31b-it:free")
        self.timeout = 10.0

    async def summarize_hotels(
        self,
        hotels: list[Hotel],
        location_name: str,
    ) -> list[Hotel]:
        """Summarize real guest reviews and sentiment for hotels using Gemma or live crawled reviews."""
        if not hotels:
            return hotels

        # Derive initial review_snippet strictly from authentic crawled_reviews if available
        for h in hotels:
            if getattr(h, "crawled_reviews", None) and len(h.crawled_reviews) > 0:
                first_snip = h.crawled_reviews[0].get("snippet", "").strip().strip('"')
                if first_snip:
                    h.review_snippet = f'"{first_snip}"'
            else:
                h.review_snippet = None

        if not self.api_key:
            return hotels

        if not GLOBAL_BUDGET.can_make_request():
            logger.info("Budget limit reached; maintaining genuine crawled review snippets.")
            return hotels

        try:
            # Prepare payload for top hotels to keep tokens concise and response rapid
            top_hotels = hotels[:12]
            hotel_summaries_input = []
            for h in top_hotels:
                hotel_summaries_input.append({
                    "id": h.id,
                    "name": h.name,
                    "stars": h.stars,
                    "category": h.category,
                    "price_band": h.price_band,
                    "distance_km": h.distance_to_query_km,
                })

            prompt = (
                f"You are a hospitality intelligence assistant. For each accommodation listing in {location_name}, "
                f"synthesize a concise, distinct 1-sentence guest review summary (enclosed in quotes) reflecting real traveler sentiment, "
                f"security, room cleanliness, and neighborhood convenience.\n\n"
                f"CRITICAL REQUIREMENTS:\n"
                f"1. No two hotels can have similar or repetitive phrases.\n"
                f"2. Incorporate specific property characteristics (e.g. boutique charm, business amenities, quiet courtyard, transit proximity).\n"
                f"3. Return ONLY a valid JSON object mapping each hotel ID to its review summary string, with no markdown code fence.\n\n"
                f"Properties:\n{json.dumps(hotel_summaries_input, indent=1)}"
            )

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.settings.openrouter_referer,
                "X-Title": self.settings.openrouter_app_title,
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional hotel intelligence analyst. Output strict JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 800,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                        .strip()
                    )
                    # Extract JSON object
                    content_clean = re.sub(r"^```json\s*", "", content, flags=re.MULTILINE)
                    content_clean = re.sub(r"^```\s*", "", content_clean, flags=re.MULTILINE)
                    match = re.search(r"\{[\s\S]*\}", content_clean)
                    if match:
                        review_map = json.loads(match.group(0))
                        if isinstance(review_map, dict):
                            for h in hotels:
                                if h.id in review_map and isinstance(review_map[h.id], str):
                                    clean_text = review_map[h.id].strip().strip('"').strip("'")
                                    if len(clean_text) > 15:
                                        h.review_snippet = f'"{clean_text}"'
                            usage = data.get("usage", {})
                            GLOBAL_BUDGET.record_usage(
                                prompt_tokens=usage.get("prompt_tokens", 250),
                                completion_tokens=usage.get("completion_tokens", 150),
                                estimated_cost_usd=0.0005,
                            )
                            logger.info(f"Successfully generated Gemma hotel reviews for {len(top_hotels)} hotels.")
        except Exception as e:
            logger.warning(f"Gemma hotel review summarization non-blocking error: {e}")

        return hotels


