import axios, { AxiosError, type AxiosProgressEvent } from 'axios'
import type {
  DocumentListResponse,
  DocumentResponse,
  DocumentSummaryStats,
  DocumentWithHistoryResponse,
  ProcessingStatusResponse,
  RagQueryRequest,
  RagQueryResponse,
  ReviewActionResponse,
  ReviewDetailsResponse,
  ReviewQueueResponse,
  SystemHealthResponse,
  WorkflowStartResponse,
  WorkflowStatusResponse,
  AnalyticsSummary,
  StatusDistributionResponse,
  DocumentTypeDistributionResponse,
  ConfidenceStatistics,
  StagePerformanceResponse,
  ReviewStatistics,
  ProcessingVolumeResponse,
  RecentActivityResponse,
} from '../types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

export const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

/**
 * Extract human-readable error message from Axios errors.
 */
export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const err = error as AxiosError<{ detail?: string | Array<{ msg?: string; loc?: string[] }> }>
    if (err.response?.data?.detail) {
      const detail = err.response.data.detail
      if (typeof detail === 'string') {
        return detail
      }
      if (Array.isArray(detail)) {
        return detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      }
    }
    if (err.response?.status === 404) return 'The requested resource was not found (404).'
    if (err.response?.status === 409) return err.response.data?.detail ? String(err.response.data.detail) : 'Operation conflict with current resource state (409).'
    if (err.response?.status === 413) return 'File size exceeds maximum upload limit (25MB).'
    if (err.response?.status === 500) return 'Internal server error occurred in backend service.'
    if (err.response?.status === 502) return 'Backend service is currently unreachable (502 Bad Gateway). Please verify that the FastAPI backend server is running.'
    if (err.response?.status === 503) return 'Backend service temporarily unavailable (503). Service is starting up or overloaded.'
    if (err.code === 'ERR_NETWORK') return 'Unable to connect to the backend service. Please check if the server is running.'
    return err.message || 'An error occurred during network request.'
  }
  if (error instanceof Error) return error.message
  return String(error)
}

// ---------------------------------------------------------------------------
// Document API
// ---------------------------------------------------------------------------

