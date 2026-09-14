"""
overpass_fetch.py

Fetches tourism=hotel|hostel|guest_house POIs from the Overpass API across a
set of India/Nepal bounding boxes and normalizes them into a flat DataFrame
with the schema expected by osm_xotelo_join.py.

Usage:
    python overpass_fetch.py --out osm_accommodations.csv
"""

import argparse
import time
import requests
import pandas as pd

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# (region_name, south, west, north, east)
BBOXES = [
    ("rishikesh_haridwar", 29.85, 78.10, 30.20, 78.40),
    ("manali_kasol", 32.00, 77.05, 32.35, 77.40),
    ("goa", 14.90, 73.65, 15.85, 74.35),
    ("hampi", 15.30, 76.44, 15.38, 76.50),
    ("varanasi", 25.24, 82.90, 25.35, 83.05),
    ("jaisalmer", 26.88, 70.85, 26.96, 71.00),
    ("kathmandu_thamel", 27.68, 85.28, 27.74, 85.34),
    ("pokhara_lakeside", 28.18, 83.92, 28.26, 84.05),
    ("chitwan_sauraha", 27.55, 84.42, 27.60, 84.52),
]

TOURISM_TAGS = ("hotel", "hostel", "guest_house")


def build_query(south: float, west: float, north: float, east: float) -> str:
    tag_regex = "^(" + "|".join(TOURISM_TAGS) + ")$"
    return f"""
    [out:json][timeout:90];
    (
      node["tourism"~"{tag_regex}"]({south},{west},{north},{east});
      way["tourism"~"{tag_regex}"]({south},{west},{north},{east});
    );
    out center tags;
    """


def fetch_region(name: str, south, west, north, east, retries: int = 3) -> list[dict]:
    query = build_query(south, west, north, east)
    for attempt in range(retries):
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=120)
        if resp.status_code == 200:
            elements = resp.json().get("elements", [])
            return normalize(elements, name)
        # 429 / 504 -> backoff and retry
        time.sleep(5 * (attempt + 1))
    print(f"[warn] failed to fetch region={name} after {retries} retries")
    return []


def normalize(elements: list[dict], region: str) -> list[dict]:
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        rows.append({
            "osm_id": el.get("id"),
            "osm_type": el.get("type"),
            "region": region,
            "name": tags.get("name"),
            "tourism_type": tags.get("tourism"),
            "lat": lat,
            "lon": lon,
            "addr_full": ", ".join(filter(None, [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:city"),
                tags.get("addr:postcode"),
            ])) or None,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "website": tags.get("website") or tags.get("contact:website"),
            "stars": tags.get("stars"),
            "beds": tags.get("beds"),
            "rooms": tags.get("rooms"),
        })
    return rows


def main(out_path: str):
    all_rows = []
    for name, south, west, north, east in BBOXES:
        print(f"[info] fetching {name} ...")
        all_rows.extend(fetch_region(name, south, west, north, east))
        time.sleep(2)  # be polite to the public Overpass instance

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["osm_id", "osm_type"])
    df.to_csv(out_path, index=False)
    print(f"[info] wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="osm_accommodations.csv")
    args = parser.parse_args()
    main(args.out)
