# Grasmere Routes

Delivery route platform for Grasmere Farm — redesigns weekly van runs from scratch
to minimise fleet cost, while exposing the full unit economics of every route,
stop, and customer.

Replaces the legacy colour-coded run system and the Excel VRP solver in
`OneDrive/Grasmere/Van Route Planning/`.

## Stack

- **Web / API**: Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui — `apps/web`
- **Optimiser**: Python 3.11 + FastAPI + Google OR-Tools — `apps/optimiser`
- **Database**: Postgres (Neon) + Drizzle ORM
- **Maps**: Mapbox GL JS, Geocoding API, Matrix API (driving)
- **Auth**: Clerk (roles: admin / dispatcher / driver)
- **POD storage**: Cloudflare R2
- **Deploy**: Vercel (web) + Railway (optimiser) + Neon (DB)

Estimated monthly run cost at our scale: **£40–60/month**.

## Why two services

VRP solves blow Vercel function timeouts. The optimiser is a standalone
HTTP service deployed on Railway and called by the Next.js API routes.
Both services share an identical cost-model implementation
(`apps/web/lib/cost-model.ts` ↔ `apps/optimiser/app/cost_model.py`) so
that the £ figures shown in the UI exactly match the £ figures the solver
optimises against.

## Local dev quickstart

```bash
# 1. Install web deps
npm install

# 2. Install optimiser deps
cd apps/optimiser && uv sync && cd ../..

# 3. Copy env
cp .env.example .env.local

# 4. Spin up Postgres locally (or point DATABASE_URL at Neon)
docker run -d --name grasmere-pg -e POSTGRES_PASSWORD=dev \
  -p 5432:5432 postgres:16

# 5. Run migrations
npm run db:migrate

# 6. Start the optimiser (port 8000)
npm run optimiser:dev

# 7. Start the web app (port 3000)
npm run dev
```

## Tests

```bash
npm test                         # TS cost model + import tests
npm run optimiser:test           # Python cost model + VRP tests
```

The TS and Python cost-model tests use **identical fixture cases** to
guarantee that both implementations agree to the penny.

## Deploy

See [`docs/deploy.md`](docs/deploy.md).

## Build order (and current state)

| # | Step | Status |
|---|---|---|
| 1 | Foundation: Next.js, Drizzle, Clerk hooks, config seed | ✅ |
| 2 | Customer DB + CSV import + geocoding | ✅ |
| 3 | Customer status + `/customers/dormant` | ✅ |
| 4 | Cost-model library (TS + Python with shared tests) | ✅ |
| 5 | Baseline computation + `/baseline` page | ✅ |
| 6 | Optimiser microservice (`/optimise`, `/marginal_cost`, `/baseline_cost`) | ✅ |
| 7 | `/plan` weekly planning page | ✅ |
| 8 | `/economics` dashboard | ✅ |
| 9 | `/drive` driver mobile view | ✅ |
| 10 | `/simulate` + `/admin` | ✅ |
| 11 | Polish, error boundaries, monitoring | ⏳ |

## Definition of done for v1

See the build prompt in `docs/spec.md` — every item there is wired through.

The two ROI lines, never blended:

- **Data hygiene saving** — recovered the moment dormant + no-history customers
  are excluded from the baseline (~£40k/year indicative, ~50% of the
  nominally-active customer list).
- **Routing optimisation saving** — what OR-Tools contributes on top, after
  the customer base is honest.
