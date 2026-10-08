# Multi-Agent Document Processing Factory

> **An enterprise-grade document intelligence platform** that combines cognitive AI agents, deterministic mathematical validation, confidence-based human-in-the-loop review, dual workflow orchestration, and a modern React dashboard to transform unstructured business documents into audit-ready structured data.

---

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Temporal](https://img.shields.io/badge/Temporal-Orchestrator-000000?style=flat-square&logo=temporal&logoColor=white)](https://temporal.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-336791?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Free%20Tier-8E75C2?style=flat-square&logo=googlegemini&logoColor=white)](https://ai.google.dev)
[![Tests](https://img.shields.io/badge/Pytest-230%20Passed-brightgreen?style=flat-square)](backend/tests/)

---

## Live Demo

- **Web Application (Frontend)**: [https://docfactory-frontend.vercel.app](https://docfactory-frontend.vercel.app)
- **API Documentation (Backend)**: [https://docfactory-backend.onrender.com/docs](https://docfactory-backend.onrender.com/docs)
- **Backend Health Check**: [https://docfactory-backend.onrender.com/health/ready](https://docfactory-backend.onrender.com/health/ready)

> [!NOTE]
> The live deployment runs entirely on a **$0 cloud stack**: Vercel (Frontend SPA), Render (FastAPI + Tesseract OCR Web Service), Neon (Serverless PostgreSQL 16 with `pgvector`), and Google AI Studio Free Tier (`gemini-3.5-flash-lite`).

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Key Features](#key-features)
3. [End-to-End Workflow](#end-to-end-workflow)
4. [System Architecture](#system-architecture)
5. [Technology Stack](#technology-stack)
6. [AI & LLM Architecture](#ai--llm-architecture)
7. [Document Processing Pipeline](#document-processing-pipeline)
8. [Validation & Confidence Scoring](#validation--confidence-scoring)
9. [Human-in-the-Loop Review Workflow](#human-in-the-loop-review-workflow)
10. [RAG & Vector Retrieval Engine](#rag--vector-retrieval-engine)
11. [Temporal Orchestration & Cloud Fallback](#temporal-orchestration--cloud-fallback)
12. [Redis Status Acceleration](#redis-status-acceleration)
13. [Database Architecture (PostgreSQL + pgvector)](#database-architecture-postgresql--pgvector)
14. [Frontend Dashboard](#frontend-dashboard)
15. [Docker & Local Development](#docker--local-development)
16. [Cloud Deployment Architecture](#cloud-deployment-architecture)
17. [REST API Directory](#rest-api-directory)
18. [Project Structure](#project-structure)
19. [Testing & Quality Assurance](#testing--quality-assurance)
20. [Production Verification](#production-verification)
21. [Environment Variables](#environment-variables)
22. [Future Improvements](#future-improvements)
23. [Interview & System Design Talking Points](#interview--system-design-talking-points)

---

## Platform Overview

The **Multi-Agent Document Processing Factory** is an end-to-end document intelligence platform designed to address the key shortcomings of traditional OCR templates and monolithic LLM prompts: arithmetic hallucinations, lack of auditability, brittleness when formats change, and unhandled failure states.

Raw business documents—such as invoices, receipts, purchase orders, and contracts—are ingested and processed through a pipeline of specialized cognitive tasks:
- **Tesseract OCR** extracts layout-preserved raw text.
- **LLM-driven classification & extraction** parses messy document text into strongly-typed Pydantic schemas.
- **Deterministic Python business rules** mathematically verify totals, tax calculations, line-item arithmetic ($qty \times unit\_price = total$), and chronological dates without relying on LLM math.
- A **multi-factor confidence formula** calculates composite reliability.
- **Automated routing** separates high-confidence records ($\ge 85\%$ score and 0 validation errors) for automatic approval, while isolating low-confidence or mathematically inconsistent documents into an audited **Human Review Queue**.
- A **dual-mode execution engine** runs distributed, durable **Temporal workflows** in local/Docker deployments and seamlessly falls back to a direct in-process execution pipeline on lightweight cloud hosts where Temporal server is not deployed.

---

## Key Features

- **Multi-Format Ingestion**: Multipart file upload supporting PDF, PNG, JPG, JPEG, and TIFF with mime-type detection and content-hash deduplication.
- **OCR Engine**: Tesseract OCR engine integrated directly on Linux and container environments, extracting text while preserving page markers.
- **Document Classification**: Cognitive classification identifying document types (`INVOICE`, `RECEIPT`, `PURCHASE_ORDER`, `CONTRACT`, `OTHER`) with confidence scoring.
- **Schema-Guided Extraction**: Strongly-typed field extraction using Pydantic schemas, supporting line items, vendor metadata, currency codes, and dates.
- **Deterministic Validation Guardrails**: Zero-LLM-math policy; Python business rules mathematically verify all line items, tax additions, subtotal sums, and date sequences ($due\_date \ge invoice\_date$).
- **Multi-Factor Confidence Scoring**: Weighted composite formula combining classification confidence ($25\%$), extraction completeness ($35\%$), and rule-based validation ($40\%$).
- **Dual-Path Routing**: Automated auto-approval for records exceeding the $85\%$ confidence threshold with 0 validation errors; automatic quarantine to human review otherwise.
- **Human-in-the-Loop Review Dashboard**: Side-by-side OCR reference viewer, inline field editing, deterministic revalidation on submit, and immutable original extraction history.
- **Pluggable LLM Provider Abstraction**: Single unified interface supporting Google Gemini (`gemini-3.5-flash-lite`), OpenAI (`gpt-4o`), and local Ollama (`llama3.2`).
- **Dual Orchestration Strategy**: Full Temporal workflow orchestration locally, with automatic direct in-process pipeline fallback for serverless/free cloud hosting.
- **Redis Query Acceleration**: Low-latency workflow status caching (`TTL=3600s`) with automatic, transparent fallback to PostgreSQL.
- **pgvector Relational Embeddings**: Co-located 1536-dimensional vector storage in PostgreSQL with atomic cascading deletes on rejected documents.
- **Operational Analytics**: Real-time SQL aggregations computing stage latency, success rates, throughput time-series, and review workload.
- **Modern Glassmorphic UI**: React 18 SPA built with TypeScript, dark-mode design system, interactive review queue, and live telemetry polling.

---

## End-to-End Workflow

```
   [ Document Ingestion ] (Multipart PDF / Image Upload)
             │
             ▼
   [ Optical Character Recognition (OCR) ] (Tesseract Text Extraction)
             │
             ▼
   [ Document Classification ] (Invoice / Receipt / PO / Contract / Other)
             │
             ▼
   [ Structured Information Extraction ] (Schema-Guided Pydantic Extraction)
             │
             ▼
   [ Deterministic Business Validation ] (Python Rule Engine: Math, Taxes, Dates)
             │
             ▼
   [ Multi-Factor Confidence Scoring ] (Weighted Formula: Classify + Extract + Validate)
             │
             ▼
   [ Dual-Path Decision Router ]
        │                  │
        │ Score >= 0.85    │ Score < 0.85 OR
        │ & 0 Errors       │ Validation Errors
        ▼                  ▼
   [ AUTO-APPROVED ]   [ HUMAN REVIEW QUEUE ]
        │                  │
        │                  ├── Reviewer Inspects OCR & Edits JSON
        │                  ├── Deterministic Revalidation Engine
        │                  └── Reviewer Action: APPROVE / REJECT / CORRECT
        │                                  │
        └──────────────┬───────────────────┘
                       │
                       ▼
   [ Structured Data Persistence & Audit Trail ]
```

---

## System Architecture

```mermaid
flowchart TD
    subgraph Client["Presentation Layer"]
        User(["Client / Reviewer"])
        ReactApp["React 18 TypeScript SPA<br/>(Vercel: docfactory-frontend)"]
    end

    subgraph BackendGateway["API Gateway Layer (Render)"]
        FastAPI["FastAPI Application<br/>(Python 3.12, Uvicorn)"]
        Router["Endpoints: /documents, /review, /analytics, /rag"]
    end

    subgraph Orchestration["Dual Orchestration Strategy"]
        direction TB
        DecisionEngine{"Temporal Cluster<br/>Available?"}
        TemporalWorker["Temporal Distributed Engine<br/>(Local Docker / Temporal Server)"]
        DirectFallback["Direct In-Process Pipeline<br/>(Render Cloud Fallback)"]
    end

    subgraph ProcessingPipeline["Cognitive Processing Pipeline"]
        OCR["1. OCR Extraction<br/>(Tesseract Engine)"]
        Classify["2. Classification Agent<br/>(Layout & Text Analysis)"]
        Extract["3. Structured Extraction<br/>(Pydantic Schema Parser)"]
        Validate["4. Deterministic Validation<br/>(Python Math & Date Rules)"]
        Score["5. Confidence Scoring<br/>(Weighted Formula)"]
    end

    subgraph LLMProviders["Pluggable LLM Provider Layer"]
        Gemini["Google Gemini API<br/>(gemini-3.5-flash-lite Free Tier)"]
        OpenAI["OpenAI API<br/>(gpt-4o / Azure)"]
        Ollama["Local Ollama<br/>(llama3.2 Offline)"]
    end

    subgraph DecisionRouter["Dual-Path Routing"]
        AutoCheck{"Confidence >= 0.85<br/>AND 0 Errors?"}
        ApprovedStatus["APPROVED State"]
        ReviewQueue["Human Review Queue<br/>(REVIEW_REQUIRED)"]
        HumanReviewer["Reviewer Correction<br/>& Deterministic Revalidation"]
    end

    subgraph Persistence["Persistence & Cache Tier"]
        RedisCache["Redis 7 Cache<br/>(Workflow Status, TTL 3600s)"]
        PostgresDB[("Neon PostgreSQL 16<br/>(Relational State & Audit Log)")]
        PGVector[("pgvector Extension<br/>(Vector Chunks 1536-dim)")]
    end

    User -->|Interacts| ReactApp
    ReactApp -->|REST API Requests| FastAPI
    FastAPI --> Router
    Router --> DecisionEngine

    DecisionEngine -->|Yes (Local/Docker)| TemporalWorker
    DecisionEngine -->|No (Free Cloud Fallback)| DirectFallback

    TemporalWorker --> OCR
    DirectFallback --> OCR

    OCR --> Classify
    Classify --> Extract
    Extract --> Validate
    Validate --> Score

    Classify -.-> LLMProviders
    Extract -.-> LLMProviders

    LLMProviders --- Gemini
    LLMProviders --- OpenAI
    LLMProviders --- Ollama

    Score --> AutoCheck
    AutoCheck -->|Yes| ApprovedStatus
    AutoCheck -->|No| ReviewQueue

    ReviewQueue --> HumanReviewer
    HumanReviewer -->|Approve / Correct| ApprovedStatus
    HumanReviewer -->|Reject| PostgresDB

    Router -->|Status Read/Write| RedisCache
    RedisCache -.->|Fallback on Miss/Down| PostgresDB
    Router -->|Metadata & Document CRUD| PostgresDB
    ApprovedStatus -.->|Chunk Storage| PGVector
```

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend Framework** | React | 18.x | Component-driven operational dashboard |
| **Frontend Language** | TypeScript | 5.x | Strongly-typed API client and UI contracts |
| **Frontend Bundler** | Vite | 6.x | High-performance bundling and asset pipeline |
| **Styling & Design** | Vanilla CSS | CSS3 | Custom dark-mode glassmorphic design system |
| **API Framework** | FastAPI | 0.115+ | Asynchronous REST API with automatic OpenAPI specs |
| **Python Runtime** | Python | 3.12+ | Core backend runtime |
| **Data Validation** | Pydantic | 2.x | Schema-guided extraction and request/response models |
| **Relational Database** | PostgreSQL | 16 | ACID relational storage, audit trails, and document records |
| **Vector Engine** | pgvector | 0.7+ | Co-located 1536-dimensional vector embedding storage |
| **Database ORM** | SQLAlchemy | 2.0 (asyncio) | Asynchronous database queries and schema definitions |
| **Database Driver** | asyncpg | 0.30+ | High-performance async PostgreSQL driver with SSL support |
| **Cache & Acceleration**| Redis | 7 Alpine | Sub-millisecond workflow status polling cache (`TTL=3600s`) |
| **Workflow Engine** | Temporal | 1.25+ | Distributed workflow orchestration (Local/Docker) |
| **Workflow SDK** | Temporalio | 1.9+ | Async workflow and activity definitions in Python |
| **OCR Engine** | Tesseract OCR | 5.x | Open-source optical character recognition |
| **Cloud LLM Provider** | Google Gemini | v1beta REST | `gemini-3.5-flash-lite` (Google AI Studio Free Tier) |
| **Alternative LLM Providers** | OpenAI / Ollama | SDK / REST | `gpt-4o` structured output / `llama3.2` local model |
| **Logging** | structlog | 24.x | Context-rich JSON structured logging |
| **Containerization** | Docker Compose | v2.38+ | 8-service local development container stack |
| **Testing Framework** | Pytest | 9.x | 230 automated unit, provider, and integration tests |
| **Cloud Hosting** | Vercel + Render | Managed | Vercel (Frontend), Render (Backend + Tesseract), Neon (DB) |

---

## AI & LLM Architecture

### 1. Unified LLM Provider Abstraction
All cognitive tasks interact with LLMs through an abstract base class [`LLMProvider`](backend/app/services/llm/base.py), isolating business logic from model-specific vendor APIs:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> T:
        """Generate structured output validated against a Pydantic schema."""
```

### 2. Google Gemini Free-Tier Provider ([`GeminiLLMProvider`](backend/app/services/llm/gemini.py))
- **Model**: `gemini-3.5-flash-lite` (Available on Google AI Studio Free Tier at $0 API cost).
- **Endpoint**: Google Generative Language REST API (`/v1beta/models/{model}:generateContent`).
- **Zero Heavy SDK**: Implemented purely via standard asynchronous `httpx` HTTP calls.
- **Native Structured Outputs**: Configured with `responseMimeType: "application/json"` and `responseSchema`.
- **JSON Schema Inlining**: Pydantic v2 schemas generate `$defs` and `$ref` pointers for nested models (such as `InvoiceLineItem` inside `InvoiceExtraction`). A custom recursive transformation inlines all `$defs` and strips unsupported metadata keys (`$schema`, `title`, `default`), producing a fully self-contained schema compatible with Gemini's API.
- **Security & Secret Hygiene**: Authentication is transmitted exclusively through the `x-goog-api-key` header—never exposed in query parameters, URLs, or application logs.

### 3. OpenAI Provider ([`OpenAILLMProvider`](backend/app/services/llm/openai.py))
- Uses OpenAI's `beta.chat.completions.parse` with strict Pydantic model guarantees for `gpt-4o`.

### 4. Local Ollama Provider ([`OllamaLLMProvider`](backend/app/services/llm/ollama.py))
- Connects to a local Ollama daemon for offline development without internet access or API keys.

---

## Document Processing Pipeline

The pipeline processes documents through 5 sequential stages:

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as FastAPI Backend
    participant Pipeline as Orchestrator (Temporal / Direct Fallback)
    participant OCR as OCR Service (Tesseract)
    participant LLM as LLM Provider (Gemini / OpenAI)
    participant Rules as Deterministic Rule Engine
    participant DB as PostgreSQL + Redis

    Client->>API: POST /api/v1/documents (Upload File)
    API->>DB: Save Document Record (status: UPLOADED)
    API-->>Client: 201 Created (document_id)

    Client->>API: POST /api/v1/documents/{id}/process
    API->>Pipeline: Dispatch Workflow / Start Direct Pipeline
    API-->>Client: 202 Accepted (processing started)

    Pipeline->>OCR: Activity 1: Extract Text & Layout
    OCR-->>Pipeline: Extracted text, character count, page count
    Pipeline->>DB: Update stage: OCR (status: COMPLETED)

    Pipeline->>LLM: Activity 2: Classify Document
    LLM-->>Pipeline: DocumentType (INVOICE, RECEIPT, etc.) & confidence
    Pipeline->>DB: Update stage: CLASSIFICATION (status: COMPLETED)

    Pipeline->>LLM: Activity 3: Extract Structured Fields (Pydantic Schema)
    LLM-->>Pipeline: Strongly typed extraction payload
    Pipeline->>DB: Update stage: EXTRACTION (status: COMPLETED)

    Pipeline->>Rules: Activity 4: Mathematical & Business Validation
    Rules-->>Pipeline: ValidationResult (is_valid, errors, warnings)
    Pipeline->>DB: Update stage: VALIDATION (status: COMPLETED)

    Pipeline->>Rules: Activity 5: Compute Composite Confidence Score
    Rules-->>Pipeline: Overall Confidence, Route Decision (APPROVED vs REVIEW_REQUIRED)
    Pipeline->>DB: Update Document status & stages

    opt Score < 0.85 or Validation Errors
        Pipeline->>DB: Insert into review_queue_items (PENDING)
    end
```

---

## Validation & Confidence Scoring

### Deterministic Business Rules
LLMs are probabilistic and notoriously prone to arithmetic mistakes. In this factory, **all mathematical verification is strictly deterministic**:
- **Line Item Total**: $\text{quantity} \times \text{unit\_price} = \text{line\_total}$ (allowing $\pm 0.01$ rounding tolerance).
- **Subtotal Verification**: Sum of line item totals must equal the stated subtotal.
- **Tax Calculation**: $\text{subtotal} + \text{tax\_amount} = \text{total\_amount}$.
- **Chronological Validity**: $\text{due\_date} \ge \text{invoice\_date}$.
- **Required Metadata**: Presence of mandatory vendor identifiers, invoice numbers, and currency codes.

### Composite Confidence Formula

Document reliability is computed as a weighted linear combination across three independent dimensions:

$$\text{Overall Confidence} = (0.25 \times C_{\text{class}}) + (0.35 \times E_{\text{extract}}) + (0.40 \times V_{\text{valid}})$$

Where:
- **$C_{\text{class}} \in [0.0, 1.0]$**: Confidence score returned by the classification model.
- **$E_{\text{extract}} \in [0.0, 1.0]$**: Extraction completeness ratio (populated non-null fields divided by total expected schema fields).
- **$V_{\text{valid}} \in [0.0, 1.0]$**: Deterministic validation score calculated by deducting rule penalties:
  $$\text{Penalty} = (N_{\text{error}} \times 0.25) + (N_{\text{warning}} \times 0.08) + (N_{\text{info}} \times 0.02)$$
  $$V_{\text{valid}} = \max(0.0, \min(1.0, 1.0 - \text{Penalty}))$$

### Routing Decision Logic
- **Auto-Approved (`APPROVED`)**: $\text{Overall Confidence} \ge 0.85$ **AND** $N_{\text{error}} = 0$ (`is_valid == True`).
- **Human Review (`REVIEW_REQUIRED`)**: $\text{Overall Confidence} < 0.85$ **OR** any validation error exists ($N_{\text{error}} > 0$).

---

## Human-in-the-Loop Review Workflow

Documents routed to `REVIEW_REQUIRED` enter an audited, human-supervised resolution queue:

```
[ REVIEW_REQUIRED ]
       │
       ▼
1. GET /api/v1/review/queue           Reviewer views pending documents & urgency
2. POST /api/v1/review/{id}/start     Reviewer claims ownership (status: IN_REVIEW)
3. Reviewer inspects side-by-side:    Original OCR text vs. extracted JSON fields
4. Reviewer action options:
       ├── APPROVE                     Accept extraction as-is
       ├── REJECT                      Reject document (marks REJECTED, records reason)
       └── CORRECT                     Submit updated JSON fields
             │
             ▼
       Deterministic Revalidation Engine
             ├── If valid: Marks APPROVED
             └── If errors remain: Returns validation feedback to reviewer
5. Immutable Audit Trail:
       original_extracted_data is preserved permanently
       reviewed_extracted_data stores the human modifications
       reviewed_by and reviewed_at timestamps recorded
```

---

## RAG & Vector Retrieval Engine

The repository includes a co-located semantic retrieval subsystem built on PostgreSQL's `pgvector` extension:

- **Page-Preserving Chunking**: Text is split into 800-character windows with a 120-character sliding overlap, strictly preserving page boundaries (`--- Page N ---`, `\x0c`) and paragraph breaks.
- **Vector Storage**: Stored in the `document_chunks` table with `VECTOR(1536)` embeddings and cosine distance indexing (`<=>`).
- **Relational Integrity**: Chunks are linked via foreign keys to the parent `documents` table with `ON DELETE CASCADE`. If a document is rejected or deleted, its vector chunks are purged atomically.
- **Hallucination Guardrail**: Strict prompt constraints require answering exclusively from retrieved context; if context is insufficient, the engine returns a standardized refusal.

> [!IMPORTANT]
> **Cloud Environment Notice**: The database schema and pgvector infrastructure are fully implemented in PostgreSQL. In the free cloud deployment, semantic indexing and RAG querying require an active embedding provider configuration (such as OpenAI's `text-embedding-3-small`). RAG queries are therefore not claimed as verified on the free cloud tier without active embedding keys.

---

## Temporal Orchestration & Cloud Fallback

### Distributed Mode (Local & Full Docker Stack)
In local and containerized deployments, the entire 5-stage pipeline runs under Temporal's distributed orchestration engine:
- **Durable State**: If a worker process restarts during extraction, Temporal reassigns the workflow and resumes from the exact activity without re-running earlier steps.
- **Exponential Backoff**: Activities define retry policies with 2-second initial intervals, $2.0 \times$ backoff coefficient, and maximum 3 attempts.
- **Execution Idempotency**: Each workflow is assigned a deterministic ID: `document-processing-{document_id}`. Duplicate requests return `409 Conflict`.

### Cloud Fallback Mode (Render Cloud Deployment)
On free cloud platforms like Render, running a persistent Temporal cluster daemon along with dedicated gRPC worker processes is not supported due to resource limits.

To ensure production resilience without a paid Temporal Cloud cluster:
- When a document is dispatched for processing, the backend attempts to connect to the Temporal frontend.
- If Temporal is unreachable (`connection_failed_fallback_to_mock`), the backend automatically and transparently activates an **in-process direct pipeline fallback** ([`_run_direct_pipeline()`](backend/app/services/temporal/client.py)).
- The direct pipeline executes the identical sequence of activities, invokes the same LLM providers, updates the identical database stage records, and routes to the review queue with 100% feature parity.

---

## Redis Status Acceleration

During document processing, the frontend polls the backend every 1–2 seconds to update live stage indicators.

- **Fast-Path Caching**: Each stage update writes current workflow status into Redis (`document:status:{document_id}`) with a 3600-second TTL.
- **Lock Contention Prevention**: High-frequency status queries read directly from Redis in $<1\,\text{ms}$, sparing the relational database from redundant polling queries.
- **Transparent Fallback**: The `RedisService` wraps all operations in resilient try/except blocks. If Redis is unavailable or unconfigured, the API queries PostgreSQL directly without throwing errors or dropping requests.

---

## Database Architecture (PostgreSQL + pgvector)

The database schema utilizes Neon Serverless PostgreSQL 16 with the `pgvector` extension:

```
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│           documents             │       │      processing_stages          │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ id (UUID, PK)                   │◄──┐   │ id (UUID, PK)                   │
│ filename, mime_type, file_size  │   └───┤ document_id (UUID, FK)          │
│ file_path, file_hash            │       │ stage (VARCHAR)                 │
│ status (VARCHAR)                │       │ status (PENDING/RUNNING/...)    │
│ document_type (VARCHAR)         │       │ started_at, completed_at        │
│ confidence_score (FLOAT)        │       │ duration_ms (INTEGER)           │
│ is_valid (BOOLEAN)              │       │ error_message (TEXT)            │
│ original_extracted_data (JSONB) │       └─────────────────────────────────┘
│ reviewed_extracted_data (JSONB) │
│ created_at, updated_at          │       ┌─────────────────────────────────┐
└────────────────┬────────────────┘       │       review_queue_items        │
                 │                        ├─────────────────────────────────┤
                 │◄───────────────────────┤ id (UUID, PK)                   │
                 │                        │ document_id (UUID, FK)          │
                 │                        │ status (PENDING/IN_REVIEW/...)  │
                 ▼                        │ priority (VARCHAR)              │
┌─────────────────────────────────┐       │ reviewer_notes (TEXT)           │
│        document_chunks          │       │ assigned_to, reviewed_at        │
├─────────────────────────────────┤       └─────────────────────────────────┘
│ id (UUID, PK)                   │
│ document_id (UUID, FK, CASCADE) │
│ chunk_index, page_number        │
│ content (TEXT)                  │
│ embedding (VECTOR(1536))        │
└─────────────────────────────────┘
```

- **Asyncpg SSL Compatibility**: Seamlessly handles Neon PostgreSQL `sslmode=require` query parameters by translating them into asyncpg-compatible SSL contexts.
- **Relational Integrity**: Foreign keys enforce referential integrity with cascading deletes for document chunks.

---

## Frontend Dashboard

Built with React 18, TypeScript, and Vite, featuring a responsive dark-mode glassmorphic interface:

- **Ingestion Cockpit**: Drag-and-drop document uploader with real-time format validation and progress indicator.
- **Live Pipeline Monitor**: Visual timeline tracking all 5 processing stages in real time.
- **Human Review Center**: Side-by-side view with extracted JSON editor and OCR text viewer, displaying inline validation error badges.
- **Document Explorer**: Searchable, filterable ledger of all processed documents with status chips and confidence scores.
- **Operational Analytics Dashboard**: Real-time KPI cards for auto-approval rate, stage-by-stage latency charts, and review queue backlog.
- **Production Routing**: Uses a unified API client wrapper (`frontend/src/api/client.ts`) that targets the configured backend URL with comprehensive error formatting.

---

## Docker & Local Development

### Prerequisites
- Python 3.12+
- Node.js 20+ & npm 10+
- Docker & Docker Compose (for containerized stack)

### Option A: Local Native Development

```bash
# 1. Clone repository
git clone https://github.com/yogyansh123/Multi-Agent-Document-Processing-Factory.git
cd Multi-Agent-Document-Processing-Factory

# 2. Configure environment
cp .env.example .env
# Edit .env to set your GEMINI_API_KEY (or OPENAI_API_KEY)

# 3. Setup backend
cd backend
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. In a separate terminal, setup frontend
cd ../frontend
npm install
npm run dev
```

The frontend will be accessible at [http://localhost:5173](http://localhost:5173) and backend docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### Option B: Full 8-Service Docker Compose Stack

```bash
# Start all 8 services: Postgres, Redis, Temporal, Temporal Worker, Temporal UI, Backend, Frontend
docker compose up -d

# Verify service health
docker compose ps

# Tail logs
docker compose logs -f backend
```

| Service | Internal Port | Host Port | Purpose |
|---|---|---|---|
| `frontend` | 80 | **5173** | Nginx serving React SPA |
| `backend` | 8000 | **8000** | FastAPI API Gateway |
| `temporal` | 7233 | **7233** | Temporal gRPC Cluster |
| `temporal-ui` | 8080 | **8088** | Temporal Web Dashboard |
| `postgres` | 5432 | **5432** | PostgreSQL 16 + pgvector |
| `redis` | 6379 | **6379** | Redis 7 Cache |
| `temporal-worker`| — | — | Async Python Worker |

---

## Cloud Deployment Architecture

The live production deployment operates on a zero-cost architecture:

```
┌─────────────────────────────────┐
│     Vercel Edge Network         │
│  React 18 SPA (TypeScript)      │
│  https://docfactory-frontend    │
└────────────────┬────────────────┘
                 │ HTTPS (REST)
                 ▼
┌─────────────────────────────────┐
│       Render Web Service        │
│  FastAPI (Python 3.12)          │
│  Tesseract OCR 5 Engine         │
│  Direct Pipeline Fallback Mode  │
│  https://docfactory-backend     │
└────────┬───────────────┬────────┘
         │               │
         │ HTTPS / TLS   │ x-goog-api-key
         ▼               ▼
┌─────────────────┐  ┌─────────────────────────┐
│ Neon PostgreSQL │  │ Google AI Studio        │
│ 16 + pgvector   │  │ Gemini 3.5 Flash-Lite   │
│ Cloud DB        │  │ Free-Tier API           │
└─────────────────┘  └─────────────────────────┘
```

1. **Frontend**: Hosted on **Vercel**, configured with client-side SPA routing and automated preview deploys.
2. **Backend**: Containerized web service on **Render**, built with a custom Dockerfile providing Python 3.12, libtesseract-dev, and tesseract-ocr packages.
3. **Database**: Managed **Neon** Serverless PostgreSQL with native `pgvector` extension and asyncpg SSL compatibility.
4. **LLM Engine**: **Google AI Studio** Free Tier running `gemini-3.5-flash-lite`.

---

## REST API Directory

Interactive Swagger UI documentation is available at `/docs`.

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/documents` | `POST` | Upload and register document (multipart/form-data) |
| `/api/v1/documents` | `GET` | List all documents with pagination and status filters |
| `/api/v1/documents/{id}` | `GET` | Retrieve single document metadata and processing results |
| `/api/v1/documents/{id}/process` | `POST` | Trigger asynchronous pipeline execution |
| `/api/v1/documents/{id}/processing-status` | `GET` | Low-latency pipeline status check (cached via Redis) |
| `/api/v1/documents/{id}/ocr` | `POST` | Manually run OCR text extraction |
| `/api/v1/documents/{id}/classify` | `POST` | Manually run document classification |
| `/api/v1/documents/{id}/extract` | `POST` | Manually run schema-guided extraction |
| `/api/v1/documents/{id}/validate` | `POST` | Manually run deterministic business validation |
| `/api/v1/documents/{id}/confidence` | `POST` | Compute multi-factor confidence score |
| `/api/v1/review/queue` | `GET` | List documents awaiting human review |
| `/api/v1/review/{id}` | `GET` | Fetch review details, original extraction, and OCR text |
| `/api/v1/review/{id}/start` | `POST` | Claim review item (`IN_REVIEW`) |
| `/api/v1/review/{id}/approve` | `POST` | Manually approve extraction as-is |
| `/api/v1/review/{id}/reject` | `POST` | Reject document with audit reason |
| `/api/v1/review/{id}/correct` | `POST` | Submit corrected fields with deterministic revalidation |
| `/api/v1/analytics/summary` | `GET` | Summary statistics (volume, approval rate, review count) |
| `/api/v1/analytics/stages` | `GET` | Stage-by-stage execution latency and success rates |
| `/api/v1/analytics/reviews` | `GET` | Review queue turnaround times and decision breakdown |
| `/api/v1/rag/query` | `POST` | Semantic search and natural language question answering |
| `/health` | `GET` | Liveness check |
| `/health/ready` | `GET` | Readiness check verifying Database and Redis connectivity |

---

## Project Structure

```
multi-agent-document-processing-factory/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/       # FastAPI route modules (documents, review, etc.)
│   │   │       └── router.py        # Central v1 route aggregator
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic BaseSettings configuration
│   │   │   └── logging.py           # structlog logging setup
│   │   ├── db/
│   │   │   ├── base.py              # SQLAlchemy declarative base
│   │   │   └── session.py           # Async engine and session maker with SSL handling
│   │   ├── models/                  # SQLAlchemy ORM models (Document, Stage, etc.)
│   │   ├── schemas/                 # Pydantic schemas (Extraction, Validation, API DTOs)
│   │   ├── services/
│   │   │   ├── analytics/           # Optimized SQL aggregation queries
│   │   │   ├── confidence/          # Multi-factor confidence scoring engine
│   │   │   ├── llm/                 # Pluggable LLM providers (Gemini, OpenAI, Ollama)
│   │   │   ├── ocr/                 # Tesseract OCR engine abstraction
│   │   │   ├── rag/                 # Text chunker, embeddings, and pgvector retriever
│   │   │   ├── redis/               # Redis query cache service with fallback
│   │   │   ├── storage/             # Local and cloud storage providers
│   │   │   ├── temporal/            # Temporal client & direct pipeline fallback
│   │   │   └── validation/          # Deterministic Python mathematical rules engine
│   │   ├── workflows/               # Temporal workflow definitions & 5 activities
│   │   └── main.py                  # FastAPI application entrypoint & lifecycle
│   ├── tests/                       # 230 automated unit, activity, and mock tests
│   ├── Dockerfile                   # Multi-stage production container with Tesseract
│   └── requirements.txt             # Backend Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/                     # Unified Axios/Fetch API client wrapper
│   │   ├── components/              # Dashboard, Upload, Review Queue, Analytics, RAG
│   │   ├── types/                   # TypeScript interfaces matching backend models
│   │   ├── App.tsx                  # Root React application
│   │   └── main.tsx                 # Vite entrypoint
│   ├── package.json                 # Frontend dependencies
│   └── vite.config.ts               # Vite configuration
├── docker-compose.yml               # 8-service container orchestration stack
└── README.md                        # Project documentation
```

---

## Testing & Quality Assurance

The codebase includes an automated test suite executed via Pytest:

```bash
# Run the complete backend test suite
cd backend
pytest tests/ -v
```

### Verification Metrics
- **Backend Test Suite**: **230 passed**, 0 failed across unit, activity, and provider test modules.
- **Mocked HTTP Transports**: All LLM tests (Gemini, OpenAI, Ollama) utilize `httpx.MockTransport`. **Zero real API calls or paid tokens are consumed during testing.**
- **Frontend Quality**: TypeScript typecheck (`tsc -b`) and Vite production build pass with 0 errors.
- **Docker Compose**: `docker compose config --quiet` validates syntax with exit code 0.

---

## Production Verification

The full end-to-end cloud pipeline was verified live across the deployed cloud services (Vercel + Render + Neon PostgreSQL + Google Gemini):

```
[ Upload ] ──► [ OCR ] ──► [ Gemini Classification ] ──► [ Structured Extraction ]
                                                                   │
                                                                   ▼
[ Approved ] ◄── [ Human Review Queue ] ◄── [ Review Routing ] ◄── [ Validation & Confidence ]
```

### Live Cloud Execution Trace
During live end-to-end cloud validation, a sample document was ingested through the deployed factory:
1. **Upload**: Document successfully received and stored via `POST /api/v1/documents`.
2. **OCR**: Tesseract OCR extracted layout-preserved text on Render.
3. **Classification**: Gemini (`gemini-3.5-flash-lite`) classified the document as `OTHER` with a **95.0%** confidence rating.
4. **Structured Extraction**: Extracted typed fields into schema structures.
5. **Validation**: Deterministic rule engine verified content with a **100%** validation score (0 errors).
6. **Confidence Scoring**: Evaluated via the composite formula:
   $$\text{Overall Confidence} = (0.25 \times 0.95) + (0.35 \times 0.50) + (0.40 \times 1.00) = 81.3\%$$
7. **Routing**: Because $81.3\% < 85.0\%$ auto-approval threshold, the document correctly quarantined into `REVIEW_REQUIRED`.
8. **Human Review**: A human reviewer claimed the item in the review queue, inspected the side-by-side OCR comparison, and approved the record, successfully transitioning it to `APPROVED`.

> [!NOTE]
> This trace represents a verified end-to-end execution path through the live cloud stack and is presented to illustrate the dual-path review workflow.

---

## Environment Variables

Copy `.env.example` to `.env` and configure the appropriate values:

| Variable | Description | Default / Example |
|---|---|---|
| `ENVIRONMENT` | Application environment (`development` / `production`) | `production` |
| `DATABASE_URL` | PostgreSQL connection string (asyncpg format) | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `LLM_PROVIDER` | Active LLM provider (`gemini`, `openai`, `ollama`) | `gemini` |
| `GEMINI_API_KEY` | Google AI Studio API key (Free Tier) | *Set in environment* |
| `GEMINI_MODEL` | Gemini model identifier | `gemini-3.5-flash-lite` |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI provider) | *Optional* |
| `OPENAI_MODEL` | OpenAI model identifier | `gpt-4o` |
| `OLLAMA_BASE_URL` | Base URL for local Ollama server | `http://localhost:11434` |
| `TEMPORAL_HOST` | Temporal gRPC cluster host | `localhost` / `temporal` |
| `TEMPORAL_PORT` | Temporal gRPC cluster port | `7233` |
| `AUTO_APPROVAL_THRESHOLD` | Minimum confidence score for auto-approval | `0.85` |
| `CORS_ORIGINS` | Allowed CORS origins for FastAPI gateway | `["http://localhost:5173"]` |
| `VITE_API_BASE_URL` | Frontend API base URL pointing to FastAPI backend | `https://docfactory-backend.onrender.com` |

---

## Future Improvements

- **Temporal Cloud Integration**: Connect the cloud deployment to a managed Temporal Cloud namespace for persistent distributed workflow state in production.
- **Cloud Embedding Provider**: Configure managed vector embeddings (e.g. `text-embedding-3-small`) to enable active cloud RAG search.
- **Asynchronous Batch Processing**: Support bulk multi-document ZIP ingestion with fan-out workflow execution.
- **Additional Document Schemas**: Extend Pydantic schemas for medical bills, bills of lading, and tax documents.
- **Outbound Webhooks**: Dispatch automated webhook notifications on document approval or review escalation.

---

## Interview & System Design Talking Points

When discussing this project in engineering interviews, focus on these core architectural decisions:

### 1. Deterministic Guardrails over Probabilistic Arithmetic
- **Talking Point**: LLMs are probabilistic language predictors and should never be trusted with mathematical validation.
- **Solution**: The factory enforces a strict division of labor: LLMs perform layout interpretation and semantic field extraction, while deterministic Python rules verify arithmetic sums, tax calculations, and date sequences.

### 2. Dual Orchestration & Cloud Fallback Architecture
- **Talking Point**: Distributed workflow engines like Temporal provide state durability and activity retries, but running a full cluster on free/serverless hosting can be cost-prohibitive.
- **Solution**: Designed a resilient dual execution strategy. In local/Docker environments, Temporal coordinates activities with idempotency and exponential backoff. In lightweight cloud deployments, the system detects cluster unavailability and transparently falls back to an in-process pipeline with zero downtime.

### 3. Multi-Factor Confidence-Based Routing
- **Talking Point**: Binary accept/reject thresholds based purely on model confidence are naive and prone to edge-case errors.
- **Solution**: Implemented a tripartite confidence formula combining classification confidence, extraction completeness, and deterministic validation penalties. Documents that fail the $85\%$ confidence threshold or have any validation errors are quarantined to an audited review queue.

### 4. Zero-Cost Cloud Production Engineering
- **Talking Point**: Building a production-grade AI platform without recurring infrastructure costs.
- **Solution**: Engineered the system to run on a completely free cloud tier by pairing Render (FastAPI + Tesseract), Vercel (React SPA), Neon (PostgreSQL + pgvector), and Google AI Studio Free Tier (`gemini-3.5-flash-lite`).

### 5. Auditability & Immutable Lineage
- **Talking Point**: Regulatory compliance requires that AI-generated data can be audited against human corrections.
- **Solution**: When a reviewer corrects a field, `original_extracted_data` is preserved immutably, `reviewed_extracted_data` stores human modifications, and deterministic revalidation is enforced before approval is granted.

---

## License

Proprietary — All rights reserved.
