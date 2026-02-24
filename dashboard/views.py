from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from django.contrib import messages
from django.db.models import Count, Max
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from dashboard.models import Constructor, Driver, Race, Season, Winner
from dashboard.services.legends import (
    ERA_CHOICES,
    get_season_queryset_by_era,
    parse_era,
    top_constructors,
    top_drivers,
)
from dashboard.services.predictions import (
    compute_confidence,
    compute_constructor_scores,
    compute_driver_scores,
    get_recent_seasons,
)
from dashboard.services.profiles import (
    constructor_summary,
    driver_summary,
    get_current_season_year,
    list_2026_constructors,
    list_2026_drivers,
)
from dashboard.services.refresh import refresh_f1_data

logger = logging.getLogger(__name__)


@require_GET
def index(request: HttpRequest) -> HttpResponse:
    seasons = list(Season.objects.order_by("year").values_list("year", flat=True))
    context = {
        "stats": {
            "seasons": Season.objects.count(),
            "races": Race.objects.count(),
            "constructors": Constructor.objects.count(),
            "drivers": Driver.objects.count(),
        },
        "last_refresh": Winner.objects.aggregate(last=Max("updated_at"))["last"],
        "constructor_line_chart": _constructor_wins_by_season(seasons),
        "driver_line_chart": _driver_wins_by_season(seasons),
        "constructor_bar_chart": _top_constructor_totals(),
    }
    return render(request, "dashboard/index.html", context)


