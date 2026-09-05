from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...container import Container, container

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(state: Container = Depends(container)) -> list[dict]:
    return state.jobs.list_recent()


@router.get("/{job_id}")
def get_job(job_id: str, state: Container = Depends(container)) -> dict:
    job = state.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job не найден")
    return job
