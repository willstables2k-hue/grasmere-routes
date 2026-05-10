# Deploy — Streamlit Community Cloud + Supabase

## 1. Database — Supabase

You already have a Supabase project for the Brain. Reuse it.

1. Get the connection URL (Settings → Database → Connection string → URI).
2. Add as `BRAIN_DB_URL` to `.streamlit/secrets.toml` locally and to the
   Streamlit Cloud secrets editor (one-line value).

## 2. Apply schema

The two SQL files (`001_schema.sql`, `003_seed.sql`) are applied by:

```python
from grasmere_routes.db import run_migrations
run_migrations()
```

Idempotent (`IF NOT EXISTS` / `OR REPLACE` everywhere) so safe to re-run
after every deploy.

## 3. Auth — shared team password

The app is gated behind a single shared password. Default is `grasmere2026`,
hard-coded in `grasmere_routes/auth.py`. To rotate it, add to your secrets:

```toml
[app]
password = "your-new-password"
```

Set `LOCAL_DEV=1` env var to bypass auth entirely in development.

Per-user identity (Google OIDC + role-based access) is parked — the app is a
single-user strategy tool today, so a shared password is enough.

## 4. Mapbox

- **Geocoding API**: server-side calls during import (UK-bounded).
- **Matrix API**: server-side calls from the optimiser.
- Token: `MAPBOX_TOKEN` in secrets. Without it, the optimiser uses a
  haversine fallback (good enough for dev — production needs real driving
  distances).

Cache: `distance_cache` table is H3-keyed at resolution 9 — small GPS jitter
does not bust the cache. Target hit rate after first month: **>90%**.

## 5. Streamlit Community Cloud

1. Push to `github.com/willstables2k-hue/grasmere-routes` (main).
2. https://share.streamlit.io → New app → pick the repo → main branch →
   entry point `streamlit_app.py`.
3. Paste secrets via the secrets editor.
4. Deploy.

Auto-deploys on every push to `main`.

## Monitoring

Streamlit Cloud surfaces logs and crashes natively. For deeper monitoring,
add Sentry to `streamlit_app.py` (init in the first 5 lines).
