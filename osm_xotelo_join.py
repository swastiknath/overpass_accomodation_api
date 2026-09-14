"""
osm_xotelo_join.py

Joins OSM-derived accommodation POIs (geospatial ground truth, sparse on
price) with Xotelo/OTA-derived listings (rich on price, needs a location_key
per property) by nearest-neighbor geo-proximity, with a name-similarity
guard to reject bad matches.

Pipeline:
  1. Load osm_accommodations.csv  (from overpass_fetch.py)
  2. Load xotelo_listings.csv      (your own pull from the Xotelo /rates
     endpoint per TripAdvisor location_key — see NOTE below)
  3. Build a cKDTree over OSM coordinates (approximated in a local
     equirectangular projection — fine at this scale, avoids a geodesy dep)
  4. For each Xotelo listing, find nearest OSM POI within a distance
     threshold; accept the match only if name similarity clears a floor
     (guards against joining the wrong hostel when two sit 30m apart)
  5. Emit a unified table

NOTE on Xotelo listings.csv: Xotelo's API is keyed by TripAdvisor
location_key, not lat/lon directly — you resolve location_key -> lat/lon by
also pulling TripAdvisor's location details (via the geo_id / mapped
location endpoints) or by geocoding the returned name+address with your
own gazetteer. Fold that into whatever produces xotelo_listings.csv;
this script assumes lat/lon are already present.
"""

import argparse
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

try:
    from rapidfuzz import fuzz
except ImportError:  # fallback so the script still runs without rapidfuzz
    fuzz = None

EARTH_RADIUS_M = 6_371_000
MATCH_RADIUS_M = 150       # max distance to consider a candidate match
NAME_SIM_FLOOR = 55        # 0-100 rapidfuzz token_sort_ratio; below this, reject

UNIFIED_SCHEMA = [
    "listing_id",          # synthetic: f"{osm_type}_{osm_id}" if matched, else xotelo key
    "name_osm",
    "name_xotelo",
    "name_similarity",
    "tourism_type",        # hotel / hostel / guest_house (from OSM)
    "lat", "lon",
    "region",
    "addr_full",
    "phone",
    "website",
    "stars",
    "price_min",
    "price_max",
    "price_currency",
    "rating",
    "review_count",
    "match_distance_m",
    "match_status",        # 'matched' | 'osm_only' | 'xotelo_only'
]


def equirect_xy(lat, lon, lat0):
    """Cheap local projection (meters) — fine for <200km spans, avoids haversine loop cost."""
    lat_r, lon_r, lat0_r = np.radians(lat), np.radians(lon), np.radians(lat0)
    x = EARTH_RADIUS_M * lon_r * np.cos(lat0_r)
    y = EARTH_RADIUS_M * lat_r
    return x, y


def name_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if fuzz is None:
        return 100.0 if a.strip().lower() == b.strip().lower() else 0.0
    return fuzz.token_sort_ratio(a.lower(), b.lower())


def join(osm_df: pd.DataFrame, xotelo_df: pd.DataFrame) -> pd.DataFrame:
    lat0 = pd.concat([osm_df["lat"], xotelo_df["lat"]]).mean()

    osm_x, osm_y = equirect_xy(osm_df["lat"].values, osm_df["lon"].values, lat0)
    tree = cKDTree(np.column_stack([osm_x, osm_y]))

    xot_x, xot_y = equirect_xy(xotelo_df["lat"].values, xotelo_df["lon"].values, lat0)
    dist, idx = tree.query(np.column_stack([xot_x, xot_y]), k=1)

    matched_osm_idx = set()
    rows = []

    for i, (d, j) in enumerate(zip(dist, idx)):
        xot_row = xotelo_df.iloc[i]
        candidate_accept = d <= MATCH_RADIUS_M
        sim = 0.0
        if candidate_accept:
            osm_row = osm_df.iloc[j]
            sim = name_similarity(osm_row.get("name"), xot_row.get("name"))
            candidate_accept = sim >= NAME_SIM_FLOOR

        if candidate_accept:
            osm_row = osm_df.iloc[j]
            matched_osm_idx.add(j)
            rows.append({
                "listing_id": f"{osm_row['osm_type']}_{osm_row['osm_id']}",
                "name_osm": osm_row.get("name"),
                "name_xotelo": xot_row.get("name"),
                "name_similarity": sim,
                "tourism_type": osm_row.get("tourism_type"),
                "lat": osm_row.get("lat"),
                "lon": osm_row.get("lon"),
                "region": osm_row.get("region"),
                "addr_full": osm_row.get("addr_full"),
                "phone": osm_row.get("phone"),
                "website": osm_row.get("website"),
                "stars": osm_row.get("stars"),
                "price_min": xot_row.get("price_min"),
                "price_max": xot_row.get("price_max"),
                "price_currency": xot_row.get("price_currency"),
                "rating": xot_row.get("rating"),
                "review_count": xot_row.get("review_count"),
                "match_distance_m": round(float(d), 1),
                "match_status": "matched",
            })
        else:
            rows.append({
                "listing_id": xot_row.get("location_key", f"xotelo_{i}"),
                "name_osm": None,
                "name_xotelo": xot_row.get("name"),
                "name_similarity": sim,
                "tourism_type": None,
                "lat": xot_row.get("lat"),
                "lon": xot_row.get("lon"),
                "region": None,
                "addr_full": xot_row.get("address"),
                "phone": None,
                "website": None,
                "stars": None,
                "price_min": xot_row.get("price_min"),
                "price_max": xot_row.get("price_max"),
                "price_currency": xot_row.get("price_currency"),
                "rating": xot_row.get("rating"),
                "review_count": xot_row.get("review_count"),
                "match_distance_m": round(float(d), 1) if candidate_accept is not None else None,
                "match_status": "xotelo_only",
            })

    # unmatched OSM rows — geospatial ground truth with no price data
    for j in range(len(osm_df)):
        if j in matched_osm_idx:
            continue
        osm_row = osm_df.iloc[j]
        rows.append({
            "listing_id": f"{osm_row['osm_type']}_{osm_row['osm_id']}",
            "name_osm": osm_row.get("name"),
            "name_xotelo": None,
            "name_similarity": None,
            "tourism_type": osm_row.get("tourism_type"),
            "lat": osm_row.get("lat"),
            "lon": osm_row.get("lon"),
            "region": osm_row.get("region"),
            "addr_full": osm_row.get("addr_full"),
            "phone": osm_row.get("phone"),
            "website": osm_row.get("website"),
            "stars": osm_row.get("stars"),
            "price_min": None,
            "price_max": None,
            "price_currency": None,
            "rating": None,
            "review_count": None,
            "match_distance_m": None,
            "match_status": "osm_only",
        })

    return pd.DataFrame(rows, columns=UNIFIED_SCHEMA)


def main(osm_path: str, xotelo_path: str, out_path: str):
    osm_df = pd.read_csv(osm_path)
    xotelo_df = pd.read_csv(xotelo_path)

    result = join(osm_df, xotelo_df)
    result.to_csv(out_path, index=False)

    n_matched = (result["match_status"] == "matched").sum()
    print(f"[info] matched={n_matched}  osm_only={(result.match_status=='osm_only').sum()}  "
          f"xotelo_only={(result.match_status=='xotelo_only').sum()}")
    print(f"[info] wrote {len(result)} rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--osm", default="osm_accommodations.csv")
    parser.add_argument("--xotelo", default="xotelo_listings.csv")
    parser.add_argument("--out", default="unified_accommodations.csv")
    args = parser.parse_args()
    main(args.osm, args.xotelo, args.out)
