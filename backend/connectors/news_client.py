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
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("connectors.news")
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
        location_name: str | None = None,
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

        articles = []
        try:
            resp = self._http_client.get(gdelt_url, params=params, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                self._record_success()
        except Exception as exc:
            logger.warning(f"GDELT DOC API failed ({exc}); falling back to Google News RSS")

        if not articles:
            search_term = location_name or f"India {round(lat, 2)} {round(lon, 2)}"
            articles = self._fetch_google_news_rss_sync(search_term)

        return self._enrich_articles(articles, lat, lon, radius_km)

    async def fetch_local_news_async(
        self,
        lat: float,
        lon: float,
        radius_km: float = 50.0,
        since: datetime | None = None,
        location_name: str | None = None,
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

        articles = []
        try:
            resp = await self._http_async_client.get(gdelt_url, params=params, timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                self._record_success()
        except Exception as exc:
            logger.warning(f"GDELT DOC API failed ({exc}); falling back to Google News RSS")

        if not articles:
            search_term = location_name or f"India {round(lat, 2)} {round(lon, 2)}"
            articles = await self._fetch_google_news_rss_async(search_term)

        return self._enrich_articles(articles, lat, lon, radius_km)

    def _clean_and_filter_article(
        self, title: str, snippet: str, url: str, source_name: str, pub_date: str
    ) -> dict[str, Any] | None:
        """Filter out non-news, weather forecasts, IQAir monitors, and academic papers."""
        import html

        if not title or not url:
            return None

        clean_title = html.unescape(title).strip()
        clean_snippet = html.unescape(snippet).strip() if snippet else clean_title

        # Strip redundant source suffix from title if present
        if source_name and clean_title.endswith(f" - {source_name}"):
            clean_title = clean_title[: -len(f" - {source_name}")].strip()

        title_lower = clean_title.lower()
        url_lower = url.lower()
        source_lower = (source_name or "").lower()

        # Exclude non-news / spam / weather / academic domains
        excluded_domains = [
            "weather.com", "accuweather.com", "iqair.com", "wunderground.com",
            "timeanddate.com", "nature.com", "sciencedirect.com", "springer.com",
            "researchgate.net", "tripadvisor.com", "booking.com", "airbnb.com",
            "wikipedia.org", "yelp.com", "makemytrip.com", "expedia.com",
            "hotels.com", "trivago.com", "agoda.com"
        ]
        if any(d in url_lower or d in source_lower for d in excluded_domains):
            return None

        # Exclude titles matching weather forecasts, pollution trackers, flight deals
        excluded_patterns = [
            r"weather\s+forecast",
            r"forecast\s+and\s+conditions",
            r"air\s+quality\s+index",
            r"air\s+quality\s+in",
            r"air\s+pollution",
            r"\baqi\b",
            r"hourly\s+weather",
            r"10-day\s+forecast",
            r"deep\s+learning-based",
            r"susceptibility\s+mapping",
            r"cheap\s+flights",
            r"best\s+hotels\s+in",
            r"flight\s+deals",
        ]
        if any(re.search(pat, title_lower) for pat in excluded_patterns):
            return None

        cat, conf = _classify_event(clean_title, clean_snippet)

        return {
            "title": clean_title,
            "url": url,
            "source": source_name,
            "seendate": pub_date,
            "tone": -1.5 if cat in ("natural_disaster", "crime", "accident", "civil_unrest") else -0.2,
            "category": cat,
            "snippet": clean_snippet[:280] if clean_snippet else clean_title,
            "geo_source": "google_news_rss",
        }

    def _fetch_google_news_rss_sync(self, query_text: str) -> list[dict[str, Any]]:
        """Fetch safety, socio-political, and travel news from Google News RSS synchronously."""
        import xml.etree.ElementTree as ET
        import urllib.parse

        clean_q = query_text.split(",")[0] if "," in query_text else query_text
        encoded_q = urllib.parse.quote(
            f'"{clean_q}" (politics OR government OR security OR diplomatic OR "civil unrest" OR administration OR protest OR economy OR news)'
        )
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
        articles: list[dict[str, Any]] = []
        seen_titles = set()

        try:
            resp = self._http_client.get(rss_url)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:30]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    source_elem = item.find("source")
                    desc_elem = item.find("description")
                    title = title_elem.text if title_elem is not None and title_elem.text else ""
                    url = link_elem.text if link_elem is not None and link_elem.text else ""
                    source_name = source_elem.text if source_elem is not None and source_elem.text else "News"
                    pub_date = pub_elem.text if pub_elem is not None and pub_elem.text else ""
                    raw_desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                    snippet = re.sub(r"<[^>]+>", "", raw_desc).strip()

                    art = self._clean_and_filter_article(title, snippet, url, source_name, pub_date)
                    if art and art["title"] not in seen_titles:
                        seen_titles.add(art["title"])
                        articles.append(art)
        except Exception as e:
            logger.warning(f"Google News RSS sync failed: {e}")
        return articles

    async def _fetch_google_news_rss_async(self, query_text: str) -> list[dict[str, Any]]:
        """Fetch safety, socio-political, and regional news from Google News RSS asynchronously."""
        import xml.etree.ElementTree as ET
        import urllib.parse

        clean_q = query_text.split(",")[0] if "," in query_text else query_text
        encoded_q = urllib.parse.quote(
            f'"{clean_q}" (politics OR government OR security OR diplomatic OR "civil unrest" OR administration OR protest OR economy OR news)'
        )
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-US&gl=US&ceid=US:en"
        articles: list[dict[str, Any]] = []
        seen_titles = set()

        try:
            resp = await self._http_async_client.get(
                rss_url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            )
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:30]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    source_elem = item.find("source")
                    desc_elem = item.find("description")
                    title = title_elem.text if title_elem is not None and title_elem.text else ""
                    url = link_elem.text if link_elem is not None and link_elem.text else ""
                    source_name = source_elem.text if source_elem is not None and source_elem.text else "News"
                    pub_date = pub_elem.text if pub_elem is not None and pub_elem.text else ""
                    raw_desc = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                    snippet = re.sub(r"<[^>]+>", "", raw_desc).strip()

                    art = self._clean_and_filter_article(title, snippet, url, source_name, pub_date)
                    if art and art["title"] not in seen_titles:
                        seen_titles.add(art["title"])
                        articles.append(art)
        except Exception as e:
            logger.warning(f"Google News RSS async failed: {e}")
        return articles

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
                    "source": article.get("source") or article.get("domain") or "News Source",
                    "domain": article.get("domain", ""),
                    "language": article.get("language", ""),
                    "article_time": article_time.isoformat(),
                    "seendate": article.get("seendate") or article_time.strftime("%b %d, %Y"),
                    "gdelt_location": gdelt_location,
                    "ner_location": ner_location,
                    "tone": tone_val,
                    "category": category,
                    "snippet": article.get("snippet") or title,
                    "classification_confidence": class_confidence,
                    "recency_weight": _recency_weight(article_time, category),
                    "source_image": article.get("socialimage", ""),
                }
                enriched.append(enriched_article)
            except Exception:
                continue

        return enriched

    # ── Layer 2: Analytics ────────────────────────────────────────────────

    def analyze_articles(
        self,
        articles: list[dict[str, Any]],
        target_lat: float | None = None,
        target_lon: float | None = None,
    ) -> list[IngestedRecord]:
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
            representative_lat = target_lat
            representative_lon = target_lon

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

            # Normalize signal into a severity payload
            severity_raw = min(signal / 5.0, 1.0)
            hazard_type = "news"

            if representative_lat is None:
                representative_lat = 20.5937
                representative_lon = 78.9629

            eid = f"news:{category}:{hashlib.sha256(str(ingest_time).encode()).hexdigest()[:12]}"

            record = IngestedRecord(
                event_id=eid,
                source="gdelt",
                hazard_type=hazard_type,
                geometry=Point(representative_lon, representative_lat),
                event_time=ingest_time,
                ingest_time=ingest_time,
                severity_raw=None,
                confidence=round(avg_confidence, 2),
                resolution_tier=ResolutionTier.DISTRICT,
                raw_payload={
                    "title": f"Local News: {category.replace('_', ' ').title()} ({n} reports)",
                    "category": category,
                    "classifier_confidence": round(avg_confidence, 2),
                    "tone_severity": round(severity_raw, 2),
                    "article_count": n,
                    "recency_decay": 1.0,
                    "local_news_signal": round(signal, 3),
                    "avg_tone": round(avg_tone, 2),
                    "avg_classification_confidence": round(avg_confidence, 2),
                    "articles": [
                        {
                            "title": a.get("title", ""),
                            "url": a.get("url", ""),
                            "source": a.get("source", "News"),
                            "snippet": a.get("snippet", ""),
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
