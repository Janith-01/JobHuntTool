"""
FastAPI Backend API for JobHuntTool.
Provides REST endpoints for the React management dashboard.
Includes Phase 2 AI optimization and Phase 3 document generation endpoints.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.database.connection import Database
from backend.database.models import (
    ApplicationStatus, SourcePlatform, JobListing, ScrapingResult
)
from backend.scrapers.orchestrator import ScraperOrchestrator, SCRAPER_REGISTRY
from backend.ai.engine import AIEngine
from backend.ai.contact_extractor import ContactExtractor, extract_contact_from_text
from backend.ai.followup_generator import FollowUpGenerator, generate_followup
from backend.ai.application_email_generator import ApplicationEmailGenerator, generate_application_email
from backend.generator.pdf_generator import DocumentGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("🚀 JobHuntTool API starting up...")
    connected = await Database.ping_async()
    if connected:
        await Database.create_indexes()
        logger.info("✅ Database connected and indexes created")
    else:
        logger.warning("⚠️ Database connection failed - running in limited mode")
    
    yield
    
    # Shutdown
    await Database.close_async()
    logger.info("🔒 JobHuntTool API shutdown complete")


# ── FastAPI App ──────────────────────────────────────────────

app = FastAPI(
    title="JobHuntTool API",
    description="Intelligent Job Scraping, Filtering & Application Management",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
# Including common development origins to avoid CORS blocks
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "*", # For development flexibility
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ────────────────────────────────

class ScrapeRequest(BaseModel):
    search_query: str = "Software Intern"
    location: str = "Sri Lanka"
    max_results_per_platform: int = 30
    platforms: list[str] | None = None
    headless: bool = True
    concurrent: bool = True


class StatusUpdateRequest(BaseModel):
    status: ApplicationStatus


class FilterConfigUpdate(BaseModel):
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    min_score: float | None = None


class JobNote(BaseModel):
    note: str


class ParseJDRequest(BaseModel):
    description: str
    title: str = ""
    company: str = ""
    quick: bool = False  # True = regex-only (no API call)


class TailorCVRequest(BaseModel):
    job_description: str
    job_title: str = ""
    company_name: str = ""
    include_cover_letter: bool = True


class ScoreCVRequest(BaseModel):
    cv_text: str
    keywords: list[str]


class BatchOptimizeRequest(BaseModel):
    job_ids: list[str] | None = None
    status_filter: str = "filtered"
    max_jobs: int = 10
    include_cover_letter: bool = True


class GeneratePDFRequest(BaseModel):
    job_id: str


class EditSectionRequest(BaseModel):
    """Edit a specific section of the tailored CV before approval."""
    section: str = Field(..., description="Section to edit: summary, skills, projects, experience, cover_letter")
    content: dict = Field(..., description="Updated content for the section")


class ApprovalRequest(BaseModel):
    """Approve or reject a tailored CV."""
    action: str = Field(..., description="'approve' or 'reject'")
    notes: str = Field(default="", description="Optional reviewer notes")


import traceback


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for errors to provide consistent JSON responses and debugging info."""
    logger.error(f"Global exception caught on {request.url}: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": exc.__class__.__name__,
            "message": str(exc),
            "url": str(request.url)
        },
    )

@app.get("/api/health")
async def health_check():
    """Check API and database health."""
    db_status = await Database.ping_async()
    return {
        "status": "healthy" if db_status else "degraded",
        "database": "connected" if db_status else "disconnected",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


# ── Scraping Endpoints ──────────────────────────────────────

@app.post("/api/scrape", response_model=dict)
async def trigger_scrape(request: ScrapeRequest):
    """Trigger a new scraping session across all or selected platforms."""
    orchestrator = ScraperOrchestrator()
    
    platforms = None
    if request.platforms:
        try:
            platforms = [SourcePlatform(p) for p in request.platforms]
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform: {e}. Available: {[p.value for p in SourcePlatform]}"
            )

    results = await orchestrator.run_all(
        search_query=request.search_query,
        location=request.location,
        max_results_per_platform=request.max_results_per_platform,
        platforms=platforms,
        headless=request.headless,
        concurrent=request.concurrent,
    )

    return {
        "success": True,
        "summary": orchestrator.get_aggregated_stats(),
        "results": [r.model_dump() for r in results],
    }


@app.get("/api/scrape/platforms")
async def get_available_platforms():
    """Get list of available scraping platforms."""
    return {
        "platforms": [
            {
                "id": platform.value,
                "name": platform.value.replace("_", " ").title(),
                "registered": True,
            }
            for platform in SCRAPER_REGISTRY.keys()
        ]
    }


