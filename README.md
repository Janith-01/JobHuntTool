# 🎯 JobHuntTool — AI-Powered Job Application Automation

An intelligent, end-to-end tool that scrapes job boards, filters listings using keyword-based scoring, generates tailored CVs with AI, and automates the application process — all controlled from a sleek React dashboard.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MANAGEMENT LAYER (React Dashboard)               │
│   Dashboard  │  Pipeline View  │  Scraper Control  │  CV Review     │
├─────────────────────────────────────────────────────────────────────┤
│                    EXECUTION LAYER (Email Delivery)                  │
│          Follow-Up Generator │ Contact Extractor │ Rate Limiting    │
├─────────────────────────────────────────────────────────────────────┤
│                    GENERATION LAYER (Document Factory)               │
│          ReportLab PDF Engine │ ATS-Optimized Layout │ Templates    │
├─────────────────────────────────────────────────────────────────────┤
│                    AI LOGIC LAYER (The Optimizer)                    │
│       LangChain + Gemini │ ATS Parser │ CV Tailoring │ Cover Letter │
├─────────────────────────────────────────────────────────────────────┤
│                    DATA LAYER (Intelligence Gatherer)                │
│    LinkedIn │ TopJobs.lk │ XpressJobs │ Filter Engine │ MongoDB     │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
JobHuntTool/
├── backend/
│   ├── __init__.py
│   ├── __main__.py            # Module entry point (python -m backend)
│   ├── api.py                 # FastAPI REST API
│   ├── cli.py                 # CLI interface
│   ├── config.py              # Centralized settings
│   ├── ai/                    # AI Optimization Engine
│   │   ├── llm_client.py     # Gemini LLM wrapper via LangChain
│   │   ├── jd_parser.py      # 2-stage JD parser (regex + LLM)
│   │   ├── cv_tailor.py      # CV tailoring agent (Hook→Proof→CTA cover letters)
│   │   ├── ats_scorer.py     # ATS keyword density checker
│   │   ├── engine.py         # Unified AI orchestrator
│   │   ├── contact_extractor.py  # Email/company extraction from JDs
│   │   ├── followup_generator.py # 7/14/21-day follow-up email drafts
│   │   └── test_ai.py        # Standalone test script
│   ├── generator/              # Document Generation
│   │   ├── pdf_generator.py   # ReportLab ATS-friendly PDF engine
│   │   └── test_pdf.py        # PDF test script
│   ├── database/
│   │   ├── connection.py      # MongoDB sync + async connections
│   │   └── models.py          # Pydantic schemas (JobListing, etc.)
│   └── scrapers/
│       ├── base_scraper.py    # Abstract scraper with Playwright
│       ├── filter_engine.py   # Keyword scoring engine
│       ├── linkedin_scraper.py
│       ├── topjobs_scraper.py
│       ├── xpressjobs_scraper.py
│       └── orchestrator.py    # Concurrent scraper manager
├── frontend/                  # React + Vite dashboard
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── index.css
│       └── components/
│           ├── Sidebar.jsx
│           ├── StatsGrid.jsx
│           ├── ScrapePanel.jsx
│           ├── JobsTable.jsx
│           ├── JobDetailModal.jsx
│           ├── PipelineView.jsx
│           ├── ReviewDashboard.jsx   # Human-in-the-loop approval
│           └── ToastContainer.jsx
├── data/
│   └── master_cv.json         # Your master CV (source of truth)
├── output/pdfs/               # Generated PDFs
├── .env.example               # Environment variables template
├── requirements.txt
└── README.md
```

---

## 🚀 How to Run (Step by Step)

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| **Python** | 3.12+ | `python --version` |
| **Node.js** | 18+ | `node --version` |
| **MongoDB** | 6+ | `mongod --version` or use Docker |

---

### 📦 FIRST-TIME SETUP (do this once)

**Step 1 — Open a terminal in the project folder:**
```powershell
cd E:\JOB\JobHuntTool
```

**Step 2 — Create Python virtual environment:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Step 3 — Install Python dependencies:**
```powershell
pip install -r requirements.txt
```

**Step 4 — Install Playwright browsers (for scraping):**
```powershell
playwright install chromium
```

**Step 5 — Install frontend dependencies:**
```powershell
cd frontend
npm install
cd ..
```

**Step 6 — Configure environment variables:**
```powershell
copy .env.example .env
```
Then open `.env` in your editor and fill in:
```env
# REQUIRED — get yours free at https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_actual_gemini_api_key

