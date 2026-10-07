/**
 * Centralized TypeScript definitions for Multi-Agent Document Processing Factory.
 * Corresponds to backend Pydantic models.
 */

// ---------------------------------------------------------------------------
// Document Enums & Types
// ---------------------------------------------------------------------------

export type DocumentStatus =
  | 'UPLOADED'
  | 'OCR_IN_PROGRESS'
  | 'OCR_COMPLETED'
  | 'OCR_FAILED'
  | 'CLASSIFYING'
  | 'CLASSIFIED'
  | 'CLASSIFICATION_FAILED'
  | 'EXTRACTING'
  | 'EXTRACTED'
  | 'EXTRACTION_FAILED'
  | 'VALIDATING'
  | 'VALIDATED'
  | 'VALIDATION_FAILED'
  | 'CONFIDENCE_CALCULATING'
  | 'CONFIDENCE_CALCULATED'
  | 'AUTO_APPROVED'
  | 'REVIEW_REQUIRED'
  | 'IN_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'FAILED'

export type DocumentType =
  | 'INVOICE'
  | 'RECEIPT'
  | 'PURCHASE_ORDER'
  | 'CONTRACT'
  | 'OTHER'

export type StageName =
  | 'UPLOAD'
  | 'OCR'
  | 'CLASSIFICATION'
  | 'EXTRACTION'
  | 'VALIDATION'
  | 'CONFIDENCE'
  | 'HUMAN_REVIEW'
  | 'RAG_INDEXING'

export type StageStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'SKIPPED'

// ---------------------------------------------------------------------------
// Document Models
// ---------------------------------------------------------------------------

export interface DocumentResponse {
  id: string
  original_filename: string
  file_type: string
  mime_type: string
  file_size: number
  document_type: DocumentType | string | null
  status: DocumentStatus | string
  error_message: string | null
  ocr_provider: string | null
  ocr_page_count: number | null
  ocr_processing_time_ms: number | null
  ocr_completed_at: string | null
  ocr_metadata: Record<string, any> | null
  ocr_text: string | null
  classification_confidence: number | null
  classification_reasoning: string | null
  classification_signals: string[] | null
  classified_at: string | null
  extracted_data: Record<string, any> | null
  extraction_version: string | null
  extracted_at: string | null
  validation_result: ValidationResult | null
  validation_score: number | null
  validated_at: string | null
  overall_confidence: number | null
  extraction_confidence: number | null
  validation_confidence: number | null
  confidence_recommendation: 'AUTO_APPROVE' | 'REVIEW_REQUIRED' | string | null
  confidence_factors: Record<string, any> | null
  confidence_calculated_at: string | null
  rag_indexed: boolean
  rag_indexed_at: string | null
  rag_chunk_count: number | null
  rag_embedding_model: string | null
  created_at: string
  updated_at: string
}

export interface ProcessingHistoryItem {
  id: string
  document_id: string
  stage: string
  status: string
  message: string | null
  error_details: string | null
  duration_ms: number | null
  started_at: string | null
  completed_at: string | null
}

export interface DocumentWithHistoryResponse extends DocumentResponse {
  processing_history: ProcessingHistoryItem[]
}

