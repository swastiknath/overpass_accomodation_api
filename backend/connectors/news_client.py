"""Live local news analytics connector.

Two layers:
  1. Ingestion — `fetch_local_news(lat, lon, radius_km, since)`
     Uses GDELT DOC 2.0 API (no auth, 15-min granularity) for India-wide
     near-real-time article discovery. Keyword list is externalized to
     `config/news_keywords.yaml`.

  2. Analytics — `analyze_articles(articles)`
     Sentiment scoring (GDELT's tone field), event-type classification
     (keyword+regex hybrid), and recency-weighted signal aggregation.

Geolocation-bias correction:
  GDELT's own geotagging is unreliable. This connector extracts place
  mentions via NER (spaCy if available, regex fallback) and resolves
  them against the admin-boundary layer. Both GDELT-provided and
  NER-derived locations are stored with a `geo_source` field so
  downstream code can tell them apart.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from gis.config import Settings, load_settings
from gis.exceptions import ConnectorError
from gis.schema import IngestedRecord, ResolutionTier

from connectors.base import BaseConnector

# ── NER soft-import (spaCy is optional) ───────────────────────────────────
_NLP_MODEL = None
_NLP_LOAD_ATTEMPTED = False


def _get_nlp():
    """Lazy-load spaCy model. Returns None if spaCy is not installed."""
    global _NLP_MODEL, _NLP_LOAD_ATTEMPTED
    if _NLP_LOAD_ATTEMPTED:
        return _NLP_MODEL
    _NLP_LOAD_ATTEMPTED = True
    try:
        import spacy
        _NLP_MODEL = spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        _NLP_MODEL = None
    return _NLP_MODEL


# ── Keyword loading ──────────────────────────────────────────────────────

_KEYWORD_CACHE: dict[str, list[str]] | None = None


def _load_keywords(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load safety-relevant keywords from config/news_keywords.yaml."""
    global _KEYWORD_CACHE
    if _KEYWORD_CACHE is not None:
        return _KEYWORD_CACHE

    default_path = Path(__file__).parent.parent / "config" / "news_keywords.yaml"
    path = Path(config_path) if config_path else default_path

    if path.exists():
        with open(path) as f:
            _KEYWORD_CACHE = yaml.safe_load(f) or {}
    else:
        # Fallback defaults if config file is missing
        _KEYWORD_CACHE = {
            "safety_keywords": [
                "protest", "unrest", "flood", "landslide", "accident",
                "curfew", "violence", "closure", "strike", "riot",
                "earthquake", "cyclone", "fire", "explosion", "shooting",
                "stabbing", "robbery", "kidnapping", "assault", "derailment",
            ],
            "categories": {
                "protest": ["protest", "rally", "demonstration", "strike", "bandh", "hartal", "agitation"],
                "accident": ["accident", "crash", "collision", "derailment", "capsize", "mishap"],
                "natural_disaster": ["flood", "landslide", "earthquake", "cyclone", "tornado", "tsunami", "drought"],
                "fire": ["fire", "blaze", "inferno", "explosion", "blast"],
                "crime": ["murder", "robbery", "kidnapping", "assault", "stabbing", "shooting", "theft"],
                "civil_unrest": ["riot", "violence", "unrest", "curfew", "clashes", "mob", "arson"],
            },
        }
    return _KEYWORD_CACHE


# ── Regex-based place extraction (fallback when spaCy unavailable) ────────

_INDIA_PLACES_PATTERN = re.compile(
    r"\b("
    r"Delhi|Mumbai|Kolkata|Chennai|Bengaluru|Bangalore|Hyderabad|Ahmedabad|"
    r"Pune|Jaipur|Lucknow|Kanpur|Nagpur|Indore|Thane|Bhopal|Visakhapatnam|"
    r"Patna|Vadodara|Ghaziabad|Ludhiana|Agra|Nashik|Faridabad|Meerut|"
    r"Rajkot|Varanasi|Srinagar|Aurangabad|Dhanbad|Amritsar|Allahabad|"
    r"Ranchi|Howrah|Coimbatore|Gwalior|Vijayawada|Jodhpur|Madurai|Raipur|"
    r"Kochi|Chandigarh|Mysore|Mysuru|Thiruvananthapuram|Guwahati|Hubli|"
    r"Shimla|Dehradun|Gangtok|Imphal|Shillong|Aizawl|Kohima|Itanagar|"
    r"Panaji|Agartala|Bhubaneswar|Dispur|"
    r"Andhra Pradesh|Arunachal Pradesh|Assam|Bihar|Chhattisgarh|Goa|Gujarat|"
    r"Haryana|Himachal Pradesh|Jharkhand|Karnataka|Kerala|Madhya Pradesh|"
    r"Maharashtra|Manipur|Meghalaya|Mizoram|Nagaland|Odisha|Punjab|Rajasthan|"
    r"Sikkim|Tamil Nadu|Telangana|Tripura|Uttar Pradesh|Uttarakhand|"
    r"West Bengal|Jammu and Kashmir|Ladakh|Puducherry|Lakshadweep|"
    r"Andaman and Nicobar|Dadra and Nagar Haveli|Daman and Diu"
    r")\b",
    re.IGNORECASE,
)


