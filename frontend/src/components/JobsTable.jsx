import { useState } from 'react';

const STATUS_OPTIONS = [
    { value: '', label: 'All Statuses' },
    { value: 'discovered', label: '🔍 Discovered' },
    { value: 'filtered', label: '🎯 Filtered' },
    { value: 'reviewed', label: '👁️ Reviewed' },
    { value: 'cv_generated', label: '📄 CV Generated' },
    { value: 'ready_to_send', label: '📬 Ready to Send' },
    { value: 'sent', label: '✉️ Sent' },
    { value: 'interview', label: '🎤 Interview' },
    { value: 'rejected', label: '❌ Rejected' },
    { value: 'accepted', label: '🎉 Accepted' },
    { value: 'skipped', label: '⏭️ Skipped' },
];

const PLATFORM_OPTIONS = [
    { value: '', label: 'All Platforms' },
    { value: 'linkedin', label: '🔗 LinkedIn' },
    { value: 'topjobs_lk', label: '🇱🇰 TopJobs.lk' },
    { value: 'xpress_jobs', label: '💼 XpressJobs' },
];

export default function JobsTable({
    jobs,
    pagination,
    filters,
    isLoading,
    onFilterChange,
    onPageChange,
    onSelectJob,
    onStatusUpdate,
    onDeleteJob,
}) {
    const [searchInput, setSearchInput] = useState(filters.search || '');

    const handleSearch = (e) => {
        e.preventDefault();
        onFilterChange({ ...filters, search: searchInput });
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '—';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    const getScoreClass = (score) => {
        if (score >= 70) return 'high';
        if (score >= 40) return 'medium';
        return 'low';
    };

    const getPlatformIcon = (platform) => {
        switch (platform) {
            case 'linkedin': return '🔗';
            case 'topjobs_lk': return '🇱🇰';
            case 'xpress_jobs': return '💼';
            default: return '🌐';
        }
    };

    return (
        <div className="jobs-table-container">
            {/* Header */}
            <div className="jobs-table-header">
                <h3>Jobs ({pagination.total})</h3>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <select
                        className="search-input"
                        value={filters.status}
                        onChange={(e) => onFilterChange({ ...filters, status: e.target.value })}
                        style={{ width: '160px' }}
                        id="filter-status"
                    >
                        {STATUS_OPTIONS.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>

                    <select
                        className="search-input"
                        value={filters.platform}
                        onChange={(e) => onFilterChange({ ...filters, platform: e.target.value })}
                        style={{ width: '160px' }}
                        id="filter-platform"
                    >
                        {PLATFORM_OPTIONS.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>

                    <form onSubmit={handleSearch} style={{ display: 'flex', gap: '6px' }}>
                        <input
                            type="text"
                            className="search-input"
                            placeholder="Search jobs..."
                            value={searchInput}
                            onChange={(e) => setSearchInput(e.target.value)}
                            id="search-jobs"
                        />
                        <button type="submit" className="btn btn-secondary btn-sm">🔍</button>
                    </form>
                </div>
            </div>

            {/* Table */}
            {isLoading ? (
                <div className="loading-overlay">
                    <div className="spinner"></div>
                    <p>Loading jobs...</p>
                </div>
            ) : jobs.length === 0 ? (
                <div className="empty-state">
                    <div className="icon">📭</div>
                    <h3>No jobs found</h3>
                    <p>Run the scraper to discover new job listings, or adjust your filters.</p>
                </div>
            ) : (
                <table>
                    <thead>
                        <tr>
                            <th>Job</th>
                            <th>Platform</th>
                            <th>Status</th>
                            <th>Match Score</th>
                            <th>Keywords</th>
                            <th>Date</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {jobs.map(job => (
                            <tr key={job.job_id}>
                                <td>
                                    <div
                                        className="job-title-cell"
                                        style={{ cursor: 'pointer' }}
                                        onClick={() => onSelectJob(job)}
                                    >
                                        <span className="title">{job.title}</span>
                                        <span className="company">
                                            {job.company?.name || 'Unknown'}{' '}
                                            {job.company?.location && `• ${job.company.location}`}
                                        </span>
                                    </div>
                                </td>
                                <td>
                                    <span title={job.source_platform}>
                                        {getPlatformIcon(job.source_platform)}
                                    </span>
                                </td>
                                <td>
                                    <span className={`status-badge ${job.application_status}`}>
                                        <span className="status-dot"></span>
                                        {job.application_status?.replace(/_/g, ' ')}
                                    </span>
                                </td>
                                <td>
                                    <div className="score-bar-container">
                                        <div className="score-bar">
                                            <div
                                                className={`score-bar-fill ${getScoreClass(job.relevance_score)}`}
                                                style={{ width: `${Math.min(job.relevance_score, 100)}%` }}
                                            ></div>
                                        </div>
                                        <span className="score-value">{job.relevance_score?.toFixed(0) || 0}</span>
                                    </div>
                                </td>
                                <td>
                                    <div className="keyword-tags">
                                        {(job.keyword_matches || []).slice(0, 3).map((kw, i) => (
                                            <span key={i} className="keyword-tag">{kw}</span>
                                        ))}
                                        {(job.keyword_matches || []).length > 3 && (
                                            <span className="keyword-tag" style={{ opacity: 0.6 }}>
                                                +{job.keyword_matches.length - 3}
                                            </span>
                                        )}
                                    </div>
                                </td>
                                <td style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                                    {formatDate(job.scraped_at)}
                                </td>
                                <td>
                                    <div style={{ display: 'flex', gap: '4px' }}>
                                        <button
                                            className="btn btn-secondary btn-sm"
                                            onClick={() => onSelectJob(job)}
                                            title="View Details"
                                        >
                                            👁️
                                        </button>
                                        <button
                                            className="btn btn-danger btn-sm"
                                            onClick={() => {
                                                if (confirm('Delete this job?')) onDeleteJob(job.job_id);
                                            }}
                                            title="Delete"
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {/* Pagination */}
            {pagination.total_pages > 1 && (
                <div className="pagination">
                    <span className="pagination-info">
                        Showing {((pagination.page - 1) * pagination.limit) + 1}–
                        {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total}
                    </span>
                    <div className="pagination-buttons">
                        {Array.from({ length: Math.min(pagination.total_pages, 7) }, (_, i) => i + 1).map(p => (
                            <button
                                key={p}
                                className={`pagination-btn ${p === pagination.page ? 'active' : ''}`}
                                onClick={() => onPageChange(p)}
                            >
                                {p}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
