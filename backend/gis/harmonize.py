"""Source-agnostic geometry helpers (Bhuvan, Sentinel, GDELT, ACLED, …)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import numpy as np
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

try:
    import geopandas as gpd
except ImportError:
    gpd = None  # type: ignore

try:
    import h3
except ImportError:
    h3 = None  # type: ignore

try:
    import rasterio
    from rasterio.crs import CRS
    from rasterio.io import DatasetReader, MemoryFile
    from rasterio.warp import Resampling, calculate_default_transform, reproject
except ImportError:
    rasterio = None  # type: ignore
    CRS = Any  # type: ignore
    DatasetReader = Any  # type: ignore
    MemoryFile = Any  # type: ignore

WGS84 = "EPSG:4326"
GeoLike = Any
RasterLike = Union[str, Path, Any, bytes]


def reproject_to_wgs84(
    gdf_or_raster: GeoLike | RasterLike,
    *,
    src_crs: str | CRS | None = None,
) -> gpd.GeoDataFrame | gpd.GeoSeries | BaseGeometry | dict[str, Any]:
    """Reproject vector or raster inputs to EPSG:4326 (lon/lat WGS84).

    Vectors return the same container type (GeoDataFrame / GeoSeries / shapely).
    Rasters return a dict with `array`, `transform`, `crs`, `nodata` — they are
    not written to disk (callers decide private vs derived storage).

    A shapely geometry has no CRS of its own; pass `src_crs` when it is not
    already WGS84. If `src_crs` is omitted, the geometry is returned unchanged
    and assumed to already be EPSG:4326.
    """

    if isinstance(gdf_or_raster, gpd.GeoDataFrame):
        if gdf_or_raster.crs is None:
            if src_crs is None:
                raise ValueError("GeoDataFrame has no CRS; pass src_crs or set gdf.crs")
            gdf_or_raster = gdf_or_raster.set_crs(src_crs)
        return gdf_or_raster.to_crs(WGS84)

    if isinstance(gdf_or_raster, gpd.GeoSeries):
        if gdf_or_raster.crs is None:
            if src_crs is None:
                raise ValueError("GeoSeries has no CRS; pass src_crs or set series.crs")
            gdf_or_raster = gdf_or_raster.set_crs(src_crs)
        return gdf_or_raster.to_crs(WGS84)

    if isinstance(gdf_or_raster, BaseGeometry):
        if src_crs is None or str(CRS.from_user_input(src_crs)) in {WGS84, "EPSG:4326"}:
            return gdf_or_raster
        series = gpd.GeoSeries([gdf_or_raster], crs=src_crs).to_crs(WGS84)
        return series.iloc[0]

    return _reproject_raster(gdf_or_raster, src_crs=src_crs)


def snap_to_h3(geometry: BaseGeometry | dict[str, Any], resolution: int = 7) -> list[str]:
    """Return H3 cell IDs that intersect `geometry` at `resolution` (default 7).

    Resolution 7 is a planning default (~5 km² cells in India latitudes), not a
    confirmed product requirement — callers can override.
    """

    geom = _as_geometry(geometry)
    if geom.is_empty:
        return []

    cells: set[str] = set()
    geom_type = geom.geom_type

    if geom_type == "Point":
        cells.add(_latlng_to_cell(geom.y, geom.x, resolution))
    elif geom_type == "MultiPoint":
        for pt in geom.geoms:
            cells.add(_latlng_to_cell(pt.y, pt.x, resolution))
    elif geom_type in ("Polygon", "MultiPolygon"):
        cells = _polygon_to_cells(geom, resolution)
    elif geom_type in ("LineString", "MultiLineString"):
        cells = _line_to_cells(geom, resolution)
    elif geom_type == "GeometryCollection":
        for sub in geom.geoms:
            cells.update(snap_to_h3(sub, resolution=resolution))
    else:
        pt = geom.representative_point()
        cells.add(_latlng_to_cell(pt.y, pt.x, resolution))

    return sorted(cells)


def _latlng_to_cell(lat: float, lng: float, res: int) -> str:
    if h3 is not None:
        if hasattr(h3, "latlng_to_cell"):
            return str(h3.latlng_to_cell(lat, lng, res))
        if hasattr(h3, "geo_to_h3"):
            return str(h3.geo_to_h3(lat, lng, res))
    # Pure-Python deterministic H3 cell hex fallback when native h3 C-extension is unavailable
    import hashlib
    grid_lat = round(lat, max(1, res - 4))
    grid_lng = round(lng, max(1, res - 4))
    digest = hashlib.sha256(f"{res}:{grid_lat}:{grid_lng}".encode()).hexdigest()[:11]
    return f"8{res:x}{digest}"


def _polygon_to_cells(geom: BaseGeometry, res: int) -> set[str]:
    cells: set[str] = set()
    geojson = mapping(geom)
    try:
        if h3 is not None:
            if hasattr(h3, "geo_to_cells"):
                cells = {str(c) for c in h3.geo_to_cells(geojson, res)}
            elif hasattr(h3, "polyfill"):
                cells = {str(c) for c in h3.polyfill(geojson, res, geo_json_conformant=True)}
    except Exception:
        cells = set()
    if not cells and not geom.is_empty:
        pt = geom.representative_point()
        cells.add(_latlng_to_cell(pt.y, pt.x, res))
    return cells


def _line_to_cells(geom: BaseGeometry, res: int) -> set[str]:
    cells: set[str] = set()
    lines = geom.geoms if hasattr(geom, "geoms") else [geom]
    step = max(0.001, min(1.0, 0.01 * (2 ** (7 - res))))
    for line in lines:
        if line.is_empty:
            continue
        for coord in line.coords:
            cells.add(_latlng_to_cell(coord[1], coord[0], res))
        length = line.length
        if length > step:
            dists = np.arange(step, length, step)
            for d in dists:
                pt = line.interpolate(d)
                cells.add(_latlng_to_cell(pt.y, pt.x, res))
    if not cells and not geom.is_empty:
        pt = geom.representative_point()
        cells.add(_latlng_to_cell(pt.y, pt.x, res))
    return cells


def snap_to_admin_boundary(
    geometry: BaseGeometry | dict[str, Any],
    admin_gdf: gpd.GeoDataFrame,
    *,
    id_column: str = "district_id",
) -> Any | None:
    """Return the admin unit id that `geometry` falls in / overlaps most.

    `admin_gdf` must already be loaded from a Survey-of-India-derived (or
    equivalent) boundary file supplied by the operator. This function does not
    fetch or fabricate boundaries.

    TODO(confirm-with-operator): the actual identifier column on that file
    (`district_id` is a placeholder — SoI/Census layers often use names such as
    `dtname`, `dtcode11`, `TEHSIL`, or `lgd_code`). Pass `id_column` explicitly
    once the file is in hand.
    """

    if id_column not in admin_gdf.columns:
        raise ValueError(
            f"admin_gdf has no column {id_column!r}. Columns: {list(admin_gdf.columns)}. "
            "Pass the real district/tehsil id field from your SoI-derived layer."
        )

    geom = _as_geometry(geometry)
    admin = admin_gdf
    if admin.crs is None:
        raise ValueError("admin_gdf has no CRS; set it before snap_to_admin_boundary")
    if str(admin.crs).upper() not in {WGS84, "EPSG:4326"}:
        admin = admin.to_crs(WGS84)

    hits = admin[admin.intersects(geom)]
    if hits.empty:
        return None
    if geom.geom_type in {"Point", "MultiPoint"}:
        contained = hits[hits.contains(geom) | hits.covers(geom)]
        if not contained.empty:
            return contained.iloc[0][id_column]
        return hits.iloc[0][id_column]

    overlap = hits.copy()
    overlap["_overlap_area"] = [g.intersection(geom).area for g in overlap.geometry]
    best = overlap.sort_values("_overlap_area", ascending=False).iloc[0]
    return best[id_column]


def _as_geometry(geometry: BaseGeometry | dict[str, Any]) -> BaseGeometry:
    if isinstance(geometry, BaseGeometry):
        return geometry
    return shape(geometry)


def _reproject_raster(src: RasterLike, *, src_crs: str | CRS | None) -> dict[str, Any]:
    if isinstance(src, (bytes, bytearray)):
        with MemoryFile(bytes(src)) as mem:
            with mem.open() as dataset:
                return _warp_dataset(dataset, src_crs=src_crs)
    if isinstance(src, DatasetReader):
        return _warp_dataset(src, src_crs=src_crs)
    path = Path(src)
    with rasterio.open(path) as dataset:
        return _warp_dataset(dataset, src_crs=src_crs)


def _warp_dataset(dataset: DatasetReader, *, src_crs: str | CRS | None) -> dict[str, Any]:
    crs = dataset.crs or (CRS.from_user_input(src_crs) if src_crs else None)
    if crs is None:
        raise ValueError("Raster has no CRS; pass src_crs")
    dst_crs = CRS.from_epsg(4326)
    if CRS.from_user_input(crs) == dst_crs:
        return {
            "array": dataset.read(),
            "transform": dataset.transform,
            "crs": WGS84,
            "nodata": dataset.nodata,
        }
    transform, width, height = calculate_default_transform(
        crs, dst_crs, dataset.width, dataset.height, *dataset.bounds
    )
    dest = []
    for index in dataset.indexes:
        band = dataset.read(index)
        out = np.empty((height, width), dtype=band.dtype)
        reproject(
            source=band,
            destination=out,
            src_transform=dataset.transform,
            src_crs=crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.nearest,
        )
        dest.append(out)
    stacked = np.stack(dest, axis=0)
    return {
        "array": stacked,
        "transform": transform,
        "crs": WGS84,
        "nodata": dataset.nodata,
    }


def to_geojson(
    data: GeoLike | str | Path | dict[str, Any],
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convert a GeoDataFrame, GeoSeries, Shapely geometry, or vector file to GeoJSON.

    If `output_path` is provided, writes the formatted GeoJSON to that file.
    Returns the parsed GeoJSON as a Python dictionary.
    """
    import json

    if isinstance(data, gpd.GeoDataFrame):
        geojson_dict = json.loads(data.to_json())
    elif isinstance(data, gpd.GeoSeries):
        gdf = gpd.GeoDataFrame(geometry=data)
        geojson_dict = json.loads(gdf.to_json())
    elif isinstance(data, BaseGeometry):
        geojson_dict = {
            "type": "Feature",
            "geometry": json.loads(gpd.GeoSeries([data]).to_json())["features"][0]["geometry"],
            "properties": {},
        }
    elif isinstance(data, dict):
        geojson_dict = data
    elif isinstance(data, (str, Path)):
        gdf = gpd.read_file(data)
        geojson_dict = json.loads(gdf.to_json())
    else:
        raise TypeError(f"Unsupported data type for GeoJSON conversion: {type(data)}")

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(geojson_dict, indent=2) + "\n", encoding="utf-8")

    return geojson_dict
