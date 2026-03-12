import { useState } from 'react';
import {
    tailorCVForJob, getTailoredCV,
    extractContactFromText, generateApplicationEmail,
    openEmailClient,
} from '../api';

const STATUS_FLOW = [
    'discovered', 'filtered', 'reviewed', 'cv_generated',
    'cover_letter_done', 'ready_to_send', 'sent',
    'interview', 'accepted',
];

export default function JobDetailModal({ job, onClose, onStatusUpdate, onToast }) {
    if (!job) return null;

    const [isTailoring, setIsTailoring] = useState(false);
    const [tailorResult, setTailorResult] = useState(null);
    const [activeTab, setActiveTab] = useState('details');
    const [isApplying, setIsApplying] = useState(false);
    const [applyData, setApplyData] = useState(null); // { contact, email }

    const currentStatusIdx = STATUS_FLOW.indexOf(job.application_status);
    const nextStatus = currentStatusIdx >= 0 && currentStatusIdx < STATUS_FLOW.length - 1
        ? STATUS_FLOW[currentStatusIdx + 1]
        : null;

    const techStack = job.tech_stack_required || {};

    const handleTailor = async () => {
        setIsTailoring(true);
        try {
            const result = await tailorCVForJob(job.job_id);
            setTailorResult(result);
            setActiveTab('ai-result');
            if (onToast) onToast(`✅ ATS Score: ${result.ats_score?.toFixed(1)} (${result.ats_grade})`, 'success');
        } catch (err) {
            if (onToast) onToast(`❌ Tailoring failed: ${err.message}`, 'error');
        }
        setIsTailoring(false);
    };

    const handleLoadExisting = async () => {
        try {
            const result = await getTailoredCV(job.job_id);
            setTailorResult(result.data);
            setActiveTab('ai-result');
        } catch {
            if (onToast) onToast('No previous tailored CV found', 'info');
        }
    };

    const handleApply = async () => {
        setIsApplying(true);
        try {
            // Step 1: Extract contact info from JD
            const jdText = job.job_description || '';
            const contactRes = await extractContactFromText(
                jdText,
                job.title || '',
                job.company?.name || '',
            );
            const contact = contactRes.data || contactRes;

            // Step 2: Generate the application email
            const emailRes = await generateApplicationEmail(
                job.title || '',
                job.company?.name || '',
                jdText,
                contact.contact_person || '',
            );
            const email = emailRes.data || emailRes;

            setApplyData({ contact, email });
            setActiveTab('apply');

            if (onToast) {
                const emailFound = contact.recipient_email ? '📧 Email found!' : '⚠️ No email found in JD';
                onToast(`${emailFound} Application email generated.`, contact.recipient_email ? 'success' : 'info');
            }
        } catch (err) {
            if (onToast) onToast(`❌ Apply failed: ${err.message}`, 'error');
        }
        setIsApplying(false);
    };

    const getGradeColor = (grade) => {
        if (!grade) return 'var(--text-muted)';
        if (grade.startsWith('A')) return 'var(--accent-400)';
        if (grade.startsWith('B')) return 'var(--warning-400)';
        if (grade.startsWith('C')) return 'var(--warning-500)';
        return 'var(--danger-400)';
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '850px' }}>
                {/* Header */}
                <div className="modal-header">
                    <div>
                        <h2>{job.title}</h2>
                        <p style={{ color: 'var(--text-muted)', marginTop: '4px', fontSize: '14px' }}>
                            {job.company?.name || 'Unknown Company'}
                            {job.company?.location && ` • ${job.company.location}`}
                        </p>
                    </div>
                    <button className="close-btn" onClick={onClose}>✕</button>
                </div>

                {/* Tab Switcher */}
                <div style={{
                    display: 'flex',
                    borderBottom: '1px solid var(--border-color)',
                    padding: '0 28px',
                }}>
                    {[
                        { id: 'details', label: '📋 Details' },
                        { id: 'ai-result', label: '🧠 AI Result', disabled: !tailorResult },
                        { id: 'cover-letter', label: '✉️ Cover Letter', disabled: !tailorResult?.cover_letter },
                        { id: 'apply', label: '📨 Apply', disabled: !applyData },
                    ].map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => !tab.disabled && setActiveTab(tab.id)}
                            style={{
                                padding: '12px 16px',
                                border: 'none',
                                background: 'none',
                                color: activeTab === tab.id ? 'var(--primary-400)' : tab.disabled ? 'var(--text-muted)' : 'var(--text-secondary)',
                                borderBottom: activeTab === tab.id ? '2px solid var(--primary-400)' : '2px solid transparent',
                                fontWeight: activeTab === tab.id ? 600 : 400,
                                fontSize: '13px',
                                cursor: tab.disabled ? 'default' : 'pointer',
                                opacity: tab.disabled ? 0.4 : 1,
                                fontFamily: 'var(--font-sans)',
                                transition: 'all 150ms ease',
                            }}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Body */}
                <div className="modal-body">
                    {activeTab === 'details' && (
                        <>
                            {/* Status & Score Row */}
                            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap' }}>
                                <span className={`status-badge ${job.application_status}`}>
                                    <span className="status-dot"></span>
                                    {job.application_status?.replace(/_/g, ' ')}
                                </span>

                                <div className="score-bar-container">
                                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Match:</span>
                                    <div className="score-bar" style={{ width: '80px' }}>
                                        <div
                                            className={`score-bar-fill ${job.relevance_score >= 70 ? 'high' : job.relevance_score >= 40 ? 'medium' : 'low'}`}
                                            style={{ width: `${Math.min(job.relevance_score, 100)}%` }}
                                        ></div>
                                    </div>
                                    <span className="score-value">{job.relevance_score?.toFixed(1)}</span>
                                </div>

                                {/* AI Optimization badge if already tailored */}
                                {job.ai_optimization && (
                                    <span style={{
                                        padding: '4px 10px',
                                        borderRadius: '100px',
                                        fontSize: '11px',
                                        fontWeight: 700,
                                        background: 'rgba(16, 185, 129, 0.15)',
                                        color: getGradeColor(job.ai_optimization.ats_grade),
                                        fontFamily: 'var(--font-mono)',
                                    }}>
                                        ATS: {job.ai_optimization.ats_score?.toFixed(0)} ({job.ai_optimization.ats_grade})
                                    </span>
                                )}
                            </div>

                            {/* Action Buttons */}
                            <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
                                <button
                                    className="btn btn-primary btn-sm"
                                    onClick={handleTailor}
                                    disabled={isTailoring}
                                    id="tailor-cv-btn"
                                >
                                    {isTailoring ? (
                                        <><span className="spinner" style={{ width: 14, height: 14 }}></span> Tailoring...</>
                                    ) : (
                                        <>🧠 AI Tailor CV</>
                                    )}
                                </button>

                                <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={handleLoadExisting}
                                >
                                    📄 Load Existing
                                </button>

                                {nextStatus && (
                                    <button
                                        className="btn btn-accent btn-sm"
                                        onClick={() => onStatusUpdate(job.job_id, nextStatus)}
                                    >
                                        ➡️ {nextStatus.replace(/_/g, ' ')}
                                    </button>
                                )}

                                <button
                                    className="btn btn-secondary btn-sm"
                                    onClick={() => onStatusUpdate(job.job_id, 'reviewed')}
                                >
                                    👁️ Reviewed
                                </button>
                                <button
                                    className="btn btn-danger btn-sm"
                                    onClick={() => onStatusUpdate(job.job_id, 'skipped')}
                                >
                                    ⏭️ Skip
                                </button>
                                <button
                                    className="btn btn-sm"
                                    onClick={handleApply}
                                    disabled={isApplying}
                                    id="apply-btn"
                                    style={{
                                        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                                        color: '#fff',
                                        border: 'none',
                                        fontWeight: 600,
                                    }}
                                >
                                    {isApplying ? (
                                        <><span className="spinner" style={{ width: 14, height: 14 }}></span> Preparing...</>
                                    ) : (
                                        <>📨 Apply</>
                                    )}
                                </button>
                                {job.source_url && (
                                    <a href={job.source_url} target="_blank" rel="noopener noreferrer"
                                        className="btn btn-secondary btn-sm">🔗 Original</a>
                                )}
                            </div>

                            {/* Info Grid */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', marginBottom: '20px' }}>
                                <div className="info-row">
                                    <span className="label">Platform:</span>
                                    <span>{job.source_platform?.replace(/_/g, ' ')}</span>
                                </div>
                                {job.job_type && <div className="info-row"><span className="label">Type:</span><span>{job.job_type}</span></div>}
                                {job.experience_level && <div className="info-row"><span className="label">Level:</span><span>{job.experience_level}</span></div>}
                                {job.salary_range && <div className="info-row"><span className="label">Salary:</span><span>{job.salary_range}</span></div>}
                                {job.deadline && <div className="info-row"><span className="label">Deadline:</span><span>{job.deadline}</span></div>}
                                {job.posted_date && <div className="info-row"><span className="label">Posted:</span><span>{job.posted_date}</span></div>}
                            </div>

                            {/* Keywords */}
                            {job.keyword_matches?.length > 0 && (
                                <div style={{ marginBottom: '20px' }}>
                                    <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>Matched Keywords</h4>
                                    <div className="keyword-tags">
                                        {job.keyword_matches.map((kw, i) => <span key={i} className="keyword-tag">{kw}</span>)}
                                    </div>
                                </div>
                            )}

                            {/* Tech Stack */}
                            {Object.values(techStack).some(arr => arr?.length > 0) && (
                                <div style={{ marginBottom: '20px' }}>
                                    <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>Tech Stack Required</h4>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                        {Object.entries(techStack).flatMap(([cat, items]) =>
                                            (items || []).map((item, i) => (
                                                <span key={`${cat}-${i}`} className="keyword-tag" style={{
                                                    background: 'rgba(16, 185, 129, 0.1)',
                                                    color: 'var(--accent-400)',
                                                    borderColor: 'rgba(16, 185, 129, 0.15)',
                                                }}>{item}</span>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Description */}
                            <div>
                                <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 600 }}>Job Description</h4>
                                <div className="description-text">{job.job_description || 'No description available.'}</div>
                            </div>
                        </>
                    )}

                    {/* AI Result Tab */}
                    {activeTab === 'ai-result' && tailorResult && (
                        <AIResultView result={tailorResult} />
                    )}

                    {/* Cover Letter Tab */}
                    {activeTab === 'cover-letter' && tailorResult?.cover_letter && (
                        <CoverLetterView coverLetter={tailorResult.cover_letter} />
                    )}

                    {/* Apply Tab */}
                    {activeTab === 'apply' && applyData && (
                        <ApplyView
                            contact={applyData.contact}
                            email={applyData.email}
                            onToast={onToast}
                            onStatusUpdate={() => onStatusUpdate(job.job_id, 'sent')}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}


// ── Apply Email Sub-component ─────────────────────────────

function ApplyView({ contact, email, onToast, onStatusUpdate }) {
    const [copied, setCopied] = useState(false);

    const fullBody = email.full_text || email.body || '';
    const subjectLine = email.subject_line || contact.subject_line || '';
    const recipientEmail = contact.recipient_email || '';

    const handleCopy = () => {
        const text = `To: ${recipientEmail}\nSubject: ${subjectLine}\n\n${fullBody}`;
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        if (onToast) onToast('📋 Email copied to clipboard!', 'success');
    };

    const handleOpenEmail = () => {
        openEmailClient({ to: recipientEmail, subject: subjectLine, body: fullBody });
    };

    return (
        <div>
            {/* Contact Info Card */}
            <div style={{
                padding: '16px 20px',
                background: 'var(--bg-glass)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-color)',
                marginBottom: '16px',
            }}>
                <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '10px', fontWeight: 600 }}>📇 Extracted Contact</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 20px' }}>
                    <div className="info-row">
                        <span className="label">Email:</span>
                        <span style={{ color: recipientEmail ? 'var(--accent-400)' : 'var(--danger-400)', fontWeight: 600, fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                            {recipientEmail || 'Not found in JD'}
                        </span>
                    </div>
                    <div className="info-row">
                        <span className="label">Company:</span>
                        <span>{contact.company_name || 'Unknown'}</span>
                    </div>
                    {contact.contact_person && (
                        <div className="info-row">
                            <span className="label">Contact:</span>
                            <span>{contact.contact_person}</span>
                        </div>
                    )}
                    <div className="info-row">
                        <span className="label">Confidence:</span>
                        <span style={{
                            padding: '2px 8px', borderRadius: '100px', fontSize: '11px', fontWeight: 700,
                            background: contact.confidence === 'high' ? 'rgba(16,185,129,0.15)' : contact.confidence === 'medium' ? 'rgba(251,191,36,0.15)' : 'rgba(244,63,94,0.15)',
                            color: contact.confidence === 'high' ? '#34d399' : contact.confidence === 'medium' ? '#fbbf24' : '#fb7185',
                        }}>
                            {contact.confidence || 'low'}
                        </span>
                    </div>
                </div>
                {contact.all_emails_found?.length > 1 && (
                    <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                        All emails found: {contact.all_emails_found.join(', ')}
                    </div>
                )}
            </div>

            {/* Subject Line */}
            <div style={{
                padding: '12px 16px',
                background: 'var(--bg-glass)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-color)',
                marginBottom: '12px',
            }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>SUBJECT: </span>
                <span style={{ fontSize: '14px', fontWeight: 500 }}>{subjectLine}</span>
            </div>

            {/* Email Body */}
            <div style={{
                padding: '20px',
                background: 'var(--bg-glass)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-color)',
                marginBottom: '16px',
                lineHeight: 1.8,
                fontSize: '14px',
                whiteSpace: 'pre-line',
                color: 'var(--text-secondary)',
            }}>
                {fullBody}
            </div>

            {/* Skill/Project Match */}
            {(email.matched_skill || email.matched_project) && (
                <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
                    {email.matched_skill && (
                        <span className="keyword-tag" style={{
                            background: 'rgba(99,102,241,0.15)', color: '#818cf8', borderColor: 'rgba(99,102,241,0.25)',
                        }}>🎯 Matched: {email.matched_skill}</span>
                    )}
                    {email.matched_project && (
                        <span className="keyword-tag" style={{
                            background: 'rgba(16,185,129,0.12)', color: '#34d399', borderColor: 'rgba(16,185,129,0.2)',
                        }}>📁 Project: {email.matched_project}</span>
                    )}
                </div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button
                    className="btn btn-sm"
                    onClick={handleOpenEmail}
                    disabled={!recipientEmail}
                    style={{
                        background: recipientEmail ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'var(--bg-glass)',
                        color: recipientEmail ? '#fff' : 'var(--text-muted)',
                        border: 'none',
                        fontWeight: 600,
                        opacity: recipientEmail ? 1 : 0.5,
                        cursor: recipientEmail ? 'pointer' : 'not-allowed',
                    }}
                >
                    📧 Open in Email Client
                </button>
                <button className="btn btn-accent btn-sm" onClick={handleCopy}>
                    {copied ? '✅ Copied!' : '📋 Copy Email'}
                </button>
                <button
                    className="btn btn-secondary btn-sm"
                    onClick={onStatusUpdate}
                    title="Mark as sent after you email it"
                >
                    ✅ Mark as Sent
                </button>
            </div>

            {!recipientEmail && (
                <p style={{ marginTop: '12px', fontSize: '12px', color: 'var(--warning-400)', lineHeight: 1.5 }}>
                    ⚠️ No email found in the JD. You can copy the email above and send it manually,
                    or check the original posting for a contact email / application form.
                </p>
            )}
        </div>
    );
}


// ── ATS Report & Tailored CV Sub-component ────────────────

function AIResultView({ result }) {
    const ats = result.ats_report || {};
    const cv = result.tailored_cv || {};
    const scores = ats.scores || {};

    const getGradeColor = (grade) => {
        if (!grade) return 'var(--text-muted)';
        if (grade.startsWith('A')) return '#34d399';
        if (grade.startsWith('B')) return '#fbbf24';
        return '#fb7185';
    };

    return (
        <div>
            {/* ATS Score Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '20px',
                padding: '20px',
                background: 'var(--bg-glass)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-color)',
                marginBottom: '20px',
            }}>
                <div style={{
                    width: '80px', height: '80px',
                    borderRadius: '50%',
                    border: `3px solid ${getGradeColor(ats.grade)}`,
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    fontFamily: 'var(--font-mono)',
                }}>
                    <span style={{ fontSize: '24px', fontWeight: 800, color: getGradeColor(ats.grade) }}>
                        {ats.overall_score?.toFixed(0)}
                    </span>
                    <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>/100</span>
                </div>
                <div>
                    <p style={{ fontSize: '18px', fontWeight: 700 }}>
                        ATS Grade: <span style={{ color: getGradeColor(ats.grade) }}>{ats.grade}</span>
                    </p>
                    <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {ats.grade_label}
                    </p>
                    <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        Keywords: {ats.keywords?.found || 0}/{ats.keywords?.total_checked || 0} found •
                        Must-haves: {ats.keywords?.must_haves_found || 0}/{ats.keywords?.must_haves_total || 0}
                    </p>
                </div>
            </div>

            {/* Score Breakdown */}
            <div style={{ marginBottom: '20px' }}>
                <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '10px', fontWeight: 600 }}>Score Breakdown</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '8px' }}>
                    {[
                        { label: 'Must-Haves', value: scores.must_have, weight: '40%' },
                        { label: 'Keywords', value: scores.keyword_match, weight: '25%' },
                        { label: 'Nice-to-Have', value: scores.nice_to_have, weight: '15%' },
                        { label: 'Coverage', value: scores.section_coverage, weight: '10%' },
                        { label: 'Density', value: scores.density, weight: '10%' },
                    ].map((item, i) => (
                        <div key={i} style={{
                            padding: '10px 14px',
                            background: 'var(--bg-glass)',
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--border-color)',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.label} ({item.weight})</span>
                                <span style={{ fontSize: '12px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                                    {item.value?.toFixed(0) || 0}
                                </span>
                            </div>
                            <div style={{ height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px' }}>
                                <div style={{
                                    height: '100%', borderRadius: '2px',
                                    width: `${Math.min(item.value || 0, 100)}%`,
                                    background: (item.value || 0) >= 70 ? 'var(--accent-400)' : (item.value || 0) >= 40 ? 'var(--warning-400)' : 'var(--danger-400)',
                                    transition: 'width 0.5s ease',
                                }} />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Recommendations */}
            {ats.recommendations?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                    <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>Recommendations</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        {ats.recommendations.map((rec, i) => (
                            <div key={i} style={{
                                padding: '10px 14px',
                                background: 'var(--bg-glass)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: '13px',
                                color: 'var(--text-secondary)',
                                border: '1px solid var(--border-color)',
                                lineHeight: 1.5,
                            }}>
                                {rec}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Missing Keywords */}
            {ats.missing?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                    <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>
                        Missing Keywords ({ats.missing.length})
                    </h4>
                    <div className="keyword-tags">
                        {ats.missing.map((m, i) => (
                            <span key={i} className="keyword-tag" style={{
                                background: m.is_must_have ? 'rgba(244, 63, 94, 0.15)' : 'rgba(100, 116, 139, 0.1)',
                                color: m.is_must_have ? 'var(--danger-400)' : 'var(--text-muted)',
                                borderColor: m.is_must_have ? 'rgba(244, 63, 94, 0.2)' : 'rgba(100, 116, 139, 0.15)',
                            }}>
                                {m.is_must_have && '⚠️ '}{m.keyword}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Tailored Summary Preview */}
            {cv.professional_summary?.summary && (
                <div style={{ marginBottom: '20px' }}>
                    <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>
                        ✨ Tailored Summary
                    </h4>
                    <div className="description-text" style={{ maxHeight: '150px' }}>
                        {cv.professional_summary.summary}
                    </div>
                </div>
            )}

            {/* Tailored Skills Preview */}
            {cv.skills?.primary_skills?.length > 0 && (
                <div style={{ marginBottom: '20px' }}>
                    <h4 style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>
                        🎯 Optimized Skills (Primary)
                    </h4>
                    <div className="keyword-tags">
                        {cv.skills.primary_skills.map((s, i) => (
                            <span key={i} className="keyword-tag" style={{
                                background: 'rgba(16, 185, 129, 0.12)',
                                color: 'var(--accent-400)',
                                borderColor: 'rgba(16, 185, 129, 0.2)',
                            }}>{s}</span>
                        ))}
                    </div>
                </div>
            )}

            {/* Filename */}
            {cv.ats_optimized_filename && (
                <div style={{
                    padding: '10px 14px',
                    background: 'var(--bg-glass)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-color)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-secondary)',
                }}>
                    📄 Filename: {cv.ats_optimized_filename}
                </div>
            )}
        </div>
    );
}


// ── Cover Letter Sub-component ────────────────────────────

function CoverLetterView({ coverLetter }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        const text = coverLetter.full_text || [
            coverLetter.greeting,
            coverLetter.hook_paragraph,
            coverLetter.proof_paragraph,
            coverLetter.cta_paragraph,
            coverLetter.sign_off,
        ].filter(Boolean).join('\n\n');
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    // Support both old and new field names
    const hook = coverLetter.hook_paragraph || coverLetter.opening_paragraph || '';
    const proof = coverLetter.proof_paragraph || coverLetter.body_paragraph || '';
    const cta = coverLetter.cta_paragraph || coverLetter.closing_paragraph || '';

    return (
        <div>
            {/* Subject Line */}
            <div style={{
                padding: '12px 16px',
                background: 'var(--bg-glass)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-color)',
                marginBottom: '16px',
            }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>SUBJECT: </span>
                <span style={{ fontSize: '14px', fontWeight: 500 }}>{coverLetter.subject_line}</span>
            </div>

            {/* Full text if available, or structured paragraphs */}
            {coverLetter.full_text ? (
                <div className="description-text" style={{ maxHeight: 'none', lineHeight: 1.8, fontSize: '14px', whiteSpace: 'pre-line' }}>
                    {coverLetter.full_text}
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Greeting */}
                    <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                        {coverLetter.greeting}
                    </p>

                    {/* P1: Hook */}
                    {hook && (
                        <div>
                            <span style={{
                                fontSize: '10px', fontWeight: 700, color: 'var(--primary-400)',
                                textTransform: 'uppercase', letterSpacing: '0.5px',
                            }}>🎣 The Hook</span>
                            <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', marginTop: '4px' }}>
                                {hook}
                            </p>
                        </div>
                    )}

                    {/* P2: Proof */}
                    {proof && (
                        <div>
                            <span style={{
                                fontSize: '10px', fontWeight: 700, color: 'var(--accent-400)',
                                textTransform: 'uppercase', letterSpacing: '0.5px',
                            }}>🔧 The Proof</span>
                            <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', marginTop: '4px' }}>
                                {proof}
                            </p>
                        </div>
                    )}

                    {/* P3: CTA */}
                    {cta && (
                        <div>
                            <span style={{
                                fontSize: '10px', fontWeight: 700, color: 'var(--warning-400)',
                                textTransform: 'uppercase', letterSpacing: '0.5px',
                            }}>📞 Call to Action</span>
                            <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', marginTop: '4px' }}>
                                {cta}
                            </p>
                        </div>
                    )}

                    {/* Sign-off */}
                    <p style={{ fontSize: '14px', color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
                        {coverLetter.sign_off}
                    </p>
                </div>
            )}

            {/* Copy Button */}
            <button
                className="btn btn-accent btn-sm"
                onClick={handleCopy}
                style={{ marginTop: '12px' }}
            >
                {copied ? '✅ Copied!' : '📋 Copy to Clipboard'}
            </button>
        </div>
    );
}
