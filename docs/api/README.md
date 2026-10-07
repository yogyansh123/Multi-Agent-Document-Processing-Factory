# API Reference

> **Version**: 0.7.0  
> **Base URL**: `http://localhost:8000`  
> **OpenAPI spec**: `GET /openapi.json`  
> **Interactive docs**: `GET /docs` (Swagger UI), `GET /redoc`

---

## Health & Dependency Readiness

### `GET /health`

System health check. Returns basic liveness by default. Pass `?dependencies=true` to query live status for PostgreSQL, Redis, and Temporal.

**Response (Default Liveness)** `200 OK`
```json
{
  "status": "healthy"
}
```

**Response with Dependency Status (`GET /health?dependencies=true` or `GET /health/ready`)** `200 OK`
```json
{
  "status": "healthy",
  "dependencies": {
    "postgresql": "healthy",
    "redis": "healthy",
    "temporal": "healthy"
  }
}
```

*Status classifications*:
- `healthy`: All external dependencies are connected and operational.
- `degraded`: Core application and database are operational, but an optional dependency (Redis or Temporal) is unavailable.
- `unavailable`: Primary database connection is offline.

### `GET /api/v1/health` & `GET /api/v1/health/dependencies`

Same as above, mounted under the `/api/v1` prefix.

---

## Documents

### `POST /api/v1/documents`

Upload a document for processing.

**Content-Type**: `multipart/form-data`

**Form fields**:

| Field  | Type   | Required | Description                    |
|--------|--------|----------|--------------------------------|
| `file` | binary | ✅        | The document file to upload    |

**Supported file types**: `pdf`, `png`, `jpg`, `jpeg`, `docx`  
**Maximum file size**: configurable via `MAX_UPLOAD_SIZE_MB` (default: **25 MB**)

**Response** `201 Created`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "original_filename": "invoice_001.pdf",
  "file_type": "pdf",
  "mime_type": "application/pdf",
  "file_size": 123456,
  "document_type": null,
  "status": "UPLOADED",
  "error_message": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

> **Note**: `file_path` and `stored_filename` are intentionally omitted from the response for security.

**Error responses**:

| Status | Condition |
|--------|-----------|
| `400 Bad Request` | Unsupported file type |
| `413 Content Too Large` | File exceeds `MAX_UPLOAD_SIZE_MB` |
| `500 Internal Server Error` | Storage backend failure |

---

### `GET /api/v1/documents`

List documents with pagination.

**Query parameters**:

| Parameter   | Type    | Default | Description                        |
|-------------|---------|---------|------------------------------------|
| `page`      | integer | `1`     | Page number (1-indexed)            |
| `page_size` | integer | `20`    | Items per page (max: `100`)        |

