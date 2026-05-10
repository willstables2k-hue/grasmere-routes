# Deploy — Streamlit Community Cloud + Supabase

## 1. Database — Supabase

You already have a Supabase project for the Brain. Reuse it.

1. Get the connection URL (Settings → Database → Connection string → URI).
2. Add as `BRAIN_DB_URL` to `.streamlit/secrets.toml` locally and to the
   Streamlit Cloud secrets editor (one-line value).

## 2. Apply schema

The Admin page has a "Run migrations + seed" button — click it once after
first deploy. Locally:

```python
from grasmere_routes.db import run_migrations
run_migrations()
```

Idempotent (`IF NOT EXISTS` / `OR REPLACE` everywhere) so safe to re-run.

## 3. Auth — Google OAuth via Streamlit native OIDC

1. Create a Google OAuth client (https://console.cloud.google.com → APIs &
   Services → Credentials → OAuth 2.0 Client). Set authorised redirect URI to
   `https://YOUR-APP.streamlit.app/oauth2callback`.
2. Generate a 32-char random `cookie_secret`.
3. Fill in the `[auth]` block of `.streamlit/secrets.toml`.
4. Add allowed emails to `secrets.app.allowed_emails`.

Set `LOCAL_DEV=1` env var to bypass auth in development.

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

## 6. POD photo storage (next iteration)

Streamlit Community Cloud disk is ephemeral, so POD photos taken via
`st.camera_input` need to be uploaded to Cloudflare R2 (or Supabase
Storage). Hooks are stubbed in `pages/10_Drive.py` — currently captures the
binary and records the byte length only. Wiring the upload is a small
follow-up.

## Monitoring

Streamlit Cloud surfaces logs and crashes natively. For deeper monitoring,
add Sentry to `streamlit_app.py` (init in the first 5 lines).
