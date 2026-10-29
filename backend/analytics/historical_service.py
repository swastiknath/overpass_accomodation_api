"""Historical Incident & Disaster Analytics Service.

Builds 2021–2026 multi-hazard statistics strictly from real recorded data:

* Earthquakes  – USGS FDSN event catalogue (2021-01-01 → today, ≤ 300 km, M ≥ 3.5)
                 plus NCS (MoES) recent events for Indian cities.
* River floods – Copernicus GloFAS daily discharge archive (high-flow days ≥ P90 of
                 2021–2026, yearly peaks) for rivers situated within the city, plus
                 live CWC FloodWatch India / SACHET CAP bulletins.
* Cyclones     – Open-Meteo ERA5 archive cyclonic storm days & notable storm episodes,
                 plus live GDACS tropical cyclones.
* Conflict     – ACLED events (2021 → today) for the search bounding box when ACLED
                 credentials are configured; live news-wire protest reports.

No template, synthetic or fallback incident data is ever produced. When a source
returns nothing, the corresponding counts are zero and the gap is reported in
``data_availability``.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("analytics.historical_service")

USGS_FDSN_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
HISTORY_START = "2021-01-01"

_USGS_HISTORY_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_USGS_CACHE_TTL = 3600.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def fetch_usgs_earthquake_history_async(
    lat: float, lon: float, radius_km: float = 300.0, min_magnitude: float = 3.5
) -> list[dict[str, Any]]:
    """Fetch real 2021 → today earthquakes around (lat, lon) from the USGS FDSN catalogue."""
    import time

    key = f"{round(lat, 2)}:{round(lon, 2)}:{radius_km}:{min_magnitude}"
    cached = _USGS_HISTORY_CACHE.get(key)
    if cached and time.time() - cached[0] < _USGS_CACHE_TTL:
        return cached[1]

    params = {
        "format": "geojson",
        "starttime": HISTORY_START,
        "endtime": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "maxradiuskm": radius_km,
        "minmagnitude": min_magnitude,
        "orderby": "time",
        "limit": 2000,
    }
    quakes: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
        resp = await client.get(USGS_FDSN_URL, params=params)
        resp.raise_for_status()
        for feat in resp.json().get("features", []) or []:
            props = feat.get("properties") or {}
            coords = (feat.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2 or props.get("mag") is None or props.get("time") is None:
                continue
            q_lon, q_lat = float(coords[0]), float(coords[1])
            quakes.append({
                "id": f"usgs-{feat.get('id')}",
                "date": datetime.fromtimestamp(props["time"] / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d"),
                "magnitude": round(float(props["mag"]), 1),
                "depth_km": round(float(coords[2]), 1) if len(coords) > 2 and coords[2] is not None else None,
                "place": props.get("place") or "",
                "lat": q_lat,
                "lon": q_lon,
                "distance_km": round(_haversine_km(lat, lon, q_lat, q_lon), 1),
                "url": props.get("url"),
                "felt": props.get("felt"),
                "alert": props.get("alert"),
            })
    _USGS_HISTORY_CACHE[key] = (time.time(), quakes)
    return quakes


def _to_iso_date(raw: Any) -> str:
    """Normalise RFC-822 / ISO date strings to YYYY-MM-DD."""
    if not raw:
        return ""
    txt = str(raw).strip()
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(txt).strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return txt[:10]


def _years_range() -> list[str]:
    now_year = datetime.now(timezone.utc).year
    return [str(y) for y in range(2021, now_year + 1)]


def _pct(part: int, total: int) -> int:
    return int(round(100.0 * part / total)) if total > 0 else 0


def _rec_attr(rec: Any, name: str, default: Any = None) -> Any:
    if isinstance(rec, dict):
        return rec.get(name, default)
    return getattr(rec, name, default)


def compute_historical_stats(
    location_name: str,
    lat: float,
    lon: float,
    country: str | None = None,
    is_in_india: bool = True,
    active_records: list[Any] | None = None,
    news_articles: list[Any] | None = None,
    river_flood_telemetry: dict[str, Any] | None = None,
    cyclone_telemetry: dict[str, Any] | None = None,
    earthquake_history: list[dict[str, Any]] | None = None,
    conflict_history: list[Any] | None = None,
) -> dict[str, Any]:
    """Compute 2021–2026 historical multi-hazard statistics strictly from real recorded data."""
    base_city = (location_name or "").split(",")[0].strip() or location_name
    years = _years_range()
    river = river_flood_telemetry or {}
    cyclone = cyclone_telemetry or {}
    quakes = list(earthquake_history or [])
    conflicts_raw = list(conflict_history or [])
    data_availability: dict[str, str] = {}

    # ── Earthquakes (USGS FDSN 2021 → today, merged with NCS for India) ──────
    seen_q: set[str] = {q["id"] for q in quakes}
    for nq in river.get("ncs_recent_earthquakes") or []:
        try:
            q_date = str(nq.get("event_time", ""))[:10]
            nid = f"ncs-{nq.get('id')}"
            if nid in seen_q or not q_date:
                continue
            # skip if USGS already has an event of similar magnitude on that date
            if any(q["date"] == q_date and abs(q["magnitude"] - float(nq.get("magnitude", 0))) < 0.4 for q in quakes):
                continue
            quakes.append({
                "id": nid,
                "date": q_date,
                "magnitude": round(float(nq.get("magnitude", 0)), 1),
                "depth_km": nq.get("depth_km"),
                "place": nq.get("place", ""),
                "distance_km": nq.get("distance_km"),
                "url": nq.get("url"),
                "authority": nq.get("authority", "National Centre for Seismology (NCS, MoES)"),
            })
        except Exception:
            continue
    data_availability["earthquakes"] = (
        f"{len(quakes)} recorded events (USGS FDSN{' + NCS' if is_in_india else ''}, ≤300 km, M≥3.5)"
        if earthquake_history is not None
        else "USGS historical catalogue unavailable for this request"
    )
    felt_quakes = [q for q in quakes if q["magnitude"] >= 4.5 or (q.get("distance_km") or 999) <= 100]

    # ── River floods (GloFAS archive high-flow episodes, city rivers only) ──
    hist_flow = river.get("historical_flow_stats") or {}
    yearly_flow = {str(y["year"]): y for y in hist_flow.get("yearly_flow_trends") or []}
    has_city_river = bool(river.get("has_river_in_city"))
    p90_q = hist_flow.get("p90_watch_discharge_m3s")
    p98_q = hist_flow.get("p98_danger_discharge_m3s")
    if has_city_river and yearly_flow:
        data_availability["river_floods"] = (
            f"GloFAS 2021–2026 discharge archive for {river.get('river_name')} "
            f"({hist_flow.get('total_observed_days', 0)} days)"
        )
    elif has_city_river:
        data_availability["river_floods"] = "River within city found but GloFAS archive unavailable"
    else:
        data_availability["river_floods"] = "No river situated within city limits"

    # ── Cyclones (ERA5 archive) ──────────────────────────────────────────────
    cyc_hist = cyclone.get("historical_archive") or {}
    yearly_cyc = {str(y["year"]): y for y in cyc_hist.get("yearly_trends") or []}
    data_availability["cyclones"] = (
        f"Open-Meteo ERA5 archive ({cyc_hist.get('total_archived_days', 0)} days)"
        if yearly_cyc
        else "Cyclone archive unavailable for this request"
    )

    # ── Conflict (ACLED 2021 → today) ───────────────────────────────────────
    conflicts: list[dict[str, Any]] = []
    for rec in conflicts_raw:
        payload = _rec_attr(rec, "raw_payload", {}) or {}
        ev_time = _rec_attr(rec, "event_time")
        date_str = ev_time.strftime("%Y-%m-%d") if hasattr(ev_time, "strftime") else str(payload.get("event_date", ""))[:10]
        if not date_str:
            continue
        geom = _rec_attr(rec, "geometry")
        dist = None
        try:
            dist = round(_haversine_km(lat, lon, float(geom.y), float(geom.x)), 1)
        except Exception:
            pass
        conflicts.append({
            "id": str(_rec_attr(rec, "event_id", "")),
            "date": date_str,
            "event_type": str(payload.get("event_type") or "Unknown"),
            "sub_event_type": payload.get("sub_event_type"),
            "fatalities": int(payload.get("fatalities") or 0),
            "notes": payload.get("notes") or payload.get("title") or "",
            "location": payload.get("location") or base_city,
            "distance_km": dist,
        })
    data_availability["conflict"] = (
        f"{len(conflicts)} ACLED events in search area since {HISTORY_START}"
        if conflict_history is not None
        else "ACLED historical data unavailable (credentials or API access missing)"
    )

    # ── Yearly trends (real counts per year) ─────────────────────────────────
    yearly_trends: list[dict[str, Any]] = []
    for yr in years:
        yr_conf = [c for c in conflicts if c["date"].startswith(yr)]
        yr_quakes = [q for q in felt_quakes if q["date"].startswith(yr)]
        flow_y = yearly_flow.get(yr) or {}
        cyc_y = yearly_cyc.get(yr) or {}
        flood_days = int(flow_y.get("high_flow_days") or 0)
        cyc_days = int(cyc_y.get("cyclonic_storm_days") or 0)
        # Count discrete disaster episodes: felt earthquakes + flood episode (≥1 high-flow day ≥ P98)
        # + cyclonic storm episodes recorded in ERA5 that year
        flood_episode = 1 if (p98_q and flow_y.get("peak_discharge_m3s") and flow_y["peak_discharge_m3s"] >= p98_q) else 0
        cyc_episodes = sum(1 for e in cyc_hist.get("notable_events") or [] if str(e.get("date", "")).startswith(yr)
                           and float(e.get("peak_wind_gust_kmh") or 0) >= 62.0)
        n_disasters = len(yr_quakes) + flood_episode + cyc_episodes
        max_mag = max((q["magnitude"] for q in yr_quakes), default=0.0)
        severity_index = round(min(10.0, max_mag * 0.9 + flood_days * 0.05 + cyc_days * 0.4), 1)
        yearly_trends.append({
            "year": yr,
            "conflict_events": len(yr_conf),
            "conflict_fatalities": sum(c["fatalities"] for c in yr_conf),
            "natural_disasters": n_disasters,
            "disaster_severity_index": severity_index,
            "felt_earthquakes": len(yr_quakes),
            "max_earthquake_magnitude": max_mag or None,
            "river_high_flow_days": flood_days if has_city_river else None,
            "river_peak_discharge_m3s": flow_y.get("peak_discharge_m3s") if has_city_river else None,
            "cyclonic_storm_days": cyc_days,
            "max_wind_gust_kmh": cyc_y.get("max_wind_gust_kmh"),
        })

    tot_conflicts = sum(y["conflict_events"] for y in yearly_trends)
    tot_fatalities = sum(y["conflict_fatalities"] for y in yearly_trends)
    tot_disasters = sum(y["natural_disasters"] for y in yearly_trends)

    # Trend: compare last 2 complete years vs prior years (conflict, else disasters)
    def _trend(series: list[int]) -> tuple[str, float]:
        if len(series) < 3:
            return "stable", 0.0
        recent = sum(series[-3:-1]) / 2.0
        earlier = sum(series[:-3]) / max(1, len(series[:-3]))
        if earlier == 0 and recent == 0:
            return "stable", 0.0
        pct = round(((recent - earlier) / max(1.0, earlier)) * 100.0, 1)
        if pct >= 10:
            return "elevated", pct
        if pct <= -10:
            return "declining", pct
        return "stable", pct

    if tot_conflicts > 0:
        trend_direction, trend_pct = _trend([y["conflict_events"] for y in yearly_trends])
    else:
        trend_direction, trend_pct = _trend([y["natural_disasters"] for y in yearly_trends])

    # Volatility score from real annualised rates
    n_years = max(1.0, len(years) - 1 + (datetime.now(timezone.utc).timetuple().tm_yday / 365.0))
    conf_rate = tot_conflicts / n_years
    fat_rate = tot_fatalities / n_years
    vol_score = int(min(100, round(conf_rate * 1.2 + fat_rate * 2.5 + (tot_disasters / n_years) * 3.0)))
    volatility_index = "High" if vol_score >= 70 else ("Elevated" if vol_score >= 45 else ("Moderate" if vol_score >= 20 else "Low"))

    # ── Conflict breakdown (real ACLED event types) ──────────────────────────
    by_type: dict[str, list[dict[str, Any]]] = {}
    for c in conflicts:
        by_type.setdefault(c["event_type"], []).append(c)
    sev_by_type = {
        "Battles": "severe",
        "Explosions/Remote violence": "high",
        "Violence against civilians": "high",
        "Riots": "moderate",
        "Protests": "low",
        "Strategic developments": "low",
    }
    conflict_breakdown = [
        {
            "category": etype,
            "count": len(evs),
            "percentage": _pct(len(evs), tot_conflicts),
            "metric_label": "Fatalities",
            "metric_value": sum(e["fatalities"] for e in evs),
            "severity": sev_by_type.get(etype, "moderate"),
        }
        for etype, evs in sorted(by_type.items(), key=lambda kv: len(kv[1]), reverse=True)
    ]
    primary_threat = conflict_breakdown[0]["category"] if conflict_breakdown else "No recorded conflict events"

    # ── Disaster breakdown (real counts) ─────────────────────────────────────
    quake_count = sum(y["felt_earthquakes"] for y in yearly_trends)
    flood_ep_count = sum(1 for y in yearly_trends if y.get("river_peak_discharge_m3s") and p98_q and y["river_peak_discharge_m3s"] >= p98_q)
    cyc_ep_count = sum(
        1 for e in cyc_hist.get("notable_events") or [] if float(e.get("peak_wind_gust_kmh") or 0) >= 62.0
    )
    disaster_breakdown: list[dict[str, Any]] = []
    eq_label = "USGS / NCS Earthquakes (M4.5+ or ≤100 km)" if is_in_india else "USGS Earthquakes (M4.5+ or ≤100 km)"
    max_mag_all = max((q["magnitude"] for q in quakes), default=None)
    disaster_breakdown.append({
        "category": eq_label,
        "count": quake_count,
        "percentage": _pct(quake_count, tot_disasters),
        "metric_label": "Peak Magnitude (≤300 km)",
        "metric_value": f"M{max_mag_all}" if max_mag_all is not None else "None recorded",
        "severity": "high" if (max_mag_all or 0) >= 6.0 else ("moderate" if (max_mag_all or 0) >= 5.0 else "low"),
    })
    if has_city_river and hist_flow:
        disaster_breakdown.append({
            "category": f"River High-Flow Episodes ({river.get('river_name')})",
            "count": flood_ep_count,
            "percentage": _pct(flood_ep_count, tot_disasters),
            "metric_label": "2021–2026 Peak Discharge",
            "metric_value": (
                f"{hist_flow.get('peak_discharge_m3s')} m³/s ({hist_flow.get('peak_date')})"
                if hist_flow.get("peak_discharge_m3s") is not None
                else "Unavailable"
            ),
            "severity": "high" if flood_ep_count >= 3 else ("moderate" if flood_ep_count >= 1 else "low"),
        })
    if yearly_cyc:
        disaster_breakdown.append({
            "category": "Cyclonic Storms / Severe Wind Episodes (ERA5)",
            "count": cyc_ep_count,
            "percentage": _pct(cyc_ep_count, tot_disasters),
            "metric_label": "Peak Gust (2021–2026)",
            "metric_value": (
                f"{cyc_hist.get('max_historical_wind_gust_kmh')} km/h ({cyc_hist.get('max_historical_wind_date')})"
            ),
            "severity": "severe" if float(cyc_hist.get("max_historical_wind_gust_kmh") or 0) >= 118
            else ("high" if float(cyc_hist.get("max_historical_wind_gust_kmh") or 0) >= 62 else "low"),
        })
    disaster_breakdown.sort(key=lambda d: d["count"], reverse=True)
    disaster_threat = (
        disaster_breakdown[0]["category"] if disaster_breakdown and disaster_breakdown[0]["count"] > 0
        else "No major recorded disasters"
    )

    # ── Incident log (only real recorded items) ──────────────────────────────
    incident_log: list[dict[str, Any]] = []

    # Real news-wire protest / unrest reports
    protest_kw = ("protest", "rally", "demonstration", "strike", "bandh", "dharna", "march", "sit-in", "agitation", "riot", "clash")
    seen_titles: set[str] = set()
    for idx, art in enumerate(news_articles or []):
        if not isinstance(art, dict):
            continue
        title = str(art.get("title") or "").strip()
        url = art.get("url")
        text = f"{title} {art.get('snippet') or ''}".lower()
        if not title or not url or not any(k in text for k in protest_kw):
            continue
        norm = "".join(c for c in title.lower() if c.isalnum())[:40]
        if norm in seen_titles:
            continue
        seen_titles.add(norm)
        incident_log.append({
            "id": f"news-{hashlib.sha1(str(url).encode()).hexdigest()[:10]}",
            "date": _to_iso_date(art.get("seendate")),
            "category": "protest",
            "title": title,
            "source": art.get("source") or "News",
            "location": base_city,
            "severity": "Moderate" if any(w in text for w in ("clash", "riot", "tear gas", "lathi")) else "Low",
            "description": art.get("snippet") or title,
            "url": url,
        })

    # Real ACLED events (most recent first)
    for c in sorted(conflicts, key=lambda x: x["date"], reverse=True)[:12]:
        incident_log.append({
            "id": c["id"],
            "date": c["date"],
            "category": "protest" if c["event_type"] == "Protests" else "conflict",
            "title": f"{c['event_type']}" + (f" — {c['sub_event_type']}" if c.get("sub_event_type") else ""),
            "source": "ACLED",
            "location": c["location"],
            "distance_km": c["distance_km"],
            "fatalities": c["fatalities"],
            "severity": "Severe" if c["fatalities"] >= 3 else ("Moderate" if c["fatalities"] > 0 else "Low"),
            "description": c["notes"] or c["event_type"],
        })

    # Live Indian authority bulletins (CWC / NCS / FSI / SACHET) — real dispatches
    for b in (river.get("indian_authority_bulletins") or [])[:5]:
        if not b.get("title"):
            continue
        incident_log.append({
            "id": b.get("id") or f"auth-{hashlib.sha1(b['title'].encode()).hexdigest()[:10]}",
            "date": b.get("date") or "",
            "category": "disaster",
            "title": b["title"],
            "source": b.get("authority") or b.get("publisher") or "Indian Authority",
            "location": base_city,
            "severity": b.get("severity") or "Moderate",
            "description": f"Dispatch published by {b.get('publisher') or b.get('authority') or 'official feed'}.",
            "url": b.get("url"),
        })

    # Real recorded earthquakes (strongest / closest)
    for q in sorted(felt_quakes, key=lambda x: (x["magnitude"], x["date"]), reverse=True)[:8]:
        incident_log.append({
            "id": q["id"],
            "date": q["date"],
            "category": "disaster",
            "title": f"M{q['magnitude']} Earthquake — {q.get('place') or 'regional'}",
            "source": q.get("authority") or "USGS FDSN Catalogue",
            "location": q.get("place") or base_city,
            "distance_km": q.get("distance_km"),
            "severity": "Severe" if q["magnitude"] >= 6.0 else ("Moderate" if q["magnitude"] >= 5.0 else "Low"),
            "description": (
                f"Magnitude {q['magnitude']} at depth {q.get('depth_km')} km, "
                f"{q.get('distance_km')} km from {base_city}."
            ),
            "url": q.get("url"),
        })

    # Real GloFAS yearly peak flow events for the city river
    if has_city_river and p90_q:
        for y in hist_flow.get("yearly_flow_trends") or []:
            if y.get("peak_discharge_m3s") is None or y["peak_discharge_m3s"] < p90_q:
                continue
            is_extreme = bool(p98_q and y["peak_discharge_m3s"] >= p98_q)
            incident_log.append({
                "id": f"glofas-peak-{y['year']}",
                "date": y.get("peak_date") or y["year"],
                "category": "disaster",
                "title": f"{'Extreme' if is_extreme else 'High'} river flow on {river.get('river_name')}: "
                         f"{y['peak_discharge_m3s']} m³/s",
                "source": "Copernicus GloFAS River Discharge Archive",
                "location": base_city,
                "severity": "Severe" if is_extreme else "Moderate",
                "description": (
                    f"{y['year']} peak daily discharge {y['peak_discharge_m3s']} m³/s "
                    f"({y.get('peak_discharge_cusecs', 0):,} cusecs); {y.get('high_flow_days', 0)} days above the "
                    f"2021–2026 P90 of {p90_q} m³/s."
                ),
            })

    # Real ERA5 notable cyclonic / storm episodes
    for e in (cyc_hist.get("notable_events") or [])[:6]:
        incident_log.append({
            "id": f"era5-storm-{e.get('date')}",
            "date": e.get("date") or "",
            "category": "weather",
            "title": f"{e.get('imd_category')}: {e.get('peak_wind_gust_kmh')} km/h gusts",
            "source": "Open-Meteo ERA5 Archive",
            "location": base_city,
            "severity": "Severe" if float(e.get("peak_wind_gust_kmh") or 0) >= 89 else (
                "Moderate" if float(e.get("peak_wind_gust_kmh") or 0) >= 62 else "Low"
            ),
            "description": (
                f"Recorded peak gust {e.get('peak_wind_gust_kmh')} km/h, sustained {e.get('max_sustained_wind_kmh')} km/h, "
                f"mean sea-level pressure {e.get('min_pressure_hpa')} hPa, rainfall {e.get('rainfall_mm')} mm."
            ),
        })

    # Live GDACS tropical cyclones affecting the area
    for tc in (cyclone.get("active_global_and_basin_cyclones") or [])[:3]:
        if not tc.get("in_impact_zone"):
            continue
        incident_log.append({
            "id": f"gdacs-{tc.get('event_id')}",
            "date": _to_iso_date(tc.get("from_date")),
            "category": "disaster",
            "title": f"Tropical Cyclone {tc.get('name')} ({tc.get('alert_level')} alert)",
            "source": "GDACS",
            "location": tc.get("affected_countries") or base_city,
            "distance_km": tc.get("distance_km"),
            "severity": "Severe" if tc.get("alert_level") == "Red" else "Moderate",
            "description": f"Max winds {tc.get('max_wind_kmh')} km/h; tracked {tc.get('distance_km')} km from {base_city}.",
            "url": tc.get("report_url"),
        })

    # Live active records (GDACS/FIRMS/USGS) in the current feed
    for rec in active_records or []:
        src = str(_rec_attr(rec, "source", ""))
        if src not in ("gdacs", "nasa_firms", "firms", "usgs", "fsi_vanagni", "ncs_india", "bhuvan"):
            continue
        payload = _rec_attr(rec, "raw_payload", {}) or {}
        title = payload.get("title")
        if not title:
            continue
        ev_time = _rec_attr(rec, "event_time")
        incident_log.append({
            "id": str(_rec_attr(rec, "event_id", "")),
            "date": ev_time.strftime("%Y-%m-%d") if hasattr(ev_time, "strftime") else "",
            "category": "disaster",
            "title": str(title),
            "source": src.upper(),
            "location": base_city,
            "severity": "Moderate",
            "description": str(payload.get("description") or title),
            "url": payload.get("link") or payload.get("url"),
        })

    # Deduplicate by id and sort newest first
    uniq: dict[str, dict[str, Any]] = {}
    for item in incident_log:
        uniq.setdefault(item["id"], item)
    incident_log = sorted(uniq.values(), key=lambda x: str(x.get("date") or ""), reverse=True)

    return {
        "location_name": location_name,
        "timeframe": f"2021 – {years[-1]}",
        "summary": {
            "total_conflicts": tot_conflicts,
            "total_fatalities": tot_fatalities,
            "total_disasters": tot_disasters,
            "volatility_index": volatility_index,
            "volatility_score": vol_score,
            "trend_direction": trend_direction,
            "trend_pct": trend_pct,
            "primary_threat": primary_threat,
            "disaster_threat": disaster_threat,
        },
        "yearly_trends": yearly_trends,
        "conflict_breakdown": conflict_breakdown,
        "disaster_breakdown": disaster_breakdown,
        "incident_log": incident_log,
        "data_availability": data_availability,
    }
