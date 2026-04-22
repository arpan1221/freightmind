# FreightMind — Architecture Diagrams

Four diagrams: system overview, analytics pipeline, extraction pipeline, and the Part 2 verification pipeline.

---

## 1. System Architecture

```mermaid
flowchart TB
    User(["Logistics Analyst / CG User"])

    subgraph Frontend["Frontend — Next.js 16 · TypeScript · Tailwind"]
        Main["/ — Analytics + Documents tabs"]
        VerifPage["/verification — CG Verification UI"]
    end

    subgraph Backend["Backend — FastAPI · Python 3.12 · Docker"]
        Router["API Router
        /api/query  /documents/*  /verify/*  /schema  /health"]

        subgraph AnalyticsAgent["Analytics Agent"]
            AP["Planner — intent classification"]
            AE["Executor — SQL generation + auto-repair"]
            AV["Verifier — read-only SQL guard"]
            AP --> AE --> AV
        end

        subgraph ExtractionAgent["Vision Extraction Agent"]
            EP["Planner — PDF→PNG via PyMuPDF"]
            EE["Executor — vision LLM + JSON parse"]
            EV["Verifier — confidence scoring"]
            EP --> EE --> EV
        end

        subgraph VerificationAgent["Verification Agent (Part 2)"]
            VP2["Pipeline — Trigger→Extract→Compare→Flag→Draft"]
            VC["Comparator — customer rules config (separate module)"]
            VD["Drafter — LLM draft email"]
            VP2 --> VC --> VD
        end

        MC["ModelClient
        SHA-256 cache · retry · fallback"]

        subgraph DB["SQLite — freightmind.db"]
            S[("shipments")]
            ED[("extracted_documents")]
            EL[("extracted_line_items")]
            VR[("verification_results ★")]
            VF[("verification_fields ★")]
        end
    end

    subgraph LLM["LLM APIs"]
        TXT["Text model — SQL + draft generation"]
        VIS["Vision model — field extraction"]
    end

    User -- "NL question" --> Main
    User -- "PDF upload" --> Main
    User -- "SU document" --> VerifPage
    Main --> Router
    VerifPage --> Router
    Router --> AnalyticsAgent
    Router --> ExtractionAgent
    Router --> VerificationAgent
    AnalyticsAgent --> MC
    ExtractionAgent --> MC
    VerificationAgent --> MC
    MC -- "cache miss" --> LLM
    AV -- "SELECT" --> S
    AV -. "cross-table" .-> ED
    AV -. "cross-table" .-> VF
    EV --> ED
    EV --> EL
    VC --> VR
    VC --> VF
```

★ = Part 2 tables

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
    participant LLM as LLM API

    U->>FE: Type natural language question
    FE->>API: POST /api/query {question, previous_sql?}
    API->>P: classify intent
    P->>MC: LLM call (intent classification)
    MC->>MC: check SHA-256 cache
    alt Cache hit
        MC-->>P: cached response
    else Cache miss
        MC->>LLM: API call
        LLM-->>MC: completion
        MC-->>P: response
    end
    P-->>E: intent + SQL plan
    E->>MC: LLM call (SQL generation)
    MC-->>E: generated SQL
    E->>V: validate SQL
    alt SQL contains DROP/DELETE/INSERT/UPDATE/ALTER
        V-->>API: unsafe_sql error (422)
    else SQL is safe SELECT
        V->>DB: execute(sql)
        DB-->>V: rows + columns
        V-->>API: AnalyticsResponse
    end
    API-->>FE: {answer, sql, results, chart, anomaly_note}
    FE-->>U: answer + SQL disclosure + table + chart
```

---

## 3. Vision Extraction Pipeline

```mermaid
sequenceDiagram
    actor U as User
    participant FE as Frontend
    participant API as FastAPI
    participant PL as Planner
    participant EX as Executor
    participant VE as Verifier
    participant MC as ModelClient
    participant DB as SQLite
    participant LLM as Vision LLM

    U->>FE: Upload PDF or image
    FE->>API: POST /api/documents/extract (multipart)
    API->>PL: prepare(file_bytes, content_type)
    PL->>PL: PDF → PyMuPDF → 2x PNG
    PL-->>EX: image_bytes, mime_type
    EX->>MC: call(vision_model, image + extraction_fields prompt)
    MC->>LLM: vision API call
    LLM-->>MC: raw JSON {field: {value, confidence}}
    MC-->>EX: raw dict
    EX->>VE: score_confidence(raw_fields, raw_line_items)
    VE->>VE: coerce types, validate confidence strings
    VE-->>API: fields dict + line_items + low_confidence_fields
    API->>DB: INSERT extracted_documents (confirmed_by_user=0)
    API-->>FE: ExtractionResponse {extraction_id, fields, low_confidence_fields}
    FE-->>U: review table with confidence badges
    alt User confirms
        U->>FE: optional corrections → Confirm
        FE->>API: POST /api/documents/confirm {extraction_id, corrections}
        API->>DB: UPDATE confirmed_by_user=1
        API-->>FE: 200 OK
    else User discards
        U->>FE: Cancel
        FE->>API: DELETE /api/documents/extractions/{id}
        API->>DB: DELETE row + cascade line items
    end
```

---

## 4. Verification Pipeline (Part 2)

```mermaid
sequenceDiagram
    actor CG as CG User
    participant FE as /verification UI
    participant API as FastAPI
    participant PL as ExtractionPlanner
    participant EX as ExtractionExecutor
    participant VE as ExtractionVerifier
    participant CMP as DocumentComparator
    participant DR as VerificationDrafter
    participant MC as ModelClient
    participant DB as SQLite
    participant LLM as LLM APIs

    CG->>FE: Upload SU document + select customer
    FE->>FE: Show "Incoming" state (spinner)
    FE->>API: POST /api/verify/submit (file + customer_id)

    API->>API: validate file (empty/bad type → store_failed)
    API->>PL: prepare(file_bytes, content_type)
    PL-->>EX: image_bytes

    EX->>MC: call(vision_model, image + trade fields prompt)
    MC->>LLM: vision API call
    alt LLM fails after retries
        MC-->>API: raise exception
        API->>DB: INSERT verification_results (status=failed)
        API-->>FE: {overall_status: "failed", error: "..."}
    else LLM success
        LLM-->>MC: raw JSON
        MC-->>EX: raw dict
    end

    EX->>VE: score_confidence(raw_fields)
    VE->>VE: LOW/NOT_FOUND confidence → flagged uncertain

    API->>CMP: load_customer_rules(customer_id)
    alt Config file missing
        CMP-->>API: FileNotFoundError
        API->>DB: INSERT verification_results (status=failed)
        API-->>FE: {overall_status: "failed", error: "..."}
    else Rules loaded
        CMP->>CMP: compare each field
        Note over CMP: confidence < 0.6 → uncertain (even if matches)
        Note over CMP: no rule defined → no_rule (not approved)
        CMP-->>API: []FieldResult {name, extracted, expected, status, confidence}
    end

    API->>DR: generate(field_results, overall_status, rules_config)
    DR->>MC: call(text_model, discrepancy prompt)
    MC->>LLM: text API call
    LLM-->>DR: draft email body
    DR-->>API: draft_reply string

    API->>DB: INSERT verification_results + verification_fields
    API-->>FE: VerificationResultResponse

    FE->>FE: Render verification result (4 states)
    FE-->>CG: Status banner + field table + discrepancy detail + draft reply
    CG->>FE: Edit draft → Send to SU
```
