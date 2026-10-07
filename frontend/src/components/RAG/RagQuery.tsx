import React, { useState, useEffect } from 'react'
import type { RagQueryResponse, RagSourceCitation, ApprovedDocumentOption } from './types'
import SourceCard from './SourceCard'
import './Rag.css'

export const RagQuery: React.FC = () => {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [docTypeFilter, setDocTypeFilter] = useState<string>('')
  const [selectedDocId, setSelectedDocId] = useState<string>('')
  const [documents, setDocuments] = useState<ApprovedDocumentOption[]>([])

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<RagQueryResponse | null>(null)
  const [highlightedSource, setHighlightedSource] = useState<number | null>(null)
  const [focusedDocModal, setFocusedDocModal] = useState<RagSourceCitation | null>(null)

  // Fetch document options for dropdown filter
  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const res = await fetch('/api/v1/documents?page_size=50')
        if (res.ok) {
          const data = await res.json()
          const items = data.items || data || []
          setDocuments(
            items.map((d: any) => ({
              id: d.id,
              original_filename: d.original_filename,
              document_type: d.document_type,
              status: d.status,
            }))
          )
        }
      } catch {
        // Fallback silently if documents endpoint not available
      }
    }
    fetchDocs()
  }, [])

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const cleanQuery = query.trim()
    if (!cleanQuery) return

    setLoading(true)
    setError(null)
    setHighlightedSource(null)

    try {
      const payload: Record<string, any> = {
        query: cleanQuery,
        top_k: topK,
      }
      if (docTypeFilter && docTypeFilter !== 'ALL') {
        payload.document_type = docTypeFilter
      }
      if (selectedDocId && selectedDocId !== 'ALL') {
        payload.document_id = selectedDocId
      }

      const res = await fetch('/api/v1/rag/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Query failed: ${res.statusText}`)
      }

      const data: RagQueryResponse = await res.json()
      setResult(data)
    } catch (err: any) {
      setError(err.message || 'An error occurred while running semantic search.')
    } finally {
      setLoading(false)
    }
  }

  // Helper to render answer text with interactive [Source N] clickable chips
  const renderFormattedAnswer = (answerText: string) => {
    const parts = answerText.split(/(\[Source\s*\d+\])/gi)
    return parts.map((part, index) => {
      const match = part.match(/\[Source\s*(\d+)\]/i)
      if (match) {
        const srcNum = parseInt(match[1], 10)
        return (
          <button
            key={index}
            type="button"
            className="rag-citation-marker"
            onClick={() => {
              setHighlightedSource(srcNum)
              const cardEl = document.getElementById(`source-card-${srcNum}`)
              if (cardEl) {
                cardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
              }
            }}
            title={`View Source ${srcNum}`}
          >
            {part}
          </button>
        )
      }
      return <span key={index}>{part}</span>
    })
  }

  return (
    <div className="rag-container" id="rag-intelligence-view">
      {/* Header */}
      <div className="rag-header">
        <div>
          <h1 className="rag-header__title">
            Document Intelligence & RAG
            <span className="rag-badge-pgvector">pgvector</span>
          </h1>
          <p className="rag-header__subtitle">
            Semantic retrieval and grounded LLM answers across verified repository documents.
          </p>
        </div>
      </div>

      {/* Query Search Bar & Controls */}
      <div className="rag-search-card">
        <form onSubmit={handleSearch} className="rag-search-form">
          <div className="rag-input-wrapper">
            <svg
              className="rag-input-icon"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              id="rag-query-input"
              type="text"
              className="rag-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a natural-language question about any processed documents (e.g. 'What is the payment term for Acme Corp?')"
              disabled={loading}
            />
            <button
              id="rag-ask-button"
              type="submit"
              className="rag-ask-btn"
              disabled={loading || !query.trim()}
            >
              {loading ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
                    <circle cx="12" cy="12" r="10" strokeDasharray="32" strokeDashoffset="10" />
                  </svg>
                  Searching...
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                  Ask
                </>
              )}
            </button>
          </div>

          {/* Filters Row */}
          <div className="rag-filters-row">
            <div className="rag-filter-group">
              <label htmlFor="rag-top-k-select">Top Chunks (k):</label>
              <select
                id="rag-top-k-select"
                className="rag-filter-select"
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
              >
                <option value={3}>3 chunks</option>
                <option value={5}>5 chunks (default)</option>
                <option value={8}>8 chunks</option>
                <option value={10}>10 chunks</option>
                <option value={15}>15 chunks</option>
              </select>
            </div>

            <div className="rag-filter-group">
              <label htmlFor="rag-doc-type-filter">Document Type:</label>
              <select
                id="rag-doc-type-filter"
                className="rag-filter-select"
                value={docTypeFilter}
                onChange={(e) => setDocTypeFilter(e.target.value)}
              >
                <option value="">All Document Types</option>
                <option value="INVOICE">Invoices</option>
                <option value="RECEIPT">Receipts</option>
                <option value="PURCHASE_ORDER">Purchase Orders</option>
                <option value="CONTRACT">Contracts</option>
                <option value="OTHER">Other</option>
              </select>
            </div>

            {documents.length > 0 && (
              <div className="rag-filter-group">
                <label htmlFor="rag-doc-id-filter">Document:</label>
                <select
                  id="rag-doc-id-filter"
                  className="rag-filter-select"
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                  style={{ maxWidth: '240px' }}
                >
                  <option value="">All Indexed Documents</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.original_filename} ({d.document_type || 'DOC'})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </form>
      </div>

      {/* Error Banner */}
      {error && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#f87171',
          padding: '14px 18px',
          borderRadius: '10px',
          fontSize: '14px',
        }}>
          {error}
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="rag-search-card rag-skeleton-loader">
          <div className="rag-skeleton-line" style={{ width: '40%' }} />
          <div className="rag-skeleton-line" style={{ width: '90%' }} />
          <div className="rag-skeleton-line" style={{ width: '85%' }} />
          <div className="rag-skeleton-line" style={{ width: '70%' }} />
        </div>
      )}

      {/* Main Results: Answer and Sources */}
      {result && !loading && (
        <div className="rag-layout-grid">
          {/* Answer Card */}
          <div className="rag-answer-card" id="rag-answer-panel">
            <div className="rag-answer-header">
              <h2 className="rag-answer-heading">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                Grounded Answer
              </h2>
              {result.generation_metadata?.has_sufficient_evidence !== false ? (
                <span className="rag-evidence-badge rag-evidence-badge--grounded">
                  ✓ Grounded in Evidence
                </span>
              ) : (
                <span className="rag-evidence-badge rag-evidence-badge--insufficient">
                  ⚠ Insufficient Evidence
                </span>
              )}
            </div>

            <div className="rag-answer-text">
              {renderFormattedAnswer(result.answer)}
            </div>

            <div className="rag-meta-footer">
              <span>
                Retrieved <strong>{result.retrieved_count}</strong> chunk(s) via pgvector
              </span>
              {result.generation_metadata?.model && (
                <span>LLM: {result.generation_metadata.model}</span>
              )}
            </div>
          </div>

          {/* Sources List */}
          <div className="rag-sources-column">
            <div className="rag-sources-heading">
              <span>Source Citations ({result.sources.length})</span>
              <span style={{ fontSize: '11px', color: '#6366f1' }}>Click to inspect</span>
            </div>

            {result.sources.length === 0 ? (
              <div style={{ color: 'var(--color-text-secondary)', fontSize: '13px', padding: '16px' }}>
                No document chunks met the similarity threshold.
              </div>
            ) : (
              result.sources.map((src) => (
                <SourceCard
                  key={src.source_number}
                  source={src}
                  isHighlighted={highlightedSource === src.source_number}
                  onClick={() => {
                    setHighlightedSource(src.source_number)
                    setFocusedDocModal(src)
                  }}
                />
              ))
            )}
          </div>
        </div>
      )}

      {/* Initial Empty State */}
      {!result && !loading && (
        <div className="rag-search-card rag-empty-state">
          <svg
            className="rag-empty-icon"
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          <h3 className="rag-empty-title">Ask Your Document Repository</h3>
          <p className="rag-empty-desc">
            Search across contracts, invoices, receipts, and purchase orders. Every answer provides traceable citations back to specific document pages and chunks.
          </p>
        </div>
      )}

      {/* Source Provenance Modal */}
      {focusedDocModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
          onClick={() => setFocusedDocModal(null)}
        >
          <div
            className="rag-search-card"
            style={{ maxWidth: '600px', width: '100%', position: 'relative' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="rag-source-tag">Source {focusedDocModal.source_number}</span>
                <h3 style={{ fontSize: '16px', fontWeight: 600 }}>{focusedDocModal.filename}</h3>
              </div>
              <button
                type="button"
                onClick={() => setFocusedDocModal(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--color-text-secondary)',
                  cursor: 'pointer',
                  fontSize: '18px',
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <div>
                <strong>Document ID:</strong> <span style={{ fontFamily: 'monospace' }}>{focusedDocModal.document_id}</span>
              </div>
              <div>
                <strong>Chunk ID:</strong> <span style={{ fontFamily: 'monospace' }}>{focusedDocModal.chunk_id}</span>
              </div>
              <div>
                <strong>Page:</strong> {focusedDocModal.page_number ?? '1'}
              </div>
              <div>
                <strong>Similarity Score:</strong> {(focusedDocModal.similarity_score * 100).toFixed(1)}%
              </div>
              <div>
                <strong>Full Chunk Excerpt:</strong>
                <div className="rag-source-excerpt" style={{ marginTop: '6px', maxHeight: '200px', overflowY: 'auto' }}>
                  {focusedDocModal.excerpt}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default RagQuery
