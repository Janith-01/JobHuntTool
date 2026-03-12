"""
Pydantic models for the JobHuntTool database schema.
Defines the structure for jobs, applications, and related entities.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class ApplicationStatus(str, Enum):
    """Tracks the lifecycle of a job application."""
    DISCOVERED = "discovered"           # Found by scraper
    FILTERED = "filtered"               # Passed keyword filters
    REVIEWED = "reviewed"               # Human reviewed
    CV_GENERATED = "cv_generated"       # Tailored CV created
    COVER_LETTER_DONE = "cover_letter_done"  # Cover letter generated
    READY_TO_SEND = "ready_to_send"     # Queued for delivery
    SENT = "sent"                       # Email sent
    OPENED = "opened"                   # Email opened (if tracked)
    RESPONDED = "responded"             # Got a response
    INTERVIEW = "interview"             # Interview scheduled
    REJECTED = "rejected"               # Rejected
    ACCEPTED = "accepted"               # Got the job!
    SKIPPED = "skipped"                 # Manually skipped


class SourcePlatform(str, Enum):
    """Supported job board sources."""
    LINKEDIN = "linkedin"
    GLASSDOOR = "glassdoor"
    TOPJOBS_LK = "topjobs_lk"
    XPRESS_JOBS = "xpress_jobs"
    IKMAN_LK = "ikman_lk"
    CUSTOM = "custom"


class TechStack(BaseModel):
    """Technology stack requirements extracted from job description."""
    languages: list[str] = Field(default_factory=list, description="Programming languages")
    frameworks: list[str] = Field(default_factory=list, description="Frameworks & libraries")
    databases: list[str] = Field(default_factory=list, description="Database technologies")
    tools: list[str] = Field(default_factory=list, description="DevOps, CI/CD, etc.")
    cloud: list[str] = Field(default_factory=list, description="Cloud platforms")
    other: list[str] = Field(default_factory=list, description="Other technologies")


class CompanyInfo(BaseModel):
    """Company details extracted from the job listing."""
    name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None  # "About Us" or "Why Choose Us" section


class ContactInfo(BaseModel):
    """Contact information for application delivery."""
    email: Optional[str] = None
    phone: Optional[str] = None
    contact_person: Optional[str] = None
    linkedin_url: Optional[str] = None


class JobListing(BaseModel):
    """
    Core schema for a scraped job listing.
    Maps to the 'jobs' collection in MongoDB.
    """
    job_id: str = Field(..., description="Unique identifier (hash of URL + title)")
    title: str = Field(..., description="Job title")
    company: CompanyInfo = Field(..., description="Company information")
    job_description: str = Field(..., description="Full job description text")
    tech_stack_required: TechStack = Field(
        default_factory=TechStack,
        description="Extracted technology requirements"
    )
    requirements: list[str] = Field(
        default_factory=list,
        description="Listed job requirements"
    )
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Listed job responsibilities"
    )
    qualifications: list[str] = Field(
        default_factory=list,
        description="Education/experience qualifications"
    )

    # ── Application Metadata ─────────────────────────────────
    application_status: ApplicationStatus = Field(
        default=ApplicationStatus.DISCOVERED,
        description="Current status in the application pipeline"
    )
    source_platform: SourcePlatform = Field(..., description="Where the job was found")
    source_url: str = Field(..., description="Original listing URL")
    apply_url: Optional[str] = Field(None, description="Direct application link")
    contact: ContactInfo = Field(
        default_factory=ContactInfo,
        description="Contact information for the employer"
    )

    # ── Job Details ──────────────────────────────────────────
    job_type: Optional[str] = None  # Full-time, Part-time, Intern, Contract
    experience_level: Optional[str] = None  # Entry, Mid, Senior
    salary_range: Optional[str] = None
    location_type: Optional[str] = None  # Remote, On-site, Hybrid
    posted_date: Optional[str] = None
    deadline: Optional[str] = None

    # ── AI Analysis ──────────────────────────────────────────
    relevance_score: float = Field(
        default=0.0,
        description="AI-calculated match score (0-100)"
    )
    keyword_matches: list[str] = Field(
        default_factory=list,
        description="Keywords from the description matching your skills"
    )
    ai_summary: Optional[str] = Field(
        None,
        description="AI-generated summary of fit"
    )

    # ── Timestamps ───────────────────────────────────────────
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    applied_at: Optional[datetime] = None

    # ── Generated Documents ──────────────────────────────────
    generated_cv_path: Optional[str] = None
    generated_cover_letter_path: Optional[str] = None

    class Config:
        use_enum_values = True


class ApplicationRecord(BaseModel):
    """
    Tracks the full history of an application.
    Maps to the 'applications' collection in MongoDB.
    """
    job_id: str
    company_name: str
    job_title: str
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    cv_version: Optional[str] = None       # Path to the specific CV used
    cover_letter_version: Optional[str] = None  # Path to the cover letter used
    email_sent_to: Optional[str] = None
    email_subject: Optional[str] = None
    notes: list[str] = Field(default_factory=list)

    # ── Timeline ─────────────────────────────────────────────
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    response_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class ScrapingResult(BaseModel):
    """Result from a single scraping session."""
    platform: SourcePlatform
    total_found: int = 0
    new_jobs: int = 0
    duplicates_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
