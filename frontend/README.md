# FreightMind frontend

Next.js (App Router) + TypeScript + Tailwind. This directory is the **web UI** for FreightMind.

**Run the full application (backend + frontend + env):** see the **[root README](../README.md)** — Docker Compose is the recommended path.

For local frontend-only development against a running API:

```bash
pnpm install
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 pnpm dev
```

Then open [http://localhost:3000](http://localhost:3000). The API base URL is also configurable via `NEXT_PUBLIC_API_URL` (see `src/lib/getApiBaseUrl.ts`).