@require_POST
def refresh_data(request: HttpRequest) -> HttpResponse:
    seasons_range = request.POST.get("seasons") or None
    try:
        summary = refresh_f1_data(
            seasons_range=seasons_range,
            log=lambda message: logger.info("[refresh] %s", message),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Refresh failed: {exc}")
    else:
        messages.success(request, summary.short_message())
        if summary.errors:
            messages.warning(
                request,
                f"Refresh completed with {len(summary.errors)} warnings. Check server logs for details.",
            )
    return redirect("dashboard:index")


@require_GET
def predictions(request: HttpRequest) -> HttpResponse:
    seasons_used = get_recent_seasons(n=5)
    if not seasons_used:
        return render(
            request,
            "dashboard/predictions.html",
            {
                "is_empty": True,
                "seasons_used": [],
                "seasons_range_label": "No seasons available",
                "driver_rows": [],
                "constructor_rows": [],
                "predicted_driver": None,
                "predicted_constructor": None,
                "driver_confidence": {"value": 0.0, "label": "Low"},
                "constructor_confidence": {"value": 0.0, "label": "Low"},
                "driver_score_chart": {"labels": [], "datasets": []},
                "constructor_score_chart": {"labels": [], "datasets": []},
            },
        )

    driver_rows = compute_driver_scores(seasons_used)[:10]
    constructor_rows = compute_constructor_scores(seasons_used)[:10]

    predicted_driver = driver_rows[0] if driver_rows else None
    predicted_constructor = constructor_rows[0] if constructor_rows else None

    driver_top_score = predicted_driver["score"] if predicted_driver else 0.0
    driver_second_score = driver_rows[1]["score"] if len(driver_rows) > 1 else 0.0
    constructor_top_score = predicted_constructor["score"] if predicted_constructor else 0.0
    constructor_second_score = (
        constructor_rows[1]["score"] if len(constructor_rows) > 1 else 0.0
    )

    driver_confidence_value, driver_confidence_label = compute_confidence(
        driver_top_score, driver_second_score
    )
    constructor_confidence_value, constructor_confidence_label = compute_confidence(
        constructor_top_score, constructor_second_score
    )

    driver_score_chart = {
        "labels": [row["name"] for row in driver_rows],
        "datasets": [
            {
                "label": "Driver Score",
                "data": [row["score"] for row in driver_rows],
                "backgroundColor": "#2563EB",
                "borderRadius": 8,
            }
        ],
    }
    constructor_score_chart = {
        "labels": [row["name"] for row in constructor_rows],
        "datasets": [
            {
                "label": "Constructor Score",
                "data": [row["score"] for row in constructor_rows],
                "backgroundColor": "#0F766E",
                "borderRadius": 8,
            }
        ],
    }

    context = {
        "is_empty": False,
        "seasons_used": seasons_used,
        "seasons_range_label": f"{seasons_used[0]}-{seasons_used[-1]}",
        "driver_rows": driver_rows,
        "constructor_rows": constructor_rows,
        "predicted_driver": predicted_driver,
        "predicted_constructor": predicted_constructor,
        "driver_confidence": {
            "value": driver_confidence_value,
            "label": driver_confidence_label,
        },
        "constructor_confidence": {
            "value": constructor_confidence_value,
            "label": constructor_confidence_label,
        },
        "driver_score_chart": driver_score_chart,
        "constructor_score_chart": constructor_score_chart,
    }
    return render(request, "dashboard/predictions.html", context)


@require_GET
def legends(request: HttpRequest) -> HttpResponse:
    selected_era = request.GET.get("era", "all")
    start_year, end_year, era_label = parse_era(selected_era)
    seasons_used = list(
        get_season_queryset_by_era(start=start_year, end=end_year).values_list("year", flat=True)
    )
    has_any_winners = Winner.objects.exists()
    driver_rows = top_drivers(limit=5, start=start_year, end=end_year)
    constructor_rows = top_constructors(limit=5, start=start_year, end=end_year)
    chart_rows = top_drivers(limit=10, start=start_year, end=end_year)
    filtered_empty = has_any_winners and (not seasons_used or not (driver_rows or constructor_rows))

    seasons_range_label = (
        f"{seasons_used[0]}-{seasons_used[-1]}" if seasons_used else f"{era_label} (no data)"
    )
    chart_data = {
        "labels": [row["name"] for row in chart_rows],
        "datasets": [
            {
                "label": "Driver Wins",
                "data": [row["total_wins"] for row in chart_rows],
                "backgroundColor": "#2563EB",
                "borderRadius": 8,
            }
        ],
    }

    context = {
        "selected_era": selected_era if selected_era in {item[0] for item in ERA_CHOICES} else "all",
        "era_options": [{"value": value, "label": label} for value, label in ERA_CHOICES],
        "era_label": era_label,
        "seasons_used": seasons_used,
        "seasons_range_label": seasons_range_label,
        "driver_rows": driver_rows,
        "constructor_rows": constructor_rows,
        "chart_data": chart_data,
        "is_empty": not has_any_winners,
        "is_filtered_empty": filtered_empty,
    }
    return render(request, "dashboard/legends.html", context)


@require_GET
def profiles_index(request: HttpRequest) -> HttpResponse:
    current_year = get_current_season_year()
    drivers = list_2026_drivers()
    constructors = list_2026_constructors()

    context = {
        "current_year": current_year,
        "drivers": drivers,
        "constructors": constructors,
        "has_current_data": bool(drivers or constructors),
    }
    return render(request, "dashboard/profiles_index.html", context)


@require_GET
def driver_profile(request: HttpRequest, driver_id: str) -> HttpResponse:
    try:
        summary = driver_summary(driver_id)
    except Driver.DoesNotExist as exc:
        raise Http404("Driver not found") from exc
    return render(request, "dashboard/driver_profile.html", summary)


@require_GET
def constructor_profile(request: HttpRequest, constructor_id: str) -> HttpResponse:
    try:
        summary = constructor_summary(constructor_id)
    except Constructor.DoesNotExist as exc:
        raise Http404("Constructor not found") from exc
    return render(request, "dashboard/constructor_profile.html", summary)


def _constructor_wins_by_season(seasons: list[int]) -> dict[str, Any]:
    top_constructors = list(
        Winner.objects.values("constructor_id", "constructor__name")
        .annotate(total_wins=Count("id"))
        .order_by("-total_wins", "constructor__name")[:5]
    )
    constructor_ids = [row["constructor_id"] for row in top_constructors]
    per_season = Winner.objects.filter(constructor_id__in=constructor_ids).values(
        "constructor_id", "race__season__year"
    ).annotate(wins=Count("id"))
    wins_map: dict[int, dict[int, int]] = defaultdict(dict)
    for row in per_season:
        wins_map[row["constructor_id"]][row["race__season__year"]] = row["wins"]

    datasets = []
    for idx, row in enumerate(top_constructors):
        constructor_id = row["constructor_id"]
        datasets.append(
            {
                "label": row["constructor__name"],
                "data": [wins_map[constructor_id].get(season, 0) for season in seasons],
                "borderColor": _color(idx),
                "backgroundColor": _color(idx, alpha=0.1),
                "pointRadius": 2,
                "pointHoverRadius": 4,
                "fill": False,
                "tension": 0.25,
            }
        )
    return {"labels": seasons, "datasets": datasets}


def _driver_wins_by_season(seasons: list[int]) -> dict[str, Any]:
    top_drivers = list(
        Winner.objects.values("driver_id", "driver__given_name", "driver__family_name")
        .annotate(total_wins=Count("id"))
        .order_by("-total_wins", "driver__family_name", "driver__given_name")[:5]
    )
    driver_ids = [row["driver_id"] for row in top_drivers]
    per_season = Winner.objects.filter(driver_id__in=driver_ids).values(
        "driver_id", "race__season__year"
    ).annotate(wins=Count("id"))
    wins_map: dict[int, dict[int, int]] = defaultdict(dict)
    for row in per_season:
        wins_map[row["driver_id"]][row["race__season__year"]] = row["wins"]

    datasets = []
    for idx, row in enumerate(top_drivers):
        driver_id = row["driver_id"]
        name = f"{row['driver__given_name']} {row['driver__family_name']}".strip()
        datasets.append(
            {
                "label": name or driver_id,
                "data": [wins_map[driver_id].get(season, 0) for season in seasons],
                "borderColor": _color(idx),
                "backgroundColor": _color(idx, alpha=0.1),
                "pointRadius": 2,
                "pointHoverRadius": 4,
                "fill": False,
                "tension": 0.25,
            }
        )
    return {"labels": seasons, "datasets": datasets}


def _top_constructor_totals() -> dict[str, Any]:
    rows = list(
        Winner.objects.values("constructor__name")
        .annotate(total_wins=Count("id"))
        .order_by("-total_wins", "constructor__name")[:10]
    )
    return {
        "labels": [row["constructor__name"] for row in rows],
        "datasets": [
            {
                "label": "Total Wins",
                "data": [row["total_wins"] for row in rows],
                "backgroundColor": "#0F766E",
                "borderRadius": 8,
            }
        ],
    }


def _color(index: int, *, alpha: float = 1.0) -> str:
    palette = [
        (15, 118, 110),
        (37, 99, 235),
        (234, 88, 12),
        (220, 38, 38),
        (107, 33, 168),
    ]
    r, g, b = palette[index % len(palette)]
    return f"rgba({r}, {g}, {b}, {alpha})"
