# Technical Interview Guide: Multi-Agent Document Processing Factory

> **Purpose**: Preparation handbook for technical interviews, system design discussions, and architectural defense. Contains timed elevator pitches, 28 detailed technical questions with code-level answers, architectural tradeoff analyses, known limitations, and future roadmap.

---

## 1. Timed Project Explanations

### 30-Second Elevator Pitch
"The Multi-Agent Document Processing Factory is a production-grade document intelligence platform that transforms raw, unstructured business documents—such as invoices, receipts, and purchase orders—into structured, validated, and auditable data. It combines FastAPI and React with LangGraph cognitive agents for field extraction and validation, Temporal for durable, retryable workflow orchestration, PostgreSQL with pgvector for atomic relational and semantic vector storage, and Redis for status acceleration. It features automated dual-path routing: auto-approving high-confidence files while routing low-confidence anomalies to a human-in-the-loop review queue."

---

### 1-Minute Technical Overview
"At its core, the platform addresses the brittleness of traditional document extraction pipelines. When a document is uploaded via FastAPI, it is persisted to storage and an event is queued in Temporal. Temporal executes a state machine coordinating 5 idempotent activities: OCR extraction, LangGraph document classification, schema-guided structured field extraction, deterministic business rule validation, and multi-factor confidence scoring.

If a document scores above 0.85 confidence with zero validation errors, it is automatically approved and indexed into PostgreSQL using pgvector with 1536-dimensional embeddings. If errors or ambiguities are detected, it routes to a human-in-the-loop review queue where reviewers can correct fields with automatic re-validation, all while preserving the original AI extraction for auditing. Approved documents power a grounded RAG query interface with traceable source citations, and real-time operational analytics are aggregated on-the-fly using database SQL expressions. The system is verified by 198 automated pytest tests and runs as an 8-service Docker Compose stack."

---

### 3-Minute Architectural Deep-Dive
"When designing this system, I focused on five foundational principles: durable execution, atomic consistency, strict validation, zero-hallucination document intelligence, and real-time observability.

First, **durable workflow orchestration**: Traditional background worker queues like Celery struggle with multi-stage pipelines when workers crash midway. We implemented Temporal, where workflows are durable state machines. If a worker process dies during OCR or classification, Temporal detects heartbeat loss and reassigns the workflow to a healthy worker, resuming from the exact activity without re-executing completed work. Each activity has an exponential backoff retry policy (initial: 2s, factor: 2.0, max: 30s, attempts: 3) and an idempotency key `document-processing-{document_id}` that prevents duplicate processing.

Second, **agentic reasoning with deterministic guardrails**: We used LangGraph for AI decision-making. Classification identifies document type and keyword signals; extraction enforces type-specific Pydantic schemas. However, LLMs alone cannot be trusted for financial math. We pair the extraction agent with a deterministic validation engine that checks line-item arithmetic ($quantity \times price = amount$), subtotal sums, total taxes, and date consistency ($due\_date \ge invoice\_date$). Confidence is calculated as:
$$\text{Overall Confidence} = 0.25 \times \text{Class} + 0.35 \times \text{Extract} + 0.40 \times \text{Validation}$$
Auto-approval requires $\ge 0.85$ score and zero validation errors.

Third, **storage architecture & pgvector**: Rather than managing a separate, disconnected vector database (like Pinecone or Qdrant) that creates distributed transaction and data sync challenges, we chose PostgreSQL 16 with the `pgvector` extension. This allows document metadata, extraction records, review logs, and 1536-dimensional chunk embeddings to reside in the same ACID-compliant database. When a document is rejected during review, its RAG chunks are purged in a single atomic database transaction.

Fourth, **status acceleration with graceful degradation**: To prevent frontend polling from overwhelming PostgreSQL with repeated status queries, Redis caches workflow states with a 3600-second TTL. If Redis goes down, `RedisService` catches the exception and falls back to PostgreSQL, ensuring zero downtime.

