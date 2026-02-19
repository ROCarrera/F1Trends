from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from dashboard.services.refresh import refresh_f1_data


class Command(BaseCommand):
    help = (
        "Fetches F1 seasons/races/winners from the Jolpica Ergast-compatible API "
        "and caches them in SQLite."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--seasons",
            type=str,
            default=None,
            help="Season range in START:END format (example: 2005:2025). Default: 2005:latest.",
        )

    def handle(self, *args, **options) -> None:
        seasons_range = options.get("seasons")
        self.stdout.write("Starting F1 data refresh...")
        try:
            summary = refresh_f1_data(seasons_range=seasons_range, log=self.stdout.write)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f"Unexpected refresh failure: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(summary.short_message()))
        if summary.errors:
            self.stdout.write(
                self.style.WARNING(f"Refresh completed with {len(summary.errors)} warnings/errors.")
            )
            for error in summary.errors[:10]:
                self.stdout.write(self.style.WARNING(f"- {error}"))

