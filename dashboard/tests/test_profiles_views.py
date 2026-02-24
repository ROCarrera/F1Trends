from __future__ import annotations

from datetime import date

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Constructor, Driver, Race, Season, Winner


class ProfilesViewTests(TestCase):
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

    def test_profiles_index_no_2026_data(self) -> None:
        response = self.client.get(reverse("dashboard:profiles_index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/profiles_index.html")
        self.assertContains(response, "No 2026 data cached yet. Refresh seasons including 2026.")
        self.assertFalse(response.context["has_current_data"])

    def test_profiles_index_with_2026_data(self) -> None:
        season_2026 = Season.objects.create(year=2026)
        driver = Driver.objects.create(driver_id="alice_apex", given_name="Alice", family_name="Apex")
        constructor = Constructor.objects.create(constructor_id="apex_team", name="Apex Team")
        self._create_winner(
            season=season_2026,
            round_number=1,
            race_name="Race A",
            driver=driver,
            constructor=constructor,
        )

        response = self.client.get(reverse("dashboard:profiles_index"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_current_data"])
        self.assertContains(response, "Alice Apex")
        self.assertContains(response, "Apex Team")

    def test_driver_profile_page(self) -> None:
        season_2025 = Season.objects.create(year=2025)
        season_2026 = Season.objects.create(year=2026)
        driver = Driver.objects.create(driver_id="driver_alpha", given_name="Driver", family_name="Alpha")
        constructor = Constructor.objects.create(constructor_id="constructor_alpha", name="Constructor Alpha")

        self._create_winner(
            season=season_2025,
            round_number=1,
            race_name="Race 2025",
            driver=driver,
            constructor=constructor,
        )
        self._create_winner(
            season=season_2026,
            round_number=1,
            race_name="Race 2026",
            driver=driver,
            constructor=constructor,
        )

        response = self.client.get(reverse("dashboard:driver_profile", args=[driver.driver_id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/driver_profile.html")
        self.assertEqual(response.context["total_wins"], 2)
        self.assertEqual(response.context["wins_2026"], 1)
        self.assertIn("chart_data", response.context)
        self.assertContains(response, "Driver Alpha")

    def test_constructor_profile_page(self) -> None:
        season_2024 = Season.objects.create(year=2024)
        season_2026 = Season.objects.create(year=2026)
        driver = Driver.objects.create(driver_id="driver_beta", given_name="Driver", family_name="Beta")
        constructor = Constructor.objects.create(constructor_id="constructor_beta", name="Constructor Beta")

        self._create_winner(
            season=season_2024,
            round_number=1,
            race_name="Race 2024",
            driver=driver,
            constructor=constructor,
        )
        self._create_winner(
            season=season_2026,
            round_number=1,
            race_name="Race 2026",
            driver=driver,
            constructor=constructor,
        )

        response = self.client.get(
            reverse("dashboard:constructor_profile", args=[constructor.constructor_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/constructor_profile.html")
        self.assertEqual(response.context["total_wins"], 2)
        self.assertEqual(response.context["wins_2026"], 1)
        self.assertIn("chart_data", response.context)
        self.assertContains(response, "Constructor Beta")

    def test_profile_pages_return_404_when_not_found(self) -> None:
        driver_response = self.client.get(reverse("dashboard:driver_profile", args=["missing_driver"]))
        constructor_response = self.client.get(
            reverse("dashboard:constructor_profile", args=["missing_constructor"])
        )

        self.assertEqual(driver_response.status_code, 404)
        self.assertEqual(constructor_response.status_code, 404)
