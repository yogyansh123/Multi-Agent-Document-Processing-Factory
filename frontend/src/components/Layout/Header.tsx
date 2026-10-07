import React, { useEffect, useState } from 'react'
import { systemApi } from '../../api/client'
import './Header.css'

interface HeaderProps {
  currentSection?: string
  onSearch?: (query: string) => void
  onNavigateHome?: () => void
}

export const Header: React.FC<HeaderProps> = ({
  currentSection = 'Dashboard',
  onSearch,
  onNavigateHome,
}) => {
  const [searchValue, setSearchValue] = useState('')
  const [apiStatus, setApiStatus] = useState<'healthy' | 'degraded' | 'unavailable'>('healthy')

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await systemApi.getHealth()
        if (res.status === 'healthy') setApiStatus('healthy')
        else if (res.status === 'degraded') setApiStatus('degraded')
        else setApiStatus('unavailable')
      } catch {
        setApiStatus('unavailable')
      }
    }

    checkHealth()
    const timer = setInterval(checkHealth, 30000)
    return () => clearInterval(timer)
  }, [])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (onSearch) onSearch(searchValue)
  }

  return (
    <header className="header glass" id="app-header" role="banner">
      <div className="header__left">
        <div
          className="header__logo"
          aria-label="Document Processing Factory logo"
          onClick={onNavigateHome}
          style={{ cursor: onNavigateHome ? 'pointer' : 'default' }}
        >
          <div className="header__logo-icon">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
              <rect x="3" y="3" width="9" height="11" rx="2" fill="url(#grad1)" opacity="0.9" />
              <rect x="14" y="3" width="11" height="7" rx="2" fill="url(#grad2)" opacity="0.8" />
              <rect x="3" y="16" width="11" height="9" rx="2" fill="url(#grad2)" opacity="0.8" />
              <rect x="16" y="12" width="9" height="13" rx="2" fill="url(#grad1)" opacity="0.9" />
              <defs>
                <linearGradient id="grad1" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#4f8ef7" />
                  <stop offset="100%" stopColor="#7c5cfc" />
                </linearGradient>
                <linearGradient id="grad2" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#7c5cfc" />
                  <stop offset="100%" stopColor="#00d4aa" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <div className="header__logo-text">
            <span className="header__logo-name gradient-text">DocFactory</span>
            <span className="header__logo-tag">AI</span>
          </div>
        </div>

        <div className="header__breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '16px', color: 'var(--color-text-secondary)', fontSize: '0.85rem' }}>
          <span>/</span>
          <span style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>{currentSection}</span>
        </div>
      </div>

      <div className="header__center">
        <form className="header__search" role="search" onSubmit={handleSearchSubmit}>
          <svg className="header__search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            id="header-search"
            type="search"
            className="header__search-input"
            placeholder="Search documents, jobs, results..."
            aria-label="Search documents"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
          />
          <kbd className="header__search-kbd">⌘K</kbd>
        </form>
      </div>

      <div className="header__right">
        <div
          className="header__status"
          title={`Backend status: ${apiStatus}`}
        >
          <span
            className={`header__status-dot header__status-dot--${apiStatus}`}
            aria-label={`API ${apiStatus}`}
          />
          <span className="header__status-label">
            {apiStatus === 'healthy' ? 'API Online' : apiStatus === 'degraded' ? 'Degraded' : 'Offline'}
          </span>
        </div>

        <button
          id="header-notifications-btn"
          className="header__icon-btn"
          aria-label="Notifications"
          title="Notifications"
          type="button"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </button>

        <button
          id="header-user-btn"
          className="header__avatar"
          aria-label="Auditor profile"
          title="Auditor Profile"
          type="button"
        >
          <span>A</span>
        </button>
      </div>
    </header>
  )
}

export default Header
