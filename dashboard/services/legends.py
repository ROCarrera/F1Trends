from __future__ import annotations

from typing import Any

from django.db.models import Count, Max, Min, QuerySet

from dashboard.models import Season, Winner

ERA_CHOICES: tuple[tuple[str, str], ...] = (
    ("all", "All Eras"),
    ("1950-1979", "1950-1979"),
    ("1980-1999", "1980-1999"),
    ("2000-2013", "2000-2013"),
    ("2014-2021", "2014-2021"),
    ("2022-2026", "2022-2026"),
)


def parse_era(era_str: str | None) -> tuple[int | None, int | None, str]:
    era_value = (era_str or "all").strip()
    if era_value == "all":
        return None, None, "All Eras"

    allowed = {value for value, _ in ERA_CHOICES}
    if era_value not in allowed:
        return None, None, "All Eras"

    start_str, end_str = era_value.split("-")
    return int(start_str), int(end_str), era_value


def get_season_queryset_by_era(start: int | None, end: int | None) -> QuerySet[Season]:
    seasons = Season.objects.filter(races__winner__isnull=False)
    if start is not None:
        seasons = seasons.filter(year__gte=start)
    if end is not None:
        seasons = seasons.filter(year__lte=end)
    return seasons.distinct().order_by("year")


def top_drivers(
    *, limit: int = 5, start: int | None = None, end: int | None = None
) -> list[dict[str, Any]]:
    base_qs = _winner_queryset_by_era(start=start, end=end)
    rows = list(
        base_qs.values(
            "driver_id",
            "driver__driver_id",
            "driver__given_name",
            "driver__family_name",
        )
        .annotate(
            total_wins=Count("id"),
            first_year=Min("race__season__year"),
            last_year=Max("race__season__year"),
        )
        .order_by("-total_wins", "driver__family_name", "driver__given_name")[:limit]
    )
    if not rows:
        return []

    driver_ids = [row["driver_id"] for row in rows]
    peaks = _peak_seasons_for_entities(
        entity_type="driver", entity_ids=driver_ids, start=start, end=end
    )

    result: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        driver_id = row["driver_id"]
        peak_year, peak_wins = peaks.get(driver_id, (None, 0))
        name = f"{row['driver__given_name']} {row['driver__family_name']}".strip()
        result.append(
            {
                "rank": idx,
                "entity_id": row["driver__driver_id"],
                "name": name or row["driver__driver_id"],
                "total_wins": row["total_wins"],
                "peak_season_year": peak_year,
                "peak_season_wins": peak_wins,
                "active_start_year": row["first_year"],
                "active_end_year": row["last_year"],
                "active_years_label": f"{row['first_year']}-{row['last_year']}",
            }
        )
    return result


def top_constructors(
    *, limit: int = 5, start: int | None = None, end: int | None = None
) -> list[dict[str, Any]]:
    base_qs = _winner_queryset_by_era(start=start, end=end)
    rows = list(
        base_qs.values(
            "constructor_id",
            "constructor__constructor_id",
            "constructor__name",
        )
        .annotate(
            total_wins=Count("id"),
            first_year=Min("race__season__year"),
            last_year=Max("race__season__year"),
        )
        .order_by("-total_wins", "constructor__name")[:limit]
    )
    if not rows:
        return []

    constructor_ids = [row["constructor_id"] for row in rows]
    peaks = _peak_seasons_for_entities(
        entity_type="constructor",
        entity_ids=constructor_ids,
        start=start,
        end=end,
    )

    result: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        constructor_id = row["constructor_id"]
        peak_year, peak_wins = peaks.get(constructor_id, (None, 0))
        result.append(
            {
                "rank": idx,
                "entity_id": row["constructor__constructor_id"],
                "name": row["constructor__name"] or row["constructor__constructor_id"],
                "total_wins": row["total_wins"],
                "peak_season_year": peak_year,
                "peak_season_wins": peak_wins,
                "active_start_year": row["first_year"],
                "active_end_year": row["last_year"],
                "active_years_label": f"{row['first_year']}-{row['last_year']}",
            }
        )
    return result


def compute_peak_season_for_entity(
    entity_id: int,
    entity_type: str,
    start: int | None = None,
    end: int | None = None,
) -> tuple[int | None, int]:
    if entity_type not in {"driver", "constructor"}:
        raise ValueError("entity_type must be 'driver' or 'constructor'")

    base_qs = _winner_queryset_by_era(start=start, end=end)
    filter_key = "driver_id" if entity_type == "driver" else "constructor_id"
    grouped = (
        base_qs.filter(**{filter_key: entity_id})
        .values("race__season__year")
        .annotate(wins=Count("id"))
        .order_by("-wins", "race__season__year")
    )
    first = grouped.first()
    if not first:
        return None, 0
    return first["race__season__year"], first["wins"]


def _winner_queryset_by_era(start: int | None, end: int | None) -> QuerySet[Winner]:
    winners = Winner.objects.all()
    if start is not None:
        winners = winners.filter(race__season__year__gte=start)
    if end is not None:
        winners = winners.filter(race__season__year__lte=end)
    return winners


def _peak_seasons_for_entities(
    *,
    entity_type: str,
    entity_ids: list[int],
    start: int | None,
    end: int | None,
) -> dict[int, tuple[int, int]]:
    if not entity_ids:
        return {}

    if entity_type == "driver":
        group_field = "driver_id"
        filters = {"driver_id__in": entity_ids}
    elif entity_type == "constructor":
        group_field = "constructor_id"
        filters = {"constructor_id__in": entity_ids}
    else:
        raise ValueError("entity_type must be 'driver' or 'constructor'")

    rows = (
        _winner_queryset_by_era(start=start, end=end)
        .filter(**filters)
        .values(group_field, "race__season__year")
        .annotate(wins=Count("id"))
        .order_by(group_field, "-wins", "race__season__year")
    )
    peaks: dict[int, tuple[int, int]] = {}
    for row in rows:
        grouped_id = row[group_field]
        if grouped_id not in peaks:
            peaks[grouped_id] = (row["race__season__year"], row["wins"])
    return peaks
