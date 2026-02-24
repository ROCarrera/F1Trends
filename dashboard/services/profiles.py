from __future__ import annotations

from typing import Any

from django.db.models import Count

from dashboard.models import Constructor, Driver, Season, Winner


def get_current_season_year(default: int = 2026) -> int:
    return default


def list_2026_drivers() -> list[Driver]:
    current_year = get_current_season_year()
    return list(
        Driver.objects.filter(wins__race__season__year=current_year)
        .distinct()
        .order_by("family_name", "given_name")
    )


def list_2026_constructors() -> list[Constructor]:
    current_year = get_current_season_year()
    return list(
        Constructor.objects.filter(wins__race__season__year=current_year)
        .distinct()
        .order_by("name")
    )


def driver_summary(driver_id: str) -> dict[str, Any]:
    driver = Driver.objects.get(driver_id=driver_id)
    current_year = get_current_season_year()
    winners_qs = Winner.objects.filter(driver=driver)

    total_wins = winners_qs.count()
    wins_current_season = winners_qs.filter(race__season__year=current_year).count()

    season_rows = winners_qs.values("race__season__year").annotate(wins=Count("id"))
    wins_map = {row["race__season__year"]: row["wins"] for row in season_rows}
    seasons = _all_winner_seasons()
    wins_series = [wins_map.get(season, 0) for season in seasons]

    recent_wins = list(
        winners_qs.select_related("race__season", "constructor")
        .order_by("-race__season__year", "-race__round")[:10]
        .values(
            "race__season__year",
            "race__round",
            "race__race_name",
            "constructor__name",
        )
    )

    chart_data = {
        "labels": seasons,
        "datasets": [
            {
                "label": "Wins",
                "data": wins_series,
                "borderColor": "#2563EB",
                "backgroundColor": "rgba(37, 99, 235, 0.15)",
                "pointRadius": 2,
                "pointHoverRadius": 4,
                "fill": True,
                "tension": 0.3,
            }
        ],
    }

    return {
        "driver": driver,
        "total_wins": total_wins,
        "wins_2026": wins_current_season,
        "seasons": seasons,
        "wins_series": wins_series,
        "chart_data": chart_data,
        "recent_wins": recent_wins,
        "current_year": current_year,
    }


def constructor_summary(constructor_id: str) -> dict[str, Any]:
    constructor = Constructor.objects.get(constructor_id=constructor_id)
    current_year = get_current_season_year()
    winners_qs = Winner.objects.filter(constructor=constructor)

    total_wins = winners_qs.count()
    wins_current_season = winners_qs.filter(race__season__year=current_year).count()

    season_rows = winners_qs.values("race__season__year").annotate(wins=Count("id"))
    wins_map = {row["race__season__year"]: row["wins"] for row in season_rows}
    seasons = _all_winner_seasons()
    wins_series = [wins_map.get(season, 0) for season in seasons]

    recent_wins = list(
        winners_qs.select_related("race__season", "driver")
        .order_by("-race__season__year", "-race__round")[:10]
        .values(
            "race__season__year",
            "race__round",
            "race__race_name",
            "driver__given_name",
            "driver__family_name",
        )
    )

    chart_data = {
        "labels": seasons,
        "datasets": [
            {
                "label": "Wins",
                "data": wins_series,
                "borderColor": "#0F766E",
                "backgroundColor": "rgba(15, 118, 110, 0.15)",
                "pointRadius": 2,
                "pointHoverRadius": 4,
                "fill": True,
                "tension": 0.3,
            }
        ],
    }

    return {
        "constructor": constructor,
        "total_wins": total_wins,
        "wins_2026": wins_current_season,
        "seasons": seasons,
        "wins_series": wins_series,
        "chart_data": chart_data,
        "recent_wins": recent_wins,
        "current_year": current_year,
    }


def _all_winner_seasons() -> list[int]:
    return list(
        Season.objects.filter(races__winner__isnull=False)
        .distinct()
        .order_by("year")
        .values_list("year", flat=True)
    )

