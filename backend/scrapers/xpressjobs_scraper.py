"""
XpressJobs.lk Scraper - Sri Lankan job portal.
Uses httpx for fetching and BeautifulSoup for parsing.
"""

import logging
from typing import AsyncGenerator
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from backend.scrapers.base_scraper import BaseScraper
from backend.database.models import SourcePlatform

logger = logging.getLogger(__name__)


class XpressJobsScraper(BaseScraper):
    """Scraper for XpressJobs.lk"""

    @property
    def platform(self) -> SourcePlatform:
        return SourcePlatform.XPRESS_JOBS

    @property
    def base_url(self) -> str:
        return "https://xpress.jobs"

    def _build_search_url(self, query: str, page_num: int = 1) -> str:
        """Build XpressJobs search URL."""
        encoded_query = quote_plus(query)
        return f"{self.base_url}/jobs?q={encoded_query}&page={page_num}"

    async def scrape_listings(
        self, search_query: str, location: str = "Sri Lanka"
    ) -> AsyncGenerator[dict, None]:
        """Scrape XpressJobs listings."""
        max_pages = 3

        for page_num in range(1, max_pages + 1):
            url = self._build_search_url(search_query, page_num)
            logger.info(f"📄 XpressJobs page {page_num}: {url}")

            try:
                content = await self._fetch_page(url)
                soup = BeautifulSoup(content, "lxml")

                # XpressJobs uses card-based layouts
                job_cards = soup.select(
                    "div.job-card, "
                    "div.vacancy-card, "
                    "article.job-listing, "
                    "div.search-result-item, "
                    "a.job-link"
                )

                # Fallback: find all links that look like job listings
                if not job_cards:
                    job_cards = soup.select("a[href*='/job/'], a[href*='/vacancy/']")

                if not job_cards:
                    logger.info(f"📭 No results on page {page_num}, stopping")
                    break

                logger.info(f"📋 Found {len(job_cards)} cards on page {page_num}")

                for card in job_cards:
                    listing = self._parse_card(card)
                    if listing:
                        if listing.get("url"):
                            detail = await self._get_listing_detail(listing["url"])
                            if detail:
                                listing.update(detail)
                        yield listing

                await self._rate_limit()

            except Exception as e:
                logger.error(f"💥 Error scraping XpressJobs page {page_num}: {e}")
                self.result.errors.append(str(e))
                break

    def _parse_card(self, card) -> dict | None:
        """Parse an XpressJobs card element."""
        try:
            # Try to find title
            title_el = card.select_one(
                "h2, h3, h4, "
                "span.job-title, "
                "div.title"
            )
            title = title_el.get_text(strip=True) if title_el else card.get_text(strip=True)

            if not title or len(title) < 3:
                return None

            # Extract company
            company_el = card.select_one(
                "span.company-name, "
                "div.company, "
                "p.company"
            )
            company_name = company_el.get_text(strip=True) if company_el else "See Details"

            # Extract URL
            if card.name == "a":
                url = card.get("href", "")
            else:
                link = card.select_one("a[href]")
                url = link.get("href", "") if link else ""

            if url and not url.startswith("http"):
                url = f"{self.base_url}{url}"

            # Extract location
            loc_el = card.select_one("span.location, div.location")
            location = loc_el.get_text(strip=True) if loc_el else "Sri Lanka"

            return {
                "title": title,
                "company_name": company_name,
                "url": url,
                "location": location,
                "description": "",
                "source": "xpress_jobs",
            }

        except Exception as e:
            logger.debug(f"Failed to parse XpressJobs card: {e}")
            return None

    async def _get_listing_detail(self, url: str) -> dict | None:
        """Get full job details from an XpressJobs listing page."""
        try:
            content = await self._fetch_page(url)
            soup = BeautifulSoup(content, "lxml")

            # Extract description
            desc_el = soup.select_one(
                "div.job-description, "
                "div.vacancy-details, "
                "div.content, "
                "article"
            )
            description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

            # Extract contact email
            contact_email = None
            for text in soup.stripped_strings:
                if "@" in text and "." in text and len(text) < 100:
                    contact_email = text.strip()
                    break

            # Extract deadline
            deadline = None
            deadline_el = soup.select_one(
                "span.deadline, "
                "div.closing-date"
            )
            if deadline_el:
                deadline = deadline_el.get_text(strip=True)

            await self._rate_limit()

            return {
                "description": description[:5000],
                "contact_email": contact_email,
                "deadline": deadline,
            }

        except Exception as e:
            logger.debug(f"Failed to get XpressJobs detail for {url}: {e}")
            return None

    async def parse_listing_page(self, url: str) -> dict | None:
        """Parse a single XpressJobs listing page."""
        return await self._get_listing_detail(url)
