const API_BASE = 'http://localhost:8000/api';

export async function fetchJobs({ status, platform, search, page = 1, limit = 20, sortBy = 'scraped_at', sortOrder = -1 } = {}) {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (platform) params.append('platform', platform);
    if (search) params.append('search', search);
    params.append('page', page);
    params.append('limit', limit);
    params.append('sort_by', sortBy);
    params.append('sort_order', sortOrder);

    const res = await fetch(`${API_BASE}/jobs?${params}`);
    if (!res.ok) throw new Error('Failed to fetch jobs');
    return res.json();
}

export async function fetchJobDetail(jobId) {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`);
    if (!res.ok) throw new Error('Job not found');
    return res.json();
}

export async function updateJobStatus(jobId, status) {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error('Failed to update status');
    return res.json();
}

export async function deleteJob(jobId) {
    const res = await fetch(`${API_BASE}/jobs/${jobId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete job');
    return res.json();
}

export async function addJobNote(jobId, note) {
    const res = await fetch(`${API_BASE}/jobs/${jobId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note }),
    });
    if (!res.ok) throw new Error('Failed to add note');
    return res.json();
}

export async function triggerScrape({ searchQuery, location, maxResults, platforms, headless = true, concurrent = true } = {}) {
    const res = await fetch(`${API_BASE}/scrape`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            search_query: searchQuery || 'Software Intern',
            location: location || 'Sri Lanka',
            max_results_per_platform: maxResults || 30,
            platforms: platforms || null,
            headless,
            concurrent,
        }),
    });
    if (!res.ok) throw new Error('Scraping failed');
    return res.json();
}

export async function fetchStats() {
    const res = await fetch(`${API_BASE}/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
}

export async function fetchPlatforms() {
    const res = await fetch(`${API_BASE}/scrape/platforms`);
    if (!res.ok) throw new Error('Failed to fetch platforms');
    return res.json();
}

export async function fetchScrapeHistory(limit = 20) {
    const res = await fetch(`${API_BASE}/scrape/history?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch history');
    return res.json();
}

export async function healthCheck() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
}

// ── AI Optimization Endpoints ──────────────────────────────

export async function parseJobDescription(description, title = '', company = '', quick = false) {
    const res = await fetch(`${API_BASE}/ai/parse-jd`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description, title, company, quick }),
    });
    if (!res.ok) throw new Error('Parsing failed');
    return res.json();
}

export async function tailorCVForJob(jobId, includeCoverLetter = true) {
    const res = await fetch(`${API_BASE}/ai/tailor/${jobId}?include_cover_letter=${includeCoverLetter}`, {
        method: 'POST',
    });
    if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || 'Tailoring failed');
    }
    return res.json();
}

export async function tailorCVDirect(jobDescription, jobTitle = '', companyName = '', includeCoverLetter = true) {
    const res = await fetch(`${API_BASE}/ai/tailor-direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            job_description: jobDescription,
            job_title: jobTitle,
            company_name: companyName,
            include_cover_letter: includeCoverLetter,
        }),
    });
    if (!res.ok) throw new Error('Direct tailoring failed');
    return res.json();
}

export async function batchOptimize({ jobIds, statusFilter, maxJobs, includeCoverLetter } = {}) {
    const res = await fetch(`${API_BASE}/ai/batch-optimize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            job_ids: jobIds || null,
            status_filter: statusFilter || 'filtered',
            max_jobs: maxJobs || 10,
            include_cover_letter: includeCoverLetter !== false,
        }),
    });
    if (!res.ok) throw new Error('Batch optimization failed');
    return res.json();
}

export async function scoreCVKeywords(cvText, keywords) {
    const res = await fetch(`${API_BASE}/ai/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cv_text: cvText, keywords }),
    });
    if (!res.ok) throw new Error('Scoring failed');
    return res.json();
}

export async function getTailoredCV(jobId) {
    const res = await fetch(`${API_BASE}/ai/tailored/${jobId}`);
    if (!res.ok) throw new Error('No tailored CV found');
    return res.json();
}

export async function getAIStats() {
    const res = await fetch(`${API_BASE}/ai/stats`);
    if (!res.ok) throw new Error('Failed to fetch AI stats');
    return res.json();
}

