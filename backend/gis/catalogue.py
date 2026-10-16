"""Bhuvan / NRSC 6,670+ Layer Catalogue & Geo-Hazard Analytics Engine.

Provides sub-millisecond search, state/thematic categorization, spatial overlap
analysis, hazard risk scoring, and GeoJSON export across all 6,670+ layers.
"""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from gis.config import INDIA_BBOX, Settings, load_settings

# 36 Indian States & Union Territories with common acronyms and prefixes
STATE_LOOKUP: dict[str, str] = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "CT": "Chhattisgarh",
    "DN": "Dadra and Nagar Haveli and Daman and Diu",
    "DD": "Dadra and Nagar Haveli and Daman and Diu",
    "DL": "Delhi",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "JK": "Jammu and Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "OR": "Odisha",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "UT": "Uttarakhand",
    "WB": "West Bengal",
}

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "disasters_hazards": "Flood risk, landslide vulnerability, cyclone storm surges, drought & seismic hazards",
    "transport_mobility": "National/state road networks, railways, expressways, street lines & transport junctions",
    "admin_boundaries": "State, district, tehsil, city/town, village & panchayat administrative boundaries",
    "tourism_recreation": "Tourist spots, cultural heritage monuments, pilgrim centers, scenic resorts & amenities",
    "water_hydrology": "Rivers, drainage basins, canals, reservoirs, lakes, waterbodies & watersheds",
    "land_terrain": "Elevation, slope gradients, geomorphology, soil, forests & Land Use / Land Cover (LULC)",
    "urban_planning": "NUIS (National Urban Information System), urban master zoning & city infrastructure",
    "rural_decentralized": "SISDP (Space Based Information Support for Decentralized Planning) & Gram Panchayat layers",
    "infrastructure_utilities": "Power transmission lines, pipelines, health facilities, schools & public utilities",
    "thematic_general": "General thematic overlays, basemaps, cadastral maps & geospatial indexes",
}


@dataclass
class BhuvanLayer:
    name: str
    title: str
    workspace: str
    abstract: str
    category: str
    state: str
    bbox: list[float]  # [min_lon, min_lat, max_lon, max_lat]
    styles: list[str] = field(default_factory=list)
    crs_list: list[str] = field(default_factory=list)
    wms_url: str = ""
    tile_url_template: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def categorize_layer(name: str, title: str, abstract: str = "") -> str:
    """Categorize a Bhuvan layer into a travel safety/GIS domain."""
    combined = f"{name} {title} {abstract}".lower()

    if any(
        k in combined
        for k in [
            "flood",
            "landslide",
            "cyclone",
            "drought",
            "hazard",
            "disaster",
            "vulnerability",
            "risk",
            "inundat",
            "slope",
            "earthquake",
            "tsunami",
            "erosion",
        ]
    ):
        return "disasters_hazards"

    if any(
        k in combined
        for k in [
            "road",
            "rail",
            "highway",
            "transport",
            "street",
            "junction",
            "route",
            "traffic",
            "mmi:india_roads",
            "mmi:india_rail",
        ]
    ):
        return "transport_mobility"

    if any(
        k in combined
        for k in [
            "admin_boundary",
            "city_town_boundary",
            "district",
            "taluk",
            "tehsil",
            "village",
            "boundary",
            "panchayat",
            "ward",
        ]
    ):
        return "admin_boundaries"

    if any(
        k in combined
        for k in [
            "tour",
            "hotel",
            "resort",
            "monument",
            "heritage",
            "pilgrim",
            "scenic",
            "attraction",
            "temple",
            "museum",
        ]
    ):
        return "tourism_recreation"

    if any(
        k in combined
        for k in [
            "water",
            "river",
            "canal",
            "drainage",
            "reservoir",
            "lake",
            "wetland",
            "stream",
            "pond",
            "basin",
            "watershed",
        ]
    ):
        return "water_hydrology"

    if any(
        k in combined
        for k in [
            "lulc",
            "geomorph",
            "soil",
            "forest",
            "elevation",
            "dem",
            "geolog",
            "terrain",
            "lithology",
            "rock",
        ]
    ):
        return "land_terrain"

    if name.startswith("nuis:") or "nuis" in combined or "urban" in combined:
        return "urban_planning"

    if name.startswith("sisdp:") or name.startswith("sisdp_base:") or "sisdp" in combined:
        return "rural_decentralized"

    if any(
        k in combined
        for k in [
            "power",
            "utility",
            "health",
            "hospital",
            "school",
            "facility",
            "infrastructure",
            "grid",
            "pipeline",
            "telecom",
        ]
    ):
        return "infrastructure_utilities"

    return "thematic_general"


