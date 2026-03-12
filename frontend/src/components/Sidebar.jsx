export default function Sidebar({ activeView, onNavigate, stats }) {
    const totalJobs = stats?.total_jobs || 0;
    const newThisWeek = stats?.recent_jobs_7d || 0;
    const interviews = stats?.status_breakdown?.interview || 0;

    const navItems = [
        { id: 'dashboard', label: 'Dashboard', icon: '📊', badge: null },
        { id: 'pipeline', label: 'Pipeline', icon: '🔀', badge: null },
        { id: 'review', label: 'Review & Approve', icon: '📋', badge: null },
        { id: 'scraper', label: 'Scraper', icon: '🕷️', badge: null },
    ];

    return (
        <aside className="sidebar">
            {/* Logo */}
            <div className="sidebar-logo">
                <div className="logo-icon">🎯</div>
                <div>
                    <h1>JobHuntTool</h1>
                    <span className="version">v1.0.0</span>
                </div>
            </div>

            {/* Navigation */}
            <nav>
                <div className="nav-section">
                    <p className="nav-section-title">Main</p>
                    {navItems.map(item => (
                        <div
                            key={item.id}
                            className={`nav-item ${activeView === item.id ? 'active' : ''}`}
                            onClick={() => onNavigate(item.id)}
                        >
                            <span className="icon">{item.icon}</span>
                            <span>{item.label}</span>
                            {item.badge !== null && <span className="badge">{item.badge}</span>}
                        </div>
                    ))}
                </div>

                <div className="nav-section">
                    <p className="nav-section-title">Quick Stats</p>
                    <div className="nav-item" style={{ cursor: 'default', opacity: 0.8 }}>
                        <span className="icon">📦</span>
                        <span>Total Jobs</span>
                        <span className="badge">{totalJobs}</span>
                    </div>
                    <div className="nav-item" style={{ cursor: 'default', opacity: 0.8 }}>
                        <span className="icon">🆕</span>
                        <span>This Week</span>
                        <span className="badge">{newThisWeek}</span>
                    </div>
                    {interviews > 0 && (
                        <div className="nav-item" style={{ cursor: 'default', opacity: 0.8 }}>
                            <span className="icon">🎤</span>
                            <span>Interviews</span>
                            <span className="badge" style={{ background: '#059669' }}>{interviews}</span>
                        </div>
                    )}
                </div>
            </nav>

            {/* Footer */}
            <div style={{ marginTop: 'auto', padding: '12px', borderTop: '1px solid var(--border-color)' }}>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center' }}>
                    Built with 🧠 by Janith Viranga
                </p>
            </div>
        </aside>
    );
}