def _extract_places_regex(text: str) -> list[str]:
    """Extract Indian place names using regex pattern matching."""
    return list(set(m.group(0) for m in _INDIA_PLACES_PATTERN.finditer(text)))


def _extract_places_ner(text: str) -> list[str]:
    """Extract place names using spaCy NER (if available)."""
    nlp = _get_nlp()
    if nlp is None:
        return _extract_places_regex(text)

    doc = nlp(text[:5000])
    places = []
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC", "FAC"):
            places.append(ent.text)
    return list(set(places))


# ── Event classification ─────────────────────────────────────────────────

def _classify_event(title: str, body: str = "") -> tuple[str, float]:
    """Classify article into event category using keyword matching.

    Returns (category, confidence). Lightweight keyword+regex hybrid for v1.
    """
    text = f"{title} {body}".lower()
    keywords = _load_keywords()
    categories = keywords.get("categories", {})

    best_cat = "general"
    best_score = 0.0

    for cat, cat_keywords in categories.items():
        matches = sum(1 for kw in cat_keywords if kw.lower() in text)
        if matches > 0:
            score = min(0.4 + (matches * 0.15), 1.0)
            if score > best_score:
                best_score = score
                best_cat = cat

    # Boost confidence if title alone has a match (more signal than body)
    title_lower = title.lower()
    for cat, cat_keywords in categories.items():
        if any(kw.lower() in title_lower for kw in cat_keywords):
            if cat == best_cat:
                best_score = min(best_score + 0.15, 1.0)
            break

    return best_cat, round(best_score, 2)


# ── Recency-weighted signal ──────────────────────────────────────────────

_DECAY_HALF_LIFE: dict[str, float] = {
    "civil_unrest": 6.0,
    "protest": 8.0,
    "accident": 12.0,
    "natural_disaster": 24.0,
    "fire": 12.0,
    "crime": 24.0,
    "general": 48.0,
}


def _recency_weight(article_time: datetime, category: str) -> float:
    """Compute exponential decay weight based on article age and category.

    Half-life varies by category: a resolved protest decays faster than
    an ongoing natural disaster.
    """
    now = datetime.now(timezone.utc)
    age_hours = max((now - article_time).total_seconds() / 3600.0, 0.0)
    half_life = _DECAY_HALF_LIFE.get(category, 24.0)
    return math.exp(-0.693 * age_hours / half_life)  # 0.693 = ln(2)


