---
name: freightmind-setup
description: "Interactive setup wizard for FreightMind PoC. Asks 3–5 questions, writes .env, and tells you exactly what to run. Handles OpenRouter, Ollama, or mixed configurations."
argument-hint: ""
---

## Overview

This skill configures FreightMind for a first-time evaluator or developer. It:

1. Detects whether `.env` already exists and pre-fills values
2. Asks 3–5 questions (provider choice, API keys, model selection)
3. Writes `.env` at the repo root
4. Prints the exact commands to start the stack and open the app

**Run this skill** by invoking `/freightmind-setup` in Claude Code from the repo root.

---

## Step 0 — Check existing config

Before asking any questions:

- Look for `.env` at the repo root. If it exists, read it and note any values already set
  (especially `OPENROUTER_API_KEY`, `ANALYTICS_PROVIDER`, `VISION_PROVIDER`, `ANALYTICS_MODEL`, `VISION_MODEL`).
- Read `.env.example` at the repo root so you know all available variables and their defaults.

Display this welcome header:

```
╔══════════════════════════════════════════════╗
║     FreightMind — Setup Wizard               ║
║     ~1 minute · writes .env · then done      ║
╚══════════════════════════════════════════════╝
```

If `.env` already exists with a non-placeholder `OPENROUTER_API_KEY`, say:
> "Found an existing `.env` — I'll use those values as defaults. Press Enter to keep any default."

---

## Step 1 — Choose inference provider

Show this question (numbered single-select):

```
Q1 │ How do you want to run inference?

   [1] OpenRouter — cloud API, easiest path (needs a free API key)
   [2] Mixed — Ollama for analytics (text) + OpenRouter for vision
   [3] Fully local — Ollama for both analytics and vision

   Default [1]:
```

Map answers:
- `1` or Enter → `ANALYTICS_PROVIDER=openrouter`, `VISION_PROVIDER=openrouter`
- `2`           → `ANALYTICS_PROVIDER=ollama`,     `VISION_PROVIDER=openrouter`
- `3`           → `ANALYTICS_PROVIDER=ollama`,     `VISION_PROVIDER=ollama`

Store the choice as `provider_mode` (1, 2, or 3).

---

## Step 2 — OpenRouter API key (if needed)

Ask this only if `provider_mode` is `1` or `2`:

```
Q2 │ OpenRouter API key
   Get a free key at: https://openrouter.ai/keys

   Key [<existing value or blank>]:
```

- If the user pastes a key that starts with `sk-or-`, store it.
- If they press Enter and there is already a non-placeholder key in `.env`, keep the existing value.
- If they press Enter with no existing key, warn:
  > "⚠  No key entered. Vision extraction will fail unless you add one to .env later."
  Continue anyway.

Store as `OPENROUTER_API_KEY`.

---

## Step 3 — Ollama configuration (if needed)

Ask this only if `provider_mode` is `2` or `3`:

### 3a — Ollama base URL

```
Q3a │ Ollama base URL
    Running inside Docker → use http://host.docker.internal:11434/v1
    Running natively      → use http://localhost:11434/v1

    URL [http://host.docker.internal:11434/v1]:
```

Store as `OLLAMA_BASE_URL`. Default: `http://host.docker.internal:11434/v1`.

### 3b — Analytics model

Run `ollama list` silently. If it succeeds, extract available model names and show them as hints.

```
Q3b │ Analytics model (text / SQL generation)
    Recommended: llama3.2:3b (fast, sufficient for SQL)
    Also good:   llama3.1:8b, mistral:7b, qwen2.5:7b
    Available on your Ollama: <list from ollama list, or "could not connect">

    Model [llama3.2:3b]:
```

Store as `ANALYTICS_MODEL`. Use the same value for `ANALYTICS_MODEL_FALLBACK`.

If the entered model is NOT in the `ollama list` output, show:
```
  ℹ  Model not found locally. Pull it before starting:
       ollama pull <model>
```

---

## Step 4 — Vision model

### If vision provider is OpenRouter (modes 1 or 2):

