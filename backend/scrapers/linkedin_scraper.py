"""
LinkedIn Job Scraper.
Uses httpx to scrape LinkedIn's public job listings.
Falls back to the guest/public search (no login required).
"""

import logging
from typing import AsyncGenerator
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from backend.scrapers.base_scraper import BaseScraper
from backend.database.models import SourcePlatform

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn public job search results."""

    @property
    def platform(self) -> SourcePlatform:
        return SourcePlatform.LINKEDIN

    @property
    def base_url(self) -> str:
        return "https://www.linkedin.com/jobs/search"

    def _build_search_url(self, query: str, location: str, page: int = 0) -> str:
        """Build LinkedIn public job search URL."""
        params = {
            "keywords": quote_plus(query),
            "location": quote_plus(location),
            "start": page * 25,
            "f_TPR": "r604800",  # Posted in last week
            "f_E": "1,2",       # Entry level & Associate
            "sortBy": "DD",     # Sort by date
        }
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.base_url}?{param_str}"

    async def scrape_listings(
        self, search_query: str, location: str = "Sri Lanka"
    ) -> AsyncGenerator[dict, None]:
        """
        Scrape LinkedIn job listings from public search results.
        Yields raw listing dictionaries.
        """
        current_page = 0
        max_pages = 4  # LinkedIn shows 25 results per page

        while current_page < max_pages:
            url = self._build_search_url(search_query, location, current_page)
            logger.info(f"📄 LinkedIn page {current_page + 1}: {url}")

            try:
                content = await self._fetch_page(url)
                soup = BeautifulSoup(content, "lxml")

                # Find job cards
                job_cards = soup.select(
                    "div.base-card, "
                    "li.jobs-search-results__list-item, "
                    "div.job-search-card"
                )

                if not job_cards:
                    # Try alternative selectors
                    job_cards = soup.select("ul.jobs-search__results-list > li")

                if not job_cards:
                    logger.info("📭 No more results found, stopping")
                    break

                logger.info(f"📋 Found {len(job_cards)} cards on page {current_page + 1}")

                for card in job_cards:
                    listing = self._parse_card(card)
                    if listing:
                        # Try to get full description from detail page
                        if listing.get("url"):
                            detail = await self._get_listing_detail(listing["url"])
                            if detail:
                                listing.update(detail)
                        yield listing

                current_page += 1
                await self._rate_limit()

            except Exception as e:
                logger.error(f"💥 Error scraping LinkedIn page {current_page + 1}: {e}")
                self.result.errors.append(str(e))
                break

    def _parse_card(self, card) -> dict | None:
        """Parse a LinkedIn job card element into a dictionary."""
        try:
            # Extract title
            title_el = card.select_one(
                "h3.base-search-card__title, "
                "a.job-card-list__title, "
                "span.sr-only"
            )
            title = title_el.get_text(strip=True) if title_el else None

            if not title:
                return None

            # Extract company name
            company_el = card.select_one(
                "h4.base-search-card__subtitle a, "
                "a.job-card-container__company-name, "
                "span.job-card-container__primary-description"
            )
            company_name = company_el.get_text(strip=True) if company_el else "Unknown"

            # Extract location
            location_el = card.select_one(
                "span.job-search-card__location, "
                "li.job-card-container__metadata-item"
            )
            location = location_el.get_text(strip=True) if location_el else None

            # Extract URL
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/']")
            url = link_el.get("href", "") if link_el else ""
            if url and not url.startswith("http"):
                url = f"https://www.linkedin.com{url}"
            # Clean tracking params
            url = url.split("?")[0] if url else ""

            # Extract posted date
            time_el = card.select_one("time, span.job-search-card__listdate")
            posted_date = time_el.get("datetime", time_el.get_text(strip=True)) if time_el else None

            return {
                "title": title,
                "company_name": company_name,
                "location": location,
                "url": url,
                "posted_date": posted_date,
                "description": "",  # Will be filled from detail page
                "source": "linkedin",
            }

        except Exception as e:
            logger.debug(f"Failed to parse card: {e}")
            return None

    async def _get_listing_detail(self, url: str) -> dict | None:
        """Fetch a job detail page and extract full description."""
        try:
            content = await self._fetch_page(url)
            soup = BeautifulSoup(content, "lxml")

            # Extract full description
            desc_el = soup.select_one(
                "div.show-more-less-html__markup, "
                "div.description__text, "
                "section.show-more-less-html"
            )
            description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

            # Extract criteria (job type, level, etc.)
            criteria = {}
            criteria_items = soup.select("li.description__job-criteria-item")
            for item in criteria_items:
                header = item.select_one("h3")
                value = item.select_one("span")
                if header and value:
                    key = header.get_text(strip=True).lower()
                    val = value.get_text(strip=True)
                    if "level" in key:
                        criteria["experience_level"] = val
                    elif "type" in key:
                        criteria["job_type"] = val
                    elif "function" in key:
                        criteria["function"] = val

            # Extract company about section
            about_el = soup.select_one("section.top-card-layout__card p")
            company_about = about_el.get_text(strip=True) if about_el else None

            await self._rate_limit()

            return {
                "description": description,
                "company_about": company_about,
                **criteria
            }

        except Exception as e:
            logger.debug(f"Failed to get detail for {url}: {e}")
            return None

    async def parse_listing_page(self, url: str) -> dict | None:
        """Parse a single LinkedIn listing page (used for direct URL scraping)."""
        return await self._get_listing_detail(url)
