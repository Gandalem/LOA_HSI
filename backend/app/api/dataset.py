from __future__ import annotations

from fastapi import APIRouter

from app.services.dataset_writer import DatasetWriter

router = APIRouter(prefix="/dataset", tags=["dataset"])


@router.get("/status")
def dataset_status():
    """Return local Parquet/DuckDB dataset status.

    Docker path /app/data maps to the host project data directory, e.g.
    D:\\LOA-HSI\\data when using the default docker-compose.yml on Windows.
    """
    return DatasetWriter().status()


@router.get("/stats")
def dataset_stats():
    """Return compact dataset statistics for the dashboard."""
    return DatasetWriter().stats()
