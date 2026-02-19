from __future__ import annotations

from collections import defaultdict
from datetime import date

from django.test import TestCase

from dashboard.models import Constructor, Driver, Race, Season, Winner
from dashboard.services.predictions import (
    compute_confidence,
    compute_constructor_scores,
    compute_driver_scores,
    get_recent_seasons,
)


class PredictionsServiceTests(TestCase):
    def setUp(self) -> None:
        self.rounds: dict[int, int] = defaultdict(int)
        self.seasons: dict[int, Season] = {}
        for year in (2020, 2021, 2022, 2023, 2024, 2025):
            self.seasons[year] = Season.objects.create(year=year)

        self.driver_a = Driver.objects.create(
            driver_id="ada_apex", given_name="Ada", family_name="Apex"
        )
        self.driver_b = Driver.objects.create(
            driver_id="ben_bolt", given_name="Ben", family_name="Bolt"
        )
        self.driver_c = Driver.objects.create(
            driver_id="cora_calm", given_name="Cora", family_name="Calm"
        )
        self.driver_d = Driver.objects.create(
            driver_id="aaron_able", given_name="Aaron", family_name="Able"
        )
        self.driver_e = Driver.objects.create(
            driver_id="zack_zed", given_name="Zack", family_name="Zed"
        )

        self.constructor_a = Constructor.objects.create(
            constructor_id="apex_works", name="Apex Works"
        )
        self.constructor_b = Constructor.objects.create(
            constructor_id="bolt_gp", name="Bolt GP"
        )
        self.constructor_c = Constructor.objects.create(
            constructor_id="calm_speed", name="Calm Speed"
        )
        self.constructor_d = Constructor.objects.create(
            constructor_id="alpha_autosport", name="Alpha Autosport"
        )
        self.constructor_e = Constructor.objects.create(
            constructor_id="zulu_racing", name="Zulu Racing"
        )

        driver_patterns = {
            2021: [(self.driver_a, self.constructor_a, 1), (self.driver_b, self.constructor_b, 2), (self.driver_c, self.constructor_c, 3)],
            2022: [(self.driver_a, self.constructor_a, 2), (self.driver_b, self.constructor_b, 2)],
            2023: [(self.driver_a, self.constructor_a, 3), (self.driver_b, self.constructor_b, 2)],
            2024: [(self.driver_a, self.constructor_a, 4), (self.driver_b, self.constructor_b, 2)],
            2025: [
                (self.driver_a, self.constructor_a, 5),
                (self.driver_b, self.constructor_b, 2),
                (self.driver_d, self.constructor_d, 1),
                (self.driver_e, self.constructor_e, 1),
            ],
        }
        for year, season_winners in driver_patterns.items():
            for driver, constructor, wins in season_winners:
                self._create_wins(year=year, driver=driver, constructor=constructor, count=wins)

    def _create_wins(
        self, *, year: int, driver: Driver, constructor: Constructor, count: int
    ) -> None:
        for _ in range(count):
            self.rounds[year] += 1
            round_number = self.rounds[year]
            race = Race.objects.create(
                season=self.seasons[year],
                round=round_number,
                race_name=f"Race {year}-{round_number}",
                circuit_name=f"Circuit {year}",
                date=date(year, 3, min(28, round_number)),
            )
            Winner.objects.create(race=race, driver=driver, constructor=constructor)

    def test_get_recent_seasons_uses_winner_history(self) -> None:
        self.assertEqual(get_recent_seasons(n=5), [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(get_recent_seasons(n=3), [2023, 2024, 2025])

    def test_compute_driver_scores_applies_weights_and_trend(self) -> None:
        scores = compute_driver_scores([2021, 2022, 2023, 2024, 2025])
        top = next(row for row in scores if row["name"] == "Ada Apex")

        self.assertEqual(scores[0]["name"], "Ada Apex")
        self.assertAlmostEqual(top["weighted_score"], 11.0)
        self.assertAlmostEqual(top["trend_adjustment"], 0.5)
        self.assertAlmostEqual(top["score"], 11.5)
        self.assertEqual(top["last_season_wins"], 5)
        self.assertEqual(top["previous_season_wins"], 4)
        self.assertEqual(top["wins_by_season"], [1, 2, 3, 4, 5])

    def test_compute_driver_scores_applies_last_season_zero_penalty(self) -> None:
        scores = compute_driver_scores([2021, 2022, 2023, 2024, 2025])
        cora = next(row for row in scores if row["name"] == "Cora Calm")

        self.assertEqual(cora["last_season_wins"], 0)
        self.assertAlmostEqual(cora["weighted_score"], 0.6)
        self.assertAlmostEqual(cora["trend_adjustment"], -0.3)
        self.assertAlmostEqual(cora["score"], 0.3)

    def test_compute_constructor_scores_and_deterministic_tie_breaking(self) -> None:
        scores = compute_constructor_scores([2021, 2022, 2023, 2024, 2025])

        self.assertEqual(scores[0]["name"], "Apex Works")
        tie_names = [row["name"] for row in scores]
        self.assertLess(tie_names.index("Alpha Autosport"), tie_names.index("Zulu Racing"))

    def test_compute_confidence_label_mapping(self) -> None:
        self.assertEqual(compute_confidence(10, 5), (0.5, "High"))
        self.assertEqual(compute_confidence(10, 8), (0.2, "Medium"))
        self.assertEqual(compute_confidence(10, 9.3), (0.07, "Low"))
        self.assertEqual(compute_confidence(0, 0), (0.0, "Low"))
