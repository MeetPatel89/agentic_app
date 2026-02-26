from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Run
from app.schemas import PaginatedRuns, RunDetail, RunSummary

router = APIRouter(prefix="/api")


@router.get("/runs", response_model=PaginatedRuns)
async def list_runs(
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PaginatedRuns:
    offset = (page - 1) * per_page
    total_q = await db.execute(select(func.count(Run.id)))
    total = total_q.scalar_one()

    q = select(Run).order_by(Run.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(q)
    runs = result.scalars().all()
    return PaginatedRuns(
        items=[RunSummary.model_validate(r) for r in runs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)) -> RunDetail:
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetail.model_validate(run)


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    await db.delete(run)
    await db.commit()
    return {"deleted": run_id}
