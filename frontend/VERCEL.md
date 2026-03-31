# Vercel deployment (Epic 6.3)

Use these steps when connecting this monorepo to Vercel. Copy anything needed into the root README in story 6.5.

## Project settings

1. Import the Git repository in the Vercel dashboard.
2. Set **Root Directory** to `frontend` (not the repo root).
3. **Framework Preset:** Next.js (auto-detected).
4. **Node.js Version:** 22.x (matches `frontend/Dockerfile` and `package.json` engines).

## Environment variables

| Name | Environment | Value |
|------|-------------|--------|
| `NEXT_PUBLIC_API_URL` | Production | `https://<your-service>.onrender.com` — HTTPS Render URL with **no** path segment |

`NEXT_PUBLIC_*` is embedded at **build** time. After changing env vars, trigger a new **Production** deployment.

Preview deployments: optionally set `NEXT_PUBLIC_API_URL` for Preview to a staging API, or leave unset to fall back to `NEXT_PUBLIC_BACKEND_URL` / localhost default (usually wrong for shared previews — set explicitly if you test API calls).

## Verification (post-deploy)

1. Open the production URL in a private/incognito window; confirm the shell renders quickly (target: usable UI within ~5s cold start, NFR6).
2. Open browser devtools → Network; submit a chat analytics query; responses should come from your Render origin and show **no** CORS errors (backend uses wildcard CORS).
3. Optional: run upload/extraction if `OPENROUTER_API_KEY` is configured on Render.

## Build

Local parity check:

```bash
cd frontend && pnpm install --frozen-lockfile && pnpm run build
```
