"""
Base scraper class for all job board scrapers.
Provides common functionality: HTTP client management, rate limiting,
deduplication, and data persistence.

Uses httpx (async HTTP client) + BeautifulSoup instead of Playwright
for maximum compatibility (no subprocess spawning needed).
"""

import asyncio
import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncGenerator

import httpx
from pymongo.errors import DuplicateKeyError

from backend.config import settings
from backend.database.connection import Database
from backend.database.models import (
    JobListing, ScrapingResult, SourcePlatform, ApplicationStatus
)
from backend.scrapers.filter_engine import FilterEngine

logger = logging.getLogger(__name__)

# Default headers to mimic a real browser
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class BaseScraper(ABC):
    """
    Abstract base class for all job board scrapers.
    
    Uses httpx for HTTP requests (no browser subprocess needed).
    
    Subclasses must implement:
        - platform: The SourcePlatform enum value
        - scrape_listings(): The core scraping logic
    """

    def __init__(self):
        self.filter_engine = FilterEngine()
        self.result = ScrapingResult(platform=self.platform)
        self._client: httpx.AsyncClient | None = None

    # ── Abstract Properties & Methods ────────────────────────

    @property
    @abstractmethod
    def platform(self) -> SourcePlatform:
        """Return the platform identifier."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base URL for the job board."""
        ...

    @abstractmethod
    async def scrape_listings(self, search_query: str, location: str = "Sri Lanka") -> AsyncGenerator[dict, None]:
        """
        Fetch and parse job listings.
        Each dict should contain at minimum: title, company_name, description, url
        """
        ...

    # ── HTTP Client Management ───────────────────────────────

    async def _init_client(self, **kwargs) -> httpx.AsyncClient:
        """Create an async HTTP client with browser-like headers."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=15.0),
                verify=False,  # Some Sri Lankan job sites have cert issues
                **kwargs,
            )
            logger.info(f"🌐 HTTP client initialized for {self.platform}")
        return self._client

    async def _fetch_page(self, url: str, **kwargs) -> str:
        """Fetch a page and return its HTML content."""
        client = await self._init_client()
        try:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.warning(f"⚠️ HTTP {e.response.status_code} for {url}")
            raise
        except httpx.RequestError as e:
            logger.warning(f"⚠️ Request failed for {url}: {e}")
            raise

    async def _close_client(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info(f"🔒 HTTP client closed for {self.platform}")

    # ── Rate Limiting ────────────────────────────────────────

    async def _rate_limit(self):
        """Enforce human-like delay between requests."""
        delay = settings.REQUEST_DELAY_SECONDS + random.uniform(0.5, 2.0)
        logger.debug(f"⏳ Rate limiting: waiting {delay:.1f}s")
        await asyncio.sleep(delay)

    # ── Deduplication ────────────────────────────────────────

    @staticmethod
    def generate_job_id(url: str, title: str, company: str) -> str:
        """Generate a unique job ID from URL + title + company."""
        raw = f"{url}|{title.lower().strip()}|{company.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def _is_duplicate(self, job_id: str) -> bool:
        """Check if a job already exists in the database."""
        db = Database.get_async_db()
        existing = await db.jobs.find_one({"job_id": job_id})
        return existing is not None

    # ── Data Persistence ─────────────────────────────────────

    async def _save_job(self, job: JobListing) -> bool:
        """
        Save a job listing to MongoDB.
        Returns True if saved, False if duplicate.
        """
        db = Database.get_async_db()
        try:
            job_dict = job.model_dump()
            await db.jobs.insert_one(job_dict)
            logger.info(f"💾 Saved: {job.title} @ {job.company.name}")
            return True
        except DuplicateKeyError:
            logger.debug(f"⏭️ Duplicate skipped: {job.title} @ {job.company.name}")
            return False
        except Exception as e:
            logger.error(f"❌ Error saving job: {e}")
            self.result.errors.append(str(e))
            return False

    # ── Main Execution Pipeline ──────────────────────────────

    async def run(
        self,
        search_query: str = "Software Intern",
        location: str = "Sri Lanka",
        max_results: int = 50,
        headless: bool = True
    ) -> ScrapingResult:
        """
        Execute the full scraping pipeline:
        1. Initialize HTTP client
        2. Scrape listings
        3. Filter by keywords
        4. Deduplicate
        5. Save to database
        6. Return results summary
        """
        start_time = time.time()
        logger.info(f"🚀 Starting scrape: {self.platform} | Query: '{search_query}' | Location: '{location}'")

        try:
            await self._init_client()
            count = 0

            async for raw_listing in self.scrape_listings(search_query, location):
                if count >= max_results:
                    logger.info(f"📊 Reached max results ({max_results})")
                    break

                self.result.total_found += 1
                title = raw_listing.get("title", "")
                company_name = raw_listing.get("company_name", "Unknown")
                description = raw_listing.get("description", "")
                url = raw_listing.get("url", "")

                # ── Step 1: Keyword filtering ────────────────
                filter_result = self.filter_engine.evaluate(title, description)
                if not filter_result["passed"]:
                    logger.debug(
                        f"🚫 Filtered out: '{title}' — "
                        f"Reason: {filter_result.get('reason', 'No match')}"
                    )
                    continue

                # ── Step 2: Generate unique ID ───────────────
                job_id = self.generate_job_id(url, title, company_name)

                # ── Step 3: Deduplication ────────────────────
                if await self._is_duplicate(job_id):
                    self.result.duplicates_skipped += 1
                    continue

                # ── Step 4: Build the JobListing model ───────
                from backend.database.models import CompanyInfo, ContactInfo
                job = JobListing(
                    job_id=job_id,
                    title=title,
                    company=CompanyInfo(
                        name=company_name,
                        website=raw_listing.get("company_website"),
                        location=raw_listing.get("location"),
                        about=raw_listing.get("company_about"),
                    ),
                    job_description=description,
                    requirements=raw_listing.get("requirements", []),
                    responsibilities=raw_listing.get("responsibilities", []),
                    source_platform=self.platform,
                    source_url=url,
                    apply_url=raw_listing.get("apply_url"),
                    contact=ContactInfo(
                        email=raw_listing.get("contact_email"),
                        contact_person=raw_listing.get("contact_person"),
                    ),
                    job_type=raw_listing.get("job_type"),
                    experience_level=raw_listing.get("experience_level"),
                    salary_range=raw_listing.get("salary_range"),
                    location_type=raw_listing.get("location_type"),
                    posted_date=raw_listing.get("posted_date"),
                    deadline=raw_listing.get("deadline"),
                    application_status=ApplicationStatus.FILTERED,
                    keyword_matches=filter_result.get("matched_keywords", []),
                    relevance_score=filter_result.get("score", 0.0),
                )

                # ── Step 5: Save to database ────────────────
                saved = await self._save_job(job)
                if saved:
                    self.result.new_jobs += 1
                    count += 1

                await self._rate_limit()

        except Exception as e:
            logger.error(f"💥 Scraping error on {self.platform}: {e}", exc_info=True)
            self.result.errors.append(str(e))
        finally:
            await self._close_client()
            self.result.duration_seconds = time.time() - start_time

        # ── Log summary ──────────────────────────────────────
        logger.info(
            f"✅ {self.platform} scrape complete | "
            f"Found: {self.result.total_found} | "
            f"New: {self.result.new_jobs} | "
            f"Duplicates: {self.result.duplicates_skipped} | "
            f"Errors: {len(self.result.errors)} | "
            f"Duration: {self.result.duration_seconds:.1f}s"
        )

        # Save scraping result to history
        await self._save_scraping_result()
        return self.result

    async def _save_scraping_result(self):
        """Persist scraping session result for analytics."""
        db = Database.get_async_db()
        try:
            await db.scraping_history.insert_one(self.result.model_dump())
        except Exception as e:
            logger.error(f"Failed to save scraping result: {e}")