// ── Phase 3: Document Generation & Review ──────────────────

export async function generatePDF(jobId) {
    const res = await fetch(`${API_BASE}/docs/generate/${jobId}`, { method: 'POST' });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'PDF generation failed');
    }
    return res.json();
}

export function getDownloadURL(jobId, docType) {
    return `${API_BASE}/docs/download/${jobId}/${docType}`;
}

export async function fetchReviewQueue() {
    const res = await fetch(`${API_BASE}/review/queue`);
    if (!res.ok) throw new Error('Failed to fetch review queue');
    return res.json();
}

export async function fetchReviewDetail(jobId) {
    const res = await fetch(`${API_BASE}/review/${jobId}`);
    if (!res.ok) throw new Error('Review item not found');
    return res.json();
}

export async function editSection(jobId, section, content) {
    const res = await fetch(`${API_BASE}/review/${jobId}/edit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section, content }),
    });
    if (!res.ok) throw new Error('Edit failed');
    return res.json();
}

export async function approveCV(jobId, notes = '') {
    const res = await fetch(`${API_BASE}/review/${jobId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve', notes }),
    });
    if (!res.ok) throw new Error('Approval failed');
    return res.json();
}

export async function rejectCV(jobId, notes = '') {
    const res = await fetch(`${API_BASE}/review/${jobId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reject', notes }),
    });
    if (!res.ok) throw new Error('Rejection failed');
    return res.json();
}


// ── Contact Extraction ──────────────────────────────────────

export async function extractContactFromText(text, jobTitle = '', companyHint = '', useLlm = false) {
    const res = await fetch(`${API_BASE}/ai/extract-contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, job_title: jobTitle, company_hint: companyHint, use_llm: useLlm }),
    });
    if (!res.ok) throw new Error('Contact extraction failed');
    return res.json();
}

export async function extractContactFromJob(jobId, useLlm = false) {
    const res = await fetch(`${API_BASE}/ai/extract-contact/${jobId}?use_llm=${useLlm}`);
    if (!res.ok) throw new Error('Contact extraction failed');
    return res.json();
}


// ── Follow-Up Email Generation ──────────────────────────────

export async function generateFollowUp(jobTitle, companyName, daysSinceApplied = 7, contactPerson = '') {
    const res = await fetch(`${API_BASE}/ai/followup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            job_title: jobTitle,
            company_name: companyName,
            days_since_applied: daysSinceApplied,
            contact_person: contactPerson,
        }),
    });
    if (!res.ok) throw new Error('Follow-up generation failed');
    return res.json();
}

export async function generateFollowUpForJob(jobId, daysOverride = null) {
    const params = daysOverride !== null ? `?days_override=${daysOverride}` : '';
    const res = await fetch(`${API_BASE}/ai/followup/${jobId}${params}`);
    if (!res.ok) throw new Error('Follow-up generation failed');
    return res.json();
}


// ── Application Email Generation ────────────────────────────

export async function generateApplicationEmail(jobTitle, companyName, jobDescription, contactPerson = '', useLlm = false) {
    const res = await fetch(`${API_BASE}/ai/apply-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            job_title: jobTitle,
            company_name: companyName,
            job_description: jobDescription,
            contact_person: contactPerson,
            use_llm: useLlm,
        }),
    });
    if (!res.ok) throw new Error('Application email generation failed');
    return res.json();
}

export async function generateApplicationEmailForJob(jobId, useLlm = false) {
    const res = await fetch(`${API_BASE}/ai/apply-email/${jobId}?use_llm=${useLlm}`);
    if (!res.ok) throw new Error('Application email generation failed');
    return res.json();
}

/**
 * Open the user's default email client with a pre-filled application email.
 * Uses mailto: protocol — works on all platforms without SMTP config.
 */
export function openEmailClient({ to, subject, body }) {
    const mailtoUrl = `mailto:${encodeURIComponent(to || '')}?subject=${encodeURIComponent(subject || '')}&body=${encodeURIComponent(body || '')}`;
    window.open(mailtoUrl, '_blank');
}