**Response** `200 OK`
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "original_filename": "invoice_001.pdf",
      "file_type": "pdf",
      "mime_type": "application/pdf",
      "file_size": 123456,
      "document_type": null,
      "status": "UPLOADED",
      "error_message": null,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 50,
  "total_pages": 3
}
```

---

### `GET /api/v1/documents/{document_id}`

Retrieve a single document including its full processing history.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "original_filename": "invoice_001.pdf",
  "file_type": "pdf",
  "mime_type": "application/pdf",
  "file_size": 123456,
  "document_type": null,
  "status": "UPLOADED",
  "error_message": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "processing_history": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "stage": "UPLOAD",
      "status": "COMPLETED",
      "message": "File 'invoice_001.pdf' uploaded successfully.",
      "started_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:00Z",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document with given ID does not exist |

---

### `DELETE /api/v1/documents/{document_id}`

Permanently delete a document and all associated data.

Deletes:
- The physical stored file from the storage backend
- The document database record
- All associated `ProcessingHistory` records (via cascade)

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `204 No Content` (empty body)

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |
| `500 Internal Server Error` | Storage deletion failed |

---

## OCR Pipeline

### `POST /api/v1/documents/{document_id}/ocr`

Trigger OCR extraction for a document using the configured OCR provider (Tesseract, PyMuPDF, python-docx).

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "OCR_COMPLETED",
  "ocr_provider": "tesseract",
  "page_count": 2,
  "processing_time_ms": 340,
  "text_preview": "INVOICE #INV-2026-001\nVendor: Acme Corp\nTotal: $1,250.00...",
  "ocr_completed_at": "2024-01-15T10:32:00Z",
  "metadata": {
    "format": "pdf",
    "language": "eng",
    "dpi": 300,
    "digital_pages": 2,
    "scanned_pages": 0
  }
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |
| `422 Unprocessable Content` | OCR extraction failed (corrupt file, unreadable image, etc.) |
| `500 Internal Server Error` | Unexpected processing error |

---

### `GET /api/v1/documents/{document_id}/text`

Retrieve the complete extracted text from a document that has completed OCR.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "OCR_COMPLETED",
  "ocr_provider": "tesseract",
  "text": "INVOICE #INV-2026-001\nDate: 2026-01-15\nVendor: Acme Corp\nTotal Amount: $1,250.00\nPayment Terms: Net 30\n..."
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |
| `409 Conflict` | Document has not yet completed OCR (status is not `OCR_COMPLETED`) |

---

## Document Classification Agent

### `POST /api/v1/documents/{document_id}/classify`

Execute the LangGraph Document Classification Agent on a document that has completed OCR.

Classifies the document into one of:
- `INVOICE`
- `RECEIPT`
- `PURCHASE_ORDER`
- `CONTRACT`
- `OTHER`

**Prerequisites**:
- Document must have completed OCR (`status == OCR_COMPLETED`). Attempting classification on un-OCR'd documents returns `409 Conflict`.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_type": "INVOICE",
  "confidence": 0.95,
  "reasoning": "Document contains invoice number INV-2026-001, itemized table of charges, subtotal, and Net 30 payment terms.",
  "signals": [
    "invoice number",
    "line items",
    "total amount",
    "payment terms"
  ],
  "status": "CLASSIFIED",
  "classified_at": "2024-01-15T10:35:00Z"
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |
| `409 Conflict` | Document has not yet completed OCR |
| `422 Unprocessable Content` | Classification failed or model produced invalid structured output |
| `503 Service Unavailable` | LLM provider not configured (e.g. missing API key) |
| `500 Internal Server Error` | Unexpected processing failure |

---

### `GET /api/v1/documents/{document_id}/classification`

Retrieve the latest classification result for a classified document.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_type": "INVOICE",
  "confidence": 0.95,
  "reasoning": "Document contains invoice number INV-2026-001, itemized table of charges, subtotal, and Net 30 payment terms.",
  "signals": [
    "invoice number",
    "line items",
    "total amount",
    "payment terms"
  ],
  "status": "CLASSIFIED",
  "classified_at": "2024-01-15T10:35:00Z"
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |
| `409 Conflict` | Document has not yet been classified |

---

## Information Extraction Agent

### `POST /api/v1/documents/{document_id}/extract`

Trigger structured field extraction on a classified document using the LangGraph Extraction Agent.

The agent selects the appropriate Pydantic schema based on the document's classified `document_type`:
- `INVOICE` → `InvoiceExtraction`
- `RECEIPT` → `ReceiptExtraction`
- `PURCHASE_ORDER` → `PurchaseOrderExtraction`
- `CONTRACT` → `ContractExtraction`
- `OTHER` → `OtherExtraction`

**Prerequisites**:
1. Document must exist (`404 Not Found` if missing)
2. Document must have completed OCR (`409 Conflict` if OCR text missing)
3. Document must have been classified (`409 Conflict` if document_type missing)

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK` (Example for `INVOICE`):
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_type": "INVOICE",
  "extraction_version": "1.0.0",
  "extracted_data": {
    "invoice_number": "INV-2026-001",
    "invoice_date": "2026-01-15",
    "due_date": "2026-02-15",
    "vendor": {
      "name": "Acme Corp",
      "address": "123 Main St, Springfield",
      "phone": "+1-555-0100",
      "email": "billing@acmecorp.com",
      "tax_id": "US12-3456789"
    },
    "customer": {
      "name": "Global Logistics LLC",
      "address": "456 Commerce Blvd",
      "phone": null,
      "email": null,
      "tax_id": null
    },
    "line_items": [
      {
        "description": "Software Consulting",
        "quantity": 40.0,
        "unit_price": 150.0,
        "total_amount": 6000.0
      }
    ],
    "subtotal": 6000.0,
    "tax_amount": 480.0,
    "total_amount": 6480.0,
    "currency": "USD",
    "payment_terms": "Net 30"
  },
  "status": "EXTRACTED",
  "extracted_at": "2026-01-15T10:40:00Z"
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |
| `409 Conflict` | Document missing OCR text or document not yet classified |
| `422 Unprocessable Content` | Agent extraction failure |
| `500 Internal Server Error` | Unexpected processing failure |

