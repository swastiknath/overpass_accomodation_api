# Overpass QL — Accommodation POIs for India & Nepal

Query endpoint (public instance): `https://overpass-api.de/api/interpreter`
Self-hosted / mirror list: https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances

Tags queried: `tourism=hotel`, `tourism=hostel`, `tourism=guest_house`
(add `tourism=motel` or `tourism=apartment` if you want a broader accommodation net)

---

## 1. Full-country bounding boxes

India bbox (south,west,north,east): `6.5,68.0,35.7,97.4`
Nepal bbox: `26.3,80.0,30.5,88.3`

```overpassql
[out:json][timeout:180];
(
  node["tourism"~"^(hotel|hostel|guest_house)$"](6.5,68.0,35.7,97.4);
  way["tourism"~"^(hotel|hostel|guest_house)$"](6.5,68.0,35.7,97.4);
  relation["tourism"~"^(hotel|hostel|guest_house)$"](6.5,68.0,35.7,97.4);
);
out center tags;
```

Full-country queries on India are large (100k+ nodes) — expect timeouts on the public
instance. Prefer the regional boxes below, or a local Overpass mirror with `osm-3s`
loaded from a `.osm.pbf` extract (Geofabrik: https://download.geofabrik.de/asia.html).

Same query for Nepal (small enough to run directly on the public instance):

```overpassql
[out:json][timeout:120];
(
  node["tourism"~"^(hotel|hostel|guest_house)$"](26.3,80.0,30.5,88.3);
  way["tourism"~"^(hotel|hostel|guest_house)$"](26.3,80.0,30.5,88.3);
  relation["tourism"~"^(hotel|hostel|guest_house)$"](26.3,80.0,30.5,88.3);
);
out center tags;
```

---

## 2. Backpacker-corridor bounding boxes (dense OSM coverage, good for hostel-heavy sampling)

| Region              | bbox (south,west,north,east)     |
|---------------------|-----------------------------------|
| Rishikesh/Haridwar  | `29.85,78.10,30.20,78.40`        |
| Manali/Kasol (HP)   | `32.00,77.05,32.35,77.40`        |
| Goa (full state)    | `14.90,73.65,15.85,74.35`        |
| Hampi               | `15.30,76.44,15.38,76.50`        |
| Varanasi            | `25.24,82.90,25.35,83.05`        |
| Jaisalmer           | `26.88,70.85,26.96,71.00`        |
| Kathmandu/Thamel    | `27.68,85.28,27.74,85.34`        |
| Pokhara/Lakeside    | `28.18,83.92,28.26,84.05`        |
| Chitwan (Sauraha)   | `27.55,84.42,27.60,84.52`        |

Template — swap in any row above:

```overpassql
[out:json][timeout:60];
(
  node["tourism"~"^(hotel|hostel|guest_house)$"](29.85,78.10,30.20,78.40);
  way["tourism"~"^(hotel|hostel|guest_house)$"](29.85,78.10,30.20,78.40);
);
out center tags;
```

---

## 3. Filtering to likely-budget stays (useful signal, not authoritative)

OSM doesn't have a reliable `price_range` tag, but you can filter on proxies:

```overpassql
[out:json][timeout:60];
(
  node["tourism"="hostel"](26.3,80.0,30.5,88.3);
  node["tourism"="guest_house"](26.3,80.0,30.5,88.3);
  node["tourism"="hotel"]["stars"~"^[1-2]$"](26.3,80.0,30.5,88.3);
);
out tags;
```

---

## 4. Python fetch wrapper

See `overpass_fetch.py` for a script that iterates the bbox table above, hits the
Overpass endpoint with retry/backoff, and normalizes results into a flat DataFrame
matching the schema in `osm_xotelo_join.py`.
