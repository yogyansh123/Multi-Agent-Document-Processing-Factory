import React, { useState } from 'react'
import './Sidebar.css'

interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  badge?: number | string
  comingSoon?: boolean
}

const navItems: NavItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    id: 'documents',
    label: 'Documents',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
    ),
  },
  {
    id: 'upload',
    label: 'Upload Document',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
    ),
  },
  {
    id: 'review',
    label: 'Review Queue',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    id: 'rag',
    label: 'Document Intelligence',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
    ),
  },
  {
    id: 'analytics',
    label: 'Analytics',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
  },
]

const bottomItems: NavItem[] = [
  {
    id: 'health',
    label: 'System Health',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
  },
]

interface SidebarProps {
  activeNav?: string
  onSelectNav?: (id: string) => void
}

const Sidebar: React.FC<SidebarProps> = ({ activeNav, onSelectNav }) => {
  const [internalActive, setInternalActive] = useState<string>('dashboard')
  const currentActive = activeNav !== undefined ? activeNav : internalActive

  const handleClick = (id: string, comingSoon?: boolean) => {
    if (comingSoon) return
    if (onSelectNav) {
      onSelectNav(id)
    } else {
      setInternalActive(id)
    }
  }

  return (
    <aside className="sidebar glass" id="app-sidebar" role="navigation" aria-label="Main navigation">
      <nav className="sidebar__nav">
        <div className="sidebar__section">
          <p className="sidebar__section-label">Main</p>
          <ul className="sidebar__list" role="list">
            {navItems.map((item) => (
              <li key={item.id}>
                <button
                  id={`sidebar-nav-${item.id}`}
                  className={`sidebar__item ${currentActive === item.id ? 'sidebar__item--active' : ''} ${item.comingSoon ? 'sidebar__item--coming-soon' : ''}`}
                  onClick={() => handleClick(item.id, item.comingSoon)}
                  aria-current={currentActive === item.id ? 'page' : undefined}
                  title={item.comingSoon ? `${item.label} — Coming soon` : item.label}
                >
                  <span className="sidebar__item-icon">{item.icon}</span>
                  <span className="sidebar__item-label">{item.label}</span>
                  {item.badge !== undefined && Number(item.badge) > 0 && (
                    <span className="sidebar__badge" aria-label={`${item.badge} items`}>
                      {item.badge}
                    </span>
                  )}
                  {item.comingSoon && (
                    <span className="sidebar__coming-soon">Soon</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="sidebar__section sidebar__section--bottom">
          <p className="sidebar__section-label">System</p>
          <ul className="sidebar__list" role="list">
            {bottomItems.map((item) => (
              <li key={item.id}>
                <button
                  id={`sidebar-nav-${item.id}`}
                  className={`sidebar__item ${currentActive === item.id ? 'sidebar__item--active' : ''} ${item.comingSoon ? 'sidebar__item--coming-soon' : ''}`}
                  onClick={() => handleClick(item.id, item.comingSoon)}
                  aria-current={currentActive === item.id ? 'page' : undefined}
                  title={item.comingSoon ? `${item.label} — Coming soon` : item.label}
                >
                  <span className="sidebar__item-icon">{item.icon}</span>
                  <span className="sidebar__item-label">{item.label}</span>
                  {item.comingSoon && (
                    <span className="sidebar__coming-soon">Soon</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      <div className="sidebar__footer">
        <div className="sidebar__version">
          <span className="sidebar__version-label">v0.1.0</span>
          <span className="sidebar__version-env">Development</span>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar
