# Architecture — Multi-Agent Document Processing Factory

> A deep dive into the technical design, design decisions, and future evolution of the platform.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Architecture](#2-component-architecture)
3. [Processing Pipeline Detail](#3-processing-pipeline-detail)
4. [Document State Machine](#4-document-state-machine)
5. [Database Design Principles](#5-database-design-principles)
6. [Provider Abstractions](#6-provider-abstractions)
7. [Temporal Workflow Design](#7-temporal-workflow-design)
8. [LangGraph Agent Design](#8-langgraph-agent-design)
9. [API Design](#9-api-design)
10. [Observability Design](#10-observability-design)
11. [Security Design](#11-security-design)
12. [Architecture Decision Records](#12-architecture-decision-records)

---

## 1. System Overview

```
                          ┌───────────────────────────────────┐
                          │           Client Layer            │
                          │  React + TypeScript + Vite SPA    │
                          └──────────────┬────────────────────┘
                                         │ HTTPS / REST
                          ┌──────────────▼────────────────────┐
                          │         API Gateway Layer          │
                          │    FastAPI (Python 3.12+)          │
                          │    CORS │ Auth │ Rate Limiting     │
                          └──────────────┬────────────────────┘
                                         │
               ┌─────────────────────────┼──────────────────────────┐
               │                         │                          │
    ┌──────────▼──────────┐   ┌──────────▼──────────┐   ┌──────────▼──────────┐
    │   Document Service   │   │  Processing Service  │   │   Review Service    │
    │  (Upload, Storage)   │   │  (Orchestration)     │   │  (Human-in-Loop)   │
    └──────────┬──────────┘   └──────────┬──────────┘   └──────────┬──────────┘
               │                         │                          │
               │              ┌──────────▼──────────┐              │
               │              │  Temporal Workflow   │              │
               │              │  Engine              │              │
               │              └──────────┬──────────┘              │
               │                         │                          │
    ┌──────────▼──────────────────────────▼─────────────────────────▼──────────┐
    │                          Agent Pipeline Layer                              │
    │                                                                            │
    │  ┌─────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
    │  │   OCR   │→ │Classification│→ │Extraction│→ │Validation│→ │Scoring │  │
    │  │  Agent  │  │    Agent     │  │  Agent   │  │  Agent   │  │ Agent  │  │
    │  └─────────┘  └──────────────┘  └──────────┘  └──────────┘  └────────┘  │
    └──────────────────────────────────────────────────────────────────────────┘
               │
    ┌──────────▼──────────────────────────────────────────────────────────────┐
    │                        Infrastructure Layer                               │
    │                                                                           │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │
    │  │  PostgreSQL  │  │    Redis    │  │  Temporal   │  │  Vector Store  │  │
    │  │  (Primary)   │  │  (Cache)    │  │  (Workflow) │  │  (RAG/Search)  │  │
    │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────────┘  │
    └───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Architecture

### Backend Layer Structure

```
backend/app/
├── main.py           ← Application factory only (no business logic)
├── core/             ← Config, logging, constants
├── api/              ← Thin HTTP handlers only (delegate immediately)
│   └── v1/
│       ├── router.py
│       ├── deps.py   ← Dependency injection
│       └── endpoints/
├── agents/           ← LangGraph agent definitions (pure, testable)
├── workflows/        ← Temporal workflow orchestrators
├── activities/       ← Temporal activities (workflow ↔ service bridge)
├── services/         ← Business logic + provider abstractions
│   ├── ocr/          ← OCR provider interface + implementations
│   ├── llm/          ← LLM provider interface + implementations
│   └── vector_store/ ← Vector DB interface + implementations
├── models/           ← SQLAlchemy ORM models (data only)
├── schemas/          ← Pydantic API schemas (validation/serialisation)
└── db/               ← Database session, engine, migration base
```

### Dependency Flow Rule

```
routes → services → agents
routes → services → repositories → models
workflows → activities → services → agents
```

No circular dependencies. No business logic in routes. No DB access in agents.

---

## 3. Processing Pipeline Detail

### Stage 1: Upload & Storage

```
Client POST /api/v1/documents/upload
  → DocumentService.upload(file)
    → validate file type, size
    → generate document_id (UUID)
    → store to StorageBackend (local/S3/GCS)
    → create Document record in PostgreSQL (status=UPLOADED)
    → enqueue Temporal workflow
    → return DocumentResponse(id, status)
```

### Stage 2: OCR

```
OCR Activity runs:
  → OCRProvider.extract_text(file_bytes, mime_type)
    → Returns: OCRResult(text, pages, confidence, provider)
  → Persist OCRResult to DB
  → Update Document status → OCR_COMPLETED
```

### Stage 3: Classification

```
ClassificationAgent runs:
  → Input: raw OCR text
  → LLM call: "What type of document is this? Invoice/Receipt/PO/Contract/General"
  → Structured output: ClassificationResult(type, confidence, reasoning)
  → Update Document status → CLASSIFIED
```

### Stage 4: Extraction

```
ExtractionAgent runs (type-specific):
  → Input: OCR text + document_type
  → LLM call with type-specific Pydantic output schema
  → Returns: ExtractionResult(fields: dict[str, FieldValue])
    where FieldValue = (value, confidence, bounding_box | None)
  → Persist ExtractionResult to DB
  → Update Document status → EXTRACTED
```

### Stage 5: Validation

```
ValidationAgent runs:
  → Input: ExtractionResult + document_type
  → Apply rule set (no LLM needed):
    - required_fields check
    - format validation
    - numeric consistency
    - date range checks
    - cross-field checks
  → Returns: ValidationResult(passed, failures: list[ValidationFailure])
  → Update Document status → VALIDATED
```

### Stage 6: Confidence Scoring

```
ConfidenceScoringAgent runs:
  → Input: ClassificationResult + ExtractionResult + ValidationResult
  → Algorithm:
    - base_score = avg(field.confidence for field in extraction)
    - classification_weight = classification.confidence * 0.2
    - validation_penalty = len(failures) * 0.1
    - final_score = clip(base_score + classification_weight - validation_penalty, 0, 1)
  → Persist ConfidenceScore to DB
```

### Stage 7: Routing

```
if final_score >= CONFIDENCE_THRESHOLD and no critical_failures:
    → Auto-approve: status → APPROVED
    → Emit webhook / notification
else:
    → Route to human review: status → REVIEW_REQUIRED
    → Create ReviewItem in DB
    → Notify assigned reviewer
```

---

## 4. Document State Machine

```
                    ┌─────────┐
            Upload  │UPLOADED │
            ────────►         │
                    └────┬────┘
                         │ Temporal workflow starts
                    ┌────▼────┐
                    │PROCESSING│
                    └────┬────┘
                         │ OCR activity completes
                    ┌────▼────────┐
                    │OCR_COMPLETED│
                    └────┬────────┘
                         │ Classification activity completes
                    ┌────▼──────┐
                    │CLASSIFIED │
                    └────┬──────┘
                         │ Extraction activity completes
                    ┌────▼──────┐
                    │EXTRACTED  │
                    └────┬──────┘
                         │ Validation activity completes
                    ┌────▼──────┐
                    │VALIDATED  │
                    └────┬──────┘
                         │ Confidence score computed
              ┌──────────┴──────────┐
              │ score >= threshold   │ score < threshold OR failures
        ┌─────▼─────┐         ┌─────▼──────────┐
        │ APPROVED  │         │REVIEW_REQUIRED │
        └───────────┘         └────────┬───────┘
                                       │ Human reviews
                              ┌────────▼───────┐
                              │ Approve/Reject  │
                              └────────────────┘

        Any stage can transition to:
                    ┌────▼──────┐
                    │  FAILED   │ ← Unrecoverable error
                    └───────────┘
```

---

## 5. Database Design Principles

1. **Every table has `created_at` and `updated_at`** — enforced in the SQLAlchemy `Base`.
2. **UUIDs as primary keys** — globally unique, no information leakage.
3. **Document status is stored as a string enum** — readable in raw SQL.
4. **Processing history is append-only** — `ProcessingStage` records are never updated; a new record is created per retry attempt.
5. **Soft deletes for documents** — `deleted_at IS NULL` filter rather than physical deletion.
6. **Alembic for all schema migrations** — no manual DDL changes.

---

## 6. Provider Abstractions

### OCR Provider Interface (planned)

```python
class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(
        self,
        file_bytes: bytes,
        mime_type: str,
        options: OCROptions | None = None,
    ) -> OCRResult: ...
```

Switch provider by setting `OCR_PROVIDER=aws_textract` in `.env`.

### LLM Provider Interface (planned)

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        response_model: type[BaseModel] | None = None,
        temperature: float = 0.0,
    ) -> str | BaseModel: ...
```

Switch provider by setting `LLM_PROVIDER=anthropic` in `.env`.

### Vector Store Interface (planned)

```python
class VectorStoreProvider(ABC):
    @abstractmethod
    async def upsert(self, documents: list[VectorDocument]) -> None: ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]: ...
```

Switch provider by setting `VECTOR_DB_PROVIDER=pinecone` in `.env`.

---

## 7. Temporal Workflow Design

### Why Temporal?

- **Durable execution**: Workflows survive process restarts, network failures, and infrastructure outages.
- **Independent retries**: Each activity (OCR, classification, extraction, validation) can fail and be retried independently without rerunning preceding stages.
- **Built-in timeout handling**: Activity and workflow timeouts are first-class concepts.
- **Visibility**: Temporal UI shows every workflow execution, activity, and event history.

### Workflow Structure

```
DocumentProcessingWorkflow
├── run_ocr_activity              (retry: 3x, timeout: 60s)
├── classify_document_activity    (retry: 3x, timeout: 30s)
├── extract_fields_activity       (retry: 3x, timeout: 60s)
├── validate_document_activity    (retry: 1x, timeout: 30s)
├── score_confidence_activity     (retry: 1x, timeout: 10s)
├── route_for_review_activity     (retry: 3x, timeout: 15s)
└── persist_result_activity       (retry: 5x, timeout: 30s)
```

---

## 8. LangGraph Agent Design

Each AI agent in the factory is built as a compiled LangGraph `StateGraph`.

### Step 4 — Classification Agent Flow

The Document Classification Agent is the first AI agent in the multi-agent pipeline. Its architecture follows:

```
                      ┌──────────────────────┐
                      │        START         │
                      └──────────┬───────────┘
                                 │
                      ┌──────────▼───────────┐
                      │  load_document_text  │  (Validates OCR completion, retrieves text)
                      └──────────┬───────────┘
                                 │
                   [error?] ─────┴───── [valid]
                      │                   │
                      │        ┌──────────▼───────────┐
                      │        │  classify_document   │  (Calls LLMProvider with structured schema)
                      │        └──────────┬───────────┘
                      │                   │
                      │     [error?] ─────┴───── [valid]
                      │        │                   │
                      │        │        ┌──────────▼───────────┐
                      │        │        │persist_classification│  (Writes to PostgreSQL, status=CLASSIFIED)
                      │        │        └──────────┬───────────┘
                      │        │                   │
                      └────────┴───────────────────┴──► END
```

### Design Principles & Decisions

1. **Why LangGraph?**:
   - **Typed State Machine**: State is modeled as a strongly typed `ClassificationState` (TypedDict), eliminating fragile untyped dictionary manipulation.
   - **Error Short-Circuiting**: If OCR text is absent or invalid, the graph short-circuits immediately before reaching the LLM node, saving API credits and latency.
   - **Independent Testability**: The graph can be compiled with or without a database session and executed in isolation using a `FakeLLMProvider`.

2. **Why Abstract the LLM Provider?**:
   - `LLMProvider` defines a universal `generate_structured(prompt, schema, system_prompt, temperature)` contract.
   - The agent depends only on the interface, never directly on `openai`, `anthropic`, or `google.generativeai` SDKs.
   - Swapping models or providers in production is an environment variable configuration (`LLM_PROVIDER=openai`).
   - Unit and integration tests run entirely against `FakeLLMProvider` without calling external APIs or requiring API keys.

3. **Why Separate Classification from OCR?**:
   - **Single Responsibility**: OCR is low-level character and layout recovery from physical formats (PDF, DOCX, images). Classification is high-level semantic reasoning over the extracted text.
   - **Decoupled Scaling & Costs**: OCR is CPU/GPU/OCR-engine bound. Classification is LLM-token bound.
   - **Independent Retries**: Corrupt OCR can be re-run with different DPI or engine settings; failed classification can be retried with different prompts or models without re-running OCR.

### Step 5 — Information Extraction Agent Flow

The Information Extraction Agent is the second AI agent in the pipeline. It transforms raw OCR text into a document-type-specific structured schema:

```
                      ┌──────────────────────┐
                      │        START         │
                      └──────────┬───────────┘
                                 │
                      ┌──────────▼───────────┐
                      │    load_document     │  (Validates document existence & OCR text)
                      └──────────┬───────────┘
                                 │
                    [error?] ────┴──── [valid]
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │ load_classification  │  (Validates classification stage completed)
                       │      └──────────┬───────────┘
                       │                 │
                    [error?] ────┴──── [valid]
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │    select_schema     │  (Selects Pydantic schema & prompt by doc_type)
                       │      └──────────┬───────────┘
                       │                 │
                    [error?] ────┴──── [valid]
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │ extract_information  │  (Calls LLM with structured schema & strict prompts)
                       │      └──────────┬───────────┘
                       │                 │
                    [error?] ────┴──── [valid]
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │  persist_extraction  │  (Writes extracted_data to PostgreSQL, status=EXTRACTED)
                       │      └──────────┬───────────┘
                       │                 │
                       └────────┴────────┴──► END
```

### Extraction Design Principles & Decisions

1. **Schema-Driven Extraction vs. Freeform Output**:
   - Every document type maps to a strict Pydantic model (`InvoiceExtraction`, `ReceiptExtraction`, `PurchaseOrderExtraction`, `ContractExtraction`, `OtherExtraction`).
   - Fields that are absent in the source document are explicitly defaulted to `None` or empty lists to prevent LLM hallucinations.
   - Outputs are directly JSON-serializable into PostgreSQL's `extracted_data` column without manual string manipulation or regex parsing.

2. **Decoupled Classification and Extraction Agents**:
   - **Step-by-step modularity**: The Classification Agent classifies what the document is (`INVOICE`, `CONTRACT`, etc.). The Extraction Agent uses that classification to choose the domain schema and specialized extraction prompt.
   - **Cost and Prompt Efficiency**: Rather than using a monolithic prompt that must extract all conceivable document types simultaneously, the prompt is tailored strictly to the recognized document type, drastically reducing token usage and error rates.
   - **Independent Verification**: A misclassified document can be reclassified without discarding extraction code, and schemas can evolve independently without touching classification prompts.

3. **Separation of Extraction from Validation**:
   - The Extraction Agent focuses solely on faithfully recording what appears in the document text.
   - Business rule validation (e.g. `subtotal + tax == total`, matching purchase orders against vendor catalogs) is strictly deferred to the subsequent Validation Agent (Step 6), ensuring extraction failures are distinguishable from business rule violations.

### Step 6 — Validation Agent & Confidence Scoring Flow

The Validation Agent combines deterministic domain business rules with LLM-assisted semantic audit:

```
                      ┌──────────────────────┐
                      │        START         │
                      └──────────┬───────────┘
                                 │
                      ┌──────────▼───────────┐
                      │    load_document     │  (Verifies document & prerequisites)
                      └──────────┬───────────┘
                                 │
                    [error?] ────┴──── [valid]
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │   load_extraction    │  (Confirms extracted_data exists)
                       │      └──────────┬───────────┘
                       │                 │
                    [error?] ────┴──── [valid]
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │ run_deterministic_val│  (Arithmetic, dates, required fields)
                       │      └──────────┬───────────┘
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │ run_semantic_val     │  (LLM checks contextual contradictions)
                       │      └──────────┬───────────┘
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │ combine_val_results  │  (Composite score, validity check)
                       │      └──────────┬───────────┘
                       │                 │
                       │      ┌──────────▼───────────┐
                       │      │  persist_validation  │  (Writes score & status=VALIDATED)
                       │      └──────────┬───────────┘
                       │                 │
                       └────────┴────────┴──► END
                                                │
                                                ▼
                                    ┌──────────────────────┐
                                    │  Confidence Scoring  │
                                    └──────────┬───────────┘
                                               │
                                 ┌─────────────┴─────────────┐
                                 │                           │
                      [>= 0.85 & is_valid]          [< 0.85 or invalid]
                                 │                           │
                      ┌──────────▼───────────┐    ┌──────────▼───────────┐
                      │     AUTO_APPROVE     │    │   REVIEW_REQUIRED    │
                      │   (status=APPROVED)  │    │(status=REVIEW_REQ'D) │
                      └──────────────────────┘    └──────────────────────┘
```

### Validation & Confidence Principles & Decisions

1. **Deterministic Rules First, LLM Semantic Validation Second**:
   - Arithmetic (e.g. `quantity * unit_price == amount`, `subtotal + tax == total`), date comparisons (`due_date >= invoice_date`), and field presence checks are deterministic and mathematical. They should never rely on LLM inference.
   - LLM validation focuses exclusively on semantic discrepancies (e.g. hallucinated company names or contradictory statements).
2. **Transparent Multi-Factor Confidence Scoring**:
   - Rather than a black-box percentage, confidence is calculated from three verifiable factors:
     - 25% Classification Confidence
     - 35% Extraction Completeness (expected schema fields populated)
     - 40% Validation Score
   - Full weight and component breakdowns are stored in `Document.confidence_factors` for auditable governance.
3. **Threshold-Based Decision Routing**:
   - `AUTO_APPROVAL_THRESHOLD` (0.85) and `REVIEW_THRESHOLD` (0.60) provide clear automated vs. human-in-the-loop boundaries.
   - Any document with a critical `ERROR` severity issue is always routed to `REVIEW_REQUIRED`, regardless of score.

---

## 7. Temporal Workflow Design

The end-to-end document processing lifecycle is orchestrated by **Temporal.io**, ensuring bulletproof reliability, distributed state management, and transparent observability without building custom polling queues.

### Architecture Overview

```
Client (POST /documents/{id}/process)
              │
              ▼
   TemporalClientService (asynchronous dispatch)
              │
              ▼
   DocumentProcessingWorkflow
   (Task Queue: "document-processing-queue")
              │
              ├──► [Activity 1] run_ocr_activity
              │       └── Calls OcrService (Tesseract / PyMuPDF)
              │       └── Status: OCR_COMPLETED
              │
              ├──► [Activity 2] classify_document_activity
              │       └── Calls ClassificationService (LangGraph Agent)
              │       └── Status: CLASSIFIED
              │
              ├──► [Activity 3] extract_fields_activity
              │       └── Calls ExtractionService (LangGraph Agent)
              │       └── Status: EXTRACTED
              │
              ├──► [Activity 4] validate_document_activity
              │       └── Calls ValidationService (Deterministic + LLM)
              │       └── Status: VALIDATED
              │
              └──► [Activity 5] score_confidence_activity
                      └── Calls ConfidenceService
                      └── Status: APPROVED or REVIEW_REQUIRED
```

### Key Workflow Features

1. **Deterministic Workflow Execution**:
   - Workflows contain zero business logic and zero direct database queries; they sequence activities deterministically.
   - All side effects and external service calls take place strictly within Temporal activities.

2. **Per-Activity Exponential Retry Policies**:
   - Every activity is executed with a configured `RetryPolicy`:
     - `initial_interval`: 2 seconds (`timedelta(seconds=2)`)
     - `backoff_coefficient`: 2.0
     - `maximum_interval`: 30 seconds (`timedelta(seconds=30)`)
     - `maximum_attempts`: 3
   - Transient failures (e.g., transient rate limits or OCR glitches) are automatically retried without restarting the entire pipeline.

3. **Workflow Idempotency**:
   - Canonical workflow ID format: `document-processing-{document_id}`.
   - Starting a workflow for a document already executing reuses the active run, preventing duplicate concurrent pipelines.
   - Conflict resolution uses `WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY`.

4. **Real-Time Queries**:
   - `get_current_stage`: Returns the active processing stage (`OCR`, `CLASSIFICATION`, `EXTRACTION`, `VALIDATION`, `CONFIDENCE_SCORING`).
   - `get_status`: Returns current document lifecycle status (`PROCESSING`, `APPROVED`, `REVIEW_REQUIRED`, `FAILED`).
   - `get_stages_completed`: Returns the ordered history of completed processing stages.

5. **Standalone Temporal Worker (`app/worker.py`)**:
   - A dedicated worker process registers `DocumentProcessingWorkflow` and all 5 activities against the `document-processing-queue`.
   - Scaled as an independent container in `docker-compose.yml`.

6. **Redis Cache-First Status Architecture**:
   - Document processing status is cached in Redis at `document:status:{document_id}` with a configurable TTL (`REDIS_STATUS_TTL_SECONDS=3600`).
   - `GET /api/v1/documents/{document_id}/processing-status` checks Redis first; on miss, it reads PostgreSQL (durable source of truth) and active Temporal workflow state, then populates Redis.
   - If Redis is unreachable, the application falls back gracefully to PostgreSQL with zero downtime.

7. **Local Infrastructure Stack & Ports**:
   - `backend` (FastAPI): Port `8000`
   - `frontend` (React + Vite): Port `5173`
   - `postgres` (PostgreSQL 16): Port `5432`
   - `redis` (Redis 7): Port `6379`
   - `temporal` (Temporal Engine): Port `7233`
   - `temporal-ui` (Web Console): Port `8088`
   - `temporal-worker`: Independent worker process running activities on `document-processing-queue`

---

## 9. API Design

### Versioning

All production API routes are under `/api/v1/`. Breaking changes will increment to `/api/v2/`.

### Route Conventions

```
GET    /api/v1/documents           — List documents (paginated)
POST   /api/v1/documents/upload    — Upload a new document
GET    /api/v1/documents/{id}      — Get document details + status
DELETE /api/v1/documents/{id}      — Soft-delete a document

GET    /api/v1/jobs/{id}           — Get processing job status
POST   /api/v1/jobs/{id}/retry     — Retry a failed job

GET    /api/v1/review              — List review queue items
POST   /api/v1/review/{id}/approve — Approve a reviewed document
POST   /api/v1/review/{id}/reject  — Reject a document
PUT    /api/v1/review/{id}/correct — Correct extracted data

GET    /api/v1/search              — Semantic document search (RAG)
GET    /health                     — Liveness check (no auth)
```

---

## 10. Observability Design

### Structured Logging

All logs are emitted as JSON in production using `structlog`. Every log line includes:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "info",
  "logger": "app.services.ocr",
  "event": "ocr.completed",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "provider": "aws_textract",
  "pages": 3,
  "duration_ms": 1234,
  "app": "Multi-Agent Document Processing Factory",
  "version": "0.1.0",
  "env": "production"
}
```

### Processing Stage Tracking

Every stage transition is persisted to `ProcessingStage` table:

```
document_id | stage           | status    | started_at | completed_at | error
------------|-----------------|-----------|------------|--------------|-------
abc123      | OCR             | COMPLETED | 10:00:00   | 10:00:05     | null
abc123      | CLASSIFICATION  | COMPLETED | 10:00:05   | 10:00:07     | null
abc123      | EXTRACTION      | FAILED    | 10:00:07   | 10:00:09     | "..."
abc123      | EXTRACTION      | COMPLETED | 10:00:15   | 10:00:18     | null  ← retry
```

---

## 11. Security Design

- **No secrets in code**: All credentials via environment variables.
- **Input validation**: All API inputs validated by Pydantic before processing.
- **File type validation**: MIME type + magic bytes checked, not just extension.
- **Non-root Docker**: Production containers run as unprivileged user.
- **Network isolation**: Docker Compose internal network; only necessary ports exposed.
- **JWT authentication** (future): Stateless token-based auth for API routes.
- **Rate limiting** (future): Per-IP and per-user rate limits on upload endpoints.

---

## 12. Architecture Decision Records

### ADR-001: Temporal for Workflow Orchestration

**Decision**: Use Temporal instead of Celery, RQ, or plain asyncio task queues.

**Rationale**: Document processing is a long-running, multi-stage operation that must survive infrastructure failures. Temporal provides durable execution, independent activity retries, built-in timeouts, and a UI for workflow visibility. Celery lacks durable state and activity-level retry granularity.

### ADR-002: Provider Abstraction for OCR, LLM, and Vector Store

**Decision**: Define abstract base classes for all AI/ML provider integrations.

**Rationale**: The AI provider landscape changes rapidly. Being locked to a single vendor (e.g., OpenAI) creates business and technical risk. The abstraction adds minimal complexity but allows provider-switching via a config change.

### ADR-003: Separate Schemas from Models

**Decision**: Pydantic schemas and SQLAlchemy models are defined in separate packages.

**Rationale**: Tight coupling between API schemas and DB models creates painful migration conflicts. Separate layers allow independent evolution of the database schema and the API contract.

### ADR-004: Async-first Backend

**Decision**: Use async SQLAlchemy, asyncpg, and async FastAPI throughout.

**Rationale**: Document processing involves high I/O: database calls, OCR API calls, LLM API calls, storage I/O. Async allows a single process to handle many concurrent requests efficiently without thread-pool overhead.

### ADR-005: Decoupled Human-in-the-Loop Review from Temporal Workflows

**Decision**: Terminate Temporal workflow when reaching `REVIEW_REQUIRED` (or `APPROVED`). Conduct Human-in-the-Loop review lifecycle (Claim, Approve, Correct, Reject) asynchronously outside the Temporal workflow.

**Rationale**: Human review cycles can take minutes, hours, or days. Embedding long-running human signals or pauses into Temporal workflows complicates workflow versioning, resource retention, and timeout handling. Instead, the workflow finishes deterministically, creating a review record in PostgreSQL. Review mutations run as atomic database transactions with deterministic revalidation, and invalidate the Redis status cache upon completion.

---

## 13. Human-in-the-Loop (HITL) Review System (Step 8)

```
                    ┌─────────────────────┐
                    │ Temporal Processing │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Confidence Scoring  │
                    └───────┬───────┬─────┘
                            │       │
                 AUTO_APPROVE       │ REVIEW_REQUIRED
                            │       │
                            ↓       ↓
                       APPROVED   Review Queue
                                      │
                                      ↓
                               Human Reviewer
                              /      |       \
                             /       |        \
                        Approve   Correct    Reject
                            │        │          │
                            └────────┼──────────┘
                                     ↓
                              Final Document State
```

### Key Components

1. **`DocumentReview` Domain Model**:
   - `id`: UUID primary key
   - `document_id`: UUID foreign key → `documents.id`
   - `status`: `PENDING` → `IN_REVIEW` → `COMPLETED`
   - `decision`: `APPROVED`, `REJECTED`, `CORRECTED`
   - `original_extracted_data`: Immutable snapshot of AI output
   - `reviewed_extracted_data`: Human-corrected extraction
   - `validation_result_snapshot`, `confidence_snapshot`
   - `reviewer_name`, `reviewer_id` (optional, no fake auth)

2. **Atomic Service Operations (`ReviewService`)**:
   - `create_review()`: Enforces single active review per document and requires `confidence_recommendation == REVIEW_REQUIRED`.
   - `start_review()`: Prevents invalid transitions (`COMPLETED` → `IN_REVIEW`).
   - `approve_review()`: Transactionally updates review (`APPROVED`), document (`APPROVED`), and appends `ProcessingHistory(stage="HUMAN_REVIEW")`.
   - `reject_review()`: Transactionally updates review (`REJECTED`), document (`REJECTED`), and records audit entry.
   - `correct_review()`:
     1. Validates corrected fields against Pydantic document schemas (`InvoiceExtraction`, etc.).
     2. Re-runs deterministic validation engine.
     3. Recalculates transparent confidence score.
     4. Transitions document to `APPROVED` if valid.
     5. Preserves original extraction and reviewed extraction side-by-side.

3. **Cache Coherency & Status Integration**:
   - On every review state transition, `document:status:{document_id}` is invalidated via `RedisService.delete_document_status`.
   - `/api/v1/documents/{id}/processing-status` exposes `review_id` and `review_status` in real-time.

4. **Document-Type Aware Frontend UI**:
   - Built with React, TypeScript, and Vite under a dark-mode glassmorphic design system.
   - Provides `ReviewQueue` (pagination, filtering, instant metrics).
   - Provides `ReviewDetails` (document metadata, confidence factor breakdown, validation issues with severity, raw OCR viewer, audit timeline).
   - Provides `ExtractedDataEditor` (structured forms for Invoice, Receipt, Purchase Order, Contract, and General documents).

---

## 14. Step 9 — RAG + Vector Database Document Intelligence

### Architecture

```
Approved Document
       │
       ▼
  Text Chunking (800 chars, 120 overlap, page preservation)
       │
       ▼
Embedding Generation (OpenAI / FakeEmbeddingProvider, dim=1536)
       │
       ▼
PostgreSQL + pgvector (document_chunks table)
       │
       ▼
Semantic Retrieval (Cosine distance `<=>` / fallback, top_k, hybrid filters)
       │
       ▼
Context Assembly ([Source 1], [Source 2] with provenance tags)
       │
       ▼
Grounded LLM Generator (Strict grounding, "I could not find sufficient evidence...", source citations)
       │
       ▼
Answer + Traceable Source Citations (filename, page, chunk, similarity %)
```

### 1. Vector Database Integration: PostgreSQL + pgvector
- Uses the official `pgvector/pgvector:pg16` Docker image.
- Database initialization executes `CREATE EXTENSION IF NOT EXISTS vector;`.
- Eliminates the operational overhead of a disconnected external vector database service while maintaining transactional atomicity with document records.

### 2. DocumentChunk Model
- `id`: UUID primary key.
- `document_id`: Foreign key with `CASCADE` delete to `documents.id`.
- `chunk_index`: 0-based sequence number within document.
- `content`: Text snippet for the chunk.
- `page_number`: 1-based page index where chunk originated.
- `token_count`: Estimated token count.
- `embedding`: Vector column mapped to `Vector(1536)`.
- `metadata`: JSONB column storing character offsets, filename, document type, and timestamps.
- Composite unique index on `(document_id, chunk_index)`.

### 3. Chunking Strategy (`chunking.py`)
- Configurable chunk size (`RAG_CHUNK_SIZE`, default 800) and overlap (`RAG_CHUNK_OVERLAP`, default 120).
- Automatic page delimiter extraction (`--- Page N ---`, `\x0c`).
- Paragraph and sentence boundary preservation, falling back to word sliding windows for unstructured blobs.
- Whitespace normalization and skipping of empty chunks.

### 4. Embedding Provider Abstraction (`embeddings.py`)
- `EmbeddingProvider` abstract base class defining `embed_text()` and `embed_documents()`.
- `OpenAIEmbeddingProvider` using configurable model (`text-embedding-3-small`, 1536 dimensions).
- `FakeEmbeddingProvider` producing deterministic non-negative unit vectors for testing without network or API dependencies.

### 5. Indexing Lifecycle & Grounding Policy
- **Auto-Indexing**: Documents are automatically indexed when approved via `ConfidenceService` (`AUTO_APPROVE`) or `ReviewService` (`approve_review`, `correct_review`).
- **Exclusion of Rejected Documents**: Documents marked `REJECTED` are prohibited from entering the vector database, and existing chunks are pruned on rejection.
- **Idempotency**: Indexing replaces previous chunks transactionally without duplicate accumulation.
- **Strict Grounding**: The LLM prompt prohibits extrapolation and mandates:
  *"I could not find sufficient evidence in the indexed documents."* when context is insufficient.

---

## 9. Analytics & Observability Subsystem (Step 11)

The Analytics and Observability subsystem provides actionable operational intelligence into pipeline performance, document lifecycle distribution, processing throughput, and human review operations.

### Architectural Principles

1. **Zero Data Duplication**: No shadow metrics database is introduced. All analytics are computed dynamically using optimized SQL aggregations directly over the core operational tables (`Document`, `ProcessingHistory`, `DocumentReview`).
2. **Database-Driven Aggregation**: Calculations leverage database-native `COUNT`, `AVG`, `CASE`, `GROUP BY`, and interval date expressions, avoiding costly in-memory row iteration in Python.
3. **Cross-Database Compatibility**:
   - **PostgreSQL (Production)**: Uses `EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000` for milliseconds and `to_char(date_trunc('day', created_at), 'YYYY-MM-DD')` for time series.
   - **SQLite (In-Memory Testing)**: Uses `(julianday(completed_at) - julianday(started_at)) * 86400000.0` and `strftime('%Y-%m-%d', created_at)` dynamically detected by dialect name.
4. **Server-Side Filtering & Validation**: Strict query parameter validation rejects invalid time ranges (`start_date > end_date` returns HTTP 400).
5. **Real-Time Glassmorphic Frontend**: Custom zero-dependency responsive SVG bar charts, live 60-second telemetry polling, and instant preset filtering (7D, 30D, 90D, All, Custom).

---

## 15. Step 12 — Docker & Production Hardening Architecture

The production container architecture ensures that the complete 8-service multi-agent document processing platform runs reliably, securely, and deterministically under containerized orchestration.

### 1. Multi-Stage Container Design

#### Backend Image (`backend/Dockerfile`):
- **Base Layer**: `python:3.12-slim-bookworm` with strict non-interactive apt flags, `gcc`, `libpq-dev`, and `tesseract-ocr`.
- **Builder Stage**: Builds Python wheels in a virtual environment to minimize runtime attack surface and exclude compiler toolchains.
- **Runtime Stage**:
  - Drops root privileges: runs as unprivileged user `appuser:appgroup` (UID/GID 1001).
  - Explicit local storage volume mount point `/app/storage` with permissions assigned to `appuser`.
  - In-container health check targeting `http://localhost:8000/health/ready`.
  - Reused for both `backend` (FastAPI/Uvicorn) and `temporal-worker` (`python -m app.worker`), ensuring identical dependency parity without image drift.

#### Frontend Image (`frontend/Dockerfile` & `frontend/nginx.conf`):
- **Stage 1 (Builder)**: `node:20-alpine` runs `npm ci` and `npm run build` using Vite to produce static production bundles in `/app/dist`.
- **Stage 2 (Runtime)**: `nginx:1.27-alpine` provides high-performance static asset delivery.
- **SPA Fallback**: Configured with `try_files $uri $uri/ /index.html;` ensuring deep routes (`/documents/:id`, `/reviews/:id`, `/rag`, `/analytics`) resolve smoothly on direct reload.
- **Security Headers**: Injects `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Lightweight Health Check**: Exposes a non-logging `/healthz` endpoint returning HTTP 200 via `wget --spider`.

### 2. Network Topology & Port Boundaries

Services reside in an isolated bridge network (`docfactory-network`).

- **Internal Container Traffic**: Services communicate strictly via Docker DNS service names:
  - `backend` → `postgres:5432`
  - `backend` → `redis:6379`
  - `backend` → `temporal:7233`
  - `temporal-worker` → `temporal:7233`, `postgres:5432`, `redis:6379`
- **External Host Access**:
  - `5173:80` (Frontend Nginx)
  - `8000:8000` (FastAPI Backend)
  - `8088:8080` (Temporal Web UI)
  - `5432:5432` (PostgreSQL / pgvector)
  - `6379:6379` (Redis)
  - `7233:7233` (Temporal gRPC)
- **Browser-to-Backend Resolution**: The browser runs on the host machine outside Docker, so frontend API calls target host-accessible `http://localhost:8000/api/v1`.

### 3. Startup Ordering & Health Dependencies

Startup cascades deterministically using Compose v2 `service_healthy` conditions:
1. `postgres` (probed via `pg_isready`) and `redis` (probed via `redis-cli ping`) start first.
2. `temporal` starts after `postgres` is healthy.
3. `temporal-admin-tools` starts after `temporal` is up to register the `document-processing` namespace.
4. `backend` starts only after `postgres`, `redis`, and `temporal` are confirmed healthy.
5. `temporal-worker` starts after `temporal`, `postgres`, and `backend` are confirmed healthy.
6. `frontend` starts after `backend` is confirmed healthy.

### 4. Storage Persistence Matrix

| Volume Name | Target Container Path | Purpose |
|---|---|---|
| `docfactory_postgres_data` | `/var/lib/postgresql/data` | Stores documents, metadata, chunks, embeddings, review histories |
| `docfactory_redis_data` | `/data` | Redis fast-path status cache |
| `docfactory_document_storage` | `/app/storage` | Uploaded raw files (PDF/images) shared between API and Temporal worker |




