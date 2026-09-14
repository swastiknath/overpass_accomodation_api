#!/usr/bin/env python3
"""
Batch Expansion Runner - Fetches hotel data from ALL new regions not yet in the dataset.
Merges with existing data and exports updated files.

This script identifies regions that have not been fetched yet and processes them
in batches to avoid overwhelming the Overpass API.
"""

import os
import sys
import time
import logging
import pandas as pd
from hotels_api.geoutils import DEFAULT_REGIONS
from hotels_api.fetcher import OverpassFetcher
from hotels_api.tag_parser import parse_osm_element
from hotels_api.storage import HotelStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("batch_expand")

DATA_DIR = "./data"
CSV_PATH = os.path.join(DATA_DIR, "hotels_master.csv")
BATCH_SIZE = 8  # regions per batch
DELAY_BETWEEN_REGIONS = 2.5  # seconds
DELAY_BETWEEN_BATCHES = 5.0  # seconds


def get_already_fetched_regions() -> set:
    """Read existing CSV and return set of already-fetched region names."""
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            if "region" in df.columns:
                return set(df["region"].dropna().unique())
        except Exception as e:
            logger.warning(f"Could not read existing CSV: {e}")
    return set()


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    already_done = get_already_fetched_regions()
    all_regions = list(DEFAULT_REGIONS.keys())
    
    # Filter to only India & Nepal regions (skip global hubs already done or not priority)
    priority_prefixes = []  # empty = all regions
    
    remaining = [r for r in all_regions if r not in already_done]
    
    if not remaining:
        print("✅ All regions have already been fetched!")
        return
    
    print("=" * 75)
    print("🏨 HOTEL DATA BATCH EXPANSION RUNNER")
    print("=" * 75)
    print(f"Total defined regions:     {len(all_regions)}")
    print(f"Already fetched:           {len(already_done)}")
    print(f"Regions to fetch:          {len(remaining)}")
    print(f"Batch size:                {BATCH_SIZE}")
    print(f"Delay between regions:     {DELAY_BETWEEN_REGIONS}s")
    print(f"Delay between batches:     {DELAY_BETWEEN_BATCHES}s")
    print("=" * 75)
    print(f"\nRegions to fetch: {', '.join(remaining[:20])}{'...' if len(remaining) > 20 else ''}")
    print()

    # Load existing data
    existing_df = None
    if os.path.exists(CSV_PATH):
        existing_df = pd.read_csv(CSV_PATH)
        logger.info(f"Loaded {len(existing_df)} existing records from CSV")

    fetcher = OverpassFetcher(timeout_seconds=60)
    all_new_properties = []
    total_errors = []
    
    # Process in batches
    batches = [remaining[i:i+BATCH_SIZE] for i in range(0, len(remaining), BATCH_SIZE)]
    
    for batch_idx, batch in enumerate(batches):
        print(f"\n{'─' * 60}")
        print(f"📦 BATCH {batch_idx + 1}/{len(batches)} — {len(batch)} regions")
        print(f"{'─' * 60}")
        
        for region_idx, region_name in enumerate(batch):
            bbox = DEFAULT_REGIONS[region_name]
            south, west, north, east = bbox
            progress = f"[{batch_idx * BATCH_SIZE + region_idx + 1}/{len(remaining)}]"
            
            print(f"  {progress} Fetching: {region_name} (bbox={south},{west},{north},{east}) ...", end=" ", flush=True)
            
            try:
                props = fetcher.fetch_bbox(south, west, north, east, region=region_name, max_retries=4)
                all_new_properties.extend(props)
                print(f"✅ {len(props)} properties")
            except Exception as e:
                err = f"Failed {region_name}: {e}"
                total_errors.append(err)
                print(f"❌ Error: {e}")
            
            time.sleep(DELAY_BETWEEN_REGIONS)
        
        # Save checkpoint after each batch
        if all_new_properties:
            storage = HotelStorage(data_dir=DATA_DIR)
            
            # Convert new properties to dataframe
            new_records = []
            for p in all_new_properties:
                new_records.append(p.model_dump())
            new_df = pd.DataFrame(new_records)
            
            # Merge with existing
            if existing_df is not None:
                combined = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                combined = new_df
            
            # Deduplicate on osm_id
            if "osm_id" in combined.columns:
                combined = combined.drop_duplicates(subset=["osm_id"], keep="last")
            
            combined.to_csv(CSV_PATH, index=False)
            print(f"  💾 Checkpoint saved: {len(combined)} total records")
        
        if batch_idx < len(batches) - 1:
            print(f"  ⏳ Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
            time.sleep(DELAY_BETWEEN_BATCHES)

    # Final export
    print(f"\n{'=' * 75}")
    print("📊 FINAL EXPORT")
    print(f"{'=' * 75}")
    
    final_df = pd.read_csv(CSV_PATH)
    
    # Also export as Parquet
    try:
        parquet_path = os.path.join(DATA_DIR, "hotels_master.parquet")
        final_df.to_parquet(parquet_path, index=False)
        print(f"  ✅ Parquet: {parquet_path}")
    except Exception as e:
        print(f"  ⚠️ Parquet export failed: {e}")
    
    print(f"\n{'=' * 75}")
    print("✨ BATCH EXPANSION COMPLETED!")
    print(f"{'=' * 75}")
    print(f"Total unique properties:   {len(final_df):,}")
    print(f"Total columns:             {len(final_df.columns)}")
    print(f"New properties added:      {len(all_new_properties):,}")
    print(f"Errors encountered:        {len(total_errors)}")
    print(f"Memory usage:              {final_df.memory_usage(deep=True).sum() / (1024*1024):.2f} MB")
    
    if "region" in final_df.columns:
        print(f"\n🌍 Region Coverage ({final_df['region'].nunique()} regions):")
        print(final_df["region"].value_counts().to_string())
    
    if total_errors:
        print(f"\n⚠️ Errors:")
        for err in total_errors:
            print(f"  - {err}")
    
    print(f"{'=' * 75}")


if __name__ == "__main__":
    main()
