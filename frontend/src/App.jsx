import { useState, useEffect, useCallback } from 'react';
import './index.css';
import { fetchJobs, fetchStats, triggerScrape, updateJobStatus, deleteJob, healthCheck } from './api';
import Sidebar from './components/Sidebar';
import StatsGrid from './components/StatsGrid';
import ScrapePanel from './components/ScrapePanel';
import JobsTable from './components/JobsTable';
import JobDetailModal from './components/JobDetailModal';
import ToastContainer from './components/ToastContainer';
import PipelineView from './components/PipelineView';
import ReviewDashboard from './components/ReviewDashboard';

function App() {
  // ── State ─────────────────────────────────────────
  const [activeView, setActiveView] = useState('dashboard');
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState(null);
  const [pagination, setPagination] = useState({ total: 0, page: 1, limit: 20, total_pages: 0 });
  const [filters, setFilters] = useState({ status: '', platform: '', search: '' });
  const [selectedJob, setSelectedJob] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isScraping, setIsScraping] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [apiConnected, setApiConnected] = useState(null);

  // ── Toast Helper ──────────────────────────────────
  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  // ── Health Check ──────────────────────────────────
  useEffect(() => {
    healthCheck()
      .then(() => {
        setApiConnected(true);
        addToast('Connected to JobHuntTool API', 'success');
      })
      .catch(() => {
        setApiConnected(false);
        addToast('API not reachable — start the backend server', 'error');
      });
  }, [addToast]);

  // ── Load Data ─────────────────────────────────────
  const loadJobs = useCallback(async (page = 1) => {
    setIsLoading(true);
    try {
      const data = await fetchJobs({
        status: filters.status || undefined,
        platform: filters.platform || undefined,
        search: filters.search || undefined,
        page,
      });
      setJobs(data.jobs);
      setPagination(data.pagination);
    } catch (err) {
      // API not available — use demo data
      setJobs(DEMO_JOBS);
      setPagination({ total: DEMO_JOBS.length, page: 1, limit: 20, total_pages: 1 });
    }
    setIsLoading(false);
  }, [filters]);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchStats();
      setStats(data);
    } catch {
      setStats(DEMO_STATS);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    loadStats();
  }, [loadJobs, loadStats]);

  // ── Handlers ──────────────────────────────────────
  const handleScrape = async (config) => {
    setIsScraping(true);
    addToast('🕷️ Scraping started — this may take a few minutes...', 'info');
    try {
      const result = await triggerScrape(config);
      const newJobs = result.summary?.total_new || 0;
      addToast(`✅ Scraping complete! Found ${newJobs} new jobs.`, 'success');
      loadJobs();
      loadStats();
    } catch (err) {
      addToast(`❌ Scraping failed: ${err.message}`, 'error');
    }
    setIsScraping(false);
  };

  const handleStatusUpdate = async (jobId, status) => {
    try {
      await updateJobStatus(jobId, status);
      addToast(`Status updated to "${status}"`, 'success');
      loadJobs(pagination.page);
      loadStats();
    } catch (err) {
      addToast(`Failed to update status: ${err.message}`, 'error');
    }
  };

  const handleDeleteJob = async (jobId) => {
    try {
      await deleteJob(jobId);
      addToast('Job deleted', 'info');
      loadJobs(pagination.page);
      loadStats();
    } catch (err) {
      addToast(`Failed to delete: ${err.message}`, 'error');
    }
  };

  // ── Render Content ────────────────────────────────
  const renderContent = () => {
    switch (activeView) {
      case 'dashboard':
        return (
          <>
            <div className="header-bar">
              <div>
                <h2>Dashboard</h2>
                <p className="subtitle">
                  {apiConnected === true && '🟢 Connected'}
                  {apiConnected === false && '🔴 API Offline — showing demo data'}
                  {apiConnected === null && '🟡 Connecting...'}
                </p>
              </div>
              <div className="header-actions">
                <button className="btn btn-secondary" onClick={() => { loadJobs(); loadStats(); }}>
                  ↻ Refresh
                </button>
              </div>
            </div>
            <StatsGrid stats={stats} />
            <ScrapePanel onScrape={handleScrape} isScraping={isScraping} />
            <JobsTable
              jobs={jobs}
              pagination={pagination}
              filters={filters}
              isLoading={isLoading}
              onFilterChange={setFilters}
              onPageChange={(p) => loadJobs(p)}
              onSelectJob={setSelectedJob}
              onStatusUpdate={handleStatusUpdate}
              onDeleteJob={handleDeleteJob}
            />
          </>
        );

      case 'pipeline':
        return (
          <>
            <div className="header-bar">
              <div>
                <h2>Application Pipeline</h2>
                <p className="subtitle">Track your applications through each stage</p>
              </div>
            </div>
            <PipelineView
              jobs={jobs}
              onSelectJob={setSelectedJob}
              onStatusUpdate={handleStatusUpdate}
            />
          </>
        );

      case 'scraper':
        return (
          <>
            <div className="header-bar">
              <div>
                <h2>Scraper Control</h2>
                <p className="subtitle">Configure and run job scrapers</p>
              </div>
            </div>
            <ScrapePanel onScrape={handleScrape} isScraping={isScraping} expanded />
          </>
        );

      case 'review':
        return (
          <ReviewDashboard onToast={addToast} />
        );

      default:
        return null;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        stats={stats}
      />
      <main className="main-content">
        {renderContent()}
      </main>

      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          onStatusUpdate={handleStatusUpdate}
          onToast={addToast}
        />
      )}

      <ToastContainer toasts={toasts} />
    </div>
  );
}