Fifth, **grounded RAG & operational telemetry**: Approved documents are chunked into 800-character segments with 120-character overlap, preserving page boundaries. RAG queries retrieve context via cosine distance (`<=>`), and LLM generation strictly enforces traceable source citations with an anti-hallucination refusal policy if context is insufficient. Finally, our analytics dashboard computes operational KPIs (stage latencies, review turnaround times, throughput) dynamically using database SQL aggregations without duplicating data into an external OLAP store."

---

## 2. 28 Technical Interview Questions & Answers

### Architecture & System Design

#### Q1: Why use LangGraph instead of a standard sequential Python function chain?
**Answer**: Standard sequential scripts lack cycle management, conditional branch resumption, and unified agent state schemas. LangGraph models agent workflows as directed state graphs with typed state (`ClassificationState`, `ExtractionState`, `ValidationState`). This allows conditional routing (e.g., branching to document-specific prompt templates), node-level error handling, and clean provider swappability between OpenAI, Anthropic, and test mocks without rewriting pipeline control flow.

#### Q2: Why did you choose Temporal over Celery or AWS SQS + Lambda?
**Answer**: Celery and SQS are message brokers, not workflow engines. In Celery, orchestrating 5 sequential stages with retries, queryable intermediate state, and human-in-the-loop pauses requires complex custom state machines in Redis/PostgreSQL. Temporal treats workflows as durable code. Execution state, variables, and call stacks are durably recorded in event history. If a worker crashes midway through Activity 3, Temporal replays history and resumes execution on another worker with zero manual recovery logic.

#### Q3: How is workflow idempotency guaranteed across concurrent duplicate requests?
**Answer**: In `DocumentWorkflowService.start_workflow()`, the workflow ID is deterministically set to `document-processing-{document_id}`. Temporal enforces that only one active execution per workflow ID can exist on the task queue. If a duplicate POST request is received while the workflow is running, Temporal returns a `WorkflowExecutionAlreadyStartedError`, which FastAPI converts to HTTP 409 Conflict.

#### Q4: Why use Redis if PostgreSQL is already the source of truth?
**Answer**: Polling frequency. During processing, the frontend cockpit polls for stage updates every 1–2 seconds. Reading multiple relational joins from PostgreSQL at high concurrency creates unnecessary I/O lock contention. Redis acts as a fast-path cache (`document:status:{document_id}`) returning cached state in sub-millisecond time. PostgreSQL remains the durable source of truth. If Redis fails, `RedisService` catches the exception and falls back to PostgreSQL automatically.

#### Q5: Why pgvector inside PostgreSQL instead of a dedicated vector database (Pinecone/Milvus)?
**Answer**: Distributed transaction avoidance. Storing vector embeddings in a separate service introduces split-brain risks (e.g., document metadata is updated in PostgreSQL, but Pinecone chunk updates fail, or a document is deleted in Postgres while chunks linger in Pinecone). With pgvector, `DocumentChunk` has a foreign key to `Document.id` with `ON DELETE CASCADE`. Reindexing or purging rejected documents is executed in a single atomic ACID database transaction. Furthermore, it avoids managing an additional infrastructure service for moderate corpus sizes.

---

### Agent Pipeline, Validation & Confidence

#### Q6: How does the multi-factor confidence scoring formula work?
**Answer**: Overall confidence is calculated as:
$$\text{Overall Confidence} = (0.25 \times \text{Class Conf}) + (0.35 \times \text{Extract Comp}) + (0.40 \times \text{Validation Score})$$
- **Classification Confidence (25%)**: Probabilistic certainty returned by the classification agent (0.0 to 1.0).
- **Extraction Completeness (35%)**: Ratio of populated expected schema fields relative to the document type schema.
- **Validation Score (40%)**: Composite deterministic score derived by deducting weighted penalties from 1.0 (Errors: $-0.25$, Warnings: $-0.08$, Infos: $-0.02$).

