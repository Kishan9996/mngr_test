"""Admin-only seed endpoint: load CSVs into the database for an org."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_query_cache, require_admin
from app.core.security import TokenPayload
from app.models.schemas import SeedRequest, SeedResponse
from app.services.cache.query_cache import QueryCache

router = APIRouter(prefix="/seed", tags=["seed"])
logger = logging.getLogger(__name__)


@router.post("", response_model=SeedResponse)
def seed_data(
    body:    SeedRequest,
    payload: TokenPayload = Depends(require_admin),
    cache:   QueryCache   = Depends(get_query_cache),
) -> SeedResponse:
    """Seed an organisation's data from CSV files.

    Admin only. Creates a new org or overwrites data for an existing org
    identified by org_name. Idempotent — safe to run multiple times.
    """
    from app.core.database import SessionLocal
    from seed import run_seed  # seed.py at project root

    try:
        result = run_seed(
            data_dir=body.data_dir,
            org_name=body.org_name,
            admin_email=body.admin_email,
            admin_password=body.admin_password,
            db_session_factory=SessionLocal,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Seed failed")
        raise HTTPException(status_code=500, detail=f"Seed failed: {exc}")

    # Invalidate all cached queries for this org
    cache.invalidate_org(result["org_id"])
    logger.info("Seeded org %d (%s)", result["org_id"], body.org_name)

    return SeedResponse(**result)
