import { useState, useEffect, useCallback } from 'react';
import {
    fetchReviewQueue, generatePDF, editSection,
    approveCV, rejectCV, getDownloadURL,
} from '../api';

const STATUS_COLORS = {
    pending_review: { bg: 'rgba(251, 191, 36, 0.12)', color: '#fbbf24', label: '⏳ Pending Review' },
    approved: { bg: 'rgba(16, 185, 129, 0.12)', color: '#34d399', label: '✅ Approved' },
    needs_revision: { bg: 'rgba(244, 63, 94, 0.12)', color: '#fb7185', label: '🔄 Needs Revision' },
};

export default function ReviewDashboard({ onToast }) {
    const [queue, setQueue] = useState([]);
    const [selectedItem, setSelectedItem] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [editingSection, setEditingSection] = useState(null);
    const [editValue, setEditValue] = useState('');
    const [approvalNotes, setApprovalNotes] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const [isApproving, setIsApproving] = useState(false);

    const loadQueue = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await fetchReviewQueue();
            setQueue(data.items || []);
        } catch (err) {
            if (onToast) onToast('Failed to load review queue', 'error');
            setQueue([]);
        }
        setIsLoading(false);
    }, [onToast]);

    useEffect(() => { loadQueue(); }, [loadQueue]);

    const handleSelect = (item) => {
        setSelectedItem(item);
        setEditingSection(null);
        setEditValue('');
        setApprovalNotes('');
    };

    const handleGeneratePDF = async (jobId) => {
        setIsGenerating(true);
        try {
            await generatePDF(jobId);
            if (onToast) onToast('📄 PDFs generated successfully!', 'success');
            loadQueue();
        } catch (err) {
            if (onToast) onToast(`PDF generation failed: ${err.message}`, 'error');
        }
        setIsGenerating(false);
    };

    const handleApprove = async (jobId) => {
        setIsApproving(true);
        try {
            const result = await approveCV(jobId, approvalNotes);
            if (onToast) onToast(result.message || 'CV Approved!', 'success');
            setSelectedItem(null);
            loadQueue();
        } catch (err) {
            if (onToast) onToast(`Approval failed: ${err.message}`, 'error');
        }
        setIsApproving(false);
    };

    const handleReject = async (jobId) => {
        setIsApproving(true);
        try {
            const result = await rejectCV(jobId, approvalNotes);
            if (onToast) onToast(result.message || 'CV sent back for revision', 'info');
            setSelectedItem(null);
            loadQueue();
        } catch (err) {
            if (onToast) onToast(`Rejection failed: ${err.message}`, 'error');
        }
        setIsApproving(false);
    };

    const startEdit = (section, currentContent) => {
        setEditingSection(section);
        setEditValue(typeof currentContent === 'string' ? currentContent : JSON.stringify(currentContent, null, 2));
    };

    const saveEdit = async () => {
        if (!selectedItem || !editingSection) return;
        try {
            let content;
            try { content = JSON.parse(editValue); }
            catch { content = { summary: editValue, tone: 'professional', keywords_woven_in: [] }; }

            await editSection(selectedItem.job_id, editingSection, content);
            if (onToast) onToast(`✏️ ${editingSection} updated`, 'success');
            setEditingSection(null);
            loadQueue();
        } catch (err) {
            if (onToast) onToast(`Edit failed: ${err.message}`, 'error');
        }
    };

    const getGradeColor = (grade) => {
        if (!grade) return 'var(--text-muted)';
        if (grade.startsWith('A')) return '#34d399';
        if (grade.startsWith('B')) return '#fbbf24';
        return '#fb7185';
    };

    // ── Render ──────────────────────────────────────────────
    return (
        <div>
            <div className="header-bar">
                <div>
                    <h2>📋 Review & Approve</h2>
                    <p className="subtitle">
                        Human-in-the-loop workflow — review, edit, and approve AI-generated CVs before sending
                    </p>
                </div>
                <div className="header-actions">
                    <button className="btn btn-secondary" onClick={loadQueue}>
                        ↻ Refresh
                    </button>
                </div>
            </div>

            {isLoading ? (
                <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
                    <div className="spinner" style={{ width: 32, height: 32, margin: '0 auto 16px' }}></div>
                    Loading review queue...
                </div>
            ) : queue.length === 0 ? (
                <EmptyState />
            ) : selectedItem ? (
                <DetailView
                    item={selectedItem}
                    onBack={() => setSelectedItem(null)}
                    onGeneratePDF={handleGeneratePDF}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    isGenerating={isGenerating}
                    isApproving={isApproving}
                    editingSection={editingSection}
                    editValue={editValue}
                    onStartEdit={startEdit}
                    onEditValueChange={setEditValue}
                    onSaveEdit={saveEdit}
                    onCancelEdit={() => setEditingSection(null)}
                    approvalNotes={approvalNotes}
                    onApprovalNotesChange={setApprovalNotes}
                    getGradeColor={getGradeColor}
                />
            ) : (
                <QueueList
                    items={queue}
                    onSelect={handleSelect}
                    getGradeColor={getGradeColor}
                />
            )}
        </div>
    );
}


