# Deploy

Three services, one Postgres database. Total monthly run-cost ~£40–60 at our scale.

## 1. Database — Neon (Postgres)

1. Sign up at https://neon.tech and create a project `grasmere-routes`.
2. Copy the **pooled** connection string (shown in the dashboard).
3. Set as `DATABASE_URL` in:
   - your local `.env.local`
   - Vercel project env (web)
   - Railway project env (optimiser, only if you persist anything there — currently no)
4. From the repo root:
   ```bash
   npm run db:migrate
   ```
   This applies all generated migrations, the `customer_status_v` view, and seeds
   the `config` + `depot` rows.

PostGIS is **not** required for v1 — we store lat/lng as `double precision` and
push spatial logic into the optimiser.

## 2. Optimiser — Railway

1. New project → "Deploy from GitHub" → pick this repo, root `apps/optimiser`.
2. Railway autodetects the `Dockerfile`.
3. Env vars:
   - `OPTIMISER_API_KEY` — random shared secret (also added to Vercel)
   - `MAPBOX_TOKEN` — required for production-quality matrix calls
   - `ALLOWED_ORIGINS` — your Vercel URL, e.g. `https://routes.grasmere.app`
4. Note the public URL Railway issues (e.g. `https://grasmere-optimiser.up.railway.app`)
   and set it as `OPTIMISER_URL` in Vercel.

## 3. Web — Vercel

1. Import the GitHub repo, root `apps/web`.
2. Framework: Next.js 15 (auto-detected).
3. Env vars (Production + Preview):
   - `DATABASE_URL` — Neon pooled URL
   - `OPTIMISER_URL` — Railway URL above
   - `OPTIMISER_API_KEY` — same shared secret as Railway
   - `MAPBOX_TOKEN` — server-side
   - `NEXT_PUBLIC_MAPBOX_TOKEN` — public token, scoped read-only, for the GL JS map
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY` — Clerk auth
   - `R2_*` — Cloudflare R2 keys (POD photo uploads)
   - `DEPOT_LAT` / `DEPOT_LNG` / `DEPOT_NAME` — Grasmere Farm, Bourne defaults are
     fine and already match the seed.
4. Deploy. Vercel will build `apps/web` only thanks to the workspace setup.

## 4. Auth — Clerk

1. New application at https://clerk.com.
2. Add roles: `admin`, `dispatcher`, `driver` (Public metadata).
3. Drop `<ClerkProvider>` into `app/layout.tsx` once keys are set
   (the `lib/auth.ts` shim returns a fake admin until then).

## 5. POD storage — Cloudflare R2

1. Create bucket `grasmere-routes-pod`.
2. Create scoped API token with **Object: Read+Write** on this bucket only.
3. The `/drive/[id]/deliver` upload uses presigned URLs minted by the web
   server (not yet implemented — placeholder camera button only).

## 6. Mapbox

- **Geocoding API**: server-side calls during import.
- **Matrix API**: server-side calls from the optimiser.
- **GL JS** (frontend): map tiles for `/baseline`, `/plan`, `/drive`.

Cache hit-rate target: **>90% after first month**, total spend **<£20/month**.
The H3 hex cache key (resolution 9) is the mechanism — small GPS jitter does
not bust the cache.

## Monitoring (post v1)

- Sentry → web + optimiser
- Logflare or Axiom → app logs

Good enough to ship; add when you start hitting unknowns.
