# Grasmere Routes

A two-page strategy tool for Grasmere Farm:

1. **Map** — all deliveries on a given day plotted on a map, with the most
   efficient route plotted.
2. **Costs** — costs per delivery and per route, original plan vs optimised.

That's it.

## Stack

- **App**: Streamlit (matches `grasmere-sales-dashboard` pattern)
- **DB**: Supabase Postgres (same Brain instance via `BRAIN_DB_URL`)
- **Optimiser**: Google OR-Tools, in-process
- **Map**: pydeck
- **Geocoder**: Mapbox if `MAPBOX_TOKEN` set, otherwise postcodes.io centroid
- **Auth**: shared team password (`grasmere2026` default; override via
  `secrets.app.password`)
- **Hosting**: Streamlit Community Cloud
- **Cost**: £0/month

## How a typical session looks

1. Open the app → see the Map page.
2. Drop a Fresho `delivery_runs` Excel file in the uploader.
3. The optimiser runs (a few seconds for ~80 stops). The map populates with
   one pin per delivery, coloured per van, with the optimised route paths
   drawn between them.
4. Click "Costs" in the sidebar → see the per-route and per-delivery
   comparison vs the original (legacy run-code) plan, with a saving banner.
5. Pick another date in the date picker to revisit a previously imported
   day. State carries over between the two pages.

## Layout

```
streamlit_app.py            # Map (landing)
pages/
  01_Costs.py               # Costs

grasmere_routes/            # core package
  cost_model.py             # the spine — pence-integer cost math
  optimise.py               # OR-Tools cost-minimising VRP
  baseline.py               # nearest-neighbour per (van, day) for the original plan
  marginal.py               # leave-one-out single-stop cost
  matrix.py                 # Mapbox Matrix + H3 cache + haversine fallback
  schemas.py                # Pydantic shapes shared across services
  orders_import.py          # Fresho delivery_runs Excel parser + idempotent upsert
  postcodes.py              # UK postcode regex + postcodes.io fallback geocoder
  geocode.py                # Mapbox geocoding when MAPBOX_TOKEN is set
  run_code.py               # legacy WP0/GOG/~NR decoder
  day_service.py            # the orchestrator: load_or_compute_day(date)
  map_layers.py             # pydeck builders (delivery pins, route paths, depot)
  db.py                     # SQLAlchemy engine + run_migrations()
  queries.py                # all SQL lives here
  format.py                 # £ / km / min / % formatters
  auth.py                   # shared-password gate
  optimiser_config.py       # env-var loader
  sql/
    001_schema.sql          # 8 tables: config, depot, customers, vehicles,
                            #   orders, routes, route_stops, distance_cache
    003_seed.sql            # config + depot + 7 default vehicles
tests/                      # pytest — currently 44 passing
```

## Local dev

```bash
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # fill BRAIN_DB_URL
$env:LOCAL_DEV = "1"   # bypass password in dev
python -c "from grasmere_routes.db import run_migrations; run_migrations()"
streamlit run streamlit_app.py
```

## Tests

```bash
PYTHONPATH=. pytest -q
```

Cost-model parity is the contract — the same fixture inputs must produce
the same penny outputs. Change a number there and every other £ figure in
the platform shifts.

## Deploy

See [`docs/deploy.md`](docs/deploy.md).
