# Grasmere Optimiser

VRP microservice for Grasmere Routes. Endpoints:

- `POST /optimise` — full daily VRP across all vehicles
- `POST /marginal_cost` — leave-one-out delta for a single stop
- `POST /baseline_cost` — nearest-neighbour cost for legacy van groupings

## Local dev

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
uv run pytest -q
```

The cost-model tests share fixtures with `apps/web/lib/cost-model.test.ts`
to guarantee TS and Python produce identical penny-level numbers.
