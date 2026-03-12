const PIPELINE_STAGES = [
    { id: 'filtered', label: 'Filtered', icon: '🎯', color: 'var(--primary-400)' },
    { id: 'reviewed', label: 'Reviewed', icon: '👁️', color: 'var(--info-400)' },
    { id: 'cv_generated', label: 'CV Ready', icon: '📄', color: 'var(--warning-400)' },
    { id: 'ready_to_send', label: 'Ready', icon: '📬', color: 'var(--accent-400)' },
    { id: 'sent', label: 'Sent', icon: '✉️', color: '#6ee7b7' },
    { id: 'interview', label: 'Interview', icon: '🎤', color: '#a78bfa' },
];

export default function PipelineView({ jobs, onSelectJob, onStatusUpdate }) {
    const groupedJobs = {};
    PIPELINE_STAGES.forEach(stage => {
        groupedJobs[stage.id] = jobs.filter(j => j.application_status === stage.id);
    });

    return (
        <div className="pipeline-grid">
            {PIPELINE_STAGES.map(stage => (
                <div className="pipeline-column" key={stage.id}>
                    <div className="pipeline-column-header">
                        <h4 style={{ color: stage.color }}>
                            {stage.icon} {stage.label}
                        </h4>
                        <span className="count">{groupedJobs[stage.id].length}</span>
                    </div>

                    {groupedJobs[stage.id].length === 0 ? (
                        <div style={{
                            padding: '20px',
                            textAlign: 'center',
                            color: 'var(--text-muted)',
                            fontSize: '13px',
                        }}>
                            No jobs
                        </div>
                    ) : (
                        groupedJobs[stage.id].map(job => (
                            <div
                                key={job.job_id}
                                className="pipeline-card"
                                onClick={() => onSelectJob(job)}
                            >
                                <div className="card-title">{job.title}</div>
                                <div className="card-company">{job.company?.name || 'Unknown'}</div>
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    marginTop: '6px',
                                }}>
                                    <div className="score-bar" style={{ width: '40px' }}>
                                        <div
                                            className={`score-bar-fill ${job.relevance_score >= 70 ? 'high' : job.relevance_score >= 40 ? 'medium' : 'low'}`}
                                            style={{ width: `${Math.min(job.relevance_score, 100)}%` }}
                                        ></div>
                                    </div>
                                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                        {job.relevance_score?.toFixed(0)}
                                    </span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            ))}
        </div>
    );
}
