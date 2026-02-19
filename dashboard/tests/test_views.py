from datetime import date
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from dashboard.models import Constructor, Driver, Race, Season, Winner
from dashboard.services.refresh import RefreshSummary
from dashboard.views import (
    _color,
    _constructor_wins_by_season,
    _driver_wins_by_season,
    _top_constructor_totals,
)


class DashboardViewTests(TestCase):
    def _seed_winner(
        self,
        *,
        season_year: int,
        round_number: int,
        race_name: str,
        driver_id: str,
        driver_name: tuple[str, str],
        constructor_id: str,
        constructor_name: str,
    ) -> None:
        season, _ = Season.objects.get_or_create(year=season_year)
        race = Race.objects.create(
            season=season,
            round=round_number,
            race_name=race_name,
            circuit_name=f"{race_name} Circuit",
            date=date(season_year, 3, min(28, round_number + 1)),
        )
        driver, _ = Driver.objects.get_or_create(
            driver_id=driver_id,
            defaults={
                "given_name": driver_name[0],
                "family_name": driver_name[1],
            },
        )
        constructor, _ = Constructor.objects.get_or_create(
            constructor_id=constructor_id,
            defaults={"name": constructor_name},
        )
        Winner.objects.create(race=race, driver=driver, constructor=constructor)

    def setUp(self) -> None:
        self._seed_winner(
            season_year=2023,
            round_number=1,
            race_name="Bahrain GP",
            driver_id="d_alpha",
            driver_name=("Alex", "Alpha"),
            constructor_id="c_red",
            constructor_name="Red Racing",
        )
        self._seed_winner(
            season_year=2023,
            round_number=2,
            race_name="Jeddah GP",
            driver_id="d_beta",
            driver_name=("Ben", "Beta"),
            constructor_id="c_blue",
            constructor_name="Blue Motorsport",
        )
        self._seed_winner(
            season_year=2024,
            round_number=1,
            race_name="Bahrain GP",
            driver_id="d_alpha",
            driver_name=("Alex", "Alpha"),
            constructor_id="c_red",
            constructor_name="Red Racing",
        )
        self._seed_winner(
            season_year=2024,
            round_number=2,
            race_name="Jeddah GP",
            driver_id="d_gamma",
            driver_name=("Gary", "Gamma"),
            constructor_id="c_red",
            constructor_name="Red Racing",
        )
        self._seed_winner(
            season_year=2025,
            round_number=1,
            race_name="Bahrain GP",
            driver_id="d_beta",
            driver_name=("Ben", "Beta"),
            constructor_id="c_blue",
            constructor_name="Blue Motorsport",
        )
        self._seed_winner(
            season_year=2025,
            round_number=2,
            race_name="Jeddah GP",
            driver_id="d_delta",
            driver_name=("Dan", "Delta"),
            constructor_id="c_green",
            constructor_name="Green Speed",
        )

    def test_index_view_renders_context_and_template(self) -> None:
        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/index.html")
        self.assertContains(response, "F1 Trends")
        self.assertEqual(response.context["stats"]["seasons"], 3)
        self.assertEqual(response.context["stats"]["races"], 6)
        self.assertEqual(response.context["stats"]["constructors"], 3)
        self.assertEqual(response.context["stats"]["drivers"], 4)
        self.assertEqual(response.context["constructor_line_chart"]["labels"], [2023, 2024, 2025])

    def test_index_view_no_data_state(self) -> None:
        Winner.objects.all().delete()
        Race.objects.all().delete()
        Season.objects.all().delete()

        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No race data cached yet")
        self.assertEqual(response.context["stats"]["races"], 0)
        self.assertEqual(response.context["constructor_line_chart"]["datasets"], [])

    def test_constructor_wins_by_season_helper(self) -> None:
        chart = _constructor_wins_by_season([2023, 2024, 2025])

        self.assertEqual(chart["labels"], [2023, 2024, 2025])
        self.assertGreaterEqual(len(chart["datasets"]), 3)
        self.assertEqual(chart["datasets"][0]["label"], "Red Racing")
        self.assertEqual(chart["datasets"][0]["data"], [1, 2, 0])

    def test_driver_wins_by_season_helper(self) -> None:
        chart = _driver_wins_by_season([2023, 2024, 2025])

        self.assertEqual(chart["labels"], [2023, 2024, 2025])
        self.assertGreaterEqual(len(chart["datasets"]), 3)
        dataset_labels = [dataset["label"] for dataset in chart["datasets"]]
        self.assertIn("Alex Alpha", dataset_labels)
        self.assertIn("Ben Beta", dataset_labels)

    def test_top_constructor_totals_helper(self) -> None:
        chart = _top_constructor_totals()

        self.assertEqual(chart["labels"][0], "Red Racing")
        self.assertEqual(chart["datasets"][0]["data"][0], 3)
        self.assertEqual(chart["datasets"][0]["label"], "Total Wins")

    def test_color_helper(self) -> None:
        self.assertEqual(_color(0), "rgba(15, 118, 110, 1.0)")
        self.assertEqual(_color(5, alpha=0.35), "rgba(15, 118, 110, 0.35)")

    def test_view_method_guards(self) -> None:
        home_post = self.client.post(reverse("dashboard:index"))
        refresh_get = self.client.get(reverse("dashboard:refresh"))
        self.assertEqual(home_post.status_code, 405)
        self.assertEqual(refresh_get.status_code, 405)

    @patch("dashboard.views.refresh_f1_data")
    def test_refresh_view_success_message(self, refresh_mock) -> None:
        summary = RefreshSummary(
            target_start=2024,
            target_end=2024,
            latest_available=2026,
            seasons_requested=1,
            seasons_processed=1,
            races_upserted=24,
            winners_upserted=24,
        )
        refresh_mock.return_value = summary

        response = self.client.post(reverse("dashboard:refresh"), follow=True)

        self.assertEqual(response.status_code, 200)
        messages = [str(msg) for msg in get_messages(response.wsgi_request)]
        self.assertTrue(any(summary.short_message() in msg for msg in messages))
        kwargs = refresh_mock.call_args.kwargs
        self.assertIsNone(kwargs["seasons_range"])
        self.assertTrue(callable(kwargs["log"]))

    @patch("dashboard.views.refresh_f1_data")
    def test_refresh_view_passes_seasons_range(self, refresh_mock) -> None:
        refresh_mock.return_value = RefreshSummary(
            target_start=2020,
            target_end=2021,
            latest_available=2026,
        )

        self.client.post(reverse("dashboard:refresh"), {"seasons": "2020:2021"}, follow=True)

        self.assertEqual(refresh_mock.call_args.kwargs["seasons_range"], "2020:2021")

    @patch("dashboard.views.refresh_f1_data")
    def test_refresh_view_warning_message_for_errors(self, refresh_mock) -> None:
        refresh_mock.return_value = RefreshSummary(
            target_start=2024,
            target_end=2024,
            latest_available=2026,
            seasons_requested=1,
            seasons_processed=1,
            races_upserted=24,
            winners_upserted=20,
            errors=["boom"],
        )

        response = self.client.post(reverse("dashboard:refresh"), follow=True)
        messages = [str(msg) for msg in get_messages(response.wsgi_request)]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("completed with 1 warnings" in msg.lower() for msg in messages))

    @patch("dashboard.views.refresh_f1_data", side_effect=ValueError("Bad season range"))
    def test_refresh_view_value_error_message(self, _refresh_mock) -> None:
        response = self.client.post(reverse("dashboard:refresh"), follow=True)
        messages = [str(msg) for msg in get_messages(response.wsgi_request)]

        self.assertEqual(response.status_code, 200)
        self.assertIn("Bad season range", messages)

    @patch("dashboard.views.refresh_f1_data", side_effect=RuntimeError("Network down"))
    def test_refresh_view_unexpected_error_message(self, _refresh_mock) -> None:
        response = self.client.post(reverse("dashboard:refresh"), follow=True)
        messages = [str(msg) for msg in get_messages(response.wsgi_request)]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(msg.startswith("Refresh failed:") for msg in messages))
