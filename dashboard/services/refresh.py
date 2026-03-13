from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from django.db import transaction
from django.db.models import Max

from dashboard.models import Constructor, Driver, Race, Season, Winner
from dashboard.services.jolpica import JolpicaAPIError, JolpicaClient, RacePayload

DEFAULT_START_SEASON = 2005
SEASONS_PATTERN = re.compile(r"^\s*(\d{4})\s*:\s*(\d{4})\s*$")

LogFn = Callable[[str], None]


@dataclass
class RefreshSummary:
    target_start: int
    target_end: int
    latest_available: int
    seasons_requested: int = 0
    seasons_processed: int = 0
    races_upserted: int = 0
    winners_upserted: int = 0
    errors: list[str] = field(default_factory=list)

    def short_message(self) -> str:
        return (
            f"Processed {self.seasons_processed}/{self.seasons_requested} seasons, "
            f"upserted {self.races_upserted} races and {self.winners_upserted} winners."
        )


def parse_season_range(raw_range: str | None, latest_available: int) -> tuple[int, int]:
    if not raw_range:
        return DEFAULT_START_SEASON, latest_available

    match = SEASONS_PATTERN.match(raw_range)
    if not match:
        raise ValueError("Invalid --seasons format. Expected START:END, for example 2005:2025.")

    start, end = int(match.group(1)), int(match.group(2))
    if start > end:
        raise ValueError("Invalid --seasons range. START must be less than or equal to END.")
    return start, end


def detect_latest_available_season_year(
    *,
    client: JolpicaClient,
    include_remote: bool = False,
) -> int:
    latest_cached = Season.objects.aggregate(latest_year=Max("year"))["latest_year"]
    if latest_cached is not None and not include_remote:
        return int(latest_cached)

    try:
        remote_seasons = client.fetch_seasons()
    except JolpicaAPIError:
        if latest_cached is not None:
            return int(latest_cached)
        raise

    if not remote_seasons:
        if latest_cached is not None:
            return int(latest_cached)
        raise ValueError("No seasons returned by Jolpica API.")

    latest_remote = max(remote_seasons)
    if latest_cached is None:
        return latest_remote
    return max(int(latest_cached), latest_remote)


def _available_seasons_set(*, client: JolpicaClient) -> set[int]:
    cached = set(Season.objects.values_list("year", flat=True))
    try:
        remote = set(client.fetch_seasons())
    except JolpicaAPIError:
        if cached:
            return cached
        raise

    if remote:
        return cached | remote
    if cached:
        return cached
    raise ValueError("No seasons returned by Jolpica API.")


def refresh_f1_data(
    *,
    seasons_range: str | None = None,
    include_latest: bool = False,
    log: LogFn | None = None,
) -> RefreshSummary:
    logger = log or (lambda _: None)
    client = JolpicaClient()
    latest_available = detect_latest_available_season_year(
        client=client,
        include_remote=include_latest,
    )
    target_start, parsed_target_end = parse_season_range(seasons_range, latest_available)
    target_end = latest_available if include_latest else parsed_target_end
    if target_start > target_end:
        raise ValueError("Invalid selected years. Start year must be less than or equal to end year.")

    available_set = _available_seasons_set(client=client)
    seasons_to_fetch = [year for year in range(target_start, target_end + 1) if year in available_set]
    if not seasons_to_fetch:
        raise ValueError(
            f"No available seasons found in selected range {target_start}:{target_end}."
        )

    summary = RefreshSummary(
        target_start=target_start,
        target_end=target_end,
        latest_available=latest_available,
        seasons_requested=len(seasons_to_fetch),
    )
    logger(
        f"Refreshing seasons {target_start}:{target_end} "
        f"(latest available: {latest_available})"
    )

    for season_year in seasons_to_fetch:
        logger(f"[{season_year}] Fetching races...")
        season_obj, _ = Season.objects.get_or_create(year=season_year)

        try:
            race_payloads = client.fetch_races_for_season(season_year)
        except JolpicaAPIError as exc:
            summary.errors.append(str(exc))
            logger(f"[{season_year}] Failed to fetch races: {exc}")
            continue

        if not race_payloads:
            logger(f"[{season_year}] No races returned, skipping.")
            summary.seasons_processed += 1
            continue

        for race_payload in race_payloads:
            _upsert_race_and_winner(
                season=season_obj,
                race_payload=race_payload,
                client=client,
                summary=summary,
                logger=logger,
            )

        summary.seasons_processed += 1
        logger(
            f"[{season_year}] Completed: {len(race_payloads)} races processed "
            f"(running winners total: {summary.winners_upserted})."
        )

    logger(summary.short_message())
    if summary.errors:
        logger(f"Completed with {len(summary.errors)} warnings/errors.")
    return summary


def _upsert_race_and_winner(
    *,
    season: Season,
    race_payload: RacePayload,
    client: JolpicaClient,
    summary: RefreshSummary,
    logger: LogFn,
) -> None:
    with transaction.atomic():
        race_obj, _ = Race.objects.update_or_create(
            season=season,
            round=race_payload.round,
            defaults={
                "race_name": race_payload.race_name,
                "circuit_name": race_payload.circuit_name,
                "date": race_payload.race_date,
            },
        )
        summary.races_upserted += 1

        try:
            winner_payload = client.fetch_race_winner(season.year, race_payload.round)
        except JolpicaAPIError as exc:
            summary.errors.append(str(exc))
            logger(f"[{season.year} R{race_payload.round}] Failed winner fetch: {exc}")
            return

        if winner_payload is None:
            logger(f"[{season.year} R{race_payload.round}] No winner payload returned.")
            return

        driver_obj, _ = Driver.objects.update_or_create(
            driver_id=winner_payload.driver_id,
            defaults={
                "given_name": winner_payload.given_name,
                "family_name": winner_payload.family_name,
                "code": winner_payload.code,
                "permanent_number": winner_payload.permanent_number,
            },
        )
        constructor_obj, _ = Constructor.objects.update_or_create(
            constructor_id=winner_payload.constructor_id,
            defaults={
                "name": winner_payload.constructor_name,
                "nationality": winner_payload.constructor_nationality,
            },
        )
        Winner.objects.update_or_create(
            race=race_obj,
            defaults={"driver": driver_obj, "constructor": constructor_obj},
        )
        summary.winners_upserted += 1