# REQUIRED — MongoDB connection (default works for local install)
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=jobhunttool

# OPTIONAL — only needed for email sending (Phase 4)
EMAIL_USER=your@email.com
EMAIL_PASSWORD=your_app_password
```

**Step 7 — Start MongoDB:**
```powershell
# Option A: If MongoDB is installed locally, it typically runs as a Windows service.
# Verify with:
mongosh --eval "db.runCommand({ping: 1})"

# Option B: Using Docker (if you don't have MongoDB installed):
docker run -d -p 27017:27017 --name jobhunt-mongo mongo:7
```

**Step 8 — Edit your Master CV:**

Open `data/master_cv.json` and replace the placeholder data with your own personal info, skills, projects, and experience. This is the source of truth the AI uses to tailor your CVs.

---

### 🏃 DAILY RUN (do this every time you want to use the tool)

You need **two terminals** open side by side:

**Terminal 1 — Start the Backend API:**
```powershell
cd E:\JOB\JobHuntTool
.\venv\Scripts\activate
python -m backend server --reload
```
> ✅ API starts at **http://localhost:8000**
> 📖 Swagger docs at **http://localhost:8000/docs**

**Terminal 2 — Start the Frontend Dashboard:**
```powershell
cd E:\JOB\JobHuntTool\frontend
npm run dev
```
> ✅ Dashboard starts at **http://localhost:5173**

**Step 3 — Open your browser:**

Go to **[http://localhost:5173](http://localhost:5173)** — that's it, you're in! 🎉

---

### 🕷️ Running Scrapers

**From the dashboard:**
Click **"🚀 Start Scraping"** in the Scraper panel and choose your platforms.

**From the CLI (Terminal 1):**
```powershell
# Scrape all platforms
python -m backend scrape --query "Software Intern" --location "Sri Lanka"

# Scrape a specific platform only
python -m backend scrape --platform linkedin --max-results 20

# Check database stats
python -m backend stats
```

---

### 🧠 Using the AI Pipeline

Once you have jobs scraped, the AI pipeline works from the dashboard:

1. **Select a job** from the Jobs table → click to open the detail modal
2. Click **"🧠 AI Optimize"** → the AI parses the JD, tailors your CV, generates a cover letter, and ATS-scores it
3. Go to **"📋 Review & Approve"** in the sidebar → review each section
4. Click **"📄 Generate PDFs"** → download ATS-friendly CV + Cover Letter PDFs
5. Click **"✅ Approve & Send"** when you're happy with the result

**Or use the API directly:**
```bash
# Tailor CV for a specific job
curl -X POST http://localhost:8000/api/ai/tailor/{job_id}

# Generate PDFs
curl -X POST http://localhost:8000/api/docs/generate/{job_id}

# Extract contact info from a job posting
curl http://localhost:8000/api/ai/extract-contact/{job_id}

# Generate 7-day follow-up email
curl http://localhost:8000/api/ai/followup/{job_id}
```

---

### 🧪 Quick Tests (verify everything works)

```powershell
# Test PDF generation (no API key needed)
python -m backend.generator.test_pdf

# Test contact extractor (no API key needed)
python -m backend.ai.test_contact_extractor

