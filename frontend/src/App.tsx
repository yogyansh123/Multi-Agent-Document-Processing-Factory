import React, { useState, useEffect } from 'react'
import Header from './components/Layout/Header'
import Sidebar from './components/Layout/Sidebar'
import Dashboard from './components/Dashboard/Dashboard'
import { DocumentList, DocumentUpload, DocumentDetails } from './components/Documents'
import { ReviewQueue, ReviewDetails } from './components/Review'
import { RagQuery } from './components/RAG'
import SystemHealth from './components/System/SystemHealth'
import { AnalyticsDashboard } from './components/Analytics'
import './components/Review/Review.css'
import './App.css'

export const App: React.FC = () => {
  const [activeNav, setActiveNav] = useState<string>('dashboard')
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null)
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)

  // Sync with browser URL / hash for clean routing
  useEffect(() => {
    const handleLocation = () => {
      const path = window.location.pathname
      const hash = window.location.hash

      // Reviews detail
      if (path.startsWith('/reviews/') || hash.startsWith('#/reviews/')) {
        const id = path.startsWith('/reviews/')
          ? path.replace('/reviews/', '')
          : hash.replace('#/reviews/', '')
        if (id) {
          setActiveNav('review')
          setSelectedReviewId(id)
          setSelectedDocId(null)
          return
        }
      }

      // Documents detail
      if (path.startsWith('/documents/') || hash.startsWith('#/documents/')) {
        const id = path.startsWith('/documents/')
          ? path.replace('/documents/', '')
          : hash.replace('#/documents/', '')
        if (id) {
          setActiveNav('documents')
          setSelectedDocId(id)
          setSelectedReviewId(null)
          return
        }
      }

      if (path === '/documents' || hash === '#/documents') {
        setActiveNav('documents')
        setSelectedDocId(null)
        setSelectedReviewId(null)
        return
      }

      if (path === '/upload' || hash === '#/upload') {
        setActiveNav('upload')
        setSelectedDocId(null)
        setSelectedReviewId(null)
        return
      }

      if (path === '/reviews' || hash === '#/reviews') {
        setActiveNav('review')
        setSelectedReviewId(null)
        setSelectedDocId(null)
        return
      }

      if (path === '/rag' || hash === '#/rag') {
        setActiveNav('rag')
        setSelectedReviewId(null)
        setSelectedDocId(null)
        return
      }

      if (path === '/health' || hash === '#/health') {
        setActiveNav('health')
        setSelectedReviewId(null)
        setSelectedDocId(null)
        return
      }

      if (path === '/analytics' || hash === '#/analytics') {
        setActiveNav('analytics')
        setSelectedReviewId(null)
        setSelectedDocId(null)
        return
      }

      // Default dashboard
      setActiveNav('dashboard')
      setSelectedReviewId(null)
      setSelectedDocId(null)
    }

    handleLocation()
    window.addEventListener('popstate', handleLocation)
    return () => window.removeEventListener('popstate', handleLocation)
  }, [])

  const handleSelectNav = (id: string) => {
    setActiveNav(id)
    setSelectedReviewId(null)
    setSelectedDocId(null)

    if (id === 'dashboard') {
      window.history.pushState({}, '', '/')
    } else if (id === 'documents') {
      window.history.pushState({}, '', '/documents')
    } else if (id === 'upload') {
      window.history.pushState({}, '', '/upload')
    } else if (id === 'review') {
      window.history.pushState({}, '', '/reviews')
    } else if (id === 'rag') {
      window.history.pushState({}, '', '/rag')
    } else if (id === 'health') {
      window.history.pushState({}, '', '/health')
    } else if (id === 'analytics') {
      window.history.pushState({}, '', '/analytics')
    }
  }

  // Document actions
  const handleSelectDocument = (docId: string) => {
    setSelectedDocId(docId)
    setActiveNav('documents')
    window.history.pushState({}, '', `/documents/${docId}`)
  }

  const handleBackToDocuments = () => {
    setSelectedDocId(null)
    window.history.pushState({}, '', '/documents')
  }

  // Review actions
  const handleSelectReview = (reviewId: string) => {
    setSelectedReviewId(reviewId)
    setActiveNav('review')
    window.history.pushState({}, '', `/reviews/${reviewId}`)
  }

  const handleBackToReviewQueue = () => {
    setSelectedReviewId(null)
    window.history.pushState({}, '', '/reviews')
  }

  const getSectionTitle = (): string => {
    switch (activeNav) {
      case 'dashboard':
        return 'Dashboard'
      case 'documents':
        return selectedDocId ? 'Document Cockpit' : 'Documents'
      case 'upload':
        return 'Upload Document'
      case 'review':
        return selectedReviewId ? 'Review & Correction' : 'Review Queue'
      case 'rag':
        return 'Document Intelligence'
      case 'health':
        return 'System Health'
      case 'analytics':
        return 'Analytics & Observability'
      default:
        return 'Overview'
    }
  }

  return (
    <div className="app-shell" id="app-shell">
      <Header
        currentSection={getSectionTitle()}
        onNavigateHome={() => handleSelectNav('dashboard')}
      />
      <div className="app-body">
        <Sidebar activeNav={activeNav} onSelectNav={handleSelectNav} />
        <main className="app-content" role="region" aria-label="Content area">
          {activeNav === 'dashboard' && (
            <Dashboard
              onNavigateToUpload={() => handleSelectNav('upload')}
              onNavigateToDocuments={() => handleSelectNav('documents')}
              onSelectDocument={handleSelectDocument}
              onNavigateToReviewQueue={() => handleSelectNav('review')}
              onSelectReview={handleSelectReview}
              onNavigateToHealth={() => handleSelectNav('health')}
            />
          )}

          {activeNav === 'documents' && (
            selectedDocId ? (
              <DocumentDetails
                documentId={selectedDocId}
                onBack={handleBackToDocuments}
                onNavigateToReview={() => handleSelectNav('review')}
              />
            ) : (
              <DocumentList
                onSelectDocument={handleSelectDocument}
                onNavigateToUpload={() => handleSelectNav('upload')}
              />
            )
          )}

          {activeNav === 'upload' && (
            <DocumentUpload
              onNavigateToDetails={handleSelectDocument}
              onNavigateToList={() => handleSelectNav('documents')}
            />
          )}

          {activeNav === 'review' && (
            selectedReviewId ? (
              <ReviewDetails
                reviewId={selectedReviewId}
                onBack={handleBackToReviewQueue}
              />
            ) : (
              <ReviewQueue onSelectReview={handleSelectReview} />
            )
          )}

          {activeNav === 'rag' && <RagQuery />}

          {activeNav === 'health' && <SystemHealth />}

          {activeNav === 'analytics' && <AnalyticsDashboard />}
        </main>
      </div>
    </div>
  )
}

export default App
