"""
TopJobs.lk Scraper - Sri Lanka's leading job portal.
Uses httpx for fetching and BeautifulSoup for parsing.
"""

import logging
from typing import AsyncGenerator
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from backend.scrapers.base_scraper import BaseScraper
from backend.database.models import SourcePlatform

logger = logging.getLogger(__name__)


class TopJobsScraper(BaseScraper):
    """Scraper for TopJobs.lk (Sri Lankan job portal)."""

    @property
    def platform(self) -> SourcePlatform:
        return SourcePlatform.TOPJOBS_LK

    @property
    def base_url(self) -> str:
        return "https://www.topjobs.lk"

    def _build_search_url(self, query: str) -> str:
        """Build TopJobs search URL."""
        return f"{self.base_url}/applicant/vacancybyfunctionalarea.jsp?FA=SDQ"

    async def scrape_listings(
        self, search_query: str, location: str = "Sri Lanka"
    ) -> AsyncGenerator[dict, None]:
        """
        Scrape TopJobs.lk listings.
        TopJobs organizes jobs by functional area - we target IT/Software.
        """
        # TopJobs functional area codes for IT/Software:
        # SDQ = Software Development
        # SFT = Software / QA
        # ICT = ICT
        functional_areas = ["SDQ", "SFT", "ICT"]

        for area_code in functional_areas:
            url = f"{self.base_url}/applicant/vacancybyfunctionalarea.jsp?FA={area_code}"
            logger.info(f"📄 TopJobs area {area_code}: {url}")

            try:
                content = await self._fetch_page(url)
                soup = BeautifulSoup(content, "lxml")

                # TopJobs uses table-based layouts for job listings
                job_rows = soup.select(
                    "table.vacancy-table tr, "
                    "div.vacancy-item, "
                    "table tr[onclick], "
                    "div.job-card"
                )

                # Also try the common pattern of links in the main content
                if not job_rows:
                    # Look for job links directly
                    job_links = soup.select("a[href*='vacancy']")
                    for link in job_links:
                        title = link.get_text(strip=True)
                        href = link.get("href", "")

                        if title and len(title) > 5 and href:
                            if not href.startswith("http"):
                                href = f"{self.base_url}/{href.lstrip('/')}"

                            listing = {
                                "title": title,
                                "company_name": "See Details",
                                "url": href,
                                "description": "",
                                "location": "Sri Lanka",
                                "source": "topjobs_lk",
                            }

                            # Get full details
                            detail = await self._get_listing_detail(href)
                            if detail:
                                listing.update(detail)

                            yield listing
                    continue

                logger.info(f"📋 Found {len(job_rows)} listings in area {area_code}")

                for row in job_rows:
                    listing = self._parse_row(row)
                    if listing:
                        if listing.get("url"):
                            detail = await self._get_listing_detail(listing["url"])
                            if detail:
                                listing.update(detail)
                        yield listing

                await self._rate_limit()

            except Exception as e:
                logger.error(f"💥 Error scraping TopJobs area {area_code}: {e}")
                self.result.errors.append(str(e))

    def _parse_row(self, row) -> dict | None:
        """Parse a TopJobs listing row."""
        try:
            # Extract text and links from the row
            links = row.select("a")
            tds = row.select("td")

            title = None
            company = None
            url = None
            deadline = None

            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if "vacancy" in href.lower() and text:
                    title = text
                    if not href.startswith("http"):
                        href = f"{self.base_url}/{href.lstrip('/')}"
                    url = href
                elif text and not title:
                    title = text

            # Try to extract company from table cells
            for td in tds:
                text = td.get_text(strip=True)
                if text and not title:
                    title = text
                elif text and title and not company:
                    company = text
                elif text and company:
                    # Likely a date
                    deadline = text

            if not title or len(title) < 3:
                return None

            return {
                "title": title,
                "company_name": company or "See Details",
                "url": url or "",
                "description": "",
                "deadline": deadline,
                "location": "Sri Lanka",
                "source": "topjobs_lk",
            }

        except Exception as e:
            logger.debug(f"Failed to parse TopJobs row: {e}")
            return None

    async def _get_listing_detail(self, url: str) -> dict | None:
        """Get full job details from a TopJobs listing page."""
        try:
            content = await self._fetch_page(url)
            soup = BeautifulSoup(content, "lxml")

            # Extract all text from the main content area
            main_content = soup.select_one(
                "div.vacancy-details, "
                "div.job-details, "
                "div#content, "
                "div.main-content, "
                "body"
            )

            description = ""
            company_name = None
            contact_email = None
            requirements = []

            if main_content:
                description = main_content.get_text(separator="\n", strip=True)

                # Try to extract structured info
                for text_block in main_content.stripped_strings:
                    text_lower = text_block.lower()
                    if "@" in text_block and "." in text_block:
                        contact_email = text_block.strip()
                    if "company" in text_lower or "organization" in text_lower:
                        # Next sibling might be company name
                        company_name = text_block

            await self._rate_limit()

            return {
                "description": description[:5000],  # Limit description length
                "contact_email": contact_email,
                "company_name": company_name,
            }

        except Exception as e:
            logger.debug(f"Failed to get TopJobs detail for {url}: {e}")
            return None

    async def parse_listing_page(self, url: str) -> dict | None:
        """Parse a single TopJobs listing page."""
        return await self._get_listing_detail(url)
