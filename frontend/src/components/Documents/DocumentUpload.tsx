import React, { useState, useRef, type DragEvent } from 'react'
import { documentsApi, formatApiError } from '../../api/client'
import type { DocumentResponse } from '../../types'
import { ErrorBanner, StatusBadge } from '../Common'
import './Documents.css'

interface DocumentUploadProps {
  onUploadSuccess?: (doc: DocumentResponse) => void
  onNavigateToDetails?: (docId: string) => void
  onNavigateToList?: () => void
}

const MAX_FILE_SIZE_MB = 25
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
const ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'docx']

export const DocumentUpload: React.FC<DocumentUploadProps> = ({
  onUploadSuccess,
  onNavigateToDetails,
  onNavigateToList,
}) => {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadedDoc, setUploadedDoc] = useState<DocumentResponse | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [processMessage, setProcessMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): string | null => {
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file format ".${ext}". Supported types: PDF, PNG, JPG, JPEG, DOCX.`
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds the ${MAX_FILE_SIZE_MB} MB limit.`
    }
    return null
  }

  const handleUpload = async (file: File) => {
    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    setError(null)
    setIsUploading(true)
    setUploadProgress(0)
    setUploadedDoc(null)
    setProcessMessage(null)

    try {
      const doc = await documentsApi.upload(file, (percent) => {
        setUploadProgress(percent)
      })
      setUploadedDoc(doc)
      if (onUploadSuccess) onUploadSuccess(doc)
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsUploading(false)
    }
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0]
      handleUpload(file)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0]
      handleUpload(file)
    }
  }

  const handleStartProcessing = async () => {
    if (!uploadedDoc) return
    setIsProcessing(true)
    setError(null)

    try {
      const workflow = await documentsApi.process(uploadedDoc.id)
      setProcessMessage(workflow.message || 'Workflow started successfully!')
      if (onNavigateToDetails) {
        setTimeout(() => {
          onNavigateToDetails(uploadedDoc.id)
        }, 800)
      }
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsProcessing(false)
    }
  }

  const resetUpload = () => {
    setUploadedDoc(null)
    setError(null)
    setUploadProgress(0)
    setProcessMessage(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="doc-page">
      <div className="doc-header">
        <div>
          <h1 className="doc-header__title">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Upload Document
          </h1>
          <p className="doc-header__subtitle">
            Upload business documents (Invoices, Receipts, Purchase Orders, Contracts) to initiate multi-agent extraction.
          </p>
        </div>
        {onNavigateToList && (
          <button type="button" className="btn btn-secondary" onClick={onNavigateToList}>
            Back to Documents
          </button>
        )}
      </div>

      {error && <ErrorBanner message={error} onRetry={() => setError(null)} />}

      <div className="upload-card">
        {!uploadedDoc ? (
          <>
            <div
              className={`dropzone ${isDragging ? 'dropzone--active' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  fileInputRef.current?.click()
                }
              }}
              aria-label="Upload document dropzone"
            >
              <input
                ref={fileInputRef}
                type="file"
                style={{ display: 'none' }}
                accept=".pdf,.png,.jpg,.jpeg,.docx"
                onChange={handleFileSelect}
                disabled={isUploading}
              />

              <div className="dropzone__icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <path d="M12 18v-6" />
                  <path d="m9 15 3-3 3 3" />
                </svg>
              </div>

              <div className="dropzone__text">
                {isUploading ? 'Uploading file to storage...' : 'Drag & drop your document here, or browse files'}
              </div>
              <div className="dropzone__hint">
                Supported formats: PDF, PNG, JPG, JPEG, DOCX (Max {MAX_FILE_SIZE_MB}MB)
              </div>
            </div>

            {isUploading && (
              <div className="upload-progress">
                <div className="progress-bar-track">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${uploadProgress}%` }}
                    role="progressbar"
                    aria-valuenow={uploadProgress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  />
                </div>
                <div className="progress-bar-label">
                  <span>Uploading...</span>
                  <span>{uploadProgress}%</span>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="upload-success-panel">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                <h3 style={{ margin: 0, color: '#e8eaf6', fontSize: '1rem' }}>Upload Successful</h3>
              </div>
              <StatusBadge status={uploadedDoc.status} />
            </div>

            <div className="upload-success-meta">
              <div className="upload-success-meta-item">
                <span>Filename</span>
                <strong>{uploadedDoc.original_filename}</strong>
              </div>
              <div className="upload-success-meta-item">
                <span>Format</span>
                <strong>{uploadedDoc.file_type.toUpperCase()}</strong>
              </div>
              <div className="upload-success-meta-item">
                <span>File Size</span>
                <strong>{(uploadedDoc.file_size / 1024).toFixed(1)} KB</strong>
              </div>
              <div className="upload-success-meta-item">
                <span>Document ID</span>
                <strong style={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                  {uploadedDoc.id.slice(0, 8)}...
                </strong>
              </div>
            </div>

            {processMessage && (
              <div style={{ padding: '8px 12px', background: 'rgba(34, 197, 94, 0.15)', borderRadius: '6px', fontSize: '0.875rem', color: '#4ade80', marginBottom: '16px' }}>
                {processMessage}
              </div>
            )}

            <div style={{ display: 'flex', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleStartProcessing}
                disabled={isProcessing}
              >
                {isProcessing ? 'Starting Pipeline...' : 'Start Multi-Agent Processing'}
              </button>

              {onNavigateToDetails && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => onNavigateToDetails(uploadedDoc.id)}
                >
                  View Details
                </button>
              )}

              <button
                type="button"
                className="btn btn-secondary"
                onClick={resetUpload}
              >
                Upload Another
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DocumentUpload