@app.get("/api/scrape/history")
async def get_scraping_history(limit: int = Query(default=20, le=100)):
    """Get history of scraping sessions."""
    db = Database.get_async_db()
    cursor = db.orchestration_history.find().sort("timestamp", -1).limit(limit)
    history = []
    async for record in cursor:
        record["_id"] = str(record["_id"])
        history.append(record)
    return {"history": history}


# ── Jobs Endpoints ───────────────────────────────────────────

@app.get("/api/jobs")
async def get_jobs(
    status: Optional[ApplicationStatus] = None,
    platform: Optional[SourcePlatform] = None,
    search: Optional[str] = None,
    sort_by: str = Query(default="scraped_at", pattern="^(scraped_at|relevance_score|title|company)$"),
    sort_order: int = Query(default=-1, ge=-1, le=1),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get job listings with filtering, sorting, and pagination.
    """
    db = Database.get_async_db()

    # Build query filter
    query = {}
    if status:
        query["application_status"] = status.value
    if platform:
        query["source_platform"] = platform.value
    if search:
        query["$text"] = {"$search": search}

    # Sort mapping
    sort_field = sort_by
    if sort_by == "company":
        sort_field = "company.name"

    # Execute query with pagination
    skip = (page - 1) * limit
    total = await db.jobs.count_documents(query)
    cursor = db.jobs.find(query).sort(sort_field, sort_order).skip(skip).limit(limit)

    jobs = []
    async for job in cursor:
        job["_id"] = str(job["_id"])
        jobs.append(job)

    return {
        "jobs": jobs,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit,
        }
    }


@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: str):
    """Get detailed information about a specific job."""
    db = Database.get_async_db()
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job["_id"] = str(job["_id"])
    return {"job": job}


@app.patch("/api/jobs/{job_id}/status")
async def update_job_status(job_id: str, request: StatusUpdateRequest):
    """Update the application status of a job."""
    db = Database.get_async_db()
    result = await db.jobs.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "application_status": request.status.value,
                "updated_at": datetime.utcnow(),
            }
        }
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "status": request.status.value}


@app.post("/api/jobs/{job_id}/notes")
async def add_job_note(job_id: str, note: JobNote):
    """Add a note to a job listing."""
    db = Database.get_async_db()
    result = await db.jobs.update_one(
        {"job_id": job_id},
        {
            "$push": {"notes": {"text": note.note, "created_at": datetime.utcnow()}},
            "$set": {"updated_at": datetime.utcnow()},
        }
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job listing."""
    db = Database.get_async_db()
    result = await db.jobs.delete_one({"job_id": job_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True}


# ── Statistics Endpoints ─────────────────────────────────────

@app.get("/api/stats")
async def get_statistics():
    """Get dashboard statistics."""
    db = Database.get_async_db()

    total_jobs = await db.jobs.count_documents({})

    # Status breakdown
    pipeline = [
        {"$group": {"_id": "$application_status", "count": {"$sum": 1}}}
    ]
    status_counts = {}
    async for doc in db.jobs.aggregate(pipeline):
        status_counts[doc["_id"]] = doc["count"]

    # Platform breakdown
    pipeline = [
        {"$group": {"_id": "$source_platform", "count": {"$sum": 1}}}
    ]
    platform_counts = {}
    async for doc in db.jobs.aggregate(pipeline):
        platform_counts[doc["_id"]] = doc["count"]

    # Recent jobs (last 7 days)
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_count = await db.jobs.count_documents({"scraped_at": {"$gte": week_ago}})

    # Average relevance score
    pipeline = [
        {"$group": {"_id": None, "avg_score": {"$avg": "$relevance_score"}}}
    ]
    avg_score = 0.0
    async for doc in db.jobs.aggregate(pipeline):
        avg_score = doc.get("avg_score", 0.0)

    return {
        "total_jobs": total_jobs,
        "status_breakdown": status_counts,
        "platform_breakdown": platform_counts,
        "recent_jobs_7d": recent_count,
        "avg_relevance_score": round(avg_score, 1),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Filter Configuration ────────────────────────────────────

@app.get("/api/filters")
async def get_filter_config():
    """Get current filter keyword configuration."""
    from backend.scrapers.filter_engine import FilterEngine
    engine = FilterEngine()
    return engine.get_config()


@app.put("/api/filters")
async def update_filter_config(config: FilterConfigUpdate):
    """Update filter keyword configuration."""
    # In a production app, this would persist to the database
    # For now, we acknowledge the update
    return {
        "success": True,
        "message": "Filter configuration updated for current session",
        "config": config.model_dump(exclude_none=True),
    }


# ── AI Optimization Endpoints ────────────────────────────────

@app.post("/api/ai/parse-jd")
async def parse_job_description(request: ParseJDRequest):
    """
    Parse a job description and extract structured requirements.
    Use quick=true for regex-only (instant, no API call).
    """
    engine = AIEngine()
    try:
        if request.quick:
            result = engine.quick_parse_job_description(request.description, request.title)
        else:
            result = engine.parse_job_description(
                request.description, request.title, request.company
            )
        return {"success": True, "parsed": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@app.post("/api/ai/tailor/{job_id}")
async def tailor_cv_for_job(job_id: str, include_cover_letter: bool = True):
    """
    Run the full AI tailoring pipeline for a job from the database.
    Parses the JD, tailors the CV, scores it, and saves results.
    """
    engine = AIEngine()
    try:
        result = await engine.optimize_for_job(
            job_id=job_id,
            include_cover_letter=include_cover_letter,
        )
        return {
            "success": True,
            "ats_score": result["ats_report"]["overall_score"],
            "ats_grade": result["ats_report"]["grade"],
            "tailored_cv": result["tailored_cv"],
            "cover_letter": result.get("cover_letter"),
            "ats_report": result["ats_report"],
            "parsed_jd": result["parsed_jd"],
            "metadata": result["metadata"],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Tailoring failed for {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")


@app.post("/api/ai/tailor-direct")
async def tailor_cv_direct(request: TailorCVRequest):
    """
    Tailor a CV directly from a job description (no database required).
    Good for testing or one-off tailoring.
    """
    engine = AIEngine()
    try:
        result = engine.tailor_cv_direct(
            job_description=request.job_description,
            job_title=request.job_title,
            company_name=request.company_name,
            include_cover_letter=request.include_cover_letter,
        )
        return {
            "success": True,
            "ats_score": result["ats_report"]["overall_score"],
            "ats_grade": result["ats_report"]["grade"],
            "tailored_cv": result["tailored_cv"],
            "cover_letter": result.get("cover_letter"),
            "ats_report": result["ats_report"],
            "cv_as_text": result.get("cv_as_text", ""),
        }
    except Exception as e:
        logger.error(f"Direct tailoring failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")


@app.post("/api/ai/batch-optimize")
async def batch_optimize(request: BatchOptimizeRequest):
    """
    Optimize multiple jobs at once. If job_ids is empty,
    takes the top filtered jobs by relevance score.
    """
    engine = AIEngine()
    try:
        results = await engine.batch_optimize(
            job_ids=request.job_ids,
            status_filter=request.status_filter,
            max_jobs=request.max_jobs,
            include_cover_letter=request.include_cover_letter,
        )
        succeeded = sum(1 for r in results if r["success"])
        return {
            "success": True,
            "total": len(results),
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch optimization failed: {str(e)}")


@app.post("/api/ai/score")
async def score_cv(request: ScoreCVRequest):
    """
    Quick ATS keyword score: check how many of the given keywords
    are present in the CV text. Returns 0-100.
    """
    engine = AIEngine()
    score = engine.quick_score(request.cv_text, request.keywords)
    return {
        "score": round(score, 1),
        "keywords_total": len(request.keywords),
        "keywords_found": sum(
            1 for kw in request.keywords
            if kw.lower() in request.cv_text.lower()
        ),
    }


@app.get("/api/ai/tailored/{job_id}")
async def get_tailored_cv(job_id: str):
    """Retrieve a previously generated tailored CV."""
    engine = AIEngine()
    doc = await engine.get_tailored_cv(job_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No tailored CV found for this job")
    return {"success": True, "data": doc}


@app.get("/api/ai/stats")
async def get_ai_stats():
    """Get AI optimization statistics."""
    engine = AIEngine()
    stats = await engine.get_optimization_stats()
    return stats


# ── Phase 3: Document Generation & Approval ──────────────────

@app.post("/api/docs/generate/{job_id}")
async def generate_pdf(job_id: str):
    """
    Generate PDF documents (CV + Cover Letter) for a tailored job.
    The job must already have a tailored CV (run AI tailor first).
    """
    db = Database.get_async_db()

    # Fetch tailored CV data
    tailored_doc = await db.tailored_cvs.find_one({"job_id": job_id})
    if not tailored_doc:
        raise HTTPException(
            status_code=404,
            detail="No tailored CV found. Run AI tailoring first (POST /api/ai/tailor/{job_id})"
        )

    # Load personal info from master CV
    try:
        with open(settings.MASTER_CV_PATH, 'r', encoding='utf-8') as f:
            master_cv = json.load(f)
        personal = master_cv.get("personal", master_cv.get("personal_info", {}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load master CV: {e}")

    tailored_cv = tailored_doc.get("tailored_cv", {})
    cover_letter = tailored_doc.get("cover_letter")

    # Generate PDFs
    try:
        gen = DocumentGenerator()
        result = gen.generate_all(tailored_cv, cover_letter, personal)
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    # Save PDF paths back to the tailored_cvs document
    await db.tailored_cvs.update_one(
        {"job_id": job_id},
        {"$set": {
            "pdf_paths": result,
            "pdf_generated_at": datetime.utcnow(),
            "review_status": "pending_review",
        }}
    )

    # Update the job status
    await db.jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "application_status": "cv_generated",
            "updated_at": datetime.utcnow(),
        }}
    )

    return {
        "success": True,
        "job_id": job_id,
        "files": result,
        "review_status": "pending_review",
        "message": "PDFs generated. Review and approve before sending.",
    }


@app.get("/api/docs/download/{job_id}/{doc_type}")
async def download_pdf(job_id: str, doc_type: str):
    """
    Download a generated PDF.
    doc_type: 'cv' or 'cover_letter'
    """
    db = Database.get_async_db()
    tailored_doc = await db.tailored_cvs.find_one({"job_id": job_id})

    if not tailored_doc or not tailored_doc.get("pdf_paths"):
        raise HTTPException(status_code=404, detail="No PDFs generated for this job")

    paths = tailored_doc["pdf_paths"]

    if doc_type == "cv":
        file_path = paths.get("cv_path")
        filename = paths.get("cv_filename", "CV.pdf")
    elif doc_type == "cover_letter":
        file_path = paths.get("cover_letter_path")
        filename = paths.get("cover_letter_filename", "Cover_Letter.pdf")
    else:
        raise HTTPException(status_code=400, detail="doc_type must be 'cv' or 'cover_letter'")

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail=f"{doc_type} PDF not found on disk")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )


@app.get("/api/review/queue")
async def get_review_queue():
    """
    Get all tailored CVs pending human review.
    Returns documents with 'pending_review' status.
    """
    db = Database.get_async_db()

    # Fetch pending reviews and enrich with job info
    pipeline = [
        {"$match": {"review_status": {"$in": ["pending_review", None]}}},
        {"$sort": {"created_at": -1}},
        {"$limit": 50},
        {"$lookup": {
            "from": "jobs",
            "localField": "job_id",
            "foreignField": "job_id",
            "as": "job_info",
        }},
        {"$unwind": {"path": "$job_info", "preserveNullAndEmptyArrays": True}},
    ]

    items = []
    async for doc in db.tailored_cvs.aggregate(pipeline):
        job_info = doc.get("job_info", {})
        items.append({
            "job_id": doc["job_id"],
            "job_title": doc.get("job_title", job_info.get("title", "")),
            "company_name": doc.get("company_name", job_info.get("company", {}).get("name", "")),
            "ats_score": doc.get("ats_report", {}).get("overall_score", 0),
            "ats_grade": doc.get("ats_report", {}).get("grade", "?"),
            "review_status": doc.get("review_status", "pending_review"),
            "has_pdfs": bool(doc.get("pdf_paths")),
            "tailored_at": doc.get("created_at", ""),
            "pdf_generated_at": doc.get("pdf_generated_at", ""),
            "approved_at": doc.get("approved_at", ""),
            "reviewer_notes": doc.get("reviewer_notes", ""),
            "tailored_cv": doc.get("tailored_cv", {}),
            "cover_letter": doc.get("cover_letter"),
            "ats_report": doc.get("ats_report", {}),
            "cv_as_text": doc.get("cv_as_text", ""),
        })

    return {
        "success": True,
        "total": len(items),
        "items": items,
    }


@app.get("/api/review/{job_id}")
async def get_review_detail(job_id: str):
    """
    Get full detail for a single review item, including editable content.
    """
    db = Database.get_async_db()
    doc = await db.tailored_cvs.find_one({"job_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail="No tailored CV found")

    doc["_id"] = str(doc["_id"])
    return {"success": True, "data": doc}


@app.put("/api/review/{job_id}/edit")
async def edit_tailored_section(job_id: str, request: EditSectionRequest):
    """
    Edit a specific section of the tailored CV.
    Allows human in the loop to refine AI output before approval.
    """
    db = Database.get_async_db()
    doc = await db.tailored_cvs.find_one({"job_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail="No tailored CV found")

    section = request.section
    valid_sections = ["summary", "skills", "projects", "experience", "cover_letter"]
    if section not in valid_sections:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section '{section}'. Must be one of: {valid_sections}"
        )

    update = {"updated_at": datetime.utcnow(), "review_status": "pending_review"}

    if section == "summary":
        update["tailored_cv.professional_summary"] = request.content
    elif section == "skills":
        update["tailored_cv.skills"] = request.content
    elif section == "projects":
        update["tailored_cv.projects"] = request.content
    elif section == "experience":
        update["tailored_cv.experience"] = request.content
    elif section == "cover_letter":
        update["cover_letter"] = request.content

    # Rebuild plain text for ATS re-scoring
    if section != "cover_letter":
        tailored_cv = doc.get("tailored_cv", {})
        # Apply the edit to in-memory CV
        if section == "summary":
            tailored_cv["professional_summary"] = request.content
        elif section == "skills":
            tailored_cv["skills"] = request.content
        elif section == "projects":
            tailored_cv["projects"] = request.content
        elif section == "experience":
            tailored_cv["experience"] = request.content

        # Regenerate plain text
        from backend.ai.cv_tailor import CVTailor
        tailor = CVTailor()
        from backend.ai.cv_tailor import TailoredCV
        try:
            cv_obj = TailoredCV(**tailored_cv)
            new_text = tailor._cv_to_text(cv_obj)
            update["cv_as_text"] = new_text
        except Exception:
            pass  # Non-critical, skip re-scoring

    await db.tailored_cvs.update_one(
        {"job_id": job_id},
        {"$set": update}
    )

    return {
        "success": True,
        "message": f"Section '{section}' updated. Re-generate PDF when ready.",
    }


@app.post("/api/review/{job_id}/approve")
async def approve_or_reject(job_id: str, request: ApprovalRequest):
    """
    Approve or reject a tailored CV.
    - 'approve': Marks as ready to send. Status → 'ready_to_send'.
    - 'reject': Marks for re-tailoring. Status → 'needs_revision'.
    """
    db = Database.get_async_db()
    doc = await db.tailored_cvs.find_one({"job_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail="No tailored CV found")

    if request.action == "approve":
        # Update tailored CV status
        await db.tailored_cvs.update_one(
            {"job_id": job_id},
            {"$set": {
                "review_status": "approved",
                "approved_at": datetime.utcnow(),
                "reviewer_notes": request.notes,
            }}
        )
        # Update job status to ready_to_send
        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "application_status": "ready_to_send",
                "updated_at": datetime.utcnow(),
            }}
        )
        return {
            "success": True,
            "status": "approved",
            "message": "CV approved and marked as ready to send! 🎉",
        }

    elif request.action == "reject":
        await db.tailored_cvs.update_one(
            {"job_id": job_id},
            {"$set": {
                "review_status": "needs_revision",
                "reviewer_notes": request.notes,
                "updated_at": datetime.utcnow(),
            }}
        )
        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "application_status": "reviewed",
                "updated_at": datetime.utcnow(),
            }}
        )
        return {
            "success": True,
            "status": "rejected",
            "message": "CV sent back for revision. Edit and re-tailor.",
        }

    else:
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")


# ── Contact Extraction ────────────────────────────────────────

class ExtractContactRequest(BaseModel):
    """Extract recipient email & company from raw text."""
    text: str = Field(..., description="Scraped job posting text")
    job_title: str = Field(default="", description="Job title (if known)")
    company_hint: str = Field(default="", description="Company name hint (if known)")
    use_llm: bool = Field(default=False, description="Use LLM for disambiguation")


@app.post("/api/ai/extract-contact")
async def extract_contact(request: ExtractContactRequest):
    """
    Extract recipient email, company name, and generate subject line
    from raw scraped job posting text.

    Returns:
        {
            "recipient_email": "hr@softvil.com",
            "company_name": "Softvil Technologies",
            "subject_line": "Application for AI Engineer Intern — Janith Viranga",
            "contact_person": "John Doe",
            "confidence": "high",
            "all_emails_found": ["hr@softvil.com"],
            "extraction_method": "regex"
        }
    """
    try:
        result = extract_contact_from_text(
            text=request.text,
            job_title=request.job_title,
            company_hint=request.company_hint,
            use_llm=request.use_llm,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Contact extraction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/extract-contact/{job_id}")
async def extract_contact_from_job(job_id: str, use_llm: bool = False):
    """
    Extract contact info from a stored job's description.
    Updates the job document's contact field with the results.
    """
    db = Database.get_async_db()
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    description = job.get("job_description", "")
    title = job.get("title", "")
    company_hint = job.get("company", {}).get("name", "")

    if not description:
        raise HTTPException(
            status_code=400,
            detail="Job has no description text to extract from"
        )

    try:
        extractor = ContactExtractor()
        result = extractor.extract(
            scraped_text=description,
            job_title=title,
            company_name_hint=company_hint,
            use_llm=use_llm,
        )

        # Save extracted contact back to the job document
        contact_update = {}
        if result.recipient_email:
            contact_update["contact.email"] = result.recipient_email
        if result.contact_person:
            contact_update["contact.contact_person"] = result.contact_person
        if contact_update:
            contact_update["updated_at"] = datetime.utcnow()
            await db.jobs.update_one(
                {"job_id": job_id},
                {"$set": contact_update}
            )

        return {
            "success": True,
            **result.model_dump(),
            "saved_to_job": bool(contact_update),
        }
    except Exception as e:
        logger.error(f"Contact extraction for job {job_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Follow-Up Email Generation ────────────────────────────────

class FollowUpRequest(BaseModel):
    """Generate a follow-up email for a job application."""
    job_title: str = Field(..., description="Job title applied for")
    company_name: str = Field(..., description="Company name")
    days_since_applied: int = Field(default=7, description="Days since application was submitted")
    contact_person: str = Field(default="", description="Hiring contact name (if known)")


@app.post("/api/ai/followup")
async def generate_followup_email(request: FollowUpRequest):
    """
    Generate a professional follow-up email from raw parameters.
    Auto-selects the right template based on days_since_applied:
      7 days  → polite check-in
      14 days → restate value + offer materials
      21 days → graceful close / request feedback
    """
    try:
        result = generate_followup(
            job_title=request.job_title,
            company_name=request.company_name,
            days_since_applied=request.days_since_applied,
            contact_person=request.contact_person,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Follow-up generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/followup/{job_id}")
async def generate_followup_for_job(job_id: str, days_override: Optional[int] = None):
    """
    Generate a follow-up email for a stored job.
    Auto-calculates days since application from the job's applied_at field.
    """
    db = Database.get_async_db()
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        gen = FollowUpGenerator()
        result = gen.generate_from_job_data(job, days_since_applied=days_override)
        return {"success": True, **result.model_dump()}
    except Exception as e:
        logger.error(f"Follow-up generation for job {job_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Application Email Generation ──────────────────────────────

class ApplicationEmailRequest(BaseModel):
    """Generate a 3-paragraph application email (Hook → Proof → CTA)."""
    job_title: str = Field(..., description="Job title being applied for")
    company_name: str = Field(..., description="Company name")
    job_description: str = Field(..., description="Full job description text")
    contact_person: str = Field(default="", description="Hiring manager or recruiter name")
    use_llm: bool = Field(default=False, description="Use Gemini LLM for a fully original email")


@app.post("/api/ai/apply-email")
async def generate_apply_email(request: ApplicationEmailRequest):
    """
    Generate a concise 3-paragraph application email from raw parameters.

    Structure:
      1. Hook  — References a specific JD requirement
      2. Proof — Connects it to a concrete CV project
      3. CTA   — Interview availability + attached PDF

    Set use_llm=true for a fully original Gemini-generated email.
    Default (use_llm=false) uses instant keyword-matched templates.
    """
    try:
        result = generate_application_email(
            job_title=request.job_title,
            company_name=request.company_name,
            job_description=request.job_description,
            contact_person=request.contact_person,
            use_llm=request.use_llm,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Application email generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/apply-email/{job_id}")
async def generate_apply_email_for_job(job_id: str, use_llm: bool = False):
    """
    Generate an application email for a stored job.
    Reads the job title, company, and description from the database.
    """
    db = Database.get_async_db()
    job = await db.jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        gen = ApplicationEmailGenerator()
        result = gen.generate_from_job_data(job, use_llm=use_llm)
        return {"success": True, **result.model_dump()}
    except Exception as e:
        logger.error(f"Application email for job {job_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
