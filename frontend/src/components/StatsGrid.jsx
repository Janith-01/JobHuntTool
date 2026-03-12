export default function StatsGrid({ stats }) {
    if (!stats) return null;

    const cards = [
        {
            icon: '📦',
            iconClass: 'blue',
            value: stats.total_jobs || 0,
            label: 'Total Jobs Found',
            change: null,
        },
        {
            icon: '🆕',
            iconClass: 'cyan',
            value: stats.recent_jobs_7d || 0,
            label: 'New This Week',
            change: null,
        },
        {
            icon: '✅',
            iconClass: 'green',
            value: (stats.status_breakdown?.sent || 0) + (stats.status_breakdown?.interview || 0),
            label: 'Applications Sent',
            change: null,
        },
        {
            icon: '🎯',
            iconClass: 'amber',
            value: stats.avg_relevance_score?.toFixed(1) || '0.0',
            label: 'Avg. Match Score',
            change: null,
        },
        {
            icon: '🎤',
            iconClass: 'green',
            value: stats.status_breakdown?.interview || 0,
            label: 'Interviews',
            change: null,
        },
    ];

    return (
        <div className="stats-grid">
            {cards.map((card, i) => (
                <div key={i} className="stat-card">
                    <div className={`stat-icon ${card.iconClass}`}>
                        {card.icon}
                    </div>
                    <div className="stat-info">
                        <h3>{card.value}</h3>
                        <p>{card.label}</p>
                        {card.change && (
                            <span className={`stat-change ${card.change > 0 ? 'up' : 'down'}`}>
                                {card.change > 0 ? '↑' : '↓'} {Math.abs(card.change)}
                            </span>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