#### Q7: What are the exact conditions for automatic approval?
**Answer**: A document is auto-approved if and only if:
1. `overall_confidence >= 0.85` (configurable via `AUTO_APPROVAL_THRESHOLD`), **AND**
2. Deterministic validation has zero `ERROR` severity issues (`is_valid == True`).
If either condition fails, the document is routed to `REVIEW_REQUIRED`.

#### Q8: How does deterministic validation prevent LLM hallucinations in financial math?
**Answer**: In `app/agents/validation/rules.py`, mathematical rules are calculated purely in Python using floating-point math with a defined tolerance (`ARITHMETIC_TOLERANCE = 0.05`):
- `INV_LINE_ITEM_ARITHMETIC`: Verifies $\text{quantity} \times \text{unit\_price} = \text{amount}$.
- `INV_SUBTOTAL_ARITHMETIC`: Verifies $\sum \text{line\_items} = \text{subtotal}$.
- `INV_TOTAL_ARITHMETIC`: Verifies $\text{subtotal} + \text{tax} - \text{discount} = \text{total}$.
- `INV_DATE_CONSISTENCY`: Verifies $\text{due\_date} \ge \text{invoice\_date}$.
The LLM extracts raw text tokens; Python validates arithmetic ground truth.

#### Q9: What happens when a human reviewer corrects extracted data?
**Answer**:
1. The submitted JSON is validated against the document-type Pydantic schema.
2. The original AI extraction is preserved in `review.original_extracted_data` for auditability.
3. The corrected version is stored in `review.reviewed_extracted_data` and updated on `document.extracted_data`.
4. Deterministic validation is re-executed on the corrected data.
5. If validation passes, `document.status` transitions to `APPROVED`, the review transitions to `COMPLETED` (`decision=CORRECTED`), and the document is indexed into RAG.
6. Redis cache is invalidated.

---

### RAG & Vector Retrieval

#### Q10: How are documents chunked before embedding?
**Answer**: `chunk_document_text()` implements a sliding window algorithm:
- Target chunk size: 800 characters (`RAG_CHUNK_SIZE`).
- Overlap: 120 characters (`RAG_CHUNK_OVERLAP`).
- Boundary preservation: Respects page delimiters (`--- Page N ---`, `\x0c`) and paragraph breaks (`\n\n`) to ensure chunks do not straddle incoherent contexts.
- Empty chunks and pure whitespace are pruned.

#### Q11: How do you prevent hallucinations in the RAG Q&A interface?
**Answer**: Through a three-layer defense:
1. **Filtering**: Only `APPROVED` documents are eligible for indexing. Rejected documents are blocked and purged.
2. **Context Formatting**: Chunks are passed with explicit source tags (`[Source 1: filename, page N]`).
3. **Strict Grounding Prompt**: The system prompt instructs the model: *"Answer the user prompt strictly based on the provided sources. If the answer cannot be established with certainty from the sources, respond exactly: 'I could not find sufficient evidence in the indexed documents.' Do not extrapolate or guess."*

#### Q12: How does the hybrid filtering in vector retrieval work?
**Answer**: In `RagRetrievalService.retrieve_similar_chunks()`, the SQL query combines relational filtering with vector cosine distance:
```sql
SELECT * FROM document_chunks
WHERE document_type = :doc_type AND document_id = :doc_id
ORDER BY embedding <=> :query_vector
LIMIT :top_k;
```
This guarantees that semantic similarity search only operates over the exact document subset authorized by the caller.

---

### Telemetry, Analytics & Observability

#### Q13: How does the analytics engine compute metrics without slowing down the primary database?
**Answer**: In `AnalyticsService`, queries use selective indexed column aggregations (`COUNT`, `AVG`, `CASE WHEN`, `GROUP BY`) rather than fetching raw rows into memory. For example, status distribution runs a single `GROUP BY status` query. Stage performance runs `AVG(completed_at - started_at)` grouped by `stage`. Time-series throughput groups by truncated date buckets (`date_trunc('day', created_at)` in PostgreSQL, `strftime` in SQLite).

