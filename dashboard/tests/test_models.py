from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from dashboard.models import Constructor, Driver, Race, Season, Winner


class ModelTests(TestCase):
    def setUp(self) -> None:
        self.season = Season.objects.create(year=2024)
        self.race = Race.objects.create(
            season=self.season,
            round=1,
            race_name="Bahrain Grand Prix",
            circuit_name="Bahrain International Circuit",
            date=date(2024, 3, 2),
        )
        self.driver = Driver.objects.create(
            driver_id="max_verstappen",
            given_name="Max",
            family_name="Verstappen",
            code="VER",
            permanent_number="1",
        )
        self.constructor = Constructor.objects.create(
            constructor_id="red_bull",
            name="Red Bull",
            nationality="Austrian",
        )
        self.winner = Winner.objects.create(
            race=self.race,
            driver=self.driver,
            constructor=self.constructor,
        )

    def test_model_string_representations(self) -> None:
        self.assertEqual(str(self.season), "2024")
        self.assertEqual(str(self.race), "2024 R1 Bahrain Grand Prix")
        self.assertEqual(str(self.driver), "Max Verstappen")
        self.assertEqual(str(self.constructor), "Red Bull")
        self.assertIn("Bahrain Grand Prix", str(self.winner))
        self.assertIn("Max Verstappen", str(self.winner))

    def test_race_unique_constraint_per_season_round(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Race.objects.create(
                    season=self.season,
                    round=1,
                    race_name="Duplicate",
                    circuit_name="Some Circuit",
                )

    def test_model_ordering(self) -> None:
        season_2023 = Season.objects.create(year=2023)
        Race.objects.create(
            season=season_2023,
            round=3,
            race_name="Race C",
            circuit_name="Circuit C",
        )
        Race.objects.create(
            season=season_2023,
            round=1,
            race_name="Race A",
            circuit_name="Circuit A",
        )

        ordered_years = list(Season.objects.values_list("year", flat=True))
        self.assertEqual(ordered_years, [2023, 2024])

        ordered_rounds_2023 = list(
            Race.objects.filter(season=season_2023).values_list("round", flat=True)
        )
        self.assertEqual(ordered_rounds_2023, [1, 3])