```
Q4 │ Vision model (invoice extraction)
   These free-tier OpenRouter models work well:

   [1] nvidia/nemotron-nano-12b-v2-vl:free     ← recommended
   [2] qwen/qwen2.5-vl-7b-instruct:free        (good fallback)
   [3] meta-llama/llama-4-scout-17b-16e-instruct:free  (powerful, may be slower)
   [4] Enter a custom OpenRouter model ID

   Default [1]:
```

Map to model IDs:
- `1` / Enter → `nvidia/nemotron-nano-12b-v2-vl:free`
- `2`         → `qwen/qwen2.5-vl-7b-instruct:free`
- `3`         → `meta-llama/llama-4-scout-17b-16e-instruct:free`
- `4`         → prompt for custom ID

Set `VISION_MODEL` to chosen model.
Set `VISION_MODEL_FALLBACK` to `qwen/qwen2.5-vl-7b-instruct:free` unless the user picked option 2 (then use option 1 as fallback).

### If vision provider is Ollama (mode 3):

```
Q4 │ Vision model (Ollama — must be a multimodal / vision-capable model)
    Recommended: llava:latest or llava-llama3:latest
    Available on your Ollama: <list from ollama list>

    Model [llava:latest]:
```

Store as `VISION_MODEL`. Use same value for `VISION_MODEL_FALLBACK`.

If not in `ollama list` output, show pull hint as in Step 3b.

---

## Step 5 — Write .env

Construct the full `.env` content using all collected values. Use this exact template, filling in `<VALUE>` with what was collected:

```dotenv
# FreightMind — generated by /freightmind-setup
# Re-run /freightmind-setup at any time to reconfigure.

OPENROUTER_API_KEY=<VALUE or your_key_here if blank>

ANALYTICS_PROVIDER=<VALUE>
VISION_PROVIDER=<VALUE>

OLLAMA_BASE_URL=<VALUE>

ANALYTICS_MODEL=<VALUE>
ANALYTICS_MODEL_FALLBACK=<VALUE>

VISION_MODEL=<VALUE>
VISION_MODEL_FALLBACK=<VALUE>

BYPASS_CACHE=false
DATABASE_URL=sqlite:///./freightmind.db
CACHE_DIR=./cache
```

Omit `OLLAMA_BASE_URL` only if `provider_mode` is `1` (pure OpenRouter — Ollama URL is irrelevant).

Write this to `.env` at the repo root (overwrite if it exists). Confirm with:
> "✓ Written `.env`"

---

## Step 6 — Summary and next steps

Print this summary block, substituting the actual values:

```
┌─────────────────────────────────────────────────────────┐
│  FreightMind — Setup Complete                           │
├─────────────────────────────────────────────────────────┤
│  Analytics  │ <ANALYTICS_PROVIDER> / <ANALYTICS_MODEL>  │
│  Vision     │ <VISION_PROVIDER> / <VISION_MODEL>        │
└─────────────────────────────────────────────────────────┘

Next steps:

  1. Start the stack:
       docker compose up --build

  2. Open the app:
       http://localhost:3000
       API docs: http://localhost:8000/docs

  3. Run the demo (1–2 min):
       See DEMO_SCRIPT.md for exact queries to type.
```

If any Ollama models need pulling, add:

```
  ⚠  Before starting, pull missing models:
       ollama pull <analytics_model>
       ollama pull <vision_model>   (if Ollama vision)
```

If `OPENROUTER_API_KEY` was left blank, add:

```
  ⚠  Add your OpenRouter API key to .env before starting:
       OPENROUTER_API_KEY=sk-or-...
```

---

## Edge cases

- **User runs from a subdirectory**: Find the repo root by looking for `docker-compose.yml`. Write `.env` there.
- **`.env` already has all values set and user just presses Enter**: Keep all existing values, rewrite `.env` unchanged, show the summary.
- **Ollama not running**: `ollama list` will fail. Note "could not connect to Ollama" in the model question hint but continue — the user may start Ollama later.
- **User provides mode 3 (fully local) but no vision model exists in ollama list**: Show a warning that vision extraction will fail, but do not block setup.
