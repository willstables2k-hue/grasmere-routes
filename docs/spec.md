# Build prompt: Grasmere Farm delivery route platform (v2)

> Captured from the original build brief on 2026-05-09. The platform code in
> this repo is the implementation of this spec — when in doubt, the code is
> truth, but every decision should be traceable back here.

## Context

I run **Grasmere Farm**, a butcher/meat producer based in Bourne, Lincolnshire (single depot).
We deliver to ~420 active wholesale and retail customers across the East Midlands and East
of England (postcode areas PE, LE, NG, NN, plus some further afield). Most customers are
on a Tuesday + Thursday or Tuesday + Friday cadence.

The platform's primary job is twofold:

1. **Redesign delivery routes from scratch** every week to minimise total fleet cost
   (fuel + labour), ignoring the existing colour-coded run structure.
2. **Show the full unit economics** of every route, every stop, and every customer — so
   pricing, minimum order values, and which customers are unprofitable to serve become
   data-driven decisions.

## Customer status (recency-based filtering)

| Status        | Rule                                  | Behaviour                                     |
|---------------|---------------------------------------|-----------------------------------------------|
| `live`        | Last delivery within 180 days         | Eligible for orders + baseline + planning     |
| `dormant`     | Last delivery > 180 days ago          | Excluded from auto-routing & baseline         |
| `no_history`  | No `latest_delivery_date` recorded    | Excluded; treated identically to dormant      |

Status is derived nightly from `last_delivery_date` + `manually_confirmed_live_at`
via the `customer_status_v` view. NEVER stored as a column.

Indicative split from the supplied CSV (449 rows): ~212 live · 159 dormant · 76 no_history.

## The two ROI lines (never blended)

1. **Data hygiene saving** — recovered the moment dormant + no-history customers
   stop appearing in the baseline. ~£40k/year.
2. **Routing optimisation saving** — what OR-Tools contributes on top.

The economics dashboard shows both as separate annualised figures.

## Cost model — the spine

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

Imperial mpg (4.546 L/gal), NOT US (3.785). Hard-coded constant in
`grasmere_routes/cost_model.py` — single source of truth for both the
optimiser objective and the £ figures the UI displays.

## Marginal cost = leave-one-out

For each stop, re-solve the route without it and take the delta. The web
caches per route — only re-runs when the route changes.

## Net contribution

```
gross_profit       = order_value × gross_margin_pct
net_contribution   = gross_profit − marginal_cost
```

Negative net contribution = customer being served at a loss after delivery cost.
Surfaced prominently in `/economics`.

## Tech stack

- App: Streamlit (matches `grasmere-sales-dashboard` pattern)
- DB: Supabase Postgres (same Brain), H3 hex cache key for distance matrix
- Optimiser: Python 3.11 + Google OR-Tools, in-process (no microservice)
- Maps: pydeck for routes, Mapbox Geocoding + Matrix server-side
- Auth: Streamlit native OIDC (`st.login("google")`) + email allowlist
- POD: Cloudflare R2 (next iteration)
- Charts: Plotly

Estimated monthly run cost: £0 (Streamlit Community Cloud + shared Supabase).

## Pages

Landing (Overview) plus Plan, Baseline, Economics, Customers, Dormant,
Customer Detail, Import, Simulate, Runs, Drive, Admin.

## Optimiser entry points (in-process functions)

- `optimise(req)` — full daily VRP, cost-minimising
- `marginal_cost(req)` — leave-one-out for one stop
- `reconstruct_baseline(req)` — nearest-neighbour per (van, day) for legacy routes

## Definition of done for v1

See README — every line item there is wired through.
