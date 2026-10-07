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

export interface DocumentIndexStatus {
  document_id: string
  indexed: boolean
  chunk_count: number
  indexed_at: string | null
  embedding_model: string | null
}

export interface ApprovedDocumentOption {
  id: string
  original_filename: string
  document_type: string | null
  status: string
}
