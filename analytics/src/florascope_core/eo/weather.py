from __future__ import annotations

import httpx
from datetime import date


class WeatherProvider:
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        date_from: date,
        date_to: date,
    ) -> dict[str, dict[str, float | None]]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": str(date_from),
            "end_date": str(date_to),
            "daily": "temperature_2m_mean,precipitation_sum",
            "timezone": "UTC",
            "models": "era5",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.get(self.endpoint, params=params)
            response.raise_for_status()
            daily = response.json().get("daily", {})

        return {
            day: {"temperature_c": temperature, "precipitation_mm": precipitation}
            for day, temperature, precipitation in zip(
                daily.get("time", []),
                daily.get("temperature_2m_mean", []),
                daily.get("precipitation_sum", []),
            )
        }