---

### `GET /api/v1/documents/{document_id}/extraction`

Retrieve the extracted structured data for an extracted document.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_type": "INVOICE",
  "extraction_version": "1.0.0",
  "extracted_data": {
    "invoice_number": "INV-2026-001",
    "total_amount": 6480.0
  },
  "status": "EXTRACTED",
  "extracted_at": "2026-01-15T10:40:00Z"
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |
| `409 Conflict` | Document has not yet been extracted |

---

## Validation Agent

### `POST /api/v1/documents/{document_id}/validate`

Trigger deterministic rule and LLM-assisted semantic validation on an extracted document.

**Prerequisites**:
1. Document must exist (`404 Not Found` if missing)
2. Document must have completed OCR (`409 Conflict` if OCR text missing)
3. Document must have been classified (`409 Conflict` if document_type missing)
4. Document must have been extracted (`409 Conflict` if extracted_data missing)

**Response** `200 OK`:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_type": "INVOICE",
  "is_valid": true,
  "validation_score": 1.0,
  "issues": [],
  "rules_checked": [
    "INV_REQUIRED_FIELDS",
    "INV_LINE_ITEM_ARITHMETIC",
    "INV_SUBTOTAL_ARITHMETIC",
    "INV_TOTAL_ARITHMETIC",
    "INV_DATE_CONSISTENCY",
    "INV_CURRENCY_CHECK",
    "INV_NON_NEGATIVE_VALUES",
    "SEMANTIC_COHERENCE_CHECK"
  ],
  "status": "VALIDATED",
  "validated_at": "2026-01-15T10:45:00Z"
}
```

---

### `GET /api/v1/documents/{document_id}/validation`

Retrieve validation outcome and issue list for a validated document.

**Response** `200 OK`:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_type": "INVOICE",
  "is_valid": false,
  "validation_score": 0.67,
  "issues": [
    {
      "code": "LINE_ITEM_ARITHMETIC_MISMATCH",
      "field": "line_items[0].total_amount",
      "message": "Line item 1 total (100.0) does not match quantity * unit_price (80.0).",
      "severity": "ERROR",
      "actual_value": 100.0,
      "expected_value": 80.0
    }
  ],
  "rules_checked": ["INV_REQUIRED_FIELDS", "INV_LINE_ITEM_ARITHMETIC"],
  "status": "VALIDATED",
  "validated_at": "2026-01-15T10:45:00Z"
}
```

---

## Confidence Scoring & Decision Routing

### `POST /api/v1/documents/{document_id}/confidence`

Calculates multi-factor confidence across classification, extraction, and validation stages, recommending auto-approval or human review.

**Formula**:
$$\text{Overall Confidence} = 0.25 \times \text{Classification} + 0.35 \times \text{Extraction Completeness} + 0.40 \times \text{Validation Score}$$

**Routing Logic**:
- If `overall_confidence >= 0.85` AND `is_valid == true`: recommendation = `AUTO_APPROVE`, status = `APPROVED`.
- Else: recommendation = `REVIEW_REQUIRED`, status = `REVIEW_REQUIRED`.