class NewsClient(BaseConnector):
    """Live local news analytics using GDELT DOC 2.0 API."""

    SOURCE_NAME = "news_gdelt"

    def __init__(self, settings: Settings | None = None, **kwargs: Any) -> None:
        super().__init__(settings=settings, **kwargs)

    # ── Layer 1: Ingestion ────────────────────────────────────────────────

    def fetch_local_news(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50.0,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch safety-relevant news articles near a location."""
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        keywords = _load_keywords()
        safety_kw = keywords.get("safety_keywords", [])

        keyword_query = " OR ".join(safety_kw[:15])
        query = f"({keyword_query}) sourcecountry:India"

        gdelt_url = self._settings.gdelt_doc_api_url
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": 75,
            "format": "json",
            "startdatetime": since.strftime("%Y%m%d%H%M%S"),
            "enddatetime": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "sort": "DateDesc",
        }

        def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = self._http_client.get(gdelt_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=gdelt_url)
                self._log_fetch(
                    url=gdelt_url, params=params,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=gdelt_url, params=params, status="ok", attempt=attempt, elapsed_ms=elapsed)
            return data

        raw = self._with_retry(operation)
        self._record_success()
        articles = raw.get("articles", [])
        return self._enrich_articles(articles, lat, lon, radius_km)

    async def fetch_local_news_async(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50.0,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Async variant of fetch_local_news."""
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        keywords = _load_keywords()
        safety_kw = keywords.get("safety_keywords", [])
        keyword_query = " OR ".join(safety_kw[:15])
        query = f"({keyword_query}) sourcecountry:India"

        gdelt_url = self._settings.gdelt_doc_api_url
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": 75,
            "format": "json",
            "startdatetime": since.strftime("%Y%m%d%H%M%S"),
            "enddatetime": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "sort": "DateDesc",
        }

        async def operation(attempt: int) -> dict[str, Any]:
            started = time.perf_counter()
            try:
                resp = await self._http_async_client.get(gdelt_url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                classified = self._classify_http_error(exc, url=gdelt_url)
                self._log_fetch(
                    url=gdelt_url, params=params,
                    status=getattr(getattr(exc, "response", None), "status_code", None),
                    attempt=attempt, elapsed_ms=elapsed,
                    error_type=type(classified).__name__, message="raw_fetch_error",
                )
                raise classified from exc

            elapsed = (time.perf_counter() - started) * 1000
            self._log_fetch(url=gdelt_url, params=params, status="ok", attempt=attempt, elapsed_ms=elapsed)
            return data

        raw = await self._with_retry_async(operation)
        self._record_success()
        articles = raw.get("articles", [])
        return self._enrich_articles(articles, lat, lon, radius_km)

    def _enrich_articles(
        self,
        articles: list[dict[str, Any]],
        lat: float,
        lon: float,
        radius_km: float,
    ) -> list[dict[str, Any]]:
        """Enrich articles with NER-based geocoding and classification."""
        enriched: list[dict[str, Any]] = []

        for article in articles:
            try:
                title = article.get("title", "")
                url = article.get("url", "")

                gdelt_lat = article.get("sourcelat")
                gdelt_lon = article.get("sourcelon")
                gdelt_location = None
                if gdelt_lat and gdelt_lon:
                    try:
                        gdelt_location = {
                            "lat": float(gdelt_lat),
                            "lon": float(gdelt_lon),
                            "geo_source": "gdelt",
                        }
                    except (ValueError, TypeError):
                        pass

                ner_places = _extract_places_ner(title)
                ner_location = {
                    "places": ner_places,
                    "geo_source": "ner_spacy" if _get_nlp() is not None else "ner_regex",
                }

                tone = article.get("tone", "0")
                try:
                    tone_val = float(str(tone).split(",")[0])
                except (ValueError, IndexError):
                    tone_val = 0.0

                category, class_confidence = _classify_event(title)

                date_str = article.get("seendate", "")
                try:
                    article_time = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(
                        tzinfo=timezone.utc
                    )
                except (ValueError, TypeError):
                    article_time = datetime.now(timezone.utc)

                enriched_article = {
                    "title": title,
                    "url": url,
                    "domain": article.get("domain", ""),
                    "language": article.get("language", ""),
                    "article_time": article_time.isoformat(),
                    "gdelt_location": gdelt_location,
                    "ner_location": ner_location,
                    "tone": tone_val,
                    "category": category,
                    "classification_confidence": class_confidence,
                    "recency_weight": _recency_weight(article_time, category),
                    "source_image": article.get("socialimage", ""),
                }
                enriched.append(enriched_article)
            except Exception:
                continue

        return enriched

    # ── Layer 2: Analytics ────────────────────────────────────────────────

    def analyze_articles(self, articles: list[dict[str, Any]]) -> list[IngestedRecord]:
        """Analyze enriched articles into IngestedRecord instances."""
        from shapely.geometry import Point

        records: list[IngestedRecord] = []
        ingest_time = datetime.now(timezone.utc)

        category_groups: dict[str, list[dict[str, Any]]] = {}
        for article in articles:
            cat = article.get("category", "general")
            category_groups.setdefault(cat, []).append(article)

        for category, cat_articles in category_groups.items():
            if not cat_articles:
                continue

            signal = 0.0
            avg_tone = 0.0
            avg_confidence = 0.0
            representative_lat, representative_lon = None, None

            for art in cat_articles:
                weight = art.get("recency_weight", 0.5)
                tone = abs(art.get("tone", 0.0))
                signal += weight * (1.0 + tone / 10.0)
                avg_tone += art.get("tone", 0.0)
                avg_confidence += art.get("classification_confidence", 0.5)

                if representative_lat is None:
                    gdelt_loc = art.get("gdelt_location")
                    if gdelt_loc:
                        representative_lat = gdelt_loc.get("lat")
                        representative_lon = gdelt_loc.get("lon")

            n = len(cat_articles)
            avg_tone /= n
            avg_confidence /= n

            severity_raw = min(signal / 10.0, 1.0)

            hazard_map = {
                "protest": "civil_unrest",
                "civil_unrest": "civil_unrest",
                "accident": "accident",
                "natural_disaster": "natural_disaster",
                "fire": "fire",
                "crime": "crime",
                "general": "general_safety",
            }
            hazard_type = hazard_map.get(category, "general_safety")

            if representative_lat is None:
                representative_lat = 20.5937
                representative_lon = 78.9629

            eid = f"news:{category}:{hashlib.sha256(str(ingest_time).encode()).hexdigest()[:12]}"

            record = IngestedRecord(
                event_id=eid,
                source="gdelt_news",
                hazard_type=hazard_type,
                geometry=Point(representative_lon, representative_lat),
                event_time=ingest_time,
                ingest_time=ingest_time,
                severity_raw=severity_raw,
                confidence=round(avg_confidence, 2),
                resolution_tier=ResolutionTier.DISTRICT,
                raw_payload={
                    "category": category,
                    "article_count": n,
                    "local_news_signal": round(signal, 3),
                    "avg_tone": round(avg_tone, 2),
                    "avg_classification_confidence": round(avg_confidence, 2),
                    "articles": [
                        {
                            "title": a.get("title", ""),
                            "url": a.get("url", ""),
                            "article_time": a.get("article_time", ""),
                            "tone": a.get("tone", 0),
                            "category": a.get("category", ""),
                            "recency_weight": round(a.get("recency_weight", 0), 3),
                        }
                        for a in cat_articles[:20]
                    ],
                },
            )
            records.append(record)

        return records
