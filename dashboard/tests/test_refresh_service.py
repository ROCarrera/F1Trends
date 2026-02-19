from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from dashboard.models import Constructor, Driver, Race, Season, Winner
from dashboard.services.jolpica import JolpicaAPIError, RacePayload, WinnerPayload
from dashboard.services.refresh import (
    DEFAULT_START_SEASON,
    RefreshSummary,
    parse_season_range,
    refresh_f1_data,
)


class ParseSeasonRangeTests(TestCase):
    def test_default_range_uses_latest_available(self) -> None:
        self.assertEqual(
            parse_season_range(None, latest_available=2026),
            (DEFAULT_START_SEASON, 2026),
        )

    def test_valid_range(self) -> None:
        self.assertEqual(parse_season_range("2018:2024", latest_available=2026), (2018, 2024))

    def test_invalid_format_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_season_range("2020-2024", latest_available=2026)

    def test_invalid_order_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_season_range("2025:2024", latest_available=2026)


class RefreshServiceTests(TestCase):
    def _winner_payload(self) -> WinnerPayload:
        return WinnerPayload(
            driver_id="max_verstappen",
            given_name="Max",
            family_name="Verstappen",
            code="VER",
            permanent_number="1",
            constructor_id="red_bull",
            constructor_name="Red Bull",
            constructor_nationality="Austrian",
        )

    def _race_payload(self) -> RacePayload:
        return RacePayload(
            season=2024,
            round=1,
            race_name="Bahrain Grand Prix",
            circuit_name="Bahrain International Circuit",
            race_date=date(2024, 3, 2),
        )

    @patch("dashboard.services.refresh.JolpicaClient")
    def test_refresh_success_and_idempotent_upserts(self, client_cls: Mock) -> None:
        client = client_cls.return_value
        client.fetch_seasons.return_value = [2023, 2024]
        client.fetch_races_for_season.return_value = [self._race_payload()]
        client.fetch_race_winner.return_value = self._winner_payload()

        logs: list[str] = []
        summary_1 = refresh_f1_data(seasons_range="2024:2024", log=logs.append)

        self.assertEqual(summary_1.seasons_processed, 1)
        self.assertEqual(summary_1.races_upserted, 1)
        self.assertEqual(summary_1.winners_upserted, 1)
        self.assertEqual(Season.objects.count(), 1)
        self.assertEqual(Race.objects.count(), 1)
        self.assertEqual(Winner.objects.count(), 1)
        self.assertEqual(Driver.objects.count(), 1)
        self.assertEqual(Constructor.objects.count(), 1)
        self.assertTrue(any("Refreshing seasons 2024:2024" in log for log in logs))

        summary_2 = refresh_f1_data(seasons_range="2024:2024")
        self.assertEqual(summary_2.seasons_processed, 1)
        self.assertEqual(Race.objects.count(), 1)
        self.assertEqual(Winner.objects.count(), 1)
        self.assertEqual(Driver.objects.count(), 1)
        self.assertEqual(Constructor.objects.count(), 1)

    @patch("dashboard.services.refresh.JolpicaClient")
    def test_refresh_raises_when_no_seasons(self, client_cls: Mock) -> None:
        client_cls.return_value.fetch_seasons.return_value = []

        with self.assertRaises(ValueError):
            refresh_f1_data()

    @patch("dashboard.services.refresh.JolpicaClient")
    def test_refresh_raises_when_selected_range_not_available(self, client_cls: Mock) -> None:
        client_cls.return_value.fetch_seasons.return_value = [1990, 1991]

        with self.assertRaises(ValueError):
            refresh_f1_data(seasons_range="2024:2025")

    @patch("dashboard.services.refresh.JolpicaClient")
    def test_refresh_handles_season_race_fetch_error(self, client_cls: Mock) -> None:
        client = client_cls.return_value
        client.fetch_seasons.return_value = [2024]
        client.fetch_races_for_season.side_effect = JolpicaAPIError("race failure")

        summary = refresh_f1_data(seasons_range="2024:2024")

        self.assertEqual(summary.seasons_processed, 0)
        self.assertEqual(summary.races_upserted, 0)
        self.assertEqual(summary.winners_upserted, 0)
        self.assertEqual(len(summary.errors), 1)
        self.assertEqual(Race.objects.count(), 0)

    @patch("dashboard.services.refresh.JolpicaClient")
    def test_refresh_handles_empty_race_list(self, client_cls: Mock) -> None:
        client = client_cls.return_value
        client.fetch_seasons.return_value = [2024]
        client.fetch_races_for_season.return_value = []

        summary = refresh_f1_data(seasons_range="2024:2024")

        self.assertEqual(summary.seasons_processed, 1)
        self.assertEqual(summary.races_upserted, 0)
        self.assertEqual(summary.winners_upserted, 0)
        self.assertEqual(Winner.objects.count(), 0)

    @patch("dashboard.services.refresh.JolpicaClient")
    def test_refresh_handles_winner_fetch_error(self, client_cls: Mock) -> None:
        client = client_cls.return_value
        client.fetch_seasons.return_value = [2024]
        client.fetch_races_for_season.return_value = [self._race_payload()]
        client.fetch_race_winner.side_effect = JolpicaAPIError("winner failure")

        summary = refresh_f1_data(seasons_range="2024:2024")

        self.assertEqual(summary.races_upserted, 1)
        self.assertEqual(summary.winners_upserted, 0)
        self.assertEqual(len(summary.errors), 1)
        self.assertEqual(Race.objects.count(), 1)
        self.assertEqual(Winner.objects.count(), 0)

    @patch("dashboard.services.refresh.JolpicaClient")
    def test_refresh_handles_missing_winner_payload(self, client_cls: Mock) -> None:
        client = client_cls.return_value
        client.fetch_seasons.return_value = [2024]
        client.fetch_races_for_season.return_value = [self._race_payload()]
        client.fetch_race_winner.return_value = None

        summary = refresh_f1_data(seasons_range="2024:2024")

        self.assertEqual(summary.races_upserted, 1)
        self.assertEqual(summary.winners_upserted, 0)
        self.assertEqual(summary.errors, [])
        self.assertEqual(Race.objects.count(), 1)
        self.assertEqual(Winner.objects.count(), 0)

    def test_refresh_summary_short_message(self) -> None:
        summary = RefreshSummary(
            target_start=2024,
            target_end=2024,
            latest_available=2026,
            seasons_requested=1,
            seasons_processed=1,
            races_upserted=24,
            winners_upserted=24,
        )
        self.assertEqual(
            summary.short_message(),
            "Processed 1/1 seasons, upserted 24 races and 24 winners.",
        )
