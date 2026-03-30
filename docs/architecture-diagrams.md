# FreightMind — Architecture Diagrams

Three diagrams covering the full system: a high-level architecture overview, and step-by-step pipeline sequences for both agents.

---

## 1. System Architecture

```mermaid
flowchart TB
    User(["Logistics Analyst"])

    subgraph Vercel["Vercel — Frontend"]
        Next["Next.js 16 · TypeScript · Tailwind
        Chat Panel · Upload Panel · Dataset Status Card"]
    end

    subgraph Render["Render — Backend (FastAPI · Python 3.12 · Docker)"]
        Router["API Router
        /api/query  /extract  /confirm  /schema  /health"]

        subgraph AnalyticsAgent["Analytics Agent"]
            AP["Planner
            intent → SQL plan"]
            AE["Executor
            SQL generation"]
            AV["Verifier
            SQL safety + DDL block"]
            AP --> AE --> AV
        end

        subgraph VisionAgent["Vision Extraction Agent"]
            VP["Vision Executor
            14-field extraction · confidence scoring · normalisation"]
            VV["Verifier
            field validation"]
            VP --> VV
        end

        MC["ModelClient
        SHA-256 file cache · 1s→2s→4s retry · model fallback"]

        subgraph DB["SQLite"]
            S[("shipments
            10,324 SCMS rows")]
            ED[("extracted_documents")]
            EL[("extracted_line_items")]
        end
    end

    subgraph OpenRouter["OpenRouter — Free Tier"]
        TXT["Llama 3.3 70B → DeepSeek R1 fallback
        text / SQL generation"]
        VIS["Qwen3 VL 235B → Nemotron Nano VL fallback
        vision extraction"]
    end

    User -- "NL question" --> Next
    User -- "PDF / image upload" --> Next
    Next -- "HTTPS · Axios" --> Router
    Router --> AnalyticsAgent
    Router --> VisionAgent
    AnalyticsAgent --> MC
    VisionAgent --> MC
    MC -- "cache miss" --> OpenRouter
    AV -- "validated SQL" --> S
    AV -. "cross-table query" .-> ED
    VV -- "confirmed write" --> ED
    VV --> EL
```

---

## 2. Analytics Agent Pipeline

```mermaid
sequenceDiagram
    actor U as User
    participant FE as Frontend
    participant API as FastAPI
    participant P as Planner
    participant E as Executor
    participant V as Verifier
    participant MC as ModelClient
    participant DB as SQLite
    participant OR as OpenRouter

    U->>FE: Type natural language question
    FE->>FE: isQuerying = true (spinner within 300ms)
    FE->>API: POST /api/query {question, previous_sql?}

    API->>P: dispatch to Analytics Agent
    P->>MC: call(llama-3.3-70b, schema + question)
    MC->>MC: check SHA-256 cache

    alt Cache hit
        MC-->>P: cached response (< 2s)
    else Cache miss
        MC->>OR: LLM API call
        OR-->>MC: completion
        MC->>MC: write response to cache
        MC-->>P: response
    end

    P-->>E: SQL plan + intent classification

    E->>MC: call(llama-3.3-70b, plan + schema)
    MC-->>E: generated SQL

    E->>V: validate SQL

    alt SQL contains DROP / DELETE / UPDATE / INSERT / ALTER
        V-->>API: unsafe_sql error
        API-->>FE: ErrorResponse {error_type, message, detail.sql}
        FE-->>U: error toast
    else SQL is safe
        V->>DB: session.execute(text(sql))
        DB-->>V: rows + columns
        V-->>API: AnalyticsResponse
    end

    API-->>FE: {answer, sql, columns, rows, row_count, chart_config, suggested_questions}
    FE->>FE: isQuerying = false
    FE-->>U: answer + collapsible SQL + result table + chart + follow-up chips
```

---

## 3. Vision Extraction Pipeline

```mermaid
sequenceDiagram
    actor U as User
    participant FE as Frontend
    participant API as FastAPI
    participant VE as Vision Executor
    participant N as Normaliser
    participant V as Verifier
    participant MC as ModelClient
    participant DB as SQLite
    participant OR as OpenRouter

    U->>FE: Drop PDF or image onto upload panel
    FE->>FE: isExtracting = true (spinner within 300ms)
    FE->>API: POST /extract (multipart/form-data)

    Note over VE: PDF → PyMuPDF → image (≤ 5s for 10 pages)
    API->>VE: dispatch to Vision Extraction Agent
    VE->>MC: call(qwen3-vl-235b, image + extraction prompt)
    MC->>OR: LLM API call
    OR-->>MC: raw extracted fields
    MC-->>VE: structured extraction

    VE->>N: normalise(shipment_mode, country, dates, weights)
    N-->>VE: normalised fields + confidence scores

    VE->>DB: INSERT extracted_documents (confirmed_by_user=0)
    DB-->>VE: extraction_id

    VE->>V: validate field schema + assign LOW/NOT_FOUND flags
    V-->>API: ExtractionResponse {extraction_id, fields, confidence, low_confidence_fields}

    API-->>FE: ExtractionResponse (within 30s)
    FE->>FE: isExtracting = false
    FE-->>U: Review table · colour-coded confidence badges · editable fields

    alt User confirms
        U->>FE: edit any fields (optional) then click Confirm
        FE->>FE: isConfirming = true
        FE->>API: POST /confirm/{extraction_id} {edited_fields}
        API->>V: Verifier validates edited values
        V->>DB: UPDATE confirmed_by_user=1 + apply edits
        DB-->>API: confirmed record
        API-->>FE: 200 OK
        FE-->>U: success state · review table cleared
    else User cancels
        U->>FE: click Cancel
        FE->>API: DELETE /extract/{extraction_id}
        API->>DB: DELETE row + line items
        API-->>FE: 200 OK
        FE-->>U: review table cleared · no data saved
    end
```
