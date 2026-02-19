from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from dashboard.services.refresh import RefreshSummary


class RefreshCommandTests(SimpleTestCase):
    @patch("dashboard.management.commands.refresh_f1.refresh_f1_data")
    def test_command_success(self, refresh_mock) -> None:
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
        out = StringIO()

        call_command("refresh_f1", "--seasons", "2024:2024", stdout=out)

        output = out.getvalue()
        self.assertIn("Starting F1 data refresh...", output)
        self.assertIn(summary.short_message(), output)
        kwargs = refresh_mock.call_args.kwargs
        self.assertEqual(kwargs["seasons_range"], "2024:2024")
        self.assertTrue(callable(kwargs["log"]))

    @patch("dashboard.management.commands.refresh_f1.refresh_f1_data")
    def test_command_success_with_warnings(self, refresh_mock) -> None:
        summary = RefreshSummary(
            target_start=2024,
            target_end=2024,
            latest_available=2026,
            seasons_requested=1,
            seasons_processed=1,
            races_upserted=24,
            winners_upserted=20,
            errors=["error one", "error two"],
        )
        refresh_mock.return_value = summary
        out = StringIO()

        call_command("refresh_f1", stdout=out)

        output = out.getvalue()
        self.assertIn("Refresh completed with 2 warnings/errors.", output)
        self.assertIn("- error one", output)
        self.assertIn("- error two", output)

    @patch("dashboard.management.commands.refresh_f1.refresh_f1_data", side_effect=ValueError("bad input"))
    def test_command_raises_for_value_error(self, _refresh_mock) -> None:
        with self.assertRaises(CommandError) as ctx:
            call_command("refresh_f1")
        self.assertIn("bad input", str(ctx.exception))

    @patch("dashboard.management.commands.refresh_f1.refresh_f1_data", side_effect=RuntimeError("boom"))
    def test_command_wraps_unexpected_error(self, _refresh_mock) -> None:
        with self.assertRaises(CommandError) as ctx:
            call_command("refresh_f1")
        self.assertIn("Unexpected refresh failure: boom", str(ctx.exception))
