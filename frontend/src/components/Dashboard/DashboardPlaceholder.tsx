import React from 'react'
import './DashboardPlaceholder.css'

interface StatCard {
  id: string
  label: string
  value: string
  change: string
  positive: boolean
  icon: React.ReactNode
  color: string
}

const stats: StatCard[] = [
  {
    id: 'total-documents',
    label: 'Total Documents',
    value: '—',
    change: 'Awaiting data',
    positive: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
    ),
    color: '#4f8ef7',
  },
  {
    id: 'processing-queue',
    label: 'Processing Queue',
    value: '—',
    change: 'Pipeline idle',
    positive: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    color: '#7c5cfc',
  },
  {
    id: 'review-queue',
    label: 'Review Queue',
    value: '—',
    change: 'No pending reviews',
    positive: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
    color: '#f5a623',
  },
  {
    id: 'accuracy-rate',
    label: 'Avg. Confidence',
    value: '—',
    change: 'No processed docs yet',
    positive: true,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
        <polyline points="17 6 23 6 23 12" />
      </svg>
    ),
    color: '#00d4aa',
  },
]

interface PipelineStage {
  id: string
  name: string
  status: 'active' | 'planned'
  description: string
}

const pipeline: PipelineStage[] = [
  { id: 'upload', name: 'Document Upload', status: 'active', description: 'PDF, PNG, JPG, TIFF, DOCX support' },
  { id: 'ocr', name: 'OCR Pipeline', status: 'active', description: 'Tesseract · PyMuPDF · python-docx extraction' },
  { id: 'classify', name: 'Classification Agent', status: 'active', description: 'LangGraph Agent · Structured Document Classification' },
  { id: 'extract', name: 'Extraction Agent', status: 'active', description: 'LangGraph Agent · Document-Type Structured Extraction' },
  { id: 'validate', name: 'Validation Agent', status: 'active', description: 'Deterministic Rules & LLM Semantic Validation' },
  { id: 'score', name: 'Confidence Scoring', status: 'active', description: 'Multi-Factor Confidence Scoring & Routing' },
  { id: 'workflow', name: 'Temporal Workflow Orchestration', status: 'active', description: 'Resilient end-to-end activity execution & retry policies' },
  { id: 'output', name: 'Structured JSON Output', status: 'planned', description: 'Webhook · API · Export' },
]