// ── Demo Data (shown when API is not available) ─────
const DEMO_JOBS = [
  {
    job_id: 'demo_001',
    title: 'Software Engineering Intern',
    company: { name: 'Softvil Technologies', location: 'Colombo, Sri Lanka' },
    job_description: 'We are looking for a passionate Software Engineering Intern to join our development team. You will work on real-world projects using React, Node.js, and Python.',
    application_status: 'filtered',
    source_platform: 'linkedin',
    source_url: 'https://linkedin.com/jobs/demo1',
    relevance_score: 85.5,
    keyword_matches: ['intern', 'software', 'react', 'node', 'python'],
    scraped_at: new Date().toISOString(),
    tech_stack_required: { languages: ['Python', 'JavaScript'], frameworks: ['React', 'Node.js'], databases: ['MongoDB'], tools: ['Docker', 'Git'] },
  },
  {
    job_id: 'demo_002',
    title: 'AI / ML Intern',
    company: { name: 'Synexis Solutions', location: 'Kandy, Sri Lanka' },
    job_description: 'Join our AI team to work on cutting-edge machine learning projects. Experience with TensorFlow, PyTorch, and Python required.',
    application_status: 'reviewed',
    source_platform: 'topjobs_lk',
    source_url: 'https://topjobs.lk/demo2',
    relevance_score: 92.0,
    keyword_matches: ['ai', 'machine learning', 'intern', 'python'],
    scraped_at: new Date().toISOString(),
    tech_stack_required: { languages: ['Python'], frameworks: ['TensorFlow', 'PyTorch'], databases: ['PostgreSQL'], tools: ['Docker'] },
  },
  {
    job_id: 'demo_003',
    title: 'Full Stack Developer Trainee',
    company: { name: 'IFS', location: 'Colombo, Sri Lanka' },
    job_description: 'IFS is looking for Full Stack Developer Trainees. You will be working with React, TypeScript, and cloud technologies.',
    application_status: 'cv_generated',
    source_platform: 'linkedin',
    source_url: 'https://linkedin.com/jobs/demo3',
    relevance_score: 78.0,
    keyword_matches: ['full stack', 'developer', 'react', 'typescript', 'trainee'],
    scraped_at: new Date().toISOString(),
    tech_stack_required: { languages: ['TypeScript', 'JavaScript'], frameworks: ['React', 'Express'], databases: ['PostgreSQL'], tools: ['AWS'] },
  },
  {
    job_id: 'demo_004',
    title: 'Junior Python Developer',
    company: { name: 'Creative Software', location: 'Colombo, Sri Lanka' },
    job_description: 'Seeking a Junior Python Developer with knowledge of Django or FastAPI. ML experience is a plus.',
    application_status: 'sent',
    source_platform: 'xpress_jobs',
    source_url: 'https://xpress.jobs/demo4',
    relevance_score: 70.0,
    keyword_matches: ['junior', 'python', 'developer'],
    scraped_at: new Date().toISOString(),
    tech_stack_required: { languages: ['Python'], frameworks: ['Django', 'FastAPI'], databases: ['PostgreSQL'], tools: ['Git'] },
  },
  {
    job_id: 'demo_005',
    title: 'React Developer Intern',
    company: { name: 'Calcey Technologies', location: 'Colombo, Sri Lanka' },
    job_description: 'Looking for a motivated React Developer Intern to help build next-generation web applications.',
    application_status: 'interview',
    source_platform: 'linkedin',
    source_url: 'https://linkedin.com/jobs/demo5',
    relevance_score: 88.0,
    keyword_matches: ['react', 'developer', 'intern'],
    scraped_at: new Date().toISOString(),
    tech_stack_required: { languages: ['JavaScript', 'TypeScript'], frameworks: ['React', 'Next.js'], databases: ['MongoDB'], tools: ['Figma'] },
  },
];

const DEMO_STATS = {
  total_jobs: 47,
  status_breakdown: {
    discovered: 12,
    filtered: 18,
    reviewed: 8,
    cv_generated: 4,
    sent: 3,
    interview: 1,
    rejected: 1,
  },
  platform_breakdown: {
    linkedin: 22,
    topjobs_lk: 15,
    xpress_jobs: 10,
  },
  recent_jobs_7d: 23,
  avg_relevance_score: 72.4,
};

export default App;
