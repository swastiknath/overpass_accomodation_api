#!/usr/bin/env python3
"""
CLI Pipeline Runner for High-Throughput Hotel Ingestion.
Extracts hotel & accommodation listings across multiple regions and outputs large DataFrames.

Usage:
    python pipeline_runner.py --all
    python pipeline_runner.py --regions goa,manali_kasol,rishikesh_haridwar
    python pipeline_runner.py --out-dir ./data
"""

import argparse
import sys
import time
from hotels_api.pipeline import HotelDataPipeline
from hotels_api.geoutils import DEFAULT_REGIONS
from hotels_api.storage import HotelStorage


def main():
    parser = argparse.ArgumentParser(description="Real-Time Hotel Data Pipeline Runner")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run pipeline over ALL default regions (India, Nepal, SE Asia, Global)"
    )
    parser.add_argument(
        "--regions",
        type=str,
        default="",
        help="Comma-separated region names (e.g. goa,rishikesh_haridwar,kathmandu_thamel)"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="./data",
        help="Output directory for generated CSV, Parquet, and SQLite databases"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay in seconds between region queries (default 1.5s)"
    )
    parser.add_argument(
        "--list-regions",
        action="store_true",
        help="List available default regions"
    )
    parser.add_argument(
        "--bbox",
        type=str,
        default="",
        help="Ad-hoc bounding box as 'name:south,west,north,east' (e.g. 'my_area:26.8,75.7,27.0,75.9'). "
             "Can be specified multiple times separated by semicolons."
    )

    args = parser.parse_args()

    if args.list_regions:
        print("\nAvailable Pre-configured Regions:")
        for idx, (k, bbox) in enumerate(DEFAULT_REGIONS.items(), 1):
            print(f" {idx:2d}. {k:<25} (south={bbox[0]}, west={bbox[1]}, north={bbox[2]}, east={bbox[3]})")
        return

    selected_regions = []
    custom_bboxes = {}

    # Parse ad-hoc bounding boxes from --bbox flag
    if args.bbox:
        for entry in args.bbox.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            if ":" in entry:
                name, coords = entry.split(":", 1)
                parts = [float(c.strip()) for c in coords.split(",")]
                if len(parts) == 4:
                    custom_bboxes[name.strip()] = parts
                else:
                    print(f"⚠️  Skipping invalid bbox '{entry}' (need 4 values: south,west,north,east)")
            else:
                parts = [float(c.strip()) for c in entry.split(",")]
                if len(parts) == 4:
                    custom_bboxes[f"custom_{len(custom_bboxes)+1}"] = parts
                else:
                    print(f"⚠️  Skipping invalid bbox '{entry}' (need 4 values: south,west,north,east)")

    if args.all:
        selected_regions = list(DEFAULT_REGIONS.keys())
    elif args.regions:
        selected_regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    elif not custom_bboxes:
        # Default sampling
        selected_regions = ["rishikesh_haridwar", "manali_kasol", "goa", "kathmandu_thamel"]

    print("=" * 70)
    print("🏨 HOTELS REAL-TIME DATA PIPELINE RUNNER")
    print("=" * 70)
    if selected_regions:
        print(f"Target Regions ({len(selected_regions)}): {', '.join(selected_regions[:10])}{'...' if len(selected_regions) > 10 else ''}")
    if custom_bboxes:
        print(f"Custom Bboxes ({len(custom_bboxes)}):")
        for name, box in custom_bboxes.items():
            print(f"  - {name}: south={box[0]}, west={box[1]}, north={box[2]}, east={box[3]}")
    print(f"Output Directory: {args.out_dir}")
    print(f"Delay Between Calls: {args.delay}s")
    print("=" * 70)

    storage = HotelStorage(data_dir=args.out_dir)
    pipeline = HotelDataPipeline(storage=storage)

    t0 = time.time()
    df = pipeline.run_sync(
        regions=selected_regions if selected_regions else None,
        custom_bboxes=custom_bboxes if custom_bboxes else None,
        output_dir=args.out_dir,
        delay_between_regions=args.delay
    )
    elapsed = time.time() - t0

    print("\n" + "=" * 70)
    print("✨ PIPELINE EXECUTION COMPLETED!")
    print("=" * 70)
    print(f"Total Unique Properties: {len(df):,}")
    print(f"Total Columns:           {len(df.columns)}")
    print(f"Elapsed Time:            {elapsed:.2f} seconds")
    print(f"Memory Usage:            {df.memory_usage(deep=True).sum() / (1024 * 1024):.2f} MB")
    print("\n📁 Output Files Generated:")
    for fmt, path in pipeline.status.output_files.items():
        print(f" - [{fmt.upper()}]: {path}")

    print("\n📊 Property Type Breakdown:")
    print(df["property_type"].value_counts().to_string())

    print("\n🌟 Top Regions Breakdown:")
    print(df["region"].value_counts().head(15).to_string())
    print("=" * 70)


if __name__ == "__main__":
    main()
