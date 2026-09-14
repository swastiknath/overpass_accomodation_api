"""
High-throughput ingestion and transformation pipeline that fetches hotel data across multiple
geographic regions, cleans, enriches, deduplicates, and generates large DataFrames.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Callable

import pandas as pd
from hotels_api.models import HotelProperty, PipelineStatus, PipelineRunRequest
from hotels_api.geoutils import DEFAULT_REGIONS
from hotels_api.fetcher import OverpassFetcher
from hotels_api.storage import storage_instance, HotelStorage

logger = logging.getLogger("hotels_api.pipeline")


class HotelDataPipeline:
    """
    Automated data ingestion pipeline orchestrator.
    """

    def __init__(self, storage: Optional[HotelStorage] = None):
        self.storage = storage or storage_instance
        self.fetcher = OverpassFetcher()
        self.status = PipelineStatus(
            is_running=False,
            current_step="Idle",
            progress_pct=0.0,
            total_regions=0,
            completed_regions=0,
            total_fetched_raw=0,
            unique_properties_processed=0,
            errors=[],
            output_files={}
        )

    def run_sync(
        self,
        regions: Optional[List[str]] = None,
        custom_bboxes: Optional[Dict[str, List[float]]] = None,
        output_dir: str = "./data",
        delay_between_regions: float = 1.5,
        status_callback: Optional[Callable[[PipelineStatus], None]] = None
    ) -> pd.DataFrame:
        """
        Run the ingestion pipeline synchronously across the requested regions.
        """
        self.status.is_running = True
        self.status.start_time = datetime.now(timezone.utc)
        self.status.end_time = None
        self.status.errors = []
        self.status.current_step = "Initializing pipeline"
        self.status.progress_pct = 0.0

        targets: Dict[str, Tuple[float, float, float, float]] = {}
        
        # Add custom bounding boxes
        if custom_bboxes:
            for name, box in custom_bboxes.items():
                if len(box) == 4:
                    targets[name] = (box[0], box[1], box[2], box[3])

        # Add predefined regions
        if regions:
            for r in regions:
                if r in DEFAULT_REGIONS:
                    targets[r] = DEFAULT_REGIONS[r]
                elif r not in targets:
                    logger.warning(f"Region '{r}' not recognized in default list")
        else:
            if not custom_bboxes:
                targets = dict(DEFAULT_REGIONS)

        self.status.total_regions = len(targets)
        self.status.completed_regions = 0
        all_properties: List[HotelProperty] = []

        logger.info(f"Starting pipeline execution for {len(targets)} regions...")

        for idx, (name, (south, west, north, east)) in enumerate(targets.items()):
            self.status.current_step = f"Fetching region: {name} ({idx+1}/{len(targets)})"
            self.status.progress_pct = round((idx / max(1, len(targets))) * 90.0, 1)
            if status_callback:
                status_callback(self.status)

            try:
                logger.info(f"Fetching region [{name}]: bbox=({south}, {west}, {north}, {east})")
                props = self.fetcher.fetch_bbox(south, west, north, east, region=name)
                all_properties.extend(props)
                self.status.total_fetched_raw += len(props)
                logger.info(f"Fetched {len(props)} accommodations for region [{name}]")
            except Exception as e:
                err_msg = f"Failed fetching region {name}: {str(e)}"
                logger.error(err_msg)
                self.status.errors.append(err_msg)

            self.status.completed_regions += 1
            time.sleep(delay_between_regions)

        # Deduplication and indexing stage
        self.status.current_step = "Normalizing and indexing DataFrame"
        self.status.progress_pct = 92.0
        if status_callback:
            status_callback(self.status)

        # Update Storage & In-memory DataFrame
        self.storage.data_dir = output_dir
        self.storage.load_from_properties(all_properties)
        self.status.unique_properties_processed = len(self.storage.df)

        # Export stage
        self.status.current_step = "Exporting data to CSV, Parquet, and SQLite"
        self.status.progress_pct = 96.0
        if status_callback:
            status_callback(self.status)

        export_paths = self.storage.export_all(base_filename="hotels_master")
        self.status.output_files = export_paths

        self.status.is_running = False
        self.status.current_step = "Completed"
        self.status.progress_pct = 100.0
        self.status.end_time = datetime.now(timezone.utc)
        if status_callback:
            status_callback(self.status)

        logger.info(f"Pipeline finished. Total unique properties: {len(self.storage.df)}")
        return self.storage.df

    async def run_async_task(self, req: PipelineRunRequest):
        """Run pipeline as an asynchronous background task."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self.run_sync,
            req.regions,
            req.custom_bboxes,
            req.output_dir,
            1.5
        )


pipeline_instance = HotelDataPipeline()
