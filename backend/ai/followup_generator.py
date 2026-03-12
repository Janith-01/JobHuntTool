"""
Follow-Up Email Generator — Drafts concise, professional follow-up emails
for job applications after a configurable waiting period.

Generates follow-ups at different stages:
  - 7-day follow-up (polite check-in)
  - 14-day follow-up (restate value + offer additional materials)
  - 21-day follow-up (graceful close / request feedback)

Usage:
    from backend.ai.followup_generator import FollowUpGenerator

    gen = FollowUpGenerator()
    email = gen.generate(
        job_title="AI Engineer Intern",
        company_name="Softvil Technologies",
        days_since_applied=7,
        contact_person="Dilshan Perera",
    )
    print(email.subject_line)
    print(email.body)
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Output Schema
# ═══════════════════════════════════════════════════════════════

class FollowUpEmail(BaseModel):
    """A generated follow-up email."""
    subject_line: str = Field(..., description="Email subject line")
    greeting: str = Field(default="Hi there,", description="Greeting line")
    body: str = Field(..., description="The email body (2-3 sentences max)")
    sign_off: str = Field(default="Best,\nJanith Viranga", description="Sign-off")
    full_text: str = Field(default="", description="Complete assembled email text")
    follow_up_stage: str = Field(default="7-day", description="Stage: 7-day, 14-day, 21-day")
    tone: str = Field(default="professional", description="Tone of the email")


# ═══════════════════════════════════════════════════════════════
#  Follow-Up Templates
# ═══════════════════════════════════════════════════════════════

# Templates keyed by stage, each with variants for randomization
TEMPLATES = {
    "7-day": {
        "subject_prefix": "Following up:",
        "templates": [
            # Template 1: Interest + offer materials
            {
                "body": (
                    "I wanted to follow up on my application for the {job_title} role — "
                    "I remain very interested in contributing to {company_name}'s work. "
                    "Please let me know if there are any additional materials I can provide, "
                    "such as code samples from my {showcase_project} project or references, "
                    "to support the review process."
                ),
            },
            # Template 2: Brief check-in
            {
                "body": (
                    "I'm writing to follow up on my {job_title} application submitted last week "
                    "— I'm genuinely excited about this opportunity at {company_name}. "
                    "Happy to share additional code samples (e.g. my {showcase_project} repo) "
                    "or any other details that would be helpful for your evaluation."
                ),
            },
            # Template 3: Ultra-concise 2-sentence (polite + non-intrusive)
            {
                "body": (
                    "I wanted to follow up on my {job_title} application and restate "
                    "my interest in the role at {company_name}. "
                    "If there are any additional details or code samples I can share — "
                    "such as my {showcase_project} repo — I'd be happy to provide them."
                ),
            },
        ],
    },
    "14-day": {
        "subject_prefix": "Checking in:",
        "templates": [
            {
                "body": (
                    "I wanted to check in on the status of my {job_title} application — "
                    "I've continued working on relevant projects since applying and remain "
                    "enthusiastic about {company_name}. "
                    "I'm happy to provide a live demo, code walkthrough, "
                    "or any additional context that would be useful."
                ),
            },
        ],
    },
    "21-day": {
        "subject_prefix": "Quick note:",
        "templates": [
            {
                "body": (
                    "I understand the {job_title} review process takes time and I appreciate "
                    "your team's consideration. If the position has been filled, I'd welcome "
                    "any brief feedback on my application — it would be genuinely valuable "
                    "for my growth. Either way, I'd love to stay on {company_name}'s radar "
                    "for future opportunities."
                ),
            },
        ],
    },
}


# ═══════════════════════════════════════════════════════════════
#  Follow-Up Generator
# ═══════════════════════════════════════════════════════════════

class FollowUpGenerator:
    """
    Generates professional follow-up emails for job applications.

    Uses template-based generation (instant, no API call) with smart
    variable substitution from job data and master CV.
    """

    def __init__(self):
        self.candidate_name = self._load_candidate_name()
        self.showcase_project = self._load_showcase_project()

    def _load_candidate_name(self) -> str:
        """Load candidate name from master CV."""
        try:
            with open(settings.MASTER_CV_PATH, 'r', encoding='utf-8') as f:
                cv = json.load(f)
            personal = cv.get("personal", cv.get("personal_info", {}))
            return personal.get("full_name", personal.get("name", "Candidate"))
        except Exception:
            return "Candidate"

    def _load_showcase_project(self) -> str:
        """Load the best showcase project from master CV.
        
        Prefers AI/high-signal projects (with keywords like 'AI', 'LangChain',
        'agentic') over generic ones. Falls back to the last project in the
        list (typically the most recent/advanced).
        """
        try:
            with open(settings.MASTER_CV_PATH, 'r', encoding='utf-8') as f:
                cv = json.load(f)
            projects = cv.get("projects", [])
            if not projects:
                return "recent project"
            
            # Prefer projects with high-signal keywords
            high_signal_keywords = ['ai', 'langchain', 'agentic', 'ml', 'machine learning',
                                    'llm', 'rag', 'intelligent', 'prediction']
            for project in reversed(projects):  # Reversed = newest first
                name = project.get("name", "").lower()
                desc = project.get("description", "").lower()
                tech = str(project.get("technologies", "")).lower()
                combined = f"{name} {desc} {tech}"
                if any(kw in combined for kw in high_signal_keywords):
                    return self._short_name(project.get("name", "recent project"))
            
            # Fallback: use the last project (typically most recent/advanced)
            return self._short_name(projects[-1].get("name", "recent project"))
        except Exception:
            return "recent project"

    @staticmethod
    def _short_name(name: str) -> str:
        """Shorten a project name for email use.
        
        'Lawnova: AI-Powered Interactive Legal...' → 'Lawnova'
        'EduTimeSync — Academic Timetable...' → 'EduTimeSync'
        'PipChat – Real-Time Chat Application' → 'PipChat'
        """
        # Split on common separators
        for sep in [':', ' — ', ' – ', ' - ']:
            if sep in name:
                short = name.split(sep)[0].strip()
                if len(short) >= 3:
                    return short
        # If name is very long, take just the first word(s)
        if len(name) > 30:
            return ' '.join(name.split()[:2])
        return name

    def generate(
        self,
        job_title: str,
        company_name: str,
        days_since_applied: int = 7,
        contact_person: str = "",
        showcase_project: Optional[str] = None,
        template_variant: int = 0,
    ) -> FollowUpEmail:
        """
        Generate a follow-up email for a job application.

        Args:
            job_title: The job title applied for
            company_name: The company name
            days_since_applied: Days since the application was submitted
            contact_person: Name of the hiring contact (if known)
            showcase_project: Override the showcase project name
            template_variant: Which template variant to use (0-indexed)

        Returns:
            FollowUpEmail with subject, body, and assembled full text
        """
        # Determine follow-up stage
        if days_since_applied >= 21:
            stage = "21-day"
        elif days_since_applied >= 14:
            stage = "14-day"
        else:
            stage = "7-day"

        stage_config = TEMPLATES[stage]
        templates = stage_config["templates"]
        template = templates[template_variant % len(templates)]

        # Build greeting
        if contact_person:
            greeting = f"Hi {contact_person.split()[0]},"
        else:
            greeting = "Hi there,"

        # Resolve showcase project
        project = showcase_project or self.showcase_project

        # Fill template
        body = template["body"].format(
            job_title=job_title,
            company_name=company_name,
            showcase_project=project,
        )

        # Build subject line
        original_subject = f"{self.candidate_name} — {job_title} Application"
        subject_line = f"Re: {original_subject}"

        # Sign-off
        sign_off = f"Best,\n{self.candidate_name}"

        # Assemble full text
        full_text = f"{greeting}\n\n{body}\n\n{sign_off}"

        result = FollowUpEmail(
            subject_line=subject_line,
            greeting=greeting,
            body=body,
            sign_off=sign_off,
            full_text=full_text,
            follow_up_stage=stage,
            tone="professional",
        )

        logger.info(
            f"📬 Generated {stage} follow-up for {job_title} @ {company_name}"
        )

        return result

    def generate_from_job_data(
        self,
        job: dict,
        days_since_applied: Optional[int] = None,
    ) -> FollowUpEmail:
        """
        Generate a follow-up from a stored job document.

        Args:
            job: Job document from MongoDB
            days_since_applied: Override days calculation

        Returns:
            FollowUpEmail
        """
        title = job.get("title", "the position")
        company = job.get("company", {})
        company_name = company.get("name", "") if isinstance(company, dict) else str(company)
        contact = job.get("contact", {})
        contact_person = contact.get("contact_person", "") if isinstance(contact, dict) else ""

        # Calculate days since application
        if days_since_applied is None:
            applied_at = job.get("applied_at")
            if applied_at:
                if isinstance(applied_at, str):
                    applied_at = datetime.fromisoformat(applied_at.replace('Z', '+00:00'))
                delta = datetime.utcnow() - applied_at.replace(tzinfo=None)
                days_since_applied = delta.days
            else:
                days_since_applied = 7  # Default

        return self.generate(
            job_title=title,
            company_name=company_name or "the company",
            days_since_applied=days_since_applied,
            contact_person=contact_person,
        )


# ═══════════════════════════════════════════════════════════════
#  Convenience function
# ═══════════════════════════════════════════════════════════════

def generate_followup(
    job_title: str,
    company_name: str,
    days_since_applied: int = 7,
    contact_person: str = "",
) -> dict:
    """Quick convenience function for generating a follow-up email."""
    gen = FollowUpGenerator()
    result = gen.generate(
        job_title=job_title,
        company_name=company_name,
        days_since_applied=days_since_applied,
        contact_person=contact_person,
    )
    return result.model_dump()
