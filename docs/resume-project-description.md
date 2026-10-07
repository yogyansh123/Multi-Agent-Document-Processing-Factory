# Resume Project Description: Multi-Agent Document Processing Factory

> **Project Name**: Multi-Agent Document Processing Factory  
> **Role Title Suggestion**: Senior AI / Backend Engineer • Distributed Systems & AI Platforms  
> **Repository Scope**: 8-Service Distributed Architecture (FastAPI, Temporal, LangGraph, PostgreSQL/pgvector, Redis, React)

---

## 1. Resume Bullet Point Options

### Version A — Concise & Impact-Oriented (2 Bullets)
- Engineered a distributed, multi-agent document processing platform using **FastAPI**, **LangGraph**, and **Temporal**, executing 5 idempotent workflow activities (OCR, classification, extraction, validation, confidence scoring) with exponential backoff retries and human-in-the-loop review queues.
- Integrated **PostgreSQL 16 + pgvector** for transactional metadata and 1536-dimensional semantic retrieval (RAG) with traceable source citations, **Redis** for sub-millisecond status acceleration, and a **React/TypeScript** glassmorphic cockpit, validated by a **211-test automated pytest suite**.

---

### Version B — Technical Architecture & Reliability Focus (3 Bullets)
- Architected an 8-service containerized document intelligence pipeline orchestrating **LangGraph** cognitive agents with **Temporal** distributed workflows (`document-processing-queue`), achieving durable state persistence, strict workflow idempotency, and automated recovery across transient failures.
- Built a multi-factor confidence scoring engine ($0.25 \times \text{Class} + 0.35 \times \text{Extract} + 0.40 \times \text{Val}$) and dual-path routing that auto-approves high-confidence documents ($\ge 0.85$) while routing anomalies to a custom human review queue with deterministic revalidation and original extraction preservation.
- Implemented an embedded **pgvector** RAG subsystem featuring 800-character paragraph-aware chunking, cosine similarity retrieval (`<=>`), strict anti-hallucination refusals, and dynamic SQL analytics aggregation across operational records, verified by **211 unit/integration tests (100% pass rate)**.

---

### Version C — ATS-Optimized Keywords & Engineering Depth (4 Bullets)
- **Distributed Workflow & Multi-Agent Architecture**: Designed a resilient document processing factory using **Python 3.12**, **FastAPI**, **Temporalio SDK**, and **LangGraph**, deploying 5 idempotent workflow activities with deterministic retry policies (`max_attempts=3`, `initial_interval=2s`).
- **Database Engineering & Vector Search**: Engineered hybrid storage utilizing **PostgreSQL** for ACID metadata and **pgvector** for 1536-dimensional vector embeddings, eliminating external vector DB latency while ensuring atomic chunk deletions on document rejection.
- **Caching & Operational Telemetry**: Deployed **Redis 7** for status acceleration (`TTL=3600s`) with graceful relational fallback, alongside read-only SQL aggregation endpoints computing stage latency, success rates, and review turnaround times.
- **Frontend & Containerization**: Constructed a dark-mode **React 18** and **TypeScript** operational dashboard served via **Nginx 1.27 Alpine** with SPA fallback routing, orchestrated through an 8-service health-gated **Docker Compose** network.

---

## 2. Technical Skills Demonstrated & Verified

| Category | Verified Technologies & Frameworks |
|---|---|
| **Backend & Core** | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncio), Uvicorn |
| **Agentic AI & LLMs** | LangGraph, Structured Output Extraction, Multi-Agent Coordination, Prompt Engineering |
| **Workflow Orchestration** | Temporal Server, Temporal Worker (`temporalio` Python SDK), Workflow Idempotency, Activity Retries |
| **Databases & Vector Storage**| PostgreSQL 16, pgvector (`Vector(1536)`), Redis 7 (caching & fallback) |
| **Retrieval-Augmented Gen (RAG)**| Text Chunking (sliding window, page preservation), Vector Similarity Search (`<=>`), Grounded Citations |
| **Frontend & UI** | React 18, TypeScript, Vite, Responsive CSS, Glassmorphic Design, SVG Charts |
| **DevOps & Infrastructure** | Docker, Docker Compose v2, Multi-Stage Builds, Nginx Alpine, Non-Root Hardening, Health Probes |
| **Testing & Quality Assurance** | Pytest, Pytest-Asyncio, HTTPX AsyncClient, Test-Double Providers, Unit & E2E Integration (211 Tests) |

---

## 3. Verified Metrics & Architecture Facts (Audit-Ready)

When discussing this project in technical interviews or screenings, use only these verified factual metrics:

- **211 automated backend tests** passing with 0 failures across 20 test modules.
- **8 coordinated Docker Compose services**: `frontend`, `backend`, `temporal-worker`, `postgres`, `redis`, `temporal`, `temporal-ui`, `temporal-admin-tools`.
- **5 sequential idempotent Temporal activities**: `run_ocr`, `classify_document`, `extract_fields`, `validate_document`, `score_confidence`.
- **3 persistent named volumes**: `docfactory_postgres_data`, `docfactory_redis_data`, `docfactory_document_storage`.
- **1536-dimensional vector embeddings** stored and retrieved via pgvector cosine distance `<=>`.
- **8-stage visual pipeline lifecycle**: `UPLOADED` $\rightarrow$ `PROCESSING` $\rightarrow$ `OCR_COMPLETED` $\rightarrow$ `CLASSIFIED` $\rightarrow$ `EXTRACTED` $\rightarrow$ `VALIDATED` $\rightarrow$ `REVIEW_REQUIRED` / `APPROVED`.
- **0 external analytics database overhead**: Real-time SQL aggregation directly over operational tables (`documents`, `processing_history`, `document_reviews`).
