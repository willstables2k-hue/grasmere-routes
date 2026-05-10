# Spec — Grasmere Routes (v2)

Two pages. Day-centric.

## Page 1 — Map (landing)

All deliveries on a given day plotted on a map, with the most efficient
route plotted.

- Date picker (defaults to most recent day with data)
- File uploader for the Fresho `delivery_runs` Excel
- Pin per delivery, coloured per optimised van, with route paths drawn
- Black depot pin
- Headline metrics row: stops · order value · optimised £ · original £ · saving £

## Page 2 — Costs

Costs per delivery and per route compared to the original plan.

- Same date picker
- Saving banner: original £, optimised £, saving £, %
- Per-route table — original (legacy run-code groupings, NN-sequenced) vs
  optimised (OR-Tools), side by side
- Per-delivery table — one row per delivery: customer, order #, original
  van + cost, optimised van + cost, Δ. Sorted by Δ ascending so the biggest
  savers are top.

## Cost model

```
fuel_litres   = (km / 1.609344) / mpg × 4.546        # imperial gallon
fuel_cost_£   = fuel_litres × diesel_price_per_litre

driving_hours = km / avg_speed_kmh
service_hours = num_stops × service_min / 60
loading_hours = depot_loading_min / 60
labour_cost_£ = (driving + service + loading) × hourly_rate

overhead_£    = vehicle_fixed_cost_per_day            # flat per route

route_total_£ = fuel + labour + overhead
```

Imperial mpg (4.546 L/gal). Hard-coded constant in `grasmere_routes/cost_model.py`.

Per-stop cost = (leg km / total km) × route fuel
              + (leg min / total min) × route labour
              + flat overhead share / num stops

## Settings

Cost parameters editable via a sidebar drawer on each page (no Admin page).

## Auth

Shared team password (`grasmere2026` default; override via `secrets.app.password`).

## Stack

- App: Streamlit, in-process OR-Tools
- DB: Supabase Postgres via `BRAIN_DB_URL`
- Maps: pydeck
- Geocode: Mapbox if `MAPBOX_TOKEN` set, postcodes.io fallback otherwise
- Hosting: Streamlit Community Cloud · £0/month
