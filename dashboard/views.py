from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from django.contrib import messages
from django.db.models import Count, Max
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from dashboard.models import Constructor, Driver, Race, Season, Winner
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