**Response** `200 OK`:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "overall_confidence": 0.965,
  "classification_confidence": 0.95,
  "extraction_confidence": 1.0,
  "validation_confidence": 1.0,
  "recommendation": "AUTO_APPROVE",
  "confidence_factors": {
    "weights": {
      "classification": 0.25,
      "extraction": 0.35,
      "validation": 0.40
    },
    "scores": {
      "classification_confidence": 0.95,
      "extraction_completeness": 1.0,
      "validation_score": 1.0
    },
    "thresholds": {
      "auto_approval_threshold": 0.85,
      "review_threshold": 0.60
    }
  },
  "status": "APPROVED",
  "calculated_at": "2026-01-15T10:46:00Z"
}
```

---

### `GET /api/v1/documents/{document_id}/confidence`

Retrieve the latest confidence scoring calculation.

---

## Workflow Orchestration (Temporal & Redis)

### `POST /api/v1/documents/{document_id}/process`

Asynchronously kick off the end-to-end document processing pipeline orchestrated by a Temporal workflow. Executes all 5 activities sequentially (`run_ocr_activity` → `classify_document_activity` → `extract_fields_activity` → `validate_document_activity` → `score_confidence_activity`) with exponential retry policies (`initial_interval=2s`, `backoff_coefficient=2.0`, `maximum_interval=30s`, `maximum_attempts=3`). Transitions document to `PROCESSING` immediately and returns `202 Accepted`.

Idempotent: starting processing for a document whose workflow is already running reuses the existing execution without creating duplicate concurrent processing.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `202 Accepted`
```json
{
  "workflow_id": "document-processing-550e8400-e29b-41d4-a716-446655440000",
  "run_id": "d0f1b2c3-4e5a-6b7c-8d9e-0f1a2b3c4d5e",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PROCESSING",
  "message": "Document processing workflow initiated successfully."
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |

---

### `GET /api/v1/documents/{document_id}/workflow`

Query real-time status and stage of the Temporal workflow for the given document.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "workflow_id": "document-processing-550e8400-e29b-41d4-a716-446655440000",
  "run_id": "d0f1b2c3-4e5a-6b7c-8d9e-0f1a2b3c4d5e",
  "workflow_status": "COMPLETED",
  "current_stage": "CONFIDENCE_SCORING",
  "document_status": "APPROVED"
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |

---

### `GET /api/v1/documents/{document_id}/processing-status`

Retrieve the consolidated processing status of a document using a Redis cache-first strategy.

**Strategy**:
1. Checks Redis cache key `document:status:{document_id}` first.
2. If cache hit, immediately returns cached status.
3. If cache miss, reads from PostgreSQL (durable source of truth).
4. If workflow is actively running, queries Temporal for real-time activity stage.
5. Updates Redis cache with configurable TTL (`REDIS_STATUS_TTL_SECONDS=3600`).
6. Returns consolidated status payload.

**Path parameters**:

| Parameter     | Type | Description        |
|---------------|------|--------------------|
| `document_id` | UUID | Document unique ID |

**Response** `200 OK`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "APPROVED",
  "current_stage": "CONFIDENCE_SCORING",
  "workflow_id": "document-processing-550e8400-e29b-41d4-a716-446655440000",
  "overall_confidence": 0.945,
  "confidence_recommendation": "APPROVED",
  "started_at": "2026-01-15T10:30:00Z",
  "updated_at": "2026-01-15T10:46:00Z",
  "completed_at": "2026-01-15T10:46:00Z",
  "failed_stage": null,
  "error_message": null
}
```

**Error responses**:

| Status | Condition |
|--------|-----------|
| `404 Not Found` | Document does not exist |

---

---

## Human-in-the-Loop Review (Step 8)

### `GET /api/v1/review/queue`

Retrieve paginated review queue items with optional status and document type filters.

**Query parameters**:
- `page`: integer (default `1`)
- `page_size`: integer (default `20`, max `100`)
- `status`: string (e.g. `PENDING`, `IN_REVIEW`, `COMPLETED`, `ALL` — default `PENDING`)
- `document_type`: string (e.g. `INVOICE`, `RECEIPT`, `PURCHASE_ORDER`, `CONTRACT`, `OTHER`)

**Response** `200 OK`
```json
{
  "items": [
    {
      "review_id": "8a32d667-8cfb-4e12-8ee7-bfe8029ff6a8",
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "original_filename": "invoice_001.pdf",
      "document_type": "INVOICE",
      "status": "PENDING",
      "overall_confidence": 0.65,
      "confidence_recommendation": "REVIEW_REQUIRED",
      "validation_score": 0.50,
      "created_at": "2026-03-01T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

### `GET /api/v1/review/{review_id}`

Retrieve full review details including document metadata, OCR text, classification, extracted data, validation results, confidence snapshots, and audit history.

**Response** `200 OK`

---

### `POST /api/v1/review/{review_id}/start`

Claim or begin reviewing a document. Transitions review status from `PENDING` to `IN_REVIEW`.

**Request body** (optional):
```json
{
  "reviewer_name": "Reviewer Alice"
}
```

---

### `POST /api/v1/review/{review_id}/approve`

Approve document extraction as-is without modifications. Sets review status to `COMPLETED` (`APPROVED`) and document status to `APPROVED`.

**Request body** (optional):
```json
{
  "reason": "AI extraction verified and confirmed",
  "reviewer_name": "Reviewer Alice"
}
```

---

### `POST /api/v1/review/{review_id}/reject`

Reject document extraction. Sets review status to `COMPLETED` (`REJECTED`) and document status to `REJECTED`.

**Request body** (optional):
```json
{
  "reason": "Inconsistent supplier details and invalid amounts",
  "reviewer_name": "Reviewer Alice"
}
```

---

### `POST /api/v1/review/{review_id}/correct`

Submit human corrections to structured extraction. Validates against the document type Pydantic schema, re-runs deterministic validation, recalculates confidence score, preserves original extraction in `original_extracted_data`, sets `reviewed_extracted_data`, and updates document status.

**Request body**:
```json
{
  "corrected_data": {
    "invoice_number": "INV-101",
    "total_amount": 100.0,
    "line_items": [
      {
        "description": "Widget",
        "quantity": 2,
        "unit_price": 50.0,
        "amount": 100.0
      }
    ]
  },
  "reason": "Corrected unit price based on original document",
  "reviewer_name": "Reviewer Alice"
}
```

---

## Document Status Values

| Status            | Description |
|-------------------|-------------|
| `UPLOADED`        | File received and stored; processing not started |
| `PROCESSING`      | Processing pipeline or workflow running |
| `OCR_COMPLETED`   | Text extraction finished |
| `CLASSIFIED`      | Document type determined by Classification Agent |
| `EXTRACTED`       | Structured fields extracted by Extraction Agent |
| `VALIDATED`       | Deterministic & semantic validation completed |
| `REVIEW_REQUIRED` | Below confidence threshold or has validation errors; queued for review |
| `APPROVED`        | Approved automatically or by human reviewer |
| `REJECTED`        | Rejected by human reviewer |
| `FAILED`          | Unrecoverable error in any stage |

---

## Review Lifecycle Values

| Status | Decision | Description |
|---|---|---|
| `PENDING` | `null` | Awaiting human reviewer claim |
| `IN_REVIEW` | `null` | Reviewer is actively inspecting/editing |
| `COMPLETED` | `APPROVED` | Approved without extraction changes |
| `COMPLETED` | `REJECTED` | Rejected by reviewer |
| `COMPLETED` | `CORRECTED` | Corrected, revalidated, and approved |

---

## Processing Stage Values

| Stage                | Description |
|----------------------|-------------|
| `UPLOAD`             | Initial file storage (active) |
| `OCR`                | Text extraction (active) |
| `CLASSIFICATION`     | Document type classification (active) |
| `EXTRACTION`         | Field extraction (active) |
| `VALIDATION`         | Business rule validation (active) |
| `CONFIDENCE_SCORING` | Confidence calculation (active) |
| `HUMAN_REVIEW`       | Human-in-the-loop audit log stage (active) |
| `REVIEW_ROUTING`     | Routing decision (active) |
| `APPROVAL`           | Final approval (active) |


---

## Document Intelligence & RAG

### `POST /api/v1/rag/query`

Ask questions across indexed documents using semantic vector similarity retrieval and grounded LLM answer generation.

**Request Body**:
```json
{
  "query": "Which vendor contracts expire in 2027?",
  "top_k": 5,
  "document_type": "CONTRACT",
  "document_id": null
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | string | *required* | Question or semantic query (1 to 2000 chars) |
| `top_k` | integer | `5` | Number of most relevant chunks to retrieve (1 to 20) |
| `document_type` | string | `null` | Optional filter (`INVOICE`, `CONTRACT`, `RECEIPT`, etc.) |
| `document_id` | UUID | `null` | Optional filter restricting search to single document |

**Response** `200 OK`
```json
{
  "query": "Which vendor contracts expire in 2027?",
  "answer": "According to the master agreement with Acme Corp, the expiration date is January 1, 2027 [Source 1].",
  "sources": [
    {
      "source_number": 1,
      "document_id": "424cb8e1-66b7-470b-845b-0b69efdfa83e",
      "filename": "contract_acme.pdf",
      "document_type": "CONTRACT",
      "page_number": 1,
      "chunk_id": "98fcf125-449c-4105-a843-87b2652364ee",
      "similarity_score": 0.885,
      "excerpt": "Term and Termination: This Agreement shall remain in effect until January 1, 2027...",
      "is_cited": true
    }
  ],
  "retrieved_count": 1,
  "generation_metadata": {
    "model": "gpt-4o-mini",
    "context_length": 850,
    "has_sufficient_evidence": true,
    "sources_cited_count": 1
  }
}
```

---

### `POST /api/v1/documents/{document_id}/index`

Manually trigger vector segmentation and embedding generation for a processed and approved document.

**Response** `200 OK`
```json
{
  "document_id": "424cb8e1-66b7-470b-845b-0b69efdfa83e",
  "chunks_created": 4,
  "status": "INDEXED",
  "indexed_at": "2026-09-24T15:30:00Z"
}
```

*Note*: Returns `400 Bad Request` if document is rejected or not yet approved.

---

### `GET /api/v1/documents/{document_id}/index-status`

Fetch vector indexing status and metadata for a document.

**Response** `200 OK`
```json
{
  "document_id": "424cb8e1-66b7-470b-845b-0b69efdfa83e",
  "indexed": true,
  "chunk_count": 4,
  "indexed_at": "2026-09-24T15:30:00Z",
  "embedding_model": "text-embedding-3-small"
}
```

---

## Analytics Endpoints

### `GET /api/v1/analytics/summary`

Retrieve high-level processing KPIs.

**Query parameters**:
- `start_date` (optional, ISO-8601): Filter start timestamp
- `end_date` (optional, ISO-8601): Filter end timestamp

**Response** `200 OK`
```json
{
  "total_documents": 42,
  "approved_documents": 28,
  "rejected_documents": 4,
  "processing_documents": 2,
  "review_required_documents": 6,
  "failed_documents": 2,
  "average_confidence": 0.8845,
  "average_processing_time_ms": 3420.5,
  "rag_indexed_documents": 28,
  "auto_approved_documents": 20,
  "human_reviewed_documents": 8
}
```

---

### `GET /api/v1/analytics/status-distribution`

Retrieve document counts and percentages grouped by lifecycle status.

**Response** `200 OK`
```json
{
  "items": [
    { "status": "APPROVED", "count": 28, "percentage": 66.67 },
    { "status": "REVIEW_REQUIRED", "count": 6, "percentage": 14.29 },
    { "status": "REJECTED", "count": 4, "percentage": 9.52 },
    { "status": "PROCESSING", "count": 2, "percentage": 4.76 },
    { "status": "FAILED", "count": 2, "percentage": 4.76 }
  ],
  "total": 42
}
```

---

### `GET /api/v1/analytics/document-types`

Retrieve counts and percentages by classified document category.

**Response** `200 OK`
```json
{
  "items": [
    { "document_type": "INVOICE", "count": 20, "percentage": 47.62 },
    { "document_type": "RECEIPT", "count": 12, "percentage": 28.57 },
    { "document_type": "PURCHASE_ORDER", "count": 6, "percentage": 14.29 },
    { "document_type": "CONTRACT", "count": 4, "percentage": 9.52 }
  ],
  "total": 42
}
```

---

### `GET /api/v1/analytics/confidence`

Retrieve aggregate confidence statistics.

**Response** `200 OK`
```json
{
  "average_overall": 0.8845,
  "average_classification": 0.942,
  "average_extraction": 0.865,
  "average_validation": 0.910,
  "min_confidence": 0.52,
  "max_confidence": 0.99,
  "auto_approve_count": 20,
  "review_required_count": 6
}
```

---

### `GET /api/v1/analytics/stages`

Retrieve execution counts, success rates, and average duration per pipeline stage.

**Response** `200 OK`
```json
{
  "stages": [
    { "stage": "OCR", "executions": 42, "completed": 41, "failed": 1, "average_duration_ms": 1240.5, "success_rate": 97.62 },
    { "stage": "CLASSIFICATION", "executions": 41, "completed": 41, "failed": 0, "average_duration_ms": 820.2, "success_rate": 100.0 },
    { "stage": "EXTRACTION", "executions": 41, "completed": 40, "failed": 1, "average_duration_ms": 1850.0, "success_rate": 97.56 },
    { "stage": "VALIDATION", "executions": 40, "completed": 40, "failed": 0, "average_duration_ms": 150.3, "success_rate": 100.0 },
    { "stage": "CONFIDENCE_SCORING", "executions": 40, "completed": 40, "failed": 0, "average_duration_ms": 80.1, "success_rate": 100.0 }
  ],
  "total_executions": 204
}
```

---

### `GET /api/v1/analytics/reviews`

Retrieve human review queue workload and turnaround times.

**Response** `200 OK`
```json
{
  "total_reviews": 12,
  "pending_reviews": 4,
  "in_review": 2,
  "completed_reviews": 6,
  "approved_reviews": 4,
  "rejected_reviews": 1,
  "corrected_reviews": 1,
  "average_review_time_seconds": 185.4
}
```

---

### `GET /api/v1/analytics/volume`

Retrieve time-series processing volume.

**Query parameters**:
- `start_date` (optional, ISO-8601)
- `end_date` (optional, ISO-8601)
- `interval` (optional, default: `day`, options: `day`, `week`)

**Response** `200 OK`
```json
{
  "points": [
    { "period": "2026-09-20", "total": 10, "completed": 8, "failed": 1 },
    { "period": "2026-09-21", "total": 15, "completed": 12, "failed": 1 },
    { "period": "2026-09-22", "total": 17, "completed": 14, "failed": 0 }
  ],
  "interval": "day"
}
```

---

### `GET /api/v1/analytics/recent-activity`

Retrieve latest processing history audit events.

**Query parameters**:
- `limit` (optional, integer, default: 20, max: 100)

**Response** `200 OK`
```json
{
  "items": [
    {
      "id": "e5b7b91d-4034-4b5a-939e-d30c5e7bfa51",
      "document_id": "424cb8e1-66b7-470b-845b-0b69efdfa83e",
      "document_filename": "invoice_001.pdf",
      "stage": "EXTRACTION",
      "status": "COMPLETED",
      "message": "Structured fields extracted successfully.",
      "started_at": "2026-09-24T15:29:58Z",
      "completed_at": "2026-09-24T15:30:00Z",
      "duration_ms": 2000.0
    }
  ],
  "total": 1
}
```

---

## Error Response Format

All error responses follow this structure:

```json
{
  "detail": "Human-readable error description"
}
```

Internal stack traces and sensitive information are never exposed in error responses.
