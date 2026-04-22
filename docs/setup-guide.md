# FreightMind — Setup Guide

## Prerequisites

- Python 3.12+
- Node.js 18+
- `uv` package manager (`pip install uv`)
- An OpenRouter API key (free tier works — vision models available on free plan)

Optional for local LLM:
- Ollama with `llama3.2:3b` pulled

---

## Quick Start (Local Dev)

### 1. Clone and configure

```bash
git clone <repo-url>
cd freightmind
```

Create `backend/.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# LLM providers
ANALYTICS_PROVIDER=ollama        # or openrouter
VISION_PROVIDER=openrouter

# Models
ANALYTICS_MODEL=llama3.2:3b
ANALYTICS_MODEL_FALLBACK=llama3.2:3b
VISION_MODEL=nvidia/nemotron-nano-12b-v2-vl:free
VISION_MODEL_FALLBACK=qwen/qwen2.5-vl-7b-instruct:free

# Database
DATABASE_URL=sqlite:///./freightmind.db

# Optional: set to 30 for live data drip demo
LIVE_SEEDING_INTERVAL_SECONDS=0
```

### 2. Start backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Backend starts at `http://localhost:8000`. On first boot:
- Creates all DB tables (including Part 2 tables)
- Runs migration for new columns on existing `extracted_documents`
- Loads ~10,000 shipment rows from CSV
- Computes statistical baseline (IQR fences for anomaly detection)

### 3. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend starts at `http://localhost:3000`.

### 4. Generate sample documents

```bash
python scripts/create_sample_invoices.py
```

Creates:
- `demo/sample_invoice_approved.pdf` — all fields match customer rules
- `demo/sample_invoice_amendment.pdf` — HS code + Incoterms mismatch

---

## Docker Compose (Full Stack)

```bash
cp .env.example .env        # fill in OPENROUTER_API_KEY
docker-compose up --build
```

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | If using OpenRouter | — | API key from openrouter.ai |
| `ANALYTICS_PROVIDER` | No | `ollama` | `openrouter` or `ollama` |
| `VISION_PROVIDER` | No | `openrouter` | `openrouter` or `ollama` |
| `OLLAMA_BASE_URL` | If using Ollama | `http://localhost:11434/v1` | Ollama API endpoint |
| `ANALYTICS_MODEL` | No | `llama3.2:3b` | Text model for SQL/analytics |
| `ANALYTICS_MODEL_FALLBACK` | No | `llama3.2:3b` | Fallback text model |
| `VISION_MODEL` | No | `nvidia/nemotron-nano-12b-v2-vl:free` | Vision model for extraction |
| `VISION_MODEL_FALLBACK` | No | `qwen/qwen2.5-vl-7b-instruct:free` | Fallback vision model |
| `DATABASE_URL` | No | `sqlite:///./freightmind.db` | SQLAlchemy DB URL |
| `BYPASS_CACHE` | No | `false` | Skip LLM response cache |
| `MAX_UPLOAD_BYTES` | No | `10485760` (10 MB) | Max file upload size |
| `VISION_TIMEOUT` | No | `120.0` | Vision LLM timeout (seconds) |
| `ANALYTICS_TIMEOUT` | No | `60.0` | Analytics LLM timeout (seconds) |
| `LIVE_SEEDING_INTERVAL_SECONDS` | No | `0` | Live data drip interval (0 = off) |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |

---

## Adding a New Customer

Create a new rules config file:

```bash
cp backend/config/customer_rules/DEMO_CUSTOMER_001.json \
   backend/config/customer_rules/YOUR_CUSTOMER_ID.json
```

Edit the fields, expected values, and match types. No code changes required.

To use in the UI, add the customer to the `CUSTOMERS` array in `frontend/src/app/verification/page.tsx`.

---

## Running Tests

```bash
cd backend
uv run pytest tests/ -v
```

```bash
cd frontend
npm run test
```

---

## API Documentation

FastAPI auto-generates interactive docs at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