export const documentsApi = {
  async list(params?: {
    page?: number
    page_size?: number
    status?: string
    document_type?: string
    search?: string
  }): Promise<DocumentListResponse> {
    const res = await apiClient.get<DocumentListResponse>('/api/v1/documents', { params })
    return res.data
  },

  async get(id: string): Promise<DocumentWithHistoryResponse> {
    const res = await apiClient.get<DocumentWithHistoryResponse>(`/api/v1/documents/${id}`)
    return res.data
  },

  async getStats(): Promise<DocumentSummaryStats> {
    const res = await apiClient.get<DocumentSummaryStats>('/api/v1/documents/stats/summary')
    return res.data
  },

  async upload(
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<DocumentResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const res = await apiClient.post<DocumentResponse>('/api/v1/documents', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent)
        }
      },
    })
    return res.data
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/documents/${id}`)
  },

  async process(id: string): Promise<WorkflowStartResponse> {
    const res = await apiClient.post<WorkflowStartResponse>(`/api/v1/documents/${id}/process`)
    return res.data
  },

  async getProcessingStatus(id: string): Promise<ProcessingStatusResponse> {
    const res = await apiClient.get<ProcessingStatusResponse>(`/api/v1/documents/${id}/processing-status`)
    return res.data
  },

  async getWorkflowStatus(id: string): Promise<WorkflowStatusResponse> {
    const res = await apiClient.get<WorkflowStatusResponse>(`/api/v1/documents/${id}/workflow`)
    return res.data
  },
}

// ---------------------------------------------------------------------------
// Review API
// ---------------------------------------------------------------------------

export const reviewApi = {
  async listQueue(params?: {
    status?: string
    document_type?: string
    page?: number
    page_size?: number
  }): Promise<ReviewQueueResponse> {
    const res = await apiClient.get<ReviewQueueResponse>('/api/v1/review/queue', { params })
    return res.data
  },

  async getDetails(reviewId: string): Promise<ReviewDetailsResponse> {
    const res = await apiClient.get<ReviewDetailsResponse>(`/api/v1/review/${reviewId}`)
    return res.data
  },

  async start(
    reviewId: string,
    reviewerId: string = 'rev_default_human',
    reviewerName: string = 'Human Reviewer'
  ): Promise<ReviewDetailsResponse> {
    const res = await apiClient.post<ReviewDetailsResponse>(`/api/v1/review/${reviewId}/start`, {
      reviewer_id: reviewerId,
      reviewer_name: reviewerName,
    })
    return res.data
  },

  async approve(
    reviewId: string,
    reviewerId: string = 'rev_default_human',
    reviewerName: string = 'Human Reviewer',
    reason?: string
  ): Promise<ReviewActionResponse> {
    const res = await apiClient.post<ReviewActionResponse>(`/api/v1/review/${reviewId}/approve`, {
      reviewer_id: reviewerId,
      reviewer_name: reviewerName,
      reason: reason || 'Approved by human reviewer',
    })
    return res.data
  },

  async reject(
    reviewId: string,
    reviewerId: string = 'rev_default_human',
    reviewerName: string = 'Human Reviewer',
    reason: string = 'Rejected by human reviewer'
  ): Promise<ReviewActionResponse> {
    const res = await apiClient.post<ReviewActionResponse>(`/api/v1/review/${reviewId}/reject`, {
      reviewer_id: reviewerId,
      reviewer_name: reviewerName,
      reason,
    })
    return res.data
  },

  async correct(
    reviewId: string,
    correctedData: Record<string, any>,
    reviewerId: string = 'rev_default_human',
    reviewerName: string = 'Human Reviewer',
    reason?: string
  ): Promise<ReviewActionResponse> {
    const res = await apiClient.post<ReviewActionResponse>(`/api/v1/review/${reviewId}/correct`, {
      corrected_data: correctedData,
      reviewer_id: reviewerId,
      reviewer_name: reviewerName,
      reason: reason || 'Corrected extracted fields by human reviewer',
    })
    return res.data
  },
}

// ---------------------------------------------------------------------------
// RAG API
// ---------------------------------------------------------------------------

export const ragApi = {
  async query(payload: RagQueryRequest): Promise<RagQueryResponse> {
    const res = await apiClient.post<RagQueryResponse>('/api/v1/rag/query', payload)
    return res.data
  },

  async indexDocument(documentId: string): Promise<{ document_id: string; indexed: boolean; chunk_count: number; message: string }> {
    const res = await apiClient.post(`/api/v1/documents/${documentId}/index`)
    return res.data
  },

  async getIndexStatus(documentId: string): Promise<{ document_id: string; indexed: boolean; chunk_count: number; indexed_at: string | null; embedding_model: string | null }> {
    const res = await apiClient.get(`/api/v1/documents/${documentId}/rag-status`)
    return res.data
  },
}

// ---------------------------------------------------------------------------
// System & Health API
// ---------------------------------------------------------------------------

export const systemApi = {
  async getHealth(): Promise<SystemHealthResponse> {
    const res = await apiClient.get<SystemHealthResponse>('/health')
    return res.data
  },

  async getDependencyHealth(): Promise<SystemHealthResponse> {
    const res = await apiClient.get<SystemHealthResponse>('/health/dependencies')
    return res.data
  },
}

// ---------------------------------------------------------------------------
// Analytics API (Step 11)
// ---------------------------------------------------------------------------

export const analyticsApi = {
  async getAnalyticsSummary(startDate?: string, endDate?: string): Promise<AnalyticsSummary> {
    const res = await apiClient.get<AnalyticsSummary>('/api/v1/analytics/summary', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined },
    })
    return res.data
  },

  async getStatusDistribution(startDate?: string, endDate?: string): Promise<StatusDistributionResponse> {
    const res = await apiClient.get<StatusDistributionResponse>('/api/v1/analytics/status-distribution', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined },
    })
    return res.data
  },

  async getDocumentTypes(startDate?: string, endDate?: string): Promise<DocumentTypeDistributionResponse> {
    const res = await apiClient.get<DocumentTypeDistributionResponse>('/api/v1/analytics/document-types', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined },
    })
    return res.data
  },

  async getConfidenceStatistics(startDate?: string, endDate?: string): Promise<ConfidenceStatistics> {
    const res = await apiClient.get<ConfidenceStatistics>('/api/v1/analytics/confidence', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined },
    })
    return res.data
  },

  async getStagePerformance(startDate?: string, endDate?: string): Promise<StagePerformanceResponse> {
    const res = await apiClient.get<StagePerformanceResponse>('/api/v1/analytics/stages', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined },
    })
    return res.data
  },

  async getReviewStatistics(startDate?: string, endDate?: string): Promise<ReviewStatistics> {
    const res = await apiClient.get<ReviewStatistics>('/api/v1/analytics/reviews', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined },
    })
    return res.data
  },

  async getProcessingVolume(startDate?: string, endDate?: string, interval: string = 'day'): Promise<ProcessingVolumeResponse> {
    const res = await apiClient.get<ProcessingVolumeResponse>('/api/v1/analytics/volume', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined, interval },
    })
    return res.data
  },

  async getRecentActivity(limit: number = 20): Promise<RecentActivityResponse> {
    const res = await apiClient.get<RecentActivityResponse>('/api/v1/analytics/recent-activity', {
      params: { limit },
    })
    return res.data
  },
}
