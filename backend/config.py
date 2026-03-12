"""
Configuration module for JobHuntTool.
Loads environment variables and provides centralized settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


class Settings:
    """Centralized application settings loaded from environment variables."""

    # ── MongoDB ──────────────────────────────────────────────
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "jobhunttool")

    # ── Google Gemini ────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ── Email ────────────────────────────────────────────────
    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "smtp.zoho.com")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", "465"))
    EMAIL_USER: str = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")

    # ── Scraping ─────────────────────────────────────────────
    SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
    MAX_CONCURRENT_SCRAPERS: int = int(os.getenv("MAX_CONCURRENT_SCRAPERS", "3"))
    REQUEST_DELAY_SECONDS: float = float(os.getenv("REQUEST_DELAY_SECONDS", "2"))

    # ── LinkedIn ─────────────────────────────────────────────
    LINKEDIN_EMAIL: str = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD: str = os.getenv("LINKEDIN_PASSWORD", "")

    # ── Application ──────────────────────────────────────────
    APP_ENV: str = os.getenv("APP_ENV", "development")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "3000"))

    # ── Paths ────────────────────────────────────────────────
    PDF_OUTPUT_DIR: Path = PROJECT_ROOT / os.getenv("PDF_OUTPUT_DIR", "output/pdfs")
    CV_TEMPLATE_DIR: Path = PROJECT_ROOT / os.getenv("CV_TEMPLATE_DIR", "templates")
    MASTER_CV_PATH: Path = PROJECT_ROOT / os.getenv("MASTER_CV_PATH", "data/master_cv.json")

    # ── Scraper Keywords ─────────────────────────────────────
    INCLUDE_KEYWORDS: list[str] = [
        "intern", "internship", "software", "ai", "machine learning",
        "deep learning", "full stack", "fullstack", "developer",
        "engineer", "python", "react", "node", "javascript",
        "typescript", "web developer", "data science", "ml",
        "artificial intelligence", "junior", "trainee", "graduate",
        "entry level", "associate"
    ]

    EXCLUDE_KEYWORDS: list[str] = [
        "senior", "lead", "principal", "staff", "director",
        "manager", "head of", "vp ", "vice president",
        "10+ years", "8+ years", "7+ years",
        "chief", "architect"
    ]

    @classmethod
    def ensure_directories(cls):
        """Create necessary output directories if they don't exist."""
        cls.PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.CV_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)
        (PROJECT_ROOT / "logs").mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
