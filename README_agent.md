# README_agent.md

Agent-oriented technical map for the `f1trends` project.

## Project Purpose
`f1trends` is a local Django MVP that visualizes Formula 1 win trends for constructors and drivers.

Core behavior:
- Fetch F1 data from Jolpica Ergast-compatible API (`http://api.jolpi.ca/ergast/f1/`)
- Cache normalized data in SQLite
- Render dashboard charts from local DB (not from live API calls)

## Tech Stack
- Python + Django (server-rendered app)
- SQLite (default Django DB)
- Tailwind CSS via CDN
- Chart.js via CDN
- `requests` for API calls

## Runtime User Flows
### Flow A: CLI refresh
1. User runs `python manage.py refresh_f1 [--seasons START:END]`
2. Command calls `dashboard.services.refresh.refresh_f1_data`
3. Service calls Jolpica client methods:
   - `fetch_seasons`
   - `fetch_races_for_season`
   - `fetch_race_winner`
4. Service performs idempotent `update_or_create` writes to models
5. Command prints summary + warnings/errors

### Flow B: UI refresh
1. User clicks `Refresh Data` button in `/`
2. `POST /refresh` triggers `dashboard.views.refresh_data`
3. View calls `refresh_f1_data(...)`
4. View redirects to `/` and surfaces success/error via Django messages

### Flow C: Dashboard load
1. User requests `GET /`
2. `dashboard.views.index` computes stats + chart data from cached DB
3. Template injects JSON via `json_script`
4. Chart.js renders charts client-side

### Flow D: Predictions page
1. User requests `GET /predictions/`
2. `dashboard.views.predictions` calls `dashboard.services.predictions`
3. Service computes deterministic heuristic scores from cached `Winner` data only
4. View renders ranked tables, champion picks, confidence labels, and score charts

## Directory and File Map
### Project root
- `manage.py`: Django entrypoint
- `requirements.txt`: dependencies
- `README.md`: user-facing setup/run guide
- `.gitignore`: local artifacts ignore list

### `f1trends/`
- `settings.py`: app config, DB, installed apps, templates, allowed hosts
- `urls.py`: root URL router (`/` -> dashboard, `/admin/`)
- `asgi.py`, `wsgi.py`: deployment entrypoints

### `dashboard/`
- `models.py`:
  - `Season`
  - `Race` (unique `season + round`)
  - `Driver`
  - `Constructor`
  - `Winner` (one-to-one with `Race`)
- `views.py`:
  - `index` (`GET /`)
  - `refresh_data` (`POST /refresh`)
  - `predictions` (`GET /predictions/`)
  - chart aggregation helpers
- `urls.py`: app URL patterns
- `admin.py`: admin registrations
- `services/jolpica.py`: API client + parsing + retry/throttle
- `services/refresh.py`: orchestration, range parsing, upsert logic, summary object
- `services/predictions.py`: heuristic scoring + confidence calculation for predictions UI
- `management/commands/refresh_f1.py`: management command wrapper
- `templates/dashboard/`: HTML templates (`base.html`, `index.html`, `predictions.html`)
- `tests/`: Django tests for models, services, views, command, wiring

## Data Model Notes
- `Race` uniqueness is enforced by DB constraint (`season`, `round`).
- `Winner` is one-per-race using `OneToOneField`.
- Refresh logic is idempotent by design (`update_or_create` across entities).

## Predictions Model Notes
- Uses only locally cached DB data (`Winner` + related season fields).
- Default window: 5 most recent seasons with winner data.
- Recency weights (most recent to oldest): `[1.0, 0.8, 0.6, 0.4, 0.2]`.
- Score per entity (driver/constructor):
  - weighted wins sum across selected seasons
  - trend adjustment:
    - `+0.5` if last season wins > previous season wins
    - `-0.3` if last season wins == 0
- Confidence heuristic:
  - `(top_score - second_score) / max(top_score, 1e-6)`
  - labels: `Low`, `Medium`, `High`

## API Integration Notes
- Endpoint usage:
  - `/seasons.json?limit=1000`
  - `/{season}.json?limit=1000`
  - `/{season}/{round}/results/1.json`
- Client behavior:
  - max 3 retries
  - request timeout (12s default)
  - ~200ms throttle between successful requests
  - defensive parsing for missing/invalid fields

## Testing Expectations
Run:
```bash
python manage.py test
```

Test design rules:
- Do not hit live network in tests.
- Mock HTTP calls using `unittest.mock`.
- Keep tests deterministic and lightweight.
- Preserve idempotency coverage (`refresh twice = same counts`).

Current test areas:
- Jolpica parsing and retry/error handling
- Refresh service upserts + range validation
- View behavior (`GET /`, `POST /refresh`, message behavior)
- Predictions service scoring logic and predictions page behavior
- Management command success/failure handling
- Basic project wiring (URLs/admin/app config)

## Change Guidelines for Agents
- Keep MVP scope: no auth, no async queue, no SPA migration.
- Prefer extending service layer (`dashboard/services/`) over embedding logic in views.
- Preserve SQLite compatibility and existing model semantics.
- Any new refresh behavior must remain idempotent.
- Add/adjust tests for every behavior change.
- Avoid heavy dependencies unless clearly justified.

## Common Agent Tasks
### Add new chart
1. Add aggregation helper in `dashboard/views.py`
2. Inject JSON data with `json_script` in template
3. Add Chart.js canvas + init script
4. Add view tests for helper output shape

### Extend refresh fields
1. Update model + migration
2. Parse fields in `services/jolpica.py`
3. Persist in `services/refresh.py` upsert path
4. Add/adjust tests for parsing + persistence

### Debug refresh failures
1. Reproduce with CLI command and explicit season range
2. Validate range parsing + available seasons
3. Inspect raised `JolpicaAPIError` message
4. Confirm messages surfaced in UI and command output
