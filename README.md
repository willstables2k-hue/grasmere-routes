# Grasmere Routes

Delivery route platform for Grasmere Farm — redesigns weekly van runs from
scratch to minimise fleet cost, while exposing the full unit economics of
every route, stop, and customer.

Replaces the legacy colour-coded run system and the Excel VRP solver in
`OneDrive/Grasmere/Van Route Planning/`.

## Stack

- **App**: Streamlit (matches `grasmere-sales-dashboard` pattern)
- **DB**: Supabase Postgres (same Brain instance via `BRAIN_DB_URL`)
- **Optimiser**: Google OR-Tools, in-process (no separate microservice)
- **Maps**: pydeck for routes; Mapbox driving matrix when `MAPBOX_TOKEN` set,
  haversine fallback otherwise
- **Geocoding**: Mapbox Geocoding API (UK-bounded)
- **Auth**: shared team password (`grasmere2026` by default — override via `secrets.app.password`)
- **Hosting**: Streamlit Community Cloud (auto-deploys on push to `main`)

Cost: Streamlit Community Cloud free + Supabase shared with Brain — no extra spend.

## Layout

```
streamlit_app.py             # landing / Overview
pages/
  01_Plan.py                 # weekly planning, optimise + headline saving banner
  02_Baseline.py             # current routing cost + caveats panel
  03_Economics.py            # KPIs + two-line ROI breakdown + bottom 20 customers
  04_Customers.py            # table with status filter + "+N hidden" pill
  05_Dormant.py              # dormancy review queue
  06_Customer_Detail.py      # per-customer profile
  07_Import.py               # Fresho CSV upload + upsert
  08_Simulate.py             # what-if exclusions
  09_Runs.py                 # planned vs actual variance
  10_Drive.py                # mobile driver view
  11_Admin.py                # config + migrations + vehicles + drivers
grasmere_routes/             # the application package
  cost_model.py              # the spine — pence-integer cost math
  optimise.py                # cost-minimising VRP
  baseline.py                # nearest-neighbour per (van, day)
  marginal.py                # leave-one-out single-stop cost
  matrix.py                  # Mapbox Matrix + H3 cache + haversine fallback
  schemas.py                 # Pydantic shapes shared across services
  csv_import.py              # Fresho CSV parser + day-group decoder
  run_code.py                # legacy run-code decoder
  status.py                  # live / dormant / no_history derivation
  geocode.py                 # Mapbox Geocoding client
  customer_upsert.py         # bulk upsert with last-delivery-monotonic guarantee
  baseline_service.py        # orchestrator: pull live → group → solve → persist
  plan_service.py            # generate_orders + optimise_plan + publish
  db.py                      # SQLAlchemy engine + run_migrations()
  queries.py                 # all SQL lives here
  format.py                  # £ / km / min / % / relative-day formatters
  auth.py                    # require_user / require_role
  sql/
    001_schema.sql           # DDL — 13 tables
    002_customer_status_view.sql
    003_seed.sql             # config + depot + 7 default vehicles
tests/                       # pytest suite
```

## Local dev

```bash
# 1. Install deps
python -m venv .venv && . .venv/Scripts/activate     # Windows
# . .venv/bin/activate                                # macOS/Linux
pip install -r requirements.txt

# 2. Copy secrets template
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit BRAIN_DB_URL etc.

# 3. (Optional) bypass auth in dev
export LOCAL_DEV=1     # PowerShell: $env:LOCAL_DEV = "1"

# 4. Apply migrations + seed (also available via Admin page button)
python -c "from grasmere_routes.db import run_migrations; run_migrations()"

# 5. Run the app
streamlit run streamlit_app.py
```

## Tests

```bash
pip install pytest
PYTHONPATH=. pytest -q
```

The cost-model tests are the contract — change a number there and every other
£ figure in the platform shifts.

## Definition of done for v1

Every line item from `docs/spec.md` is wired:

- Customer status (live / dormant / no_history) derived nightly via SQL view
  with configurable threshold (default 180 days)
- Two ROI lines on `/economics`, never blended
- Baseline reconstructed from `legacy_run_code` per (van × day),
  nearest-neighbour sequencing, with permanent honesty caveats panel
- From-scratch fleet-wide VRP on `/plan` with headline saving vs the matched
  baseline, route economics table, and pydeck map
- Bottom-20 customers by net contribution on `/economics`
- Mobile driver view with Google Maps navigate handoff and POD camera capture
- Admin config form + idempotent migration runner
- All money in integer pence; £ formatting only at the UI edge
- Imperial mpg constant (4.546 L/gal) hard-coded — never US gallon

## Deploy

See [`docs/deploy.md`](docs/deploy.md).
