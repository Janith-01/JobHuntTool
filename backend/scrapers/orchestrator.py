"""
Scraper Orchestrator - Manages concurrent execution of all scrapers.
Provides a unified interface to run scrapers with rate limiting and error handling.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from backend.config import settings
from backend.database.connection import Database
from backend.database.models import ScrapingResult, SourcePlatform
from backend.scrapers.linkedin_scraper import LinkedInScraper
from backend.scrapers.topjobs_scraper import TopJobsScraper
from backend.scrapers.xpressjobs_scraper import XpressJobsScraper

logger = logging.getLogger(__name__)


# Registry of all available scrapers
SCRAPER_REGISTRY = {
    SourcePlatform.LINKEDIN: LinkedInScraper,
    SourcePlatform.TOPJOBS_LK: TopJobsScraper,
    SourcePlatform.XPRESS_JOBS: XpressJobsScraper,
}


class ScraperOrchestrator:
    """
    Orchestrates multiple scrapers to run concurrently or sequentially.
    Manages the overall scraping pipeline with:
        - Concurrent execution with concurrency limits
        - Aggregated results
        - Scheduling support
        - Error isolation (one scraper failing doesn't stop others)
    """

    def __init__(self):
        self.results: list[ScrapingResult] = []

    async def run_all(
        self,
        search_query: str = "Software Intern",
        location: str = "Sri Lanka",
        max_results_per_platform: int = 30,
        platforms: list[SourcePlatform] | None = None,
        headless: bool = True,
        concurrent: bool = True,
    ) -> list[ScrapingResult]:
        """
        Run all (or selected) scrapers.
        
        Args:
            search_query: Job search query string
            location: Target location
            max_results_per_platform: Max jobs to scrape per platform
            platforms: Specific platforms to scrape (None = all)
            headless: Run browsers in headless mode
            concurrent: Run scrapers concurrently or sequentially
            
        Returns:
            List of ScrapingResult objects
        """
        # Ensure database indexes exist
        await Database.create_indexes()

        target_platforms = platforms or list(SCRAPER_REGISTRY.keys())
        logger.info(
            f"🎯 Starting orchestrated scrape\n"
            f"   Query: '{search_query}'\n"
            f"   Location: '{location}'\n"
            f"   Platforms: {[p.value for p in target_platforms]}\n"
            f"   Concurrent: {concurrent}"
        )

        if concurrent:
            # Run with concurrency limit
            semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_SCRAPERS)
            tasks = [
                self._run_with_semaphore(
                    semaphore, platform, search_query, location,
                    max_results_per_platform, headless
                )
                for platform in target_platforms
            ]
            self.results = await asyncio.gather(*tasks)
        else:
            # Run sequentially
            self.results = []
            for platform in target_platforms:
                result = await self._run_single(
                    platform, search_query, location,
                    max_results_per_platform, headless
                )
                self.results.append(result)

        # Print summary
        self._print_summary()

        # Save orchestration record
        await self._save_orchestration_record(search_query, location)

        return self.results

    async def run_single_platform(
        self,
        platform: SourcePlatform,
        search_query: str = "Software Intern",
        location: str = "Sri Lanka",
        max_results: int = 30,
        headless: bool = True,
    ) -> ScrapingResult:
        """Run a single platform scraper."""
        await Database.create_indexes()
        result = await self._run_single(platform, search_query, location, max_results, headless)
        self.results = [result]
        self._print_summary()
        return result

    async def _run_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        platform: SourcePlatform,
        search_query: str,
        location: str,
        max_results: int,
        headless: bool,
    ) -> ScrapingResult:
        """Run a scraper with semaphore-based concurrency control."""
        async with semaphore:
            return await self._run_single(
                platform, search_query, location, max_results, headless
            )

    async def _run_single(
        self,
        platform: SourcePlatform,
        search_query: str,
        location: str,
        max_results: int,
        headless: bool,
    ) -> ScrapingResult:
        """Execute a single scraper with error isolation."""
        scraper_class = SCRAPER_REGISTRY.get(platform)
        if not scraper_class:
            logger.error(f"❌ No scraper registered for platform: {platform}")
            return ScrapingResult(
                platform=platform,
                errors=[f"No scraper registered for {platform}"]
            )

        try:
            scraper = scraper_class()
            return await scraper.run(
                search_query=search_query,
                location=location,
                max_results=max_results,
                headless=headless,
            )
        except Exception as e:
            logger.error(f"💥 Orchestrator caught error from {platform}: {e}", exc_info=True)
            return ScrapingResult(
                platform=platform,
                errors=[f"Unhandled error: {str(e)}"]
            )

    def _print_summary(self):
        """Print a formatted summary of all scraping results."""
        total_found = sum(r.total_found for r in self.results)
        total_new = sum(r.new_jobs for r in self.results)
        total_dupes = sum(r.duplicates_skipped for r in self.results)
        total_errors = sum(len(r.errors) for r in self.results)
        total_duration = sum(r.duration_seconds for r in self.results)

        summary = f"""
╔══════════════════════════════════════════════════╗
║           🎯 SCRAPING RESULTS SUMMARY            ║
╠══════════════════════════════════════════════════╣
"""
        for r in self.results:
            status = "✅" if not r.errors else "⚠️"
            summary += (
                f"║  {status} {r.platform:<15} | "
                f"Found: {r.total_found:>3} | "
                f"New: {r.new_jobs:>3} | "
                f"Dupes: {r.duplicates_skipped:>3} | "
                f"Errs: {len(r.errors):>2}  ║\n"
            )

        summary += f"""╠══════════════════════════════════════════════════╣
║  TOTAL: Found {total_found} | New {total_new} | Dupes {total_dupes} | Errors {total_errors}
║  Duration: {total_duration:.1f}s
╚══════════════════════════════════════════════════╝"""

        logger.info(summary)
        print(summary)

    async def _save_orchestration_record(self, search_query: str, location: str):
        """Save the orchestration session to the database."""
        db = Database.get_async_db()
        try:
            record = {
                "search_query": search_query,
                "location": location,
                "platforms": [r.platform for r in self.results],
                "total_found": sum(r.total_found for r in self.results),
                "total_new": sum(r.new_jobs for r in self.results),
                "total_duplicates": sum(r.duplicates_skipped for r in self.results),
                "total_errors": sum(len(r.errors) for r in self.results),
                "total_duration": sum(r.duration_seconds for r in self.results),
                "results": [r.model_dump() for r in self.results],
                "timestamp": datetime.utcnow(),
            }
            await db.orchestration_history.insert_one(record)
        except Exception as e:
            logger.error(f"Failed to save orchestration record: {e}")

    def get_aggregated_stats(self) -> dict:
        """Return aggregated statistics from the last run."""
        return {
            "total_found": sum(r.total_found for r in self.results),
            "total_new": sum(r.new_jobs for r in self.results),
            "total_duplicates": sum(r.duplicates_skipped for r in self.results),
            "total_errors": sum(len(r.errors) for r in self.results),
            "total_duration": sum(r.duration_seconds for r in self.results),
            "per_platform": {
                r.platform: {
                    "found": r.total_found,
                    "new": r.new_jobs,
                    "duplicates": r.duplicates_skipped,
                    "errors": len(r.errors),
                    "duration": r.duration_seconds,
                }
                for r in self.results
            }
        }
