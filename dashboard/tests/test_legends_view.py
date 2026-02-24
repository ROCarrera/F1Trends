from __future__ import annotations

from datetime import date

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Constructor, Driver, Race, Season, Winner


class LegendsViewTests(TestCase):
    def _create_winner(
        self,
        *,
        season: Season,
        round_number: int,
        race_name: str,
        driver: Driver,
        constructor: Constructor,
    ) -> None:
        race = Race.objects.create(
            season=season,
            round=round_number,
            race_name=race_name,
            circuit_name=f"{race_name} Circuit",
            date=date(season.year, 3, min(28, round_number)),
        )
        Winner.objects.create(race=race, driver=driver, constructor=constructor)

    def test_legends_view_empty_state(self) -> None:
        response = self.client.get(reverse("dashboard:legends"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/legends.html")
        self.assertContains(response, "No cached data yet. Refresh data first.")
        self.assertTrue(response.context["is_empty"])

    def test_legends_view_with_data_context(self) -> None:
        season_2023 = Season.objects.create(year=2023)
        season_2024 = Season.objects.create(year=2024)

        driver_alpha = Driver.objects.create(
            driver_id="driver_alpha", given_name="Driver", family_name="Alpha"
        )
        driver_beta = Driver.objects.create(
            driver_id="driver_beta", given_name="Driver", family_name="Beta"
        )
        constructor_alpha = Constructor.objects.create(
            constructor_id="constructor_alpha", name="Constructor Alpha"
        )
        constructor_beta = Constructor.objects.create(
            constructor_id="constructor_beta", name="Constructor Beta"
        )

        self._create_winner(
            season=season_2023,
            round_number=1,
            race_name="Race A",
            driver=driver_alpha,
            constructor=constructor_alpha,
        )
        self._create_winner(
            season=season_2024,
            round_number=1,
            race_name="Race B",
            driver=driver_alpha,
            constructor=constructor_alpha,
        )
        self._create_winner(
            season=season_2024,
            round_number=2,
            race_name="Race C",
            driver=driver_beta,
            constructor=constructor_beta,
        )

        response = self.client.get(reverse("dashboard:legends") + "?era=2022-2026")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_empty"])
        self.assertFalse(response.context["is_filtered_empty"])
        self.assertEqual(response.context["selected_era"], "2022-2026")
        self.assertEqual(response.context["driver_rows"][0]["name"], "Driver Alpha")
        self.assertIn("driver_rows", response.context)
        self.assertIn("constructor_rows", response.context)
        self.assertIn("chart_data", response.context)
