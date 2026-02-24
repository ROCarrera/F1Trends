from __future__ import annotations

from collections import defaultdict
from datetime import date

from django.test import TestCase

from dashboard.models import Constructor, Driver, Race, Season, Winner
from dashboard.services.legends import (
    compute_peak_season_for_entity,
    get_season_queryset_by_era,
    parse_era,
    top_constructors,
    top_drivers,
)


class LegendsServiceTests(TestCase):
    def setUp(self) -> None:
        self.rounds: dict[int, int] = defaultdict(int)
        self.seasons: dict[int, Season] = {}
        for year in (1978, 1985, 2016, 2020, 2024):
            self.seasons[year] = Season.objects.create(year=year)

        self.driver_apex = Driver.objects.create(
            driver_id="alice_apex", given_name="Alice", family_name="Apex"
        )
        self.driver_bolt = Driver.objects.create(
            driver_id="bob_bolt", given_name="Bob", family_name="Bolt"
        )
        self.driver_comet = Driver.objects.create(
            driver_id="cara_comet", given_name="Cara", family_name="Comet"
        )

        self.constructor_apex = Constructor.objects.create(
            constructor_id="apex_team", name="Apex Team"
        )
        self.constructor_bolt = Constructor.objects.create(
            constructor_id="bolt_team", name="Bolt Team"
        )
        self.constructor_comet = Constructor.objects.create(
            constructor_id="comet_team", name="Comet Team"
        )

        self._create_wins(1978, self.driver_apex, self.constructor_apex, 2)
        self._create_wins(1985, self.driver_bolt, self.constructor_bolt, 3)
        self._create_wins(2016, self.driver_apex, self.constructor_apex, 4)
        self._create_wins(2016, self.driver_bolt, self.constructor_bolt, 1)
        self._create_wins(2020, self.driver_apex, self.constructor_apex, 1)
        self._create_wins(2020, self.driver_comet, self.constructor_comet, 5)
        self._create_wins(2024, self.driver_bolt, self.constructor_bolt, 4)
        self._create_wins(2024, self.driver_comet, self.constructor_comet, 2)

    def _create_wins(
        self, year: int, driver: Driver, constructor: Constructor, count: int
    ) -> None:
        for _ in range(count):
            self.rounds[year] += 1
            race = Race.objects.create(
                season=self.seasons[year],
                round=self.rounds[year],
                race_name=f"Race {year}-{self.rounds[year]}",
                circuit_name=f"Circuit {year}",
                date=date(year, 3, min(28, self.rounds[year])),
            )
            Winner.objects.create(race=race, driver=driver, constructor=constructor)

    def test_parse_era(self) -> None:
        self.assertEqual(parse_era(None), (None, None, "All Eras"))
        self.assertEqual(parse_era("2014-2021"), (2014, 2021, "2014-2021"))
        self.assertEqual(parse_era("bad-era"), (None, None, "All Eras"))

    def test_get_season_queryset_by_era_filters_years(self) -> None:
        years = list(
            get_season_queryset_by_era(start=2014, end=2021).values_list("year", flat=True)
        )
        self.assertEqual(years, [2016, 2020])

    def test_top_drivers_ordering_and_metrics(self) -> None:
        rows = top_drivers(limit=5)

        self.assertEqual(rows[0]["name"], "Bob Bolt")
        self.assertEqual(rows[0]["total_wins"], 8)
        self.assertEqual(rows[0]["peak_season_year"], 2024)
        self.assertEqual(rows[0]["peak_season_wins"], 4)
        self.assertEqual(rows[0]["active_years_label"], "1985-2024")

    def test_top_constructors_era_filter(self) -> None:
        rows = top_constructors(limit=5, start=2014, end=2021)

        self.assertEqual(rows[0]["name"], "Apex Team")
        self.assertEqual(rows[0]["total_wins"], 5)
        self.assertEqual(rows[0]["peak_season_year"], 2016)
        self.assertEqual(rows[1]["name"], "Comet Team")
        self.assertEqual(rows[1]["total_wins"], 5)

    def test_compute_peak_season_for_entity(self) -> None:
        peak_year, peak_wins = compute_peak_season_for_entity(
            entity_id=self.driver_apex.id, entity_type="driver"
        )
        self.assertEqual((peak_year, peak_wins), (2016, 4))

        constructor_peak = compute_peak_season_for_entity(
            entity_id=self.constructor_comet.id,
            entity_type="constructor",
            start=2014,
            end=2021,
        )
        self.assertEqual(constructor_peak, (2020, 5))