const DashboardPlaceholder: React.FC = () => {
  return (
    <main className="dashboard" id="main-content" role="main">
      {/* Hero */}
      <section className="dashboard__hero" aria-labelledby="dashboard-title">
        <div className="dashboard__hero-content">
          <div className="dashboard__hero-badge">
            <span className="dashboard__hero-badge-dot"></span>
            Step 7 — Temporal Workflow Orchestration Active (v0.7.0)
          </div>
          <h1 id="dashboard-title" className="dashboard__title">
            Multi-Agent Document
            <br />
            <span className="gradient-text">Processing Factory</span>
          </h1>
          <p className="dashboard__subtitle">
            AI-powered document intelligence platform. Processes invoices, receipts,
            purchase orders, contracts, and business documents through a resilient Temporal
            workflow with multi-agent intelligence and confidence scoring.
          </p>
          <div className="dashboard__hero-actions">
            <button id="dashboard-upload-btn" className="btn btn--primary" disabled title="Coming in Phase 2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              Upload Document
            </button>
            <button id="dashboard-docs-btn" className="btn btn--secondary">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
              </svg>
              View Architecture
            </button>
          </div>
        </div>
        <div className="dashboard__hero-visual" aria-hidden="true">
          <div className="dashboard__flow">
            {['📄', '🔍', '🤖', '⚡', '✅', '📊'].map((emoji, i) => (
              <React.Fragment key={i}>
                <div className="dashboard__flow-node">
                  <span>{emoji}</span>
                </div>
                {i < 5 && <div className="dashboard__flow-arrow">→</div>}
              </React.Fragment>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="dashboard__stats" aria-label="Processing statistics">
        {stats.map((stat) => (
          <article key={stat.id} id={`stat-card-${stat.id}`} className="stat-card glass">
            <div className="stat-card__header">
              <div
                className="stat-card__icon"
                style={{ background: `${stat.color}14`, color: stat.color, border: `1px solid ${stat.color}22` }}
              >
                {stat.icon}
              </div>
              <span className="stat-card__label">{stat.label}</span>
            </div>
            <div className="stat-card__value">{stat.value}</div>
            <div className={`stat-card__change ${stat.positive ? 'stat-card__change--positive' : 'stat-card__change--negative'}`}>
              {stat.change}
            </div>
          </article>
        ))}
      </section>

      {/* API Status Banner */}
      <section
        id="api-status-banner"
        className="dashboard__api-banner glass"
        aria-label="API availability notice"
      >
        <div className="dashboard__api-banner-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
        </div>
        <div className="dashboard__api-banner-content">
          <span className="dashboard__api-banner-title">Ingestion, OCR, Agents, Validation & Temporal Workflows — Available</span>
          <span className="dashboard__api-banner-desc">
            POST /api/v1/documents · /{'{'}id{'}'}/process · /{'{'}id{'}'}/workflow · /{'{'}id{'}'}/processing-status · /{'{'}id{'}'}/ocr · /{'{'}id{'}'}/classify · /{'{'}id{'}'}/extract · /{'{'}id{'}'}/validate · /{'{'}id{'}'}/confidence
          </span>
        </div>
        <div className="dashboard__api-banner-badge">
          <span className="pipeline__badge pipeline__badge--active">Step 7 Live</span>
        </div>
      </section>

      {/* Processing Pipeline */}
      <section className="dashboard__pipeline" aria-labelledby="pipeline-title">
        <div className="dashboard__section-header">
          <h2 id="pipeline-title" className="dashboard__section-title">Processing Pipeline</h2>
          <span className="dashboard__section-badge">8 stages</span>
        </div>
        <div className="pipeline">
          {pipeline.map((stage, index) => (
            <div key={stage.id} id={`pipeline-stage-${stage.id}`} className="pipeline__stage">
              <div className="pipeline__stage-number">{index + 1}</div>
              <div className="pipeline__stage-connector" aria-hidden="true"></div>
              <div className={`pipeline__stage-card glass pipeline__stage-card--${stage.status}`}>
                <div className="pipeline__stage-name">{stage.name}</div>
                <div className="pipeline__stage-desc">{stage.description}</div>
                <div className="pipeline__stage-status">
                  {stage.status === 'active' ? (
                    <span className="pipeline__badge pipeline__badge--active">Active</span>
                  ) : (
                    <span className="pipeline__badge pipeline__badge--planned">Planned</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Tech Stack */}
      <section className="dashboard__tech" aria-labelledby="tech-title">
        <div className="dashboard__section-header">
          <h2 id="tech-title" className="dashboard__section-title">Technology Stack</h2>
        </div>
        <div className="tech-grid">
          {[
            { category: 'Backend', items: ['FastAPI', 'Python 3.12', 'SQLAlchemy', 'PostgreSQL', 'Redis'], color: '#4f8ef7' },
            { category: 'AI / Agents', items: ['LangGraph', 'OpenAI', 'Anthropic', 'Google Gemini', 'Ollama'], color: '#7c5cfc' },
            { category: 'Workflow', items: ['Temporal', 'Async Activities', 'Retry Policies', 'Dead Letter', ''], color: '#00d4aa' },
            { category: 'Frontend', items: ['React 18', 'TypeScript', 'Vite', 'CSS Modules', ''], color: '#f5a623' },
          ].map((stack) => (
            <div
              key={stack.category}
              id={`tech-card-${stack.category.toLowerCase().replace(/\s+/g, '-')}`}
              className="tech-card glass"
            >
              <div
                className="tech-card__header"
                style={{ borderBottom: `1px solid ${stack.color}22`, paddingBottom: 'var(--space-3)', marginBottom: 'var(--space-3)' }}
              >
                <span style={{ color: stack.color, fontWeight: 600, fontSize: 'var(--text-sm)' }}>
                  {stack.category}
                </span>
              </div>
              <ul className="tech-card__list">
                {stack.items.filter(Boolean).map((item) => (
                  <li key={item} className="tech-card__item">
                    <span className="tech-card__dot" style={{ background: stack.color }}></span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}

export default DashboardPlaceholder