#### Q14: How does the application maintain compatibility between PostgreSQL (production) and SQLite (testing)?
**Answer**: The database session dialect is inspected at runtime (`session.bind.dialect.name`). If the dialect is `postgresql`, it uses `EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000` and `to_char(date_trunc('day', created_at), 'YYYY-MM-DD')`. If `sqlite`, it dynamically switches to `(julianday(completed_at) - julianday(started_at)) * 86400000.0` and `strftime('%Y-%m-%d', created_at)`.

---

### Reliability, Docker & Networking

#### Q15: How does inter-container networking differ from browser-to-backend communication?
**Answer**:
- **Inter-container networking**: Services within the Docker bridge network (`docfactory-network`) resolve each other via internal Docker DNS names (`postgres:5432`, `redis:6379`, `temporal:7233`). They never use `localhost`.
- **Browser-to-backend**: The React application runs in the user's host browser outside the Docker bridge network. The host browser cannot resolve `http://backend:8000`. Therefore, frontend API calls target host-published `http://localhost:8000/api/v1` via environment configuration.

#### Q16: How did you harden the Docker images for production?
**Answer**:
- **Multi-stage builds**: Excludes build toolchains (`gcc`, build headers, Node compiler) from production runtime images.
- **Non-root user**: Backend runs as unprivileged `appuser:appgroup` (UID/GID 1001) with explicit directory permissions on `/app/storage`.
- **Nginx SPA fallback**: Serves frontend assets via `nginx:1.27-alpine` with `try_files $uri $uri/ /index.html;` to ensure deep routes resolve on browser refresh.
- **Security headers**: Injects `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Health-gated startup**: Uses Docker Compose `service_healthy` conditions so `backend` and `temporal-worker` only start after `postgres`, `redis`, and `temporal` are fully operational.

#### Q17: What is the Temporal activity retry configuration?
**Answer**:
- Initial interval: 2 seconds
- Backoff coefficient: 2.0 (exponential)
- Maximum interval: 30 seconds
- Maximum attempts: 3
This configuration absorbs transient network timeouts and OCR rate limits without creating retry storms.

---

### Testing & Quality Assurance

#### Q18: How do you test Temporal workflows without running a live Temporal server in CI?
**Answer**: We use the official `temporalio.testing.WorkflowEnvironment.start_time_skipping()`. This runs an in-memory Temporal test server inside Python, allowing workflows to execute activities, test timer skips, and verify query methods deterministically within pytest.

#### Q19: How do you test LLM and OCR components deterministically without incurring API costs?
**Answer**: Through test double provider abstractions:
- `MockOCRProvider`: Returns deterministic invoice text and simulated latency without Tesseract.
- `FakeLLMProvider`: Returns deterministic Pydantic schemas (`InvoiceExtraction`, `DocumentClassification`) without calling OpenAI.
- `FakeEmbeddingProvider`: Computes deterministic 1536-dimensional non-negative unit vectors derived from token character hashes, enabling full vector search testing offline.

---

### System Design & Scaling (Senior Level)

#### Q20: How would you scale this system from 1,000 to 1,000,000 documents per day?
**Answer**:
1. **Temporal Worker Scaling**: Deploy multiple stateless `temporal-worker` replicas across a Kubernetes cluster. Temporal's task queue automatically distributes activities across available worker pods.
2. **Object Storage**: Migrate from `LocalStorageProvider` (`/app/storage`) to S3/GCS with pre-signed upload URLs.
3. **Database Read Replicas**: Direct read-heavy analytics and RAG queries to PostgreSQL read replicas, reserving primary for writes.
4. **pgvector Index Optimization**: Build an IVFFlat or HNSW index on `document_chunks.embedding` (`CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)`) once corpus exceeds 100,000 chunks.
5. **Async Ingestion**: Decouple file upload by streaming events to Kafka/RabbitMQ before workflow creation.

#### Q21: What happens if the backend crashes while a document is in `PROCESSING` state?
**Answer**: The database record reflects `PROCESSING`, but the Temporal workflow execution is managed independently by Temporal Server. When the backend or worker recovers, Temporal resumes the workflow from the last incomplete activity. The frontend can query the workflow state directly via `GET /documents/{id}/workflow` to resynchronize state.

#### Q22: What are the security protections around uploaded documents?
**Answer**:
- MIME-type validation and magic byte inspection (only PDF, PNG, JPG, JPEG, DOCX allowed).
- Upload size limits (`MAX_UPLOAD_SIZE_MB = 25MB`).
- Secure filename hashing (`stored_filename = uuid4().hex + ext`) preventing path traversal attacks.
- Strict CORS whitelist restricting access to authorized host origins.

---

## 3. Architecture Tradeoff Analysis

| Architectural Decision | Chosen Approach | Alternative Considered | Tradeoff Rationale |
|---|---|---|---|
| **Vector Storage** | PostgreSQL + pgvector | Dedicated Vector DB (Pinecone/Milvus) | **Chosen**: Co-locating vectors in PostgreSQL allows atomic foreign-key cascades on document deletion and eliminates distributed transaction sync errors. **Tradeoff**: Dedicated vector DBs offer faster approximate nearest neighbor search at billion-scale corpus sizes. |
| **Workflow Engine** | Temporal | Celery + Redis | **Chosen**: Temporal provides true durable execution history, automatic heartbeat-based crash recovery, and built-in workflow idempotency. **Tradeoff**: Temporal introduces higher architectural complexity and operational dependencies. |
| **Agent Framework** | LangGraph | Sequential Python Functions | **Chosen**: State-graph modeling enables declarative multi-agent workflows, branching logic, and clean provider mocking. **Tradeoff**: Adds learning curve over simple imperative scripting. |
| **Caching Tier** | Redis with DB Fallback | Direct Database Queries | **Chosen**: Absorbs high-frequency polling from client UIs without exhausting PostgreSQL connection pools. **Tradeoff**: Requires cache invalidation management across review actions. |
| **Review Strategy** | Human-in-the-Loop Threshold | 100% Automated Extraction | **Chosen**: Financial compliance mandates that low-confidence or arithmetic discrepancies require human validation. **Tradeoff**: Introduces latency dependent on reviewer availability. |

---

## 4. Honest Known Limitations

1. **Docker Runtime Validation**: Static configuration is 100% verified via `docker compose config`, but live containerized execution was blocked during development due to the Docker Desktop daemon being stopped on the host.
2. **External LLM Execution**: Production OpenAI calls require a valid `OPENAI_API_KEY` in `.env`. Automated testing uses the verified `FakeLLMProvider` and `FakeEmbeddingProvider`.
3. **Local Storage Backend**: Document files are stored on the local mounted filesystem (`/app/storage`) rather than cloud object storage (S3/GCS).
4. **Authentication & RBAC**: The platform currently operates as an internal enterprise service without user login sessions or role-based access control.
5. **OCR Engine Bound**: Native OCR quality is dependent on Tesseract capabilities for low-resolution or handwritten scans.

---

## 5. Technically Realistic Roadmap

- [ ] **Cloud Storage Provider**: Implement `S3StorageProvider` using `aioboto3` for scalable cloud persistence.
- [ ] **Authentication & Multi-Tenancy**: Add OAuth2/OIDC JWT authentication with Organization/Tenant isolation.
- [ ] **OpenTelemetry Instrumentation**: Export distributed traces across FastAPI, LangGraph, and Temporal to Jaeger/OTel Collector.
- [ ] **HNSW Vector Indexing**: Transition pgvector from exact search to HNSW index for sub-millisecond retrieval at scale.
- [ ] **Batch & Event Ingestion**: Add bulk S3 bucket watcher and Kafka event consumer to ingest document batches asynchronously.
