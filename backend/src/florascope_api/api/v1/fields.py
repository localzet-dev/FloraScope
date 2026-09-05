from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...container import Container, container
from ...schemas import DiscoverPayload, FieldPayload

router = APIRouter(prefix="/fields", tags=["fields"])


@router.get("")
def list_fields(state: Container = Depends(container)) -> list[dict]:
    return state.fields.list()


@router.post("", status_code=201)
def create_field(payload: FieldPayload, state: Container = Depends(container)) -> dict:
    try:
        return state.fields.save(payload.name, payload.geometry)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/{field_id}")
def update_field(field_id: str, payload: FieldPayload, state: Container = Depends(container)) -> dict:
    if state.fields.get(field_id) is None:
        raise HTTPException(404, "Полигон не найден")
    try:
        return state.fields.save(payload.name, payload.geometry, field_id=field_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{field_id}")
def delete_field(field_id: str, state: Container = Depends(container)) -> dict:
    if not state.fields.delete(field_id):
        raise HTTPException(404, "Полигон не найден")
    return {"deleted": True}


@router.post("/discover")
def discover_fields(payload: DiscoverPayload, state: Container = Depends(container)) -> list[dict]:
    try:
        return state.field_service.discover(payload.bbox, payload.limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"OSM сейчас не отвечает: {exc}") from exc
