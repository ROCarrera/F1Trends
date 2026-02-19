from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

BASE_API_URL = "http://api.jolpi.ca/ergast/f1"


class JolpicaAPIError(RuntimeError):
    """Raised when Jolpica API calls fail after retries."""


@dataclass(frozen=True)
class RacePayload:
    season: int
    round: int
    race_name: str
    circuit_name: str
    race_date: date | None


@dataclass(frozen=True)
class WinnerPayload:
    driver_id: str
    given_name: str
    family_name: str
    code: str | None
    permanent_number: str | None
    constructor_id: str
    constructor_name: str
    constructor_nationality: str | None


class JolpicaClient:
    def __init__(
        self,
        *,
        base_url: str = BASE_API_URL,
        timeout_seconds: int = 12,
        retries: int = 3,
        throttle_seconds: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.throttle_seconds = throttle_seconds
        self.session = requests.Session()

    def fetch_seasons(self) -> list[int]:
        payload = self._get_json("/seasons.json", params={"limit": 1000})
        raw_seasons = (
            payload.get("MRData", {})
            .get("SeasonTable", {})
            .get("Seasons", [])
        )
        years: list[int] = []
        for raw in raw_seasons:
            year = _to_int(raw.get("season"))
            if year is not None:
                years.append(year)
        return sorted(set(years))

    def fetch_races_for_season(self, season: int) -> list[RacePayload]:
        payload = self._get_json(f"/{season}.json", params={"limit": 1000})
        raw_races = (
            payload.get("MRData", {})
            .get("RaceTable", {})
            .get("Races", [])
        )
        races: list[RacePayload] = []
        for raw_race in raw_races:
            round_number = _to_int(raw_race.get("round"))
            if round_number is None:
                continue
            race_name = str(raw_race.get("raceName") or f"Round {round_number}")
            circuit_name = str(
                raw_race.get("Circuit", {}).get("circuitName") or "Unknown Circuit"
            )
            races.append(
                RacePayload(
                    season=season,
                    round=round_number,
                    race_name=race_name,
                    circuit_name=circuit_name,
                    race_date=_to_date(raw_race.get("date")),
                )
            )
        return races

    def fetch_race_winner(self, season: int, round_number: int) -> WinnerPayload | None:
        payload = self._get_json(f"/{season}/{round_number}/results/1.json")
        races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races:
            return None

        results = races[0].get("Results", [])
        if not results:
            return None

        winner = results[0]
        raw_driver = winner.get("Driver", {})
        raw_constructor = winner.get("Constructor", {})

        driver_id = raw_driver.get("driverId")
        constructor_id = raw_constructor.get("constructorId")
        if not driver_id or not constructor_id:
            return None

        return WinnerPayload(
            driver_id=str(driver_id),
            given_name=str(raw_driver.get("givenName") or ""),
            family_name=str(raw_driver.get("familyName") or ""),
            code=raw_driver.get("code"),
            permanent_number=raw_driver.get("permanentNumber"),
            constructor_id=str(constructor_id),
            constructor_name=str(raw_constructor.get("name") or constructor_id),
            constructor_nationality=raw_constructor.get("nationality"),
        )

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_seconds)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise JolpicaAPIError(f"Unexpected JSON payload shape from {url}")
                if self.throttle_seconds > 0:
                    time.sleep(self.throttle_seconds)
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
                time.sleep(0.5 * attempt)
        raise JolpicaAPIError(f"Request failed for {url}: {last_error}") from last_error


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None

