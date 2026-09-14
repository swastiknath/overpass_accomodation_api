"""
Storage and indexing engine: in-memory spatial index, large Pandas DataFrame manager,
and disk persistence (CSV, Parquet, SQLite).
"""

import os
import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from hotels_api.models import HotelProperty, TourismType, PriceTier, DataFrameSummary
from hotels_api.geoutils import EARTH_RADIUS_M, haversine_distance_meters

logger = logging.getLogger("hotels_api.storage")

DF_COLUMNS = [
    "hotel_id", "osm_id", "osm_type", "wikidata_id", "xotelo_key",
    "name", "name_international", "brand", "operator", "property_type", "description",
    "latitude", "longitude", "elevation_m", "geohash", "region",
    "formatted_address", "house_number", "street", "neighborhood", "city", "state", "country", "country_code", "postal_code",
    "stars", "user_rating", "review_count", "price_min", "price_max", "currency", "price_tier",
    "has_wifi", "has_pool", "has_parking", "has_air_conditioning", "has_restaurant", "has_bar", "has_spa", "has_gym",
    "is_pet_friendly", "is_wheelchair_accessible", "smoking_allowed",
    "rooms_count", "beds_count", "checkin_time", "checkout_time", "opening_hours",
    "phone", "email", "website", "booking_url", "image_url", "last_updated_at"
]