# Test AI engine (needs GEMINI_API_KEY in .env)
python -m backend.ai.test_ai
```

---

## 🕷️ Scrapers

| Platform | Status | Notes |
|----------|--------|-------|
| LinkedIn | ✅ Ready | Public search, no login required |
| TopJobs.lk | ✅ Ready | IT functional areas (SDQ, SFT, ICT) |
| XpressJobs | ✅ Ready | Keyword search |

## 🧠 Filter Engine

| Match Type | Points |
|------------|--------|
| Include keyword in **title** | +10 |
| Include keyword in **description** | +3 (max 15 per keyword) |
| Exclude keyword in **title** | **REJECT** (immediate) |
| Exclude keyword in **description** | -15 |

**Default Include:** intern, software, ai, react, python, node, typescript, etc.
**Default Exclude:** senior, lead, principal, director, 10+ years, etc.

Minimum score to pass: **5.0 points**

## 🧠 AI Optimization Engine

### Stage 1: JD Parsing
- **Regex pre-scan** — 60+ patterns for tech extraction (instant, free)
- **LLM deep analysis** — Gemini extracts nuanced requirements, priority keywords, culture notes
- Results are **merged** so regex catches anything the LLM misses

### Stage 2: CV Tailoring (LangChain)
- **Professional Summary** — Rewritten with Tier 1 keywords (Agentic AI, LangChain > Full-Stack)
- **Project Experience** — Bullets framed as systems-level achievements, not task descriptions
- **Skills Section** — Ordered by signal strength; generic skills (HTML, Git) suppressed
- **Cover Letter** — 3-paragraph Hook → Proof → CTA, max 150 words, human tone

### Stage 3: ATS Scoring

| Factor | Weight |
|--------|--------|
| Must-Have Keywords | **40%** |
| Overall Keyword Match | **25%** |
| Nice-to-Have | **15%** |
| Section Coverage | **10%** |
| Keyword Density | **10%** |

**Grading:** A+ (90+), A (80+), B+ (70+), B (60+), C (50+), D (40+), F (<40)

## 📊 API Endpoints

### Data Layer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/scrape` | Trigger scraping |
| GET | `/api/jobs` | List jobs (filtered, paginated) |
| GET | `/api/jobs/:id` | Job detail |
| PATCH | `/api/jobs/:id/status` | Update application status |
| DELETE | `/api/jobs/:id` | Delete job |
| GET | `/api/stats` | Dashboard statistics |

### AI Layer
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/parse-jd` | Parse a JD (regex or LLM) |
| POST | `/api/ai/tailor/:id` | Full tailoring pipeline for a job |
| POST | `/api/ai/tailor-direct` | Tailor from raw JD text |
| POST | `/api/ai/batch-optimize` | Batch optimize multiple jobs |
| POST | `/api/ai/score` | Quick ATS keyword score |
| GET | `/api/ai/tailored/:id` | Retrieve saved tailored CV |
| POST | `/api/ai/extract-contact` | Extract email/company from raw text |
| GET | `/api/ai/extract-contact/:id` | Extract contact from stored job |
| POST | `/api/ai/followup` | Generate follow-up email draft |
| GET | `/api/ai/followup/:id` | Follow-up from stored job data |

### Document Generation & Review
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/docs/generate/:id` | Generate CV + Cover Letter PDFs |
| GET | `/api/docs/download/:id/:type` | Download PDF (cv / cover_letter) |
| GET | `/api/review/queue` | CVs pending review |
| PUT | `/api/review/:id/edit` | Edit CV section |
| POST | `/api/review/:id/approve` | Approve or reject |

## 🗺️ Roadmap

- [x] **Phase 1:** Data Acquisition & Filtering
- [x] **Phase 2:** AI Logic Layer (LangChain + Gemini)
- [x] **Phase 3:** Document Generation & Review (PDF + Approval Workflow)
- [x] **Phase 3.5:** Contact Extraction + Follow-Up Emails
- [ ] **Phase 4:** Email Delivery (SMTP)
- [ ] **Phase 5:** Full Dashboard Integration + Analytics

## 🛠️ Built With

- **Backend:** Python, FastAPI, Playwright, BeautifulSoup, Motor/PyMongo, ReportLab
- **Frontend:** React 19, Vite 7, Vanilla CSS
- **Database:** MongoDB
- **AI:** LangChain, Google Gemini (keyword-tiered prompts for interview conversion)
- **PDF:** ReportLab (ATS-optimized single-column)

---

Built with 🧠 by **Janith Viranga** | [VertexStack](https://vertexstack.com)
