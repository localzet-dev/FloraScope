from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field, model_validator


class FieldPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    geometry: dict


class DiscoverPayload(BaseModel):
    bbox: tuple[float, float, float, float]
    limit: int = Field(default=30, ge=1, le=60)


class CompetitionPayload(BaseModel):
    fast: bool = True


class AnalysisPayload(BaseModel):
    field_id: str
    date_from: date
    date_to: date
    history_years: int = Field(default=3, ge=2, le=8)
    max_cloud_cover: float = Field(default=35.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_period(self) -> "AnalysisPayload":
        if self.date_from > self.date_to:
            raise ValueError("date_from должен быть <= date_to")
        if self.date_from.year != self.date_to.year:
            raise ValueError("Для live-анализа выберите один календарный сезон")
        if (self.date_to - self.date_from).days < 30:
            raise ValueError("Сезон короче 30 дней мало что покажет")
        return self
