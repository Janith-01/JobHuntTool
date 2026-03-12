"""
AI Engine — Unified interface for the AI Optimization Layer.

Orchestrates:
  - JD Parsing (extract requirements from job descriptions)
  - CV Tailoring (rewrite CV sections for each role)
  - ATS Scoring (keyword density & match analysis)
  - Cover Letter Generation

This is the single entry point used by the API and CLI.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.config import settings
from backend.database.connection import Database
from backend.database.models import ApplicationStatus
from backend.ai.jd_parser import JDParser, ParsedJobDescription
from backend.ai.cv_tailor import CVTailor, TailoredCV, CoverLetterDraft
from backend.ai.ats_scorer import ATSScorer, ATSReport

logger = logging.getLogger(__name__)


class AIEngine:
    """
    Unified AI optimization engine.
    
    Usage:
        engine = AIEngine()
        
        # Full pipeline
        result = engine.optimize_for_job(job_id="abc123")
        
        # Parse a JD only
        parsed = engine.parse_job_description("We're looking for...")
        
        # Score an existing CV
        score = engine.score_cv(cv_text, parsed_jd)
    """

    def __init__(self, master_cv_path: Optional[Path] = None):
        self.jd_parser = JDParser()
        self.cv_tailor = CVTailor(master_cv_path)
        self.ats_scorer = ATSScorer()

    # ─────────────────────────────────────────────────────────
    #  High-Level Pipeline
    # ─────────────────────────────────────────────────────────

    async def optimize_for_job(
        self,
        job_id: str,
        include_cover_letter: bool = True,
        save_to_db: bool = True,
    ) -> dict:
        """
        Full optimization pipeline for a specific job from the database:
        
        1. Fetch job from MongoDB
        2. Parse the job description
        3. Tailor the CV
        4. Score the result
        5. Generate cover letter
        6. Save results back to the job record
        
        Returns a complete optimization result dict.
        """
        logger.info(f"🧠 Starting AI optimization for job_id={job_id}")

        # ── Fetch job from database ──────────────────────────
        db = Database.get_async_db()
        job_doc = await db.jobs.find_one({"job_id": job_id})
        if not job_doc:
            raise ValueError(f"Job not found: {job_id}")

        job_title = job_doc.get("title", "")
        company_name = job_doc.get("company", {}).get("name", "")
        description = job_doc.get("job_description", "")

        if not description:
            raise ValueError(f"Job {job_id} has no description to analyze")

        # ── Run the full tailoring pipeline ──────────────────
        result = self.cv_tailor.tailor_full(
            job_description=description,
            job_title=job_title,
            company_name=company_name,
            include_cover_letter=include_cover_letter,
        )

        # ── Save results back to the job record ──────────────
        if save_to_db:
            update_data = {
                "application_status": ApplicationStatus.CV_GENERATED.value,
                "updated_at": datetime.utcnow(),
                "ai_summary": result["parsed_jd"].get("role_summary", ""),
                "relevance_score": result["ats_report"]["overall_score"],
                "keyword_matches": result["parsed_jd"].get("priority_keywords", []),
                "ai_optimization": {
                    "ats_score": result["ats_report"]["overall_score"],
                    "ats_grade": result["ats_report"]["grade"],
                    "must_haves_matched": result["ats_report"]["keywords"]["must_haves_found"],
                    "must_haves_total": result["ats_report"]["keywords"]["must_haves_total"],
                    "recommendations": result["ats_report"]["recommendations"],
                    "tailored_at": datetime.utcnow(),
                    "tailored_summary": result["tailored_cv"]["professional_summary"]["summary"],
                    "tailored_filename": result["tailored_cv"]["ats_optimized_filename"],
                },
            }

            # Store tech stack extracted by AI
            parsed_tech = result["parsed_jd"].get("tech_stack", {})
            if parsed_tech:
                update_data["tech_stack_required"] = parsed_tech

            await db.jobs.update_one(
                {"job_id": job_id},
                {"$set": update_data}
            )

            # Also save the full tailored CV to a separate collection
            await db.tailored_cvs.update_one(
                {"job_id": job_id},
                {"$set": {
                    "job_id": job_id,
                    "job_title": job_title,
                    "company_name": company_name,
                    "tailored_cv": result["tailored_cv"],
                    "cover_letter": result.get("cover_letter"),
                    "ats_report": result["ats_report"],
                    "cv_as_text": result.get("cv_as_text", ""),
                    "created_at": datetime.utcnow(),
                }},
                upsert=True,
            )

            logger.info(f"💾 Saved optimization results for job_id={job_id}")

        return result

    async def batch_optimize(
        self,
        job_ids: list[str] | None = None,
        status_filter: str = "filtered",
        max_jobs: int = 10,
        include_cover_letter: bool = True,
    ) -> list[dict]:
        """
        Optimize multiple jobs in sequence.
        
        If job_ids is None, fetches the top-scored filtered jobs.
        """
        db = Database.get_async_db()

        if job_ids:
            cursor = db.jobs.find({"job_id": {"$in": job_ids}})
        else:
            cursor = (
                db.jobs.find({"application_status": status_filter})
                .sort("relevance_score", -1)
                .limit(max_jobs)
            )

        results = []
        async for job_doc in cursor:
            job_id = job_doc["job_id"]
            try:
                result = await self.optimize_for_job(
                    job_id=job_id,
                    include_cover_letter=include_cover_letter,
                )
                results.append({
                    "job_id": job_id,
                    "title": job_doc.get("title", ""),
                    "company": job_doc.get("company", {}).get("name", ""),
                    "ats_score": result["ats_report"]["overall_score"],
                    "ats_grade": result["ats_report"]["grade"],
                    "success": True,
                })
            except Exception as e:
                logger.error(f"❌ Failed to optimize job {job_id}: {e}")
                results.append({
                    "job_id": job_id,
                    "title": job_doc.get("title", ""),
                    "company": job_doc.get("company", {}).get("name", ""),
                    "success": False,
                    "error": str(e),
                })

        logger.info(
            f"📊 Batch optimization complete: "
            f"{sum(1 for r in results if r['success'])}/{len(results)} succeeded"
        )
        return results

    # ─────────────────────────────────────────────────────────
    #  Individual Operations
    # ─────────────────────────────────────────────────────────

    def parse_job_description(
        self,
        description: str,
        title: str = "",
        company: str = "",
    ) -> dict:
        """Parse a job description and return structured requirements."""
        parsed = self.jd_parser.parse(description, title, company)
        return parsed.model_dump()

    def quick_parse_job_description(
        self,
        description: str,
        title: str = "",
    ) -> dict:
        """Quick regex-only parse (no API call)."""
        return self.jd_parser.quick_parse(description, title)

    def score_cv(
        self,
        cv_text: str,
        parsed_jd: ParsedJobDescription | dict,
    ) -> dict:
        """Score a CV against a parsed job description."""
        if isinstance(parsed_jd, dict):
            parsed_jd = ParsedJobDescription(**parsed_jd)
        report = self.ats_scorer.score(cv_text, parsed_jd)
        return report.to_dict()

    def quick_score(self, cv_text: str, keywords: list[str]) -> float:
        """Quick keyword match score (0-100) without full ATS analysis."""
        return self.ats_scorer.quick_score(cv_text, keywords)

    def tailor_cv_direct(
        self,
        job_description: str,
        job_title: str = "",
        company_name: str = "",
        include_cover_letter: bool = True,
    ) -> dict:
        """
        Tailor a CV without database interaction.
        Useful for the API's direct tailoring endpoint.
        """
        return self.cv_tailor.tailor_full(
            job_description=job_description,
            job_title=job_title,
            company_name=company_name,
            include_cover_letter=include_cover_letter,
        )

    # ─────────────────────────────────────────────────────────
    #  Retrieval Methods
    # ─────────────────────────────────────────────────────────

    async def get_tailored_cv(self, job_id: str) -> dict | None:
        """Retrieve a previously generated tailored CV."""
        db = Database.get_async_db()
        doc = await db.tailored_cvs.find_one({"job_id": job_id})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_optimization_stats(self) -> dict:
        """Get aggregate stats on AI optimizations."""
        db = Database.get_async_db()

        total_tailored = await db.tailored_cvs.count_documents({})

        # Average ATS score of tailored CVs
        pipeline = [
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$ats_report.overall_score"},
                "max_score": {"$max": "$ats_report.overall_score"},
                "min_score": {"$min": "$ats_report.overall_score"},
            }}
        ]
        scores = {"avg": 0, "max": 0, "min": 0}
        async for doc in db.tailored_cvs.aggregate(pipeline):
            scores = {
                "avg": round(doc.get("avg_score", 0), 1),
                "max": round(doc.get("max_score", 0), 1),
                "min": round(doc.get("min_score", 0), 1),
            }

        # Grade distribution
        grade_pipeline = [
            {"$group": {"_id": "$ats_report.grade", "count": {"$sum": 1}}}
        ]
        grade_dist = {}
        async for doc in db.tailored_cvs.aggregate(grade_pipeline):
            grade_dist[doc["_id"]] = doc["count"]

        return {
            "total_tailored_cvs": total_tailored,
            "ats_scores": scores,
            "grade_distribution": grade_dist,
        }
