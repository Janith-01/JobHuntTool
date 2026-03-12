"""
Intelligent keyword-based filtering engine.
Evaluates job titles and descriptions against include/exclude keyword lists
to determine relevance. Uses scoring to rank matches.
"""

import re
import logging
from backend.config import settings

logger = logging.getLogger(__name__)


class FilterEngine:
    """
    Evaluates job listings against configurable keyword rules.
    
    Scoring logic:
        - Each include keyword match in title:       +10 points
        - Each include keyword match in description: +3  points
        - Any exclude keyword match in title:        REJECT (immediate)
        - Any exclude keyword match in description:  -15 points per match
        
    A job passes the filter if:
        1. No exclude keywords appear in the title
        2. Net score > 0 after all bonuses and penalties
    """

    def __init__(
        self,
        include_keywords: list[str] | None = None,
        exclude_keywords: list[str] | None = None,
        min_score: float = 5.0
    ):
        self.include_keywords = [
            kw.lower() for kw in (include_keywords or settings.INCLUDE_KEYWORDS)
        ]
        self.exclude_keywords = [
            kw.lower() for kw in (exclude_keywords or settings.EXCLUDE_KEYWORDS)
        ]
        self.min_score = min_score

    def evaluate(self, title: str, description: str) -> dict:
        """
        Evaluate a job listing against the filter rules.
        
        Returns:
            dict with keys:
                - passed (bool): Whether the job passes the filter
                - score (float): Relevance score
                - matched_keywords (list[str]): Keywords that matched
                - excluded_keywords (list[str]): Excluded keywords found
                - reason (str): Human-readable explanation
        """
        title_lower = title.lower()
        desc_lower = description.lower()
        
        score = 0.0
        matched_keywords = []
        excluded_found = []

        # ── Step 1: Check title for exclusion keywords ───────
        for kw in self.exclude_keywords:
            if self._word_match(kw, title_lower):
                return {
                    "passed": False,
                    "score": 0.0,
                    "matched_keywords": [],
                    "excluded_keywords": [kw],
                    "reason": f"Title contains excluded keyword: '{kw}'"
                }

        # ── Step 2: Score include keywords ───────────────────
        for kw in self.include_keywords:
            # Title matches are worth more
            if self._word_match(kw, title_lower):
                score += 10.0
                if kw not in matched_keywords:
                    matched_keywords.append(kw)

            # Description matches
            count_in_desc = self._count_matches(kw, desc_lower)
            if count_in_desc > 0:
                # Diminishing returns for repeated mentions
                score += min(count_in_desc * 3.0, 15.0)
                if kw not in matched_keywords:
                    matched_keywords.append(kw)

        # ── Step 3: Penalize exclude keywords in description ─
        for kw in self.exclude_keywords:
            if self._word_match(kw, desc_lower):
                score -= 15.0
                excluded_found.append(kw)

        # ── Step 4: Determine pass/fail ──────────────────────
        passed = score >= self.min_score and len(matched_keywords) > 0

        reason = (
            f"Score: {score:.1f} | "
            f"Matches: {', '.join(matched_keywords) if matched_keywords else 'none'} | "
            f"Excluded: {', '.join(excluded_found) if excluded_found else 'none'}"
        )

        return {
            "passed": passed,
            "score": round(score, 1),
            "matched_keywords": matched_keywords,
            "excluded_keywords": excluded_found,
            "reason": reason
        }

    @staticmethod
    def _word_match(keyword: str, text: str) -> bool:
        """Check if a keyword appears as a word boundary match in text."""
        # Use word boundaries for short keywords, substring for longer ones
        if len(keyword) <= 3:
            pattern = rf'\b{re.escape(keyword)}\b'
        else:
            pattern = re.escape(keyword)
        return bool(re.search(pattern, text, re.IGNORECASE))

    @staticmethod
    def _count_matches(keyword: str, text: str) -> int:
        """Count occurrences of a keyword in text."""
        pattern = re.escape(keyword)
        return len(re.findall(pattern, text, re.IGNORECASE))

    def add_include_keyword(self, keyword: str):
        """Dynamically add a keyword to the include list."""
        kw = keyword.lower()
        if kw not in self.include_keywords:
            self.include_keywords.append(kw)

    def add_exclude_keyword(self, keyword: str):
        """Dynamically add a keyword to the exclude list."""
        kw = keyword.lower()
        if kw not in self.exclude_keywords:
            self.exclude_keywords.append(kw)

    def get_config(self) -> dict:
        """Return current filter configuration."""
        return {
            "include_keywords": self.include_keywords,
            "exclude_keywords": self.exclude_keywords,
            "min_score": self.min_score
        }
