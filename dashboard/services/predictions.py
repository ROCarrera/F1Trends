from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Count

from dashboard.models import Winner

RECENCY_WEIGHTS: tuple[float, ...] = (1.0, 0.8, 0.6, 0.4, 0.2)


def get_recent_seasons(n: int = 5) -> list[int]:
    if n <= 0:
        return []
    seasons = list(
        Winner.objects.values_list("race__season__year", flat=True)
        .distinct()
        .order_by("race__season__year")
    )
    return seasons[-n:]


def compute_driver_scores(seasons: list[int]) -> list[dict[str, Any]]:
    normalized_seasons = _normalize_seasons(seasons)
    if not normalized_seasons:
        return []

    rows = (
        Winner.objects.filter(race__season__year__in=normalized_seasons)
        .values(
            "driver_id",
            "driver__driver_id",
            "driver__given_name",
            "driver__family_name",
            "race__season__year",
        )
        .annotate(wins=Count("id"))
    )

    winners_by_season: dict[int, dict[int, int]] = defaultdict(dict)
    identities: dict[int, dict[str, str]] = {}
    for row in rows:
        driver_pk = row["driver_id"]
        season = row["race__season__year"]
        winners_by_season[driver_pk][season] = row["wins"]
        full_name = f"{row['driver__given_name']} {row['driver__family_name']}".strip()
        identities[driver_pk] = {
            "ref": row["driver__driver_id"],
            "name": full_name or row["driver__driver_id"],
        }

    season_weights = _build_season_weights(normalized_seasons)
    last_season = normalized_seasons[-1]
    previous_season = normalized_seasons[-2] if len(normalized_seasons) > 1 else None

    scores: list[dict[str, Any]] = []
    for driver_pk, season_wins in winners_by_season.items():
        weighted_score = sum(
            season_wins.get(season, 0) * season_weights[season] for season in normalized_seasons
        )
        last_wins = season_wins.get(last_season, 0)
        previous_wins = season_wins.get(previous_season, 0) if previous_season else 0
        trend_adjustment = 0.0
        if last_wins > previous_wins:
            trend_adjustment += 0.5
        if last_wins == 0:
            trend_adjustment -= 0.3

        wins_breakdown = [
            {"season": season, "wins": season_wins.get(season, 0)} for season in normalized_seasons
        ]
        scores.append(
            {
                "id": driver_pk,
                "entity_ref": identities[driver_pk]["ref"],
                "name": identities[driver_pk]["name"],
                "score": round(weighted_score + trend_adjustment, 3),
                "weighted_score": round(weighted_score, 3),
                "trend_adjustment": round(trend_adjustment, 3),
                "last_season_wins": last_wins,
                "previous_season_wins": previous_wins,
                "wins_by_season": [item["wins"] for item in wins_breakdown],
                "wins_breakdown": wins_breakdown,
            }
        )

    return sorted(scores, key=lambda item: (-item["score"], item["name"]))


def compute_constructor_scores(seasons: list[int]) -> list[dict[str, Any]]:
    normalized_seasons = _normalize_seasons(seasons)
    if not normalized_seasons:
        return []

    rows = (
        Winner.objects.filter(race__season__year__in=normalized_seasons)
        .values(
            "constructor_id",
            "constructor__constructor_id",
            "constructor__name",
            "race__season__year",
        )
        .annotate(wins=Count("id"))
    )

    winners_by_season: dict[int, dict[int, int]] = defaultdict(dict)
    identities: dict[int, dict[str, str]] = {}
    for row in rows:
        constructor_pk = row["constructor_id"]
        season = row["race__season__year"]
        winners_by_season[constructor_pk][season] = row["wins"]
        identities[constructor_pk] = {
            "ref": row["constructor__constructor_id"],
            "name": row["constructor__name"] or row["constructor__constructor_id"],
        }

    season_weights = _build_season_weights(normalized_seasons)
    last_season = normalized_seasons[-1]
    previous_season = normalized_seasons[-2] if len(normalized_seasons) > 1 else None

    scores: list[dict[str, Any]] = []
    for constructor_pk, season_wins in winners_by_season.items():
        weighted_score = sum(
            season_wins.get(season, 0) * season_weights[season] for season in normalized_seasons
        )
        last_wins = season_wins.get(last_season, 0)
        previous_wins = season_wins.get(previous_season, 0) if previous_season else 0
        trend_adjustment = 0.0
        if last_wins > previous_wins:
            trend_adjustment += 0.5
        if last_wins == 0:
            trend_adjustment -= 0.3

        wins_breakdown = [
            {"season": season, "wins": season_wins.get(season, 0)} for season in normalized_seasons
        ]
        scores.append(
            {
                "id": constructor_pk,
                "entity_ref": identities[constructor_pk]["ref"],
                "name": identities[constructor_pk]["name"],
                "score": round(weighted_score + trend_adjustment, 3),
                "weighted_score": round(weighted_score, 3),
                "trend_adjustment": round(trend_adjustment, 3),
                "last_season_wins": last_wins,
                "previous_season_wins": previous_wins,
                "wins_by_season": [item["wins"] for item in wins_breakdown],
                "wins_breakdown": wins_breakdown,
            }
        )

    return sorted(scores, key=lambda item: (-item["score"], item["name"]))


def compute_confidence(top_score: float, second_score: float) -> tuple[float, str]:
    top = max(float(top_score), 0.0)
    second = max(float(second_score), 0.0)
    confidence = max((top - second) / max(top, 1e-6), 0.0)

    if confidence >= 0.35:
        label = "High"
    elif confidence >= 0.15:
        label = "Medium"
    else:
        label = "Low"
    return round(confidence, 3), label


def _normalize_seasons(seasons: list[int]) -> list[int]:
    normalized = sorted(set(seasons))
    if len(normalized) > len(RECENCY_WEIGHTS):
        normalized = normalized[-len(RECENCY_WEIGHTS) :]
    return normalized


def _build_season_weights(seasons: list[int]) -> dict[int, float]:
    weighted: dict[int, float] = {}
    for idx, season in enumerate(reversed(seasons)):
        weight = RECENCY_WEIGHTS[idx] if idx < len(RECENCY_WEIGHTS) else RECENCY_WEIGHTS[-1]
        weighted[season] = weight
    return weighted