// ── Empty State ──────────────────────────────────────────

function EmptyState() {
    return (
        <div className="card" style={{ textAlign: 'center', padding: '60px 24px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📭</div>
            <h3 style={{ marginBottom: '8px' }}>No CVs pending review</h3>
            <p style={{ color: 'var(--text-muted)', maxWidth: '400px', margin: '0 auto', lineHeight: 1.6 }}>
                Tailor a CV for a job using the AI engine, then come here to review, edit, and approve it before generating PDFs.
            </p>
        </div>
    );
}


// ── Queue List ───────────────────────────────────────────

function QueueList({ items, onSelect, getGradeColor }) {
    return (
        <div style={{ display: 'grid', gap: '12px' }}>
            {items.map((item) => {
                const statusInfo = STATUS_COLORS[item.review_status] || STATUS_COLORS.pending_review;
                return (
                    <div
                        key={item.job_id}
                        className="card"
                        onClick={() => onSelect(item)}
                        style={{
                            cursor: 'pointer',
                            transition: 'all 150ms ease',
                            borderLeft: `3px solid ${statusInfo.color}`,
                        }}
                        id={`review-item-${item.job_id}`}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
                            <div style={{ flex: 1 }}>
                                <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '4px' }}>
                                    {item.job_title || 'Untitled Position'}
                                </h3>
                                <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
                                    {item.company_name || 'Unknown Company'}
                                </p>
                            </div>

                            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                                {/* ATS Score */}
                                <div style={{
                                    display: 'flex', alignItems: 'center', gap: '6px',
                                    padding: '5px 12px', borderRadius: '100px',
                                    background: 'var(--bg-glass)', border: '1px solid var(--border-color)',
                                    fontFamily: 'var(--font-mono)', fontSize: '12px',
                                }}>
                                    <span style={{ color: getGradeColor(item.ats_grade), fontWeight: 700 }}>
                                        {item.ats_grade}
                                    </span>
                                    <span style={{ color: 'var(--text-muted)' }}>
                                        {item.ats_score?.toFixed(0)}
                                    </span>
                                </div>

                                {/* PDF status */}
                                {item.has_pdfs && (
                                    <span style={{
                                        padding: '4px 10px', borderRadius: '100px',
                                        fontSize: '11px', background: 'rgba(16, 185, 129, 0.1)',
                                        color: 'var(--accent-400)',
                                    }}>📄 PDF Ready</span>
                                )}

                                {/* Review Status */}
                                <span style={{
                                    padding: '4px 10px', borderRadius: '100px',
                                    fontSize: '11px', fontWeight: 600,
                                    background: statusInfo.bg, color: statusInfo.color,
                                }}>
                                    {statusInfo.label}
                                </span>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}


// ── Detail View ──────────────────────────────────────────

function DetailView({
    item, onBack, onGeneratePDF, onApprove, onReject,
    isGenerating, isApproving,
    editingSection, editValue, onStartEdit, onEditValueChange, onSaveEdit, onCancelEdit,
    approvalNotes, onApprovalNotesChange, getGradeColor,
}) {
    const cv = item.tailored_cv || {};
    const cl = item.cover_letter || {};
    const ats = item.ats_report || {};
    const statusInfo = STATUS_COLORS[item.review_status] || STATUS_COLORS.pending_review;

    return (
        <div>
            {/* Back button + header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
                <button className="btn btn-secondary btn-sm" onClick={onBack}>← Back</button>
                <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600 }}>
                        {item.job_title} — {item.company_name}
                    </h3>
                    <div style={{ display: 'flex', gap: '10px', marginTop: '4px', flexWrap: 'wrap' }}>
                        <span style={{
                            fontSize: '12px', padding: '2px 10px', borderRadius: '100px',
                            fontFamily: 'var(--font-mono)', fontWeight: 700,
                            color: getGradeColor(ats.grade), background: 'var(--bg-glass)',
                            border: '1px solid var(--border-color)',
                        }}>
                            ATS: {ats.overall_score?.toFixed(0)} ({ats.grade})
                        </span>
                        <span style={{
                            fontSize: '11px', padding: '3px 10px', borderRadius: '100px',
                            background: statusInfo.bg, color: statusInfo.color, fontWeight: 600,
                        }}>
                            {statusInfo.label}
                        </span>
                    </div>
                </div>
            </div>

            {/* Action Bar */}
            <div className="card" style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                        className="btn btn-primary btn-sm"
                        onClick={() => onGeneratePDF(item.job_id)}
                        disabled={isGenerating}
                        id="generate-pdf-btn"
                    >
                        {isGenerating ? '⏳ Generating...' : '📄 Generate PDFs'}
                    </button>

                    {item.has_pdfs && (
                        <>
                            <a
                                href={getDownloadURL(item.job_id, 'cv')}
                                target="_blank" rel="noopener noreferrer"
                                className="btn btn-secondary btn-sm"
                            >⬇️ Download CV</a>
                            <a
                                href={getDownloadURL(item.job_id, 'cover_letter')}
                                target="_blank" rel="noopener noreferrer"
                                className="btn btn-secondary btn-sm"
                            >⬇️ Download Cover Letter</a>
                        </>
                    )}

                    <div style={{ flex: 1 }} />

                    <button
                        className="btn btn-danger btn-sm"
                        onClick={() => onReject(item.job_id)}
                        disabled={isApproving}
                        id="reject-btn"
                    >
                        🔄 Request Revision
                    </button>
                    <button
                        className="btn btn-accent btn-sm"
                        onClick={() => onApprove(item.job_id)}
                        disabled={isApproving}
                        id="approve-btn"
                        style={{ fontWeight: 700 }}
                    >
                        {isApproving ? '⏳...' : '✅ Approve & Send'}
                    </button>
                </div>

                {/* Approval Notes */}
                <div style={{ marginTop: '10px' }}>
                    <input
                        type="text"
                        value={approvalNotes}
                        onChange={(e) => onApprovalNotesChange(e.target.value)}
                        placeholder="Optional notes (e.g. 'Fix summary wording', 'Ready to send!')"
                        className="input"
                        style={{ width: '100%', fontSize: '13px' }}
                        id="approval-notes-input"
                    />
                </div>
            </div>

            {/* Editable Sections */}
            <div style={{ display: 'grid', gap: '12px' }}>
                {/* Summary */}
                <EditableSection
                    title="✨ Professional Summary"
                    sectionKey="summary"
                    content={typeof cv.professional_summary === 'object' ? cv.professional_summary?.summary : cv.professional_summary}
                    isEditing={editingSection === 'summary'}
                    editValue={editValue}
                    onStartEdit={() => onStartEdit('summary', typeof cv.professional_summary === 'object' ? cv.professional_summary?.summary : cv.professional_summary)}
                    onEditValueChange={onEditValueChange}
                    onSave={onSaveEdit}
                    onCancel={onCancelEdit}
                    renderContent={() => (
                        <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
                            {typeof cv.professional_summary === 'object'
                                ? cv.professional_summary?.summary
                                : cv.professional_summary}
                        </p>
                    )}
                />

                {/* Skills */}
                <EditableSection
                    title="🎯 Technical Skills"
                    sectionKey="skills"
                    content={cv.skills}
                    isEditing={editingSection === 'skills'}
                    editValue={editValue}
                    onStartEdit={() => onStartEdit('skills', cv.skills)}
                    onEditValueChange={onEditValueChange}
                    onSave={onSaveEdit}
                    onCancel={onCancelEdit}
                    renderContent={() => (
                        <div>
                            {cv.skills?.primary_skills?.length > 0 && (
                                <div style={{ marginBottom: '8px' }}>
                                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Core: </span>
                                    <span style={{ fontSize: '13px' }}>{cv.skills.primary_skills.join(', ')}</span>
                                </div>
                            )}
                            {cv.skills?.secondary_skills?.length > 0 && (
                                <div style={{ marginBottom: '8px' }}>
                                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Proficient: </span>
                                    <span style={{ fontSize: '13px' }}>{cv.skills.secondary_skills.join(', ')}</span>
                                </div>
                            )}
                            {cv.skills?.additional_skills?.length > 0 && (
                                <div>
                                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Additional: </span>
                                    <span style={{ fontSize: '13px' }}>{cv.skills.additional_skills.join(', ')}</span>
                                </div>
                            )}
                        </div>
                    )}
                />

                {/* Projects */}
                <EditableSection
                    title="🔧 Project Experience"
                    sectionKey="projects"
                    content={cv.projects}
                    isEditing={editingSection === 'projects'}
                    editValue={editValue}
                    onStartEdit={() => onStartEdit('projects', cv.projects)}
                    onEditValueChange={onEditValueChange}
                    onSave={onSaveEdit}
                    onCancel={onCancelEdit}
                    renderContent={() => (
                        <div style={{ display: 'grid', gap: '14px' }}>
                            {(cv.projects || []).map((proj, i) => (
                                <div key={i} style={{
                                    padding: '12px 16px',
                                    background: 'rgba(255,255,255,0.02)',
                                    borderRadius: 'var(--radius-md)',
                                    border: '1px solid var(--border-color)',
                                }}>
                                    <h4 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '4px' }}>{proj.name}</h4>
                                    <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>
                                        {(proj.tech_stack_display || []).join(' • ')}
                                    </p>
                                    {(proj.highlights || []).map((h, j) => (
                                        <p key={j} style={{ fontSize: '13px', color: 'var(--text-secondary)', paddingLeft: '12px', marginBottom: '2px' }}>
                                            • {h}
                                        </p>
                                    ))}
                                </div>
                            ))}
                        </div>
                    )}
                />

                {/* Experience */}
                <EditableSection
                    title="💼 Work Experience"
                    sectionKey="experience"
                    content={cv.experience}
                    isEditing={editingSection === 'experience'}
                    editValue={editValue}
                    onStartEdit={() => onStartEdit('experience', cv.experience)}
                    onEditValueChange={onEditValueChange}
                    onSave={onSaveEdit}
                    onCancel={onCancelEdit}
                    renderContent={() => (
                        <div style={{ display: 'grid', gap: '12px' }}>
                            {(cv.experience || []).map((exp, i) => (
                                <div key={i}>
                                    <h4 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '2px' }}>
                                        {exp.title}
                                        <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: '12px' }}>
                                            {' '}| {exp.company} | {exp.period}
                                        </span>
                                    </h4>
                                    {(exp.highlights || []).map((h, j) => (
                                        <p key={j} style={{ fontSize: '13px', color: 'var(--text-secondary)', paddingLeft: '12px', marginBottom: '2px' }}>
                                            • {h}
                                        </p>
                                    ))}
                                </div>
                            ))}
                        </div>
                    )}
                />

                {/* Cover Letter */}
                {cl && (
                    <EditableSection
                        title="✉️ Cover Letter"
                        sectionKey="cover_letter"
                        content={cl}
                        isEditing={editingSection === 'cover_letter'}
                        editValue={editValue}
                        onStartEdit={() => onStartEdit('cover_letter', cl)}
                        onEditValueChange={onEditValueChange}
                        onSave={onSaveEdit}
                        onCancel={onCancelEdit}
                        renderContent={() => {
                            const hook = cl.hook_paragraph || cl.opening_paragraph || '';
                            const proof = cl.proof_paragraph || cl.body_paragraph || '';
                            const cta = cl.cta_paragraph || cl.closing_paragraph || '';
                            return (
                                <div>
                                    {cl.subject_line && (
                                        <div style={{ marginBottom: '10px', padding: '8px 12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>SUBJECT: </span>
                                            <span style={{ fontSize: '13px' }}>{cl.subject_line}</span>
                                        </div>
                                    )}

                                    {cl.full_text ? (
                                        <p style={{
                                            fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)',
                                            whiteSpace: 'pre-line',
                                        }}>
                                            {cl.full_text}
                                        </p>
                                    ) : (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                            <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{cl.greeting}</p>

                                            {hook && (
                                                <div>
                                                    <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--primary-400)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>🎣 Hook</span>
                                                    <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', marginTop: '3px' }}>{hook}</p>
                                                </div>
                                            )}
                                            {proof && (
                                                <div>
                                                    <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent-400)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>🔧 Proof</span>
                                                    <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', marginTop: '3px' }}>{proof}</p>
                                                </div>
                                            )}
                                            {cta && (
                                                <div>
                                                    <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--warning-400)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>📞 CTA</span>
                                                    <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', marginTop: '3px' }}>{cta}</p>
                                                </div>
                                            )}

                                            <p style={{ fontSize: '13px', color: 'var(--text-muted)', whiteSpace: 'pre-line' }}>{cl.sign_off}</p>
                                        </div>
                                    )}
                                </div>
                            );
                        }}
                    />
                )}

                {/* ATS Report Summary */}
                {ats.recommendations?.length > 0 && (
                    <div className="card">
                        <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px' }}>
                            💡 ATS Recommendations
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {ats.recommendations.map((rec, i) => (
                                <p key={i} style={{
                                    fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5,
                                    padding: '8px 12px', background: 'rgba(255,255,255,0.02)',
                                    borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
                                }}>
                                    {rec}
                                </p>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}


// ── Editable Section Card ────────────────────────────────

function EditableSection({
    title, sectionKey, content,
    isEditing, editValue, onStartEdit, onEditValueChange, onSave, onCancel,
    renderContent,
}) {
    return (
        <div className="card" id={`section-${sectionKey}`}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 600 }}>{title}</h3>
                {!isEditing ? (
                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={onStartEdit}
                        style={{ fontSize: '12px' }}
                    >
                        ✏️ Edit
                    </button>
                ) : (
                    <div style={{ display: 'flex', gap: '6px' }}>
                        <button className="btn btn-accent btn-sm" onClick={onSave} style={{ fontSize: '12px' }}>
                            💾 Save
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={onCancel} style={{ fontSize: '12px' }}>
                            Cancel
                        </button>
                    </div>
                )}
            </div>

            {isEditing ? (
                <textarea
                    value={editValue}
                    onChange={(e) => onEditValueChange(e.target.value)}
                    style={{
                        width: '100%',
                        minHeight: '180px',
                        padding: '12px',
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                        lineHeight: 1.6,
                        background: 'var(--bg-card)',
                        color: 'var(--text-primary)',
                        border: '1px solid var(--primary-400)',
                        borderRadius: 'var(--radius-md)',
                        resize: 'vertical',
                        outline: 'none',
                    }}
                    id={`edit-${sectionKey}`}
                />
            ) : (
                renderContent()
            )}
        </div>
    );
}
