# Seeding the platform from the supplied Fresho CSV

```bash
# 1. Boot Postgres + run migrations
docker compose up -d postgres
DATABASE_URL=postgresql://grasmere:dev@localhost:5432/grasmere_routes \
  npm --workspace apps/web run db:migrate

# 2. Boot the optimiser (haversine fallback if no MAPBOX_TOKEN)
cd apps/optimiser && uv run uvicorn app.main:app --port 8000

# 3. Boot the web app
cd ../.. && npm run dev

# 4. Import the customer CSV via the UI
#    http://localhost:3000/customers/import
#    File: ~/OneDrive/Grasmere/Brain/grasmerefarm_customers_20260504.csv

# 5. Geocode (background job not yet hooked to a queue — run by hand for now)
#    TODO: cron-trigger or admin button

# 6. Compute the baseline
#    http://localhost:3000/baseline
#    Click "Recompute baseline"

# 7. Plan a Tuesday
#    http://localhost:3000/plan
#    Pick the next Tuesday, "Generate orders", then "Optimise"
```
