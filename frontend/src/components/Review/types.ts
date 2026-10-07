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

export interface ProcessingHistoryItem {
  id: string
  document_id: string
  stage: string
  status: string
  message?: string | null
  error_details?: string | null
  duration_ms?: number | null
  started_at?: string | null
  completed_at?: string | null
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