def detect_state(name: str, title: str) -> str:
    """Detect Indian State or UT from layer identifier or title."""
    clean_name = f"_{name}_".upper().replace(":", "_")
    for code, state_name in STATE_LOOKUP.items():
        if f"_{code}_" in clean_name or state_name.lower() in title.lower():
            return state_name
    return "National / Multi-State"


class BhuvanCatalogue:
    """In-memory indexing and analytics engine for 6,670+ Bhuvan layers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.layers: dict[str, BhuvanLayer] = {}
        self.loaded_at: datetime | None = None
        self.wms_base_url = self.settings.bhuvan_wms_base_url or "https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms"

    def load(
        self,
        capabilities_xml_path: str | Path | None = None,
        json_cache_path: str | Path | None = None,
        force_refresh: bool = False,
    ) -> int:
        """Load and index all layers from local JSON/XML cache or live Bhuvan endpoint."""
        default_json = Path("data/catalogue/bhuvan_layers.json")
        default_xml = Path("data/catalogue/capabilities_wms_130.xml")

        json_path = Path(json_cache_path) if json_cache_path else default_json
        xml_path = Path(capabilities_xml_path) if capabilities_xml_path else default_xml

        if not force_refresh and json_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                self.layers = {item["name"]: BhuvanLayer(**item) for item in data}
                self.loaded_at = datetime.now(timezone.utc)
                return len(self.layers)
            except Exception:
                pass

        if not force_refresh and xml_path.exists():
            count = self._parse_xml(xml_path)
            self._save_json_cache(json_path)
            return count

        # Otherwise download fresh from live Bhuvan
        count = self.refresh(xml_path=xml_path, json_path=json_path)
        return count

    def refresh(
        self,
        xml_path: Path | None = None,
        json_path: Path | None = None,
    ) -> int:
        """Download fresh Capabilities XML from live Bhuvan endpoint and rebuild index."""
        xml_dest = xml_path or Path("data/catalogue/capabilities_wms_130.xml")
        json_dest = json_path or Path("data/catalogue/bhuvan_layers.json")
        xml_dest.parent.mkdir(parents=True, exist_ok=True)

        url = f"{self.wms_base_url}?service=WMS&version=1.3.0&request=GetCapabilities"
        req = urllib.request.Request(url, headers={"User-Agent": "india-travel-safety-catalogue/0.1"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            xml_bytes = resp.read()

        xml_dest.write_bytes(xml_bytes)
        count = self._parse_xml(xml_dest)
        self._save_json_cache(json_dest)
        return count

    def _parse_xml(self, xml_path: Path) -> int:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {"wms": "http://www.opengis.net/wms"}

        layers: dict[str, BhuvanLayer] = {}
        for node in root.findall(".//wms:Layer", ns):
            name_el = node.find("wms:Name", ns)
            if name_el is None or not name_el.text:
                continue
            name = name_el.text.strip()
            title_el = node.find("wms:Title", ns)
            title = title_el.text.strip() if title_el is not None and title_el.text else name
            abstract_el = node.find("wms:Abstract", ns)
            abstract = abstract_el.text.strip() if abstract_el is not None and abstract_el.text else ""

            bbox = [68.0, 6.0, 97.5, 37.0]
            bbox_el = node.find("wms:EX_GeographicBoundingBox", ns)
            if bbox_el is not None:
                try:
                    min_lon = float(bbox_el.find("wms:westBoundLongitude", ns).text)
                    min_lat = float(bbox_el.find("wms:southBoundLatitude", ns).text)
                    max_lon = float(bbox_el.find("wms:eastBoundLongitude", ns).text)
                    max_lat = float(bbox_el.find("wms:northBoundLatitude", ns).text)
                    bbox = [min_lon, min_lat, max_lon, max_lat]
                except Exception:
                    pass

            styles = [s.find("wms:Name", ns).text for s in node.findall("wms:Style", ns) if s.find("wms:Name", ns) is not None]
            crs_list = [c.text for c in node.findall("wms:CRS", ns) if c.text]

            ws = name.split(":")[0] if ":" in name else "default"
            category = categorize_layer(name, title, abstract)
            state = detect_state(name, title)

            tile_template = (
                f"{self.wms_base_url}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
                f"&LAYERS={name}&STYLES={styles[0] if styles else ''}&CRS=EPSG:4326"
                f"&BBOX={{min_lon}},{{min_lat}},{{max_lon}},{{max_lat}}&WIDTH={{width}}&HEIGHT={{height}}"
                f"&FORMAT=image/png&TRANSPARENT=TRUE"
            )

            layer = BhuvanLayer(
                name=name,
                title=title,
                workspace=ws,
                abstract=abstract,
                category=category,
                state=state,
                bbox=bbox,
                styles=styles,
                crs_list=crs_list[:10],
                wms_url=self.wms_base_url,
                tile_url_template=tile_template,
            )
            layers[name] = layer

        self.layers = layers
        self.loaded_at = datetime.now(timezone.utc)
        return len(self.layers)

    def _save_json_cache(self, json_path: Path) -> None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        dump_data = [layer.to_dict() for layer in self.layers.values()]
        json_path.write_text(json.dumps(dump_data, indent=2) + "\n", encoding="utf-8")

    def get_summary(self) -> dict[str, Any]:
        """Aggregate statistical summary across all indexed layers."""
        total = len(self.layers)
        cat_counts = Counter(l.category for l in self.layers.values())
        state_counts = Counter(l.state for l in self.layers.values())
        ws_counts = Counter(l.workspace for l in self.layers.values())

        categories_summary = [
            {
                "category": cat,
                "count": count,
                "percentage": round((count / total) * 100, 2) if total else 0,
                "description": CATEGORY_DESCRIPTIONS.get(cat, ""),
            }
            for cat, count in cat_counts.most_common()
        ]

        states_summary = [
            {"state": state, "layer_count": count} for state, count in state_counts.most_common()
        ]

        workspaces_summary = [
            {"workspace": ws, "layer_count": count} for ws, count in ws_counts.most_common(20)
        ]

        return {
            "total_layers": total,
            "wms_endpoint": self.wms_base_url,
            "indexed_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "categories": categories_summary,
            "top_states": states_summary[:15],
            "workspaces": workspaces_summary,
            "india_geographic_envelope": list(INDIA_BBOX),
        }

    def search(
        self,
        query: str | None = None,
        category: str | None = None,
        state: str | None = None,
        workspace: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search and filter layers by text, category, state, workspace, and spatial bbox."""
        results = list(self.layers.values())

        if category:
            cat_clean = category.lower().strip()
            results = [l for l in results if l.category.lower() == cat_clean]

        if state:
            st_clean = state.lower().strip()
            results = [l for l in results if st_clean in l.state.lower()]

        if workspace:
            ws_clean = workspace.lower().strip()
            results = [l for l in results if l.workspace.lower() == ws_clean]

        if query:
            q = query.lower().strip()
            results = [l for l in results if q in l.name.lower() or q in l.title.lower() or q in l.abstract.lower()]

        if bbox:
            min_x, min_y, max_x, max_y = bbox
            results = [
                l
                for l in results
                if not (
                    l.bbox[2] < min_x
                    or l.bbox[0] > max_x
                    or l.bbox[3] < min_y
                    or l.bbox[1] > max_y
                )
            ]

        total_matched = len(results)
        paginated = results[offset : offset + limit]

        return {
            "total_matched": total_matched,
            "limit": limit,
            "offset": offset,
            "layers": [l.to_dict() for l in paginated],
        }

    def get_layer(self, layer_name: str) -> BhuvanLayer | None:
        """Fetch exact layer metadata by name."""
        return self.layers.get(layer_name)

    def analyze_point_safety(
        self,
        lon: float,
        lat: float,
        radius_deg: float = 0.05,
    ) -> dict[str, Any]:
        """Analyze hazard exposure, road accessibility, and administrative context for a GPS point."""
        query_bbox = (lon - radius_deg, lat - radius_deg, lon + radius_deg, lat + radius_deg)
        overlapping = [
            l
            for l in self.layers.values()
            if not (
                l.bbox[2] < query_bbox[0]
                or l.bbox[0] > query_bbox[2]
                or l.bbox[3] < query_bbox[1]
                or l.bbox[1] > query_bbox[3]
            )
        ]

        hazard_layers = [l.to_dict() for l in overlapping if l.category == "disasters_hazards"]
        road_layers = [l.to_dict() for l in overlapping if l.category == "transport_mobility"]
        tourism_layers = [l.to_dict() for l in overlapping if l.category == "tourism_recreation"]
        admin_layers = [l.to_dict() for l in overlapping if l.category == "admin_boundaries"]

        # Travel Safety Risk Indicator
        hazard_count = len(hazard_layers)
        if hazard_count > 5:
            risk_level = "HIGH_MONITORING"
        elif hazard_count > 0:
            risk_level = "MODERATE_ADVISORY"
        else:
            risk_level = "LOW_CLEAR"

        return {
            "query_location": {"lon": lon, "lat": lat, "radius_deg": radius_deg},
            "risk_assessment": {
                "risk_tier": risk_level,
                "hazard_layers_count": hazard_count,
                "road_connectivity_layers_count": len(road_layers),
                "tourist_points_count": len(tourism_layers),
            },
            "hazard_layers": hazard_layers[:20],
            "transport_layers": road_layers[:20],
            "tourism_layers": tourism_layers[:20],
            "admin_layers": admin_layers[:10],
            "total_overlapping_layers": len(overlapping),
        }

    def analyze_bbox_safety(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
    ) -> dict[str, Any]:
        """Corridor / Bounding box safety risk analysis across all layers."""
        search_res = self.search(bbox=(min_lon, min_lat, max_lon, max_lat), limit=1000)
        matched = [BhuvanLayer(**l) for l in search_res["layers"]]

        by_cat = Counter(l.category for l in matched)
        by_state = Counter(l.state for l in matched)

        return {
            "bbox": [min_lon, min_lat, max_lon, max_lat],
            "total_layers_in_corridor": len(matched),
            "category_breakdown": dict(by_cat),
            "states_intersected": dict(by_state),
            "hazard_layers": [l.to_dict() for l in matched if l.category == "disasters_hazards"][:30],
            "transport_layers": [l.to_dict() for l in matched if l.category == "transport_mobility"][:30],
        }

    def to_geojson(
        self,
        category: str | None = None,
        state: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Export layer bounding boxes as a GeoJSON FeatureCollection."""
        search_res = self.search(category=category, state=state, limit=limit)
        features = []
        for l in search_res["layers"]:
            bbox = l["bbox"]
            polygon_coords = [
                [
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[1]],
                    [bbox[2], bbox[3]],
                    [bbox[0], bbox[3]],
                    [bbox[0], bbox[1]],
                ]
            ]
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "name": l["name"],
                        "title": l["title"],
                        "category": l["category"],
                        "state": l["state"],
                        "workspace": l["workspace"],
                    },
                    "geometry": {"type": "Polygon", "coordinates": polygon_coords},
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
            "total_features": len(features),
        }


# Global singleton instance initialized on import
_global_catalogue: BhuvanCatalogue | None = None


def get_catalogue() -> BhuvanCatalogue:
    """Retrieve the cached singleton layer catalogue."""
    global _global_catalogue
    if _global_catalogue is None:
        _global_catalogue = BhuvanCatalogue()
        _global_catalogue.load()
    return _global_catalogue
