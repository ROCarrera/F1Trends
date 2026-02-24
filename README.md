# F1 Trends MVP

Minimal local dashboard for Formula 1 constructor/driver win trends using the Jolpica Ergast-compatible API.

## What You Get
- A server-rendered Django dashboard at `/`
- A predictions page at `/predictions/` with heuristic next-season picks
- A legends page at `/legends/` with Hall of Fame rankings and era filters
- Profiles pages at `/profiles/` and per-entity detail pages
- Local SQLite cache for seasons, races, and winners
- A one-click refresh flow (`POST /refresh`) and a CLI refresh command
- Trend charts for constructor and driver wins by season

## API
- Base URL: `http://api.jolpi.ca/ergast/f1/`
- Endpoints used:
  - `/seasons.json?limit=1000`
  - `/{season}.json?limit=1000`
  - `/{season}/{round}/results/1.json`

## User Flow (Step by Step)
### 1) Setup your environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Prepare the database
```bash
python manage.py migrate
```

### 3) Load data for the first time
Recommended (CLI):
```bash
python manage.py refresh_f1
```
Optional explicit range:
```bash
python manage.py refresh_f1 --seasons 2005:2025
```

Alternative (UI):
1. Start server with `python manage.py runserver`
2. Open `http://127.0.0.1:8000/`
3. Click **Refresh Data**

### 4) Explore the dashboard
After refresh:
- `/` shows:
- Top summary cards:
  - Seasons in DB
  - Races in DB
  - Constructors in DB
  - Drivers in DB
- Charts:
  - `Constructor Wins by Season` (top 5 overall constructors)
  - `Driver Wins by Season` (top 5 overall drivers)
  - `Top Constructors - Total Wins` (top 10)
- Last refresh timestamp
- `/predictions/` shows:
  - Predicted driver and constructor champion picks
  - Confidence labels (heuristic)
  - Top 10 ranked tables with 5-season win breakdown
  - Score bar charts for drivers and constructors
- `/legends/` shows:
  - Top 5 drivers and top 5 constructors by total wins
  - Peak season and active years for each legend
  - Era filters (`all`, `1950-1979`, `1980-1999`, `2000-2013`, `2014-2021`, `2022-2026`)
  - One compact bar chart of top driver wins
- `/profiles/` shows:
  - Current 2026 drivers and constructors from cached winner data
  - Links to `/profiles/drivers/<driver_id>/` and `/profiles/constructors/<constructor_id>/`
  - Profile pages with totals, wins in 2026, wins-by-season chart, and recent wins table

### 5) Refresh data again
Run either:
```bash
python manage.py refresh_f1
```
or click **Refresh Data** in the UI.

Refresh is idempotent: re-running the same range updates existing rows and does not create duplicates.

## Project Architecture
- `f1trends/`
  - `settings.py`: Django settings, SQLite config, installed apps
  - `urls.py`: project URL routing
- `dashboard/`
  - `models.py`: `Season`, `Race`, `Driver`, `Constructor`, `Winner`
  - `views.py`: dashboard, refresh, predictions, legends, and profiles pages
  - `urls.py`: app routes (`/`, `/refresh`, `/predictions/`, `/legends/`, `/profiles/`)
  - `templates/dashboard/`: Tailwind + Chart.js templates
  - `services/jolpica.py`: Jolpica API client (requests, retries, parsing, throttling)
  - `services/refresh.py`: refresh orchestration + upsert logic + range parsing
  - `services/predictions.py`: deterministic heuristic scoring for `/predictions/`
  - `services/legends.py`: Hall of Fame aggregations + era parsing/filtering
  - `services/profiles.py`: 2026 listings + driver/constructor profile summaries
  - `management/commands/refresh_f1.py`: CLI refresh command
  - `tests/`: unit/integration tests for models, services, views, and command behavior

## Testing
Run all tests:
```bash
python manage.py test
```

Test suite covers:
- Jolpica API parsing with mocked HTTP responses
- Refresh service upserts and idempotency (`refresh twice = same counts`)
- View behavior for `GET /` and `POST /refresh` with messages
- Predictions scoring and `GET /predictions/` behavior
- Legends service/filtering and `GET /legends/` behavior
- Profiles pages (`/profiles/`, driver profile, constructor profile)
- Command error/success handling

## Troubleshooting
### API unreachable / network error
- Symptoms: refresh fails with request or DNS errors.
- Cause: no internet access or API outage.
- Action:
  - Retry later.
  - Run tests to validate app behavior offline: `python manage.py test`.
  - Check terminal logs for exact request failure.

### Invalid season range
- Example: `python manage.py refresh_f1 --seasons 2026:2025`
- Result: command exits with a clear `CommandError`.
- Action: use `START:END` where `START <= END`.

### Empty seasons in selected range
- Symptom: refresh reports no available seasons in the chosen interval.
- Action: choose a broader or valid range, or run without `--seasons` to use default (`2005:latest available`).

### Dashboard shows no charts/data
- Cause: no winners cached yet.
- Action: run `python manage.py refresh_f1` (or use UI refresh) and reload `/`.

### Profiles page shows no current season entities
- Cause: no cached winner rows for season 2026.
- Action: refresh with a range including 2026 (for example `python manage.py refresh_f1 --seasons 2022:2026`).
- Note: this MVP lists entities from winner data only, so non-winning participants are not shown.

## Notes
- Refresh is synchronous (MVP scope): progress is logged to terminal/server logs.
- Data parsing is defensive; missing fields or empty API payloads are handled gracefully.
- `/profiles/` uses winner-derived entities for 2026; full participant rosters require storing complete race results.
- No auth/deployment/background workers in this MVP.
