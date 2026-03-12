import { useState } from 'react';

export default function ScrapePanel({ onScrape, isScraping, expanded = false }) {
    const [config, setConfig] = useState({
        searchQuery: 'Software Intern',
        location: 'Sri Lanka',
        maxResults: 30,
        platforms: [],
        headless: true,
    });

    const platformOptions = [
        { value: 'linkedin', label: '🔗 LinkedIn' },
        { value: 'topjobs_lk', label: '🇱🇰 TopJobs.lk' },
        { value: 'xpress_jobs', label: '💼 XpressJobs' },
    ];

    const handleSubmit = (e) => {
        e.preventDefault();
        onScrape({
            ...config,
            platforms: config.platforms.length > 0 ? config.platforms : undefined,
        });
    };

    const togglePlatform = (value) => {
        setConfig(prev => ({
            ...prev,
            platforms: prev.platforms.includes(value)
                ? prev.platforms.filter(p => p !== value)
                : [...prev.platforms, value],
        }));
    };

    return (
        <div className="scrape-panel">
            <h3>🕷️ {expanded ? 'Scraper Configuration' : 'Quick Scrape'}</h3>
            <form className="scrape-form" onSubmit={handleSubmit}>
                <div className="form-group">
                    <label>Search Query</label>
                    <input
                        type="text"
                        id="scrape-query"
                        value={config.searchQuery}
                        onChange={(e) => setConfig(prev => ({ ...prev, searchQuery: e.target.value }))}
                        placeholder="e.g. Software Intern, AI Developer"
                    />
                </div>

                <div className="form-group">
                    <label>Location</label>
                    <input
                        type="text"
                        id="scrape-location"
                        value={config.location}
                        onChange={(e) => setConfig(prev => ({ ...prev, location: e.target.value }))}
                        placeholder="e.g. Sri Lanka, Colombo"
                    />
                </div>

                <div className="form-group">
                    <label>Max Results / Platform</label>
                    <input
                        type="number"
                        id="scrape-max-results"
                        value={config.maxResults}
                        onChange={(e) => setConfig(prev => ({ ...prev, maxResults: parseInt(e.target.value) || 30 }))}
                        min="5"
                        max="100"
                    />
                </div>

                <div className="form-group">
                    <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={isScraping}
                        id="scrape-button"
                        style={{ marginTop: '4px' }}
                    >
                        {isScraping ? (
                            <>
                                <span className="spinner"></span>
                                Scraping...
                            </>
                        ) : (
                            <>🚀 Start Scraping</>
                        )}
                    </button>
                </div>
            </form>

            {expanded && (
                <div style={{ marginTop: '20px' }}>
                    <label style={{
                        fontSize: '12px',
                        fontWeight: 600,
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        marginBottom: '10px',
                        display: 'block',
                    }}>
                        Target Platforms (empty = all)
                    </label>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {platformOptions.map(opt => (
                            <button
                                key={opt.value}
                                type="button"
                                className={`btn btn-sm ${config.platforms.includes(opt.value) ? 'btn-primary' : 'btn-secondary'}`}
                                onClick={() => togglePlatform(opt.value)}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '16px' }}>
                        <input
                            type="checkbox"
                            id="headless-toggle"
                            checked={config.headless}
                            onChange={(e) => setConfig(prev => ({ ...prev, headless: e.target.checked }))}
                        />
                        <label htmlFor="headless-toggle" style={{ fontSize: '13px', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                            Headless mode (hide browser window)
                        </label>
                    </div>
                </div>
            )}
        </div>
    );
}