export interface DocumentListResponse {
  items: DocumentResponse[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface DocumentSummaryStats {
  total_documents: number
  processing: number
  approved: number
  review_required: number
  rejected: number
  failed: number
  average_confidence: number | null
  rag_indexed_count: number
}

// ---------------------------------------------------------------------------
// Processing & Workflow
// ---------------------------------------------------------------------------

export interface ProcessingStatusResponse {
  document_id: string
  status: string
  current_stage: string | null
  workflow_id?: string | null
  overall_confidence?: number | null
  confidence_recommendation?: string | null
  started_at?: string | null
  updated_at?: string
  completed_at?: string | null
  failed_stage?: string | null
  error_message: string | null
  review_id?: string | null
  review_status?: string | null
  progress_percent?: number
  stage_statuses?: Record<string, string>
}

export interface WorkflowStartResponse {
  workflow_id: string
  document_id: string
  run_id: string | null
  status: string
  message: string
}

export interface WorkflowStatusResponse {
  workflow_id: string
  document_id: string
  status: string
  current_stage: string | null
  error_message: string | null
  execution_details: Record<string, any> | null
}

// ---------------------------------------------------------------------------
// Validation & Review Models
// ---------------------------------------------------------------------------

export interface ValidationIssue {
  code: string
  field: string
  message: string
  severity: 'ERROR' | 'WARNING' | 'INFO'
  actual_value?: any
  expected_value?: any
}

export interface ValidationResult {
  is_valid: boolean
  issues: ValidationIssue[]
  rules_checked: string[]
  validation_score: number
}

export interface ReviewQueueItem {
  review_id: string
  document_id: string
  original_filename: string
  document_type: string | null
  status: string
  overall_confidence: number | null
  confidence_recommendation: string | null
  validation_score: number | null
  created_at: string
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ReviewDocumentDetails {
  id: string
  original_filename: string
  file_type: string
  mime_type: string
  file_size: number
  document_type: string | null
  status: string
  ocr_text: string | null
  classification_confidence: number | null
  classification_reasoning: string | null
  extracted_data: Record<string, any> | null
  validation_score: number | null
  validation_result: ValidationResult | null
  overall_confidence: number | null
  confidence_recommendation: string | null
  confidence_factors: Record<string, any> | null
  rag_indexed?: boolean | null
  rag_indexed_at?: string | null
  rag_chunk_count?: number | null
  rag_embedding_model?: string | null
}

export interface ReviewDetailsResponse {
  review_id: string
  document_id: string
  status: string
  reviewer_id?: string | null
  reviewer_name?: string | null
  decision?: string | null
  reason?: string | null
  original_extracted_data?: Record<string, any> | null
  reviewed_extracted_data?: Record<string, any> | null
  validation_result_snapshot?: Record<string, any> | null
  confidence_snapshot?: Record<string, any> | null
  created_at: string
  updated_at: string
  reviewed_at?: string | null
  document: ReviewDocumentDetails
  history: ProcessingHistoryItem[]
}

export interface ReviewActionResponse {
  review_id: string
  document_id: string
  status: string
  decision?: string | null
  reason?: string | null
  reviewed_at?: string | null
  document_status: string
  message: string
  validation_score?: number | null
  overall_confidence?: number | null
}

// ---------------------------------------------------------------------------
// RAG Models
// ---------------------------------------------------------------------------

export interface RagSourceCitation {
  source_number: number
  document_id: string
  filename: string
  document_type?: string | null
  page_number?: number | null
  chunk_id: string
  similarity_score: number
  excerpt: string
  is_cited: boolean
}

export interface RagQueryRequest {
  query: string
  top_k?: number
  document_type?: string | null
  document_id?: string | null
}

export interface RagQueryResponse {
  query: string
  answer: string
  sources: RagSourceCitation[]
  retrieved_count: number
  generation_metadata: {
    model?: string
    context_length?: number
    has_sufficient_evidence?: boolean
    sources_cited_count?: number
    [key: string]: any
  }
}

// ---------------------------------------------------------------------------
// Health & System
// ---------------------------------------------------------------------------

export interface SystemHealthResponse {
  status: 'healthy' | 'degraded' | 'unavailable' | string
  dependencies?: {
    postgresql: string
    redis: string
    temporal: string
    [key: string]: string
  }
}

// ---------------------------------------------------------------------------
// Analytics & Observability Models (Step 11)
// ---------------------------------------------------------------------------

export interface AnalyticsSummary {
  total_documents: number
  approved_documents: number
  rejected_documents: number
  processing_documents: number
  review_required_documents: number
  failed_documents: number
  average_confidence: number | null
  average_processing_time_ms: number | null
  rag_indexed_documents: number
  auto_approved_documents: number
  human_reviewed_documents: number
}

export interface StatusDistributionItem {
  status: string
  count: number
  percentage: number
}

export interface StatusDistributionResponse {
  items: StatusDistributionItem[]
  total: number
}

export interface DocumentTypeDistributionItem {
  document_type: string
  count: number
  percentage: number
}

export interface DocumentTypeDistributionResponse {
  items: DocumentTypeDistributionItem[]
  total: number
}

export interface ConfidenceStatistics {
  average_overall: number | null
  average_classification: number | null
  average_extraction: number | null
  average_validation: number | null
  min_confidence: number | null
  max_confidence: number | null
  auto_approve_count: number
  review_required_count: number
}

export interface StagePerformanceItem {
  stage: string
  executions: number
  completed: number
  failed: number
  average_duration_ms: number | null
  success_rate: number
}

export interface StagePerformanceResponse {
  stages: StagePerformanceItem[]
  total_executions: number
}

export interface ReviewStatistics {
  total_reviews: number
  pending_reviews: number
  in_review: number
  completed_reviews: number
  approved_reviews: number
  rejected_reviews: number
  corrected_reviews: number
  average_review_time_seconds: number | null
}

export interface ProcessingVolumePoint {
  period: string
  total: number
  completed: number
  failed: number
}

export interface ProcessingVolumeResponse {
  points: ProcessingVolumePoint[]
  interval: string
}

export interface RecentActivityItem {
  id: string
  document_id: string
  document_filename: string
  stage: string
  status: string
  message: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
}

export interface RecentActivityResponse {
  items: RecentActivityItem[]
  total: number
}