class HotelStorage:
    """
    High-performance storage engine that maintains a live Pandas DataFrame,
    KDTree for spatial queries, and multi-format persistence.
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.df: pd.DataFrame = pd.DataFrame(columns=DF_COLUMNS)
        self.kdtree: Optional[cKDTree] = None
        self.lat_rad: Optional[np.ndarray] = None
        self.lon_rad: Optional[np.ndarray] = None
        self.last_updated: datetime = datetime.now(timezone.utc)

    def load_from_properties(self, properties: List[HotelProperty]):
        """Convert a list of HotelProperty objects into a unified DataFrame and build spatial index."""
        if not properties:
            return

        records = [p.model_dump(exclude={"raw_tags", "data_sources", "distance_meters"}) for p in properties]
        new_df = pd.DataFrame(records)
        
        # Merge with existing DataFrame if present, deduplicating on hotel_id
        if not self.df.empty:
            combined = pd.concat([self.df, new_df], ignore_index=True)
            self.df = combined.drop_duplicates(subset=["hotel_id"], keep="last")
        else:
            self.df = new_df.drop_duplicates(subset=["hotel_id"], keep="last")

        self.last_updated = datetime.now(timezone.utc)
        self._rebuild_spatial_index()
        logger.info(f"Loaded {len(properties)} properties. Total in DataFrame: {len(self.df)}")

    def _rebuild_spatial_index(self):
        """Build 3D cartesian KDTree for ultra-fast haversine queries."""
        if self.df.empty:
            self.kdtree = None
            return

        lats = np.radians(self.df["latitude"].values.astype(float))
        lons = np.radians(self.df["longitude"].values.astype(float))
        
        # Convert lat/lon to 3D Cartesian coordinates on unit sphere
        x = np.cos(lats) * np.cos(lons)
        y = np.cos(lats) * np.sin(lons)
        z = np.sin(lats)
        
        self.lat_rad = lats
        self.lon_rad = lons
        self.kdtree = cKDTree(np.column_stack([x, y, z]))

    def query_radius(self, lat: float, lon: float, radius_meters: float, limit: int = 50) -> List[HotelProperty]:
        """Query properties within a radius using the KDTree spatial index."""
        if self.df.empty or self.kdtree is None:
            return []

        # Convert query point to 3D Cartesian
        lat_r, lon_r = np.radians(lat), np.radians(lon)
        qx = np.cos(lat_r) * np.cos(lon_r)
        qy = np.cos(lat_r) * np.sin(lon_r)
        qz = np.sin(lat_r)

        # Euclidean chord distance for great circle radius
        # chord_dist = 2 * sin(d / (2 * R))
        angular_dist = radius_meters / EARTH_RADIUS_M
        chord_dist = 2.0 * np.sin(angular_dist / 2.0)

        indices = self.kdtree.query_ball_point([qx, qy, qz], r=chord_dist)
        if not indices:
            return []

        matched_df = self.df.iloc[indices].copy()
        
        # Compute exact great-circle distance for ranking
        distances = [
            haversine_distance_meters(lat, lon, r["latitude"], r["longitude"])
            for _, r in matched_df.iterrows()
        ]
        matched_df["distance_meters"] = distances
        matched_df = matched_df.sort_values(by="distance_meters").head(limit)

        return [self._row_to_property(row) for _, row in matched_df.iterrows()]

    def query_bbox(self, south: float, west: float, north: float, east: float, limit: int = 100) -> List[HotelProperty]:
        """Filter properties within a bounding box."""
        if self.df.empty:
            return []

        mask = (
            (self.df["latitude"] >= south) &
            (self.df["latitude"] <= north) &
            (self.df["longitude"] >= west) &
            (self.df["longitude"] <= east)
        )
        subset = self.df[mask].head(limit)
        return [self._row_to_property(row) for _, row in subset.iterrows()]

    def search(
        self,
        query: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        property_type: Optional[str] = None,
        min_stars: Optional[float] = None,
        max_stars: Optional[float] = None,
        has_wifi: Optional[bool] = None,
        has_pool: Optional[bool] = None,
        has_parking: Optional[bool] = None,
        has_ac: Optional[bool] = None,
        has_restaurant: Optional[bool] = None,
        is_pet_friendly: Optional[bool] = None,
        is_wheelchair: Optional[bool] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "name",
        sort_desc: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> (List[HotelProperty], int):
        """Advanced multi-attribute search and filtering across the DataFrame."""
        if self.df.empty:
            return [], 0

        mask = pd.Series(True, index=self.df.index)

        if query:
            q = query.lower()
            name_match = self.df["name"].astype(str).str.lower().str.contains(q, na=False)
            brand_match = self.df["brand"].astype(str).str.lower().str.contains(q, na=False)
            addr_match = self.df["formatted_address"].astype(str).str.lower().str.contains(q, na=False)
            mask &= (name_match | brand_match | addr_match)

        if city:
            c = city.lower()
            mask &= self.df["city"].astype(str).str.lower().str.contains(c, na=False)

        if region:
            mask &= (self.df["region"].astype(str).str.lower() == region.lower())

        if property_type:
            mask &= (self.df["property_type"] == property_type)

        if min_stars is not None:
            mask &= (self.df["stars"].fillna(0) >= min_stars)

        if max_stars is not None:
            mask &= (self.df["stars"].fillna(5) <= max_stars)

        if has_wifi is not None:
            mask &= (self.df["has_wifi"] == has_wifi)

        if has_pool is not None:
            mask &= (self.df["has_pool"] == has_pool)

        if has_parking is not None:
            mask &= (self.df["has_parking"] == has_parking)

        if has_ac is not None:
            mask &= (self.df["has_air_conditioning"] == has_ac)

        if has_restaurant is not None:
            mask &= (self.df["has_restaurant"] == has_restaurant)

        if is_pet_friendly is not None:
            mask &= (self.df["is_pet_friendly"] == is_pet_friendly)

        if is_wheelchair is not None:
            mask &= (self.df["is_wheelchair_accessible"] == is_wheelchair)

        if min_price is not None:
            mask &= (self.df["price_min"].fillna(0) >= min_price)

        if max_price is not None:
            mask &= (self.df["price_max"].fillna(999999) <= max_price)

        filtered = self.df[mask].copy()
        total_count = len(filtered)

        # Sorting
        if sort_by in filtered.columns:
            filtered = filtered.sort_values(by=sort_by, ascending=not sort_desc, na_position="last")

        paginated = filtered.iloc[offset: offset + limit]
        items = [self._row_to_property(row) for _, row in paginated.iterrows()]
        return items, total_count

    def get_by_id(self, hotel_id: str) -> Optional[HotelProperty]:
        """Fetch a single property by hotel_id."""
        if self.df.empty:
            return None
        match = self.df[self.df["hotel_id"] == hotel_id]
        if not match.empty:
            return self._row_to_property(match.iloc[0])
        return None

    def export_all(self, base_filename: str = "hotels_master") -> Dict[str, str]:
        """Save the master DataFrame to CSV, Parquet, and SQLite."""
        if self.df.empty:
            return {}

        csv_path = os.path.join(self.data_dir, f"{base_filename}.csv")
        parquet_path = os.path.join(self.data_dir, f"{base_filename}.parquet")
        db_path = os.path.join(self.data_dir, "hotels.db")

        # Export CSV
        self.df.to_csv(csv_path, index=False)
        
        # Export Parquet
        self.df.to_parquet(parquet_path, index=False)
        
        # Export SQLite
        conn = sqlite3.connect(db_path)
        self.df.to_sql("hotels", conn, if_exists="replace", index=False)
        conn.close()

        logger.info(f"Exported {len(self.df)} records to {csv_path}, {parquet_path}, {db_path}")
        return {
            "csv": os.path.abspath(csv_path),
            "parquet": os.path.abspath(parquet_path),
            "sqlite": os.path.abspath(db_path),
        }

    def load_from_disk(self, filename: Optional[str] = None):
        """Attempt to restore DataFrame from existing CSV / Parquet on disk."""
        parquet_path = os.path.join(self.data_dir, filename or "hotels_master.parquet")
        csv_path = os.path.join(self.data_dir, filename or "hotels_master.csv")

        if os.path.exists(parquet_path):
            try:
                self.df = pd.read_parquet(parquet_path)
                self._rebuild_spatial_index()
                logger.info(f"Loaded {len(self.df)} records from Parquet: {parquet_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to read parquet: {e}")

        if os.path.exists(csv_path):
            try:
                self.df = pd.read_csv(csv_path)
                self._rebuild_spatial_index()
                logger.info(f"Loaded {len(self.df)} records from CSV: {csv_path}")
                return
            except Exception as e:
                logger.warning(f"Failed to read csv: {e}")

    def get_summary(self) -> DataFrameSummary:
        """Compute statistical breakdown and metrics of the current dataset."""
        if self.df.empty:
            return DataFrameSummary(
                total_records=0,
                columns_count=len(DF_COLUMNS),
                memory_usage_mb=0.0,
                regions_count=0,
                top_regions={},
                property_types_distribution={},
                stars_distribution={},
                amenities_coverage={},
                price_statistics={},
                last_updated=self.last_updated.isoformat(),
            )

        mem_mb = round(self.df.memory_usage(deep=True).sum() / (1024 * 1024), 2)
        top_reg = self.df["region"].value_counts().head(10).to_dict()
        p_types = self.df["property_type"].value_counts().to_dict()
        
        stars_dist = self.df["stars"].dropna().round().astype(int).value_counts().to_dict()
        stars_dist_str = {f"{k}_star": int(v) for k, v in stars_dist.items()}

        n = len(self.df)
        amenity_cov = {
            "wifi_pct": round(float(self.df["has_wifi"].sum() / n * 100), 1),
            "pool_pct": round(float(self.df["has_pool"].sum() / n * 100), 1),
            "parking_pct": round(float(self.df["has_parking"].sum() / n * 100), 1),
            "ac_pct": round(float(self.df["has_air_conditioning"].sum() / n * 100), 1),
            "restaurant_pct": round(float(self.df["has_restaurant"].sum() / n * 100), 1),
            "spa_pct": round(float(self.df["has_spa"].sum() / n * 100), 1),
            "wheelchair_pct": round(float(self.df["is_wheelchair_accessible"].sum() / n * 100), 1),
        }

        prices = self.df["price_min"].dropna()
        price_stats = {
            "count_with_price": int(len(prices)),
            "min": float(prices.min()) if not prices.empty else 0.0,
            "max": float(prices.max()) if not prices.empty else 0.0,
            "mean": round(float(prices.mean()), 2) if not prices.empty else 0.0,
            "median": round(float(prices.median()), 2) if not prices.empty else 0.0,
        }

        return DataFrameSummary(
            total_records=n,
            columns_count=len(self.df.columns),
            memory_usage_mb=mem_mb,
            regions_count=int(self.df["region"].nunique()),
            top_regions=top_reg,
            property_types_distribution={str(k): int(v) for k, v in p_types.items()},
            stars_distribution=stars_dist_str,
            amenities_coverage=amenity_cov,
            price_statistics=price_stats,
            last_updated=self.last_updated.isoformat(),
        )

    def _row_to_property(self, row: pd.Series) -> HotelProperty:
        d = row.to_dict()
        # Clean NaNs
        clean = {}
        for k, v in d.items():
            if pd.isna(v):
                clean[k] = None
            else:
                clean[k] = v
        
        # Ensure property_type is enum
        pt = clean.get("property_type") or "hotel"
        try:
            clean["property_type"] = TourismType(pt)
        except Exception:
            clean["property_type"] = TourismType.HOTEL

        # Ensure price_tier is enum
        pr_tier = clean.get("price_tier") or "unknown"
        try:
            clean["price_tier"] = PriceTier(pr_tier)
        except Exception:
            clean["price_tier"] = PriceTier.UNKNOWN

        return HotelProperty(**clean)


# Global storage instance
storage_instance = HotelStorage()
