from __future__ import annotations

from datetime import date

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Constructor, Driver, Race, Season, Winner


class PredictionsViewTests(TestCase):
    def _create_wins(
        self,
        *,
        season: Season,
        driver: Driver,
        constructor: Constructor,
        wins: int,
        round_start: int,
    ) -> None:
        for idx in range(wins):
            race = Race.objects.create(
                season=season,
                round=round_start + idx,
                race_name=f"Race {season.year}-{round_start + idx}",
                circuit_name=f"Circuit {season.year}",
                date=date(season.year, 3, min(28, round_start + idx)),
            )
            Winner.objects.create(race=race, driver=driver, constructor=constructor)

    def test_predictions_page_empty_state(self) -> None:
        response = self.client.get(reverse("dashboard:predictions"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/predictions.html")
        self.assertContains(response, "No winner history available yet")
        self.assertTrue(response.context["is_empty"])

    def test_predictions_page_with_data_has_expected_context(self) -> None:
        season_2024 = Season.objects.create(year=2024)
        season_2025 = Season.objects.create(year=2025)

        driver_a = Driver.objects.create(
            driver_id="driver_a", given_name="Driver", family_name="Alpha"
        )
        driver_b = Driver.objects.create(
            driver_id="driver_b", given_name="Driver", family_name="Beta"
        )
        constructor_a = Constructor.objects.create(
            constructor_id="constructor_a", name="Constructor Alpha"
        )
        constructor_b = Constructor.objects.create(
            constructor_id="constructor_b", name="Constructor Beta"
        )

        self._create_wins(
            season=season_2024,
            driver=driver_a,
            constructor=constructor_a,
            wins=1,
            round_start=1,
        )
        self._create_wins(
            season=season_2024,
            driver=driver_b,
            constructor=constructor_b,
            wins=2,
            round_start=2,
        )
        self._create_wins(
            season=season_2025,
            driver=driver_a,
            constructor=constructor_a,
            wins=3,
            round_start=1,
        )
        self._create_wins(
            season=season_2025,
            driver=driver_b,
            constructor=constructor_b,
            wins=1,
            round_start=4,
        )

        response = self.client.get(reverse("dashboard:predictions"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_empty"])
        self.assertIn("driver_rows", response.context)
        self.assertIn("constructor_rows", response.context)
        self.assertIn("predicted_driver", response.context)
        self.assertIn("predicted_constructor", response.context)
        self.assertEqual(response.context["predicted_driver"]["name"], "Driver Alpha")
        self.assertEqual(response.context["predicted_constructor"]["name"], "Constructor Alpha")
        self.assertEqual(response.context["seasons_used"], [2024, 2025])
        self.assertContains(response, "This is a heuristic model based on historical win counts")
