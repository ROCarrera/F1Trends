from datetime import date
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from dashboard.services.jolpica import JolpicaAPIError, JolpicaClient, _to_date, _to_int


def _mock_response(*, payload, raise_exc: Exception | None = None) -> Mock:
    response = Mock()
    if raise_exc:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None
    if isinstance(payload, Exception):
        response.json.side_effect = payload
    else:
        response.json.return_value = payload
    return response


class JolpicaParsingTests(SimpleTestCase):
    def test_to_int(self) -> None:
        self.assertEqual(_to_int("42"), 42)
        self.assertEqual(_to_int(5), 5)
        self.assertIsNone(_to_int("x"))
        self.assertIsNone(_to_int(None))

    def test_to_date(self) -> None:
        self.assertEqual(_to_date("2024-03-02"), date(2024, 3, 2))
        self.assertEqual(_to_date(date(2024, 3, 2)), date(2024, 3, 2))
        self.assertIsNone(_to_date("invalid"))
        self.assertIsNone(_to_date(None))

    def test_fetch_seasons_filters_invalid_and_deduplicates(self) -> None:
        client = JolpicaClient(throttle_seconds=0)
        payload = {
            "MRData": {
                "SeasonTable": {
                    "Seasons": [
                        {"season": "2024"},
                        {"season": "2024"},
                        {"season": "2023"},
                        {"season": "invalid"},
                    ]
                }
            }
        }
        with patch.object(client, "_get_json", return_value=payload):
            seasons = client.fetch_seasons()

        self.assertEqual(seasons, [2023, 2024])

    def test_fetch_races_for_season_parses_payload(self) -> None:
        client = JolpicaClient(throttle_seconds=0)
        payload = {
            "MRData": {
                "RaceTable": {
                    "Races": [
                        {
                            "round": "1",
                            "raceName": "Bahrain Grand Prix",
                            "Circuit": {"circuitName": "Bahrain International Circuit"},
                            "date": "2024-03-02",
                        },
                        {
                            "round": "2",
                            "Circuit": {},
                            "date": "not-a-date",
                        },
                        {"round": "bad"},
                    ]
                }
            }
        }
        with patch.object(client, "_get_json", return_value=payload):
            races = client.fetch_races_for_season(2024)

        self.assertEqual(len(races), 2)
        self.assertEqual(races[0].race_name, "Bahrain Grand Prix")
        self.assertEqual(races[0].circuit_name, "Bahrain International Circuit")
        self.assertEqual(races[0].race_date, date(2024, 3, 2))
        self.assertEqual(races[1].race_name, "Round 2")
        self.assertEqual(races[1].circuit_name, "Unknown Circuit")
        self.assertIsNone(races[1].race_date)

    def test_fetch_race_winner_success_and_missing_cases(self) -> None:
        client = JolpicaClient(throttle_seconds=0)
        success_payload = {
            "MRData": {
                "RaceTable": {
                    "Races": [
                        {
                            "Results": [
                                {
                                    "Driver": {
                                        "driverId": "max_verstappen",
                                        "givenName": "Max",
                                        "familyName": "Verstappen",
                                        "code": "VER",
                                        "permanentNumber": "1",
                                    },
                                    "Constructor": {
                                        "constructorId": "red_bull",
                                        "name": "Red Bull",
                                        "nationality": "Austrian",
                                    },
                                }
                            ]
                        }
                    ]
                }
            }
        }
        with patch.object(client, "_get_json", return_value=success_payload):
            winner = client.fetch_race_winner(2024, 1)

        self.assertIsNotNone(winner)
        assert winner is not None
        self.assertEqual(winner.driver_id, "max_verstappen")
        self.assertEqual(winner.constructor_id, "red_bull")

        no_race_payload = {"MRData": {"RaceTable": {"Races": []}}}
        with patch.object(client, "_get_json", return_value=no_race_payload):
            self.assertIsNone(client.fetch_race_winner(2024, 1))

        no_result_payload = {"MRData": {"RaceTable": {"Races": [{"Results": []}]}}}
        with patch.object(client, "_get_json", return_value=no_result_payload):
            self.assertIsNone(client.fetch_race_winner(2024, 1))

        missing_ids_payload = {
            "MRData": {
                "RaceTable": {
                    "Races": [{"Results": [{"Driver": {}, "Constructor": {}}]}]
                }
            }
        }
        with patch.object(client, "_get_json", return_value=missing_ids_payload):
            self.assertIsNone(client.fetch_race_winner(2024, 1))


class JolpicaGetJsonTests(SimpleTestCase):
    def test_get_json_success_with_throttle(self) -> None:
        client = JolpicaClient(throttle_seconds=0.2, retries=2)
        client.session.get = Mock(return_value=_mock_response(payload={"ok": True}))

        with patch("dashboard.services.jolpica.time.sleep") as sleep_mock:
            payload = client._get_json("/endpoint")

        self.assertEqual(payload, {"ok": True})
        sleep_mock.assert_called_once_with(0.2)

    def test_get_json_retries_then_succeeds(self) -> None:
        client = JolpicaClient(throttle_seconds=0, retries=2)
        client.session.get = Mock(
            side_effect=[
                requests.RequestException("temporary"),
                _mock_response(payload={"ok": True}),
            ]
        )

        with patch("dashboard.services.jolpica.time.sleep") as sleep_mock:
            payload = client._get_json("/endpoint")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(client.session.get.call_count, 2)
        sleep_mock.assert_called_once_with(0.5)

    def test_get_json_raises_for_invalid_payload_shape(self) -> None:
        client = JolpicaClient(throttle_seconds=0, retries=1)
        client.session.get = Mock(return_value=_mock_response(payload=[]))

        with self.assertRaises(JolpicaAPIError):
            client._get_json("/endpoint")

    def test_get_json_raises_after_exhausting_retries(self) -> None:
        client = JolpicaClient(throttle_seconds=0, retries=2)
        client.session.get = Mock(
            side_effect=[
                requests.RequestException("first"),
                requests.RequestException("second"),
            ]
        )

        with patch("dashboard.services.jolpica.time.sleep") as sleep_mock:
            with self.assertRaises(JolpicaAPIError) as ctx:
                client._get_json("/endpoint")

        self.assertIn("Request failed for", str(ctx.exception))
        sleep_mock.assert_called_once_with(0.5)
