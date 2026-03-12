"""
ATS (Applicant Tracking System) Scorer — Keyword Density Checker.

Simulates how real ATS systems like Greenhouse, Lever, and Workday parse
and score resumes against job descriptions.

Scoring methodology:
  1. Exact Keyword Match     — Full points for exact tech matches
  2. Semantic Variations     — Partial points for synonyms/aliases
  3. Keyword Density         — Penalizes keyword stuffing or over-optimization
  4. Section Coverage        — Bonus for keywords spread across multiple sections
  5. Priority Weighting      — Must-have keywords weighted 2x over nice-to-haves

The final ATS score is 0–100, with guidance:
  90+: Excellent — High ATS pass probability
  75–89: Good — Should pass most systems
  60–74: Fair — May get filtered by strict ATS
  <60: Poor — Likely to be auto-rejected
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from backend.ai.jd_parser import ParsedJobDescription

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Technology Synonym / Alias Map
# ═══════════════════════════════════════════════════════════════

# Maps variations of the same tech to a canonical form
TECH_ALIASES: dict[str, list[str]] = {
    "javascript": ["js", "ecmascript", "es6", "es2015"],
    "typescript": ["ts"],
    "python": ["py", "python3", "cpython"],
    "react": ["react.js", "reactjs", "react js"],
    "react native": ["react-native", "reactnative"],
    "node.js": ["nodejs", "node js", "node"],
    "next.js": ["nextjs", "next js", "next"],
    "vue.js": ["vuejs", "vue js", "vue"],
    "angular": ["angular.js", "angularjs"],
    "express": ["express.js", "expressjs"],
    "fastapi": ["fast api", "fast-api"],
    "mongodb": ["mongo", "mongo db"],
    "postgresql": ["postgres", "pg", "psql"],
    "mysql": ["my sql"],
    "docker": ["containerization", "containers"],
    "kubernetes": ["k8s", "kube"],
    "amazon web services": ["aws"],
    "google cloud": ["gcp", "google cloud platform"],
    "microsoft azure": ["azure"],
    "ci/cd": ["ci cd", "cicd", "continuous integration", "continuous deployment"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "natural language processing": ["nlp"],
    "computer vision": ["cv"],
    "three.js": ["threejs", "three js"],
    "socket.io": ["socketio", "socket io"],
    "tailwind css": ["tailwind", "tailwindcss"],
    "material ui": ["mui", "material-ui", "material design"],
    "rest api": ["restful", "rest", "restful api"],
    "graphql": ["graph ql"],
    "github actions": ["gh actions"],
    "langchain": ["lang chain"],
    "tensorflow": ["tf"],
    "pytorch": ["py torch"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "hugging face": ["huggingface", "hf"],
}

# Build reverse lookup: alias -> canonical
ALIAS_REVERSE: dict[str, str] = {}
for canonical, aliases in TECH_ALIASES.items():
    for alias in aliases:
        ALIAS_REVERSE[alias.lower()] = canonical.lower()
    ALIAS_REVERSE[canonical.lower()] = canonical.lower()


# ═══════════════════════════════════════════════════════════════
#  Data Structures
# ═══════════════════════════════════════════════════════════════

@dataclass
class KeywordMatch:
    """Result of checking a single keyword against CV text."""
    keyword: str
    canonical: str
    found: bool
    count: int = 0
    is_must_have: bool = False
    sections_found_in: list[str] = field(default_factory=list)
    variations_checked: list[str] = field(default_factory=list)


@dataclass
class ATSReport:
    """Complete ATS scoring report."""
    overall_score: float = 0.0
    grade: str = "F"
    grade_label: str = "Poor"

    # Breakdown scores (0-100 each)
    keyword_match_score: float = 0.0
    must_have_score: float = 0.0
    nice_to_have_score: float = 0.0
    density_score: float = 0.0
    coverage_score: float = 0.0

    # Keyword details
    total_keywords_checked: int = 0
    keywords_found: int = 0
    keywords_missing: int = 0
    must_haves_found: int = 0
    must_haves_total: int = 0

    # Per-keyword analysis
    matched_keywords: list[KeywordMatch] = field(default_factory=list)
    missing_keywords: list[KeywordMatch] = field(default_factory=list)

    # Recommendations
    recommendations: list[str] = field(default_factory=list)

    # Raw details
    keyword_density_pct: float = 0.0
    cv_word_count: int = 0

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "overall_score": round(self.overall_score, 1),
            "grade": self.grade,
            "grade_label": self.grade_label,
            "scores": {
                "keyword_match": round(self.keyword_match_score, 1),
                "must_have": round(self.must_have_score, 1),
                "nice_to_have": round(self.nice_to_have_score, 1),
                "density": round(self.density_score, 1),
                "section_coverage": round(self.coverage_score, 1),
            },
            "keywords": {
                "total_checked": self.total_keywords_checked,
                "found": self.keywords_found,
                "missing": self.keywords_missing,
                "must_haves_found": self.must_haves_found,
                "must_haves_total": self.must_haves_total,
            },
            "matched": [
                {
                    "keyword": km.keyword,
                    "count": km.count,
                    "is_must_have": km.is_must_have,
                    "sections": km.sections_found_in,
                }
                for km in self.matched_keywords
            ],
            "missing": [
                {
                    "keyword": km.keyword,
                    "is_must_have": km.is_must_have,
                }
                for km in self.missing_keywords
            ],
            "recommendations": self.recommendations,
            "details": {
                "keyword_density_pct": round(self.keyword_density_pct, 2),
                "cv_word_count": self.cv_word_count,
            },
        }


# ═══════════════════════════════════════════════════════════════
#  ATS Scorer Implementation
# ═══════════════════════════════════════════════════════════════

class ATSScorer:
    """
    Simulates ATS keyword scanning and scoring.
    
    Usage:
        scorer = ATSScorer()
        report = scorer.score(
            cv_text="Full text of the tailored CV...",
            parsed_jd=parsed_job_description,
        )
        print(f"ATS Score: {report.overall_score}/100 ({report.grade})")
    """

    # Weight distribution for the overall score
    WEIGHT_MUST_HAVE = 0.40      # 40% — Must-have keywords
    WEIGHT_KEYWORD_MATCH = 0.25  # 25% — Overall keyword presence
    WEIGHT_NICE_TO_HAVE = 0.15   # 15% — Nice-to-have keywords
    WEIGHT_COVERAGE = 0.10       # 10% — Section coverage spread
    WEIGHT_DENSITY = 0.10        # 10% — Healthy keyword density

    # Density thresholds
    IDEAL_DENSITY_MIN = 2.0  # Minimum healthy keyword density %
    IDEAL_DENSITY_MAX = 6.0  # Maximum before it looks like stuffing
    STUFFING_THRESHOLD = 8.0 # Definite keyword stuffing

    def score(
        self,
        cv_text: str,
        parsed_jd: ParsedJobDescription,
        cv_sections: Optional[dict[str, str]] = None,
    ) -> ATSReport:
        """
        Score a CV against a parsed job description.
        
        Args:
            cv_text: The full text of the CV (tailored version)
            parsed_jd: Structured job requirements from JDParser
            cv_sections: Optional dict of {section_name: section_text} for 
                        coverage analysis. If not provided, we try to auto-detect.
                        
        Returns:
            ATSReport with detailed scoring breakdown
        """
        report = ATSReport()
        report.cv_word_count = len(cv_text.split())

        # ── Auto-detect sections if not provided ─────────────
        if not cv_sections:
            cv_sections = self._auto_detect_sections(cv_text)

        # ── Build keyword list to check ──────────────────────
        keywords_to_check = self._build_keyword_list(parsed_jd)
        report.total_keywords_checked = len(keywords_to_check)

        # ── Check each keyword ───────────────────────────────
        cv_lower = cv_text.lower()
        total_keyword_occurrences = 0

        for kw_check in keywords_to_check:
            match = self._check_keyword(kw_check, cv_lower, cv_sections)
            total_keyword_occurrences += match.count

            if match.found:
                report.matched_keywords.append(match)
                report.keywords_found += 1
                if match.is_must_have:
                    report.must_haves_found += 1
            else:
                report.missing_keywords.append(match)
                report.keywords_missing += 1

        report.must_haves_total = sum(1 for k in keywords_to_check if k.is_must_have)

        # ── Calculate sub-scores ─────────────────────────────

        # 1. Must-have score
        if report.must_haves_total > 0:
            report.must_have_score = (report.must_haves_found / report.must_haves_total) * 100
        else:
            report.must_have_score = 100.0

        # 2. Overall keyword match score
        if report.total_keywords_checked > 0:
            report.keyword_match_score = (report.keywords_found / report.total_keywords_checked) * 100
        else:
            report.keyword_match_score = 100.0

        # 3. Nice-to-have score
        nice_total = sum(1 for k in keywords_to_check if not k.is_must_have)
        nice_found = sum(1 for m in report.matched_keywords if not m.is_must_have)
        if nice_total > 0:
            report.nice_to_have_score = (nice_found / nice_total) * 100
        else:
            report.nice_to_have_score = 100.0

        # 4. Keyword density score
        if report.cv_word_count > 0:
            report.keyword_density_pct = (total_keyword_occurrences / report.cv_word_count) * 100
            report.density_score = self._score_density(report.keyword_density_pct)
        else:
            report.density_score = 0.0

        # 5. Section coverage score
        report.coverage_score = self._score_coverage(report.matched_keywords)

        # ── Calculate overall score ──────────────────────────
        report.overall_score = (
            report.must_have_score * self.WEIGHT_MUST_HAVE +
            report.keyword_match_score * self.WEIGHT_KEYWORD_MATCH +
            report.nice_to_have_score * self.WEIGHT_NICE_TO_HAVE +
            report.coverage_score * self.WEIGHT_COVERAGE +
            report.density_score * self.WEIGHT_DENSITY
        )

        # ── Assign grade ─────────────────────────────────────
        report.grade, report.grade_label = self._assign_grade(report.overall_score)

        # ── Generate recommendations ─────────────────────────
        report.recommendations = self._generate_recommendations(report, parsed_jd)

        logger.info(
            f"📊 ATS Score: {report.overall_score:.1f}/100 ({report.grade}) | "
            f"Must-haves: {report.must_haves_found}/{report.must_haves_total} | "
            f"Keywords: {report.keywords_found}/{report.total_keywords_checked}"
        )

        return report

    def _build_keyword_list(self, parsed_jd: ParsedJobDescription) -> list[KeywordMatch]:
        """Build the complete list of keywords to check against the CV."""
        keywords: list[KeywordMatch] = []
        seen_canonicals: set[str] = set()

        # Priority keywords (from JD parser) — these are the most important
        for kw in parsed_jd.priority_keywords:
            canonical = self._canonicalize(kw)
            if canonical not in seen_canonicals:
                seen_canonicals.add(canonical)
                keywords.append(KeywordMatch(
                    keyword=kw,
                    canonical=canonical,
                    found=False,
                    is_must_have=kw.lower() in {m.lower() for m in parsed_jd.must_have_skills},
                    variations_checked=self._get_variations(kw),
                ))

        # Must-have skills not already in priority keywords
        for skill in parsed_jd.must_have_skills:
            canonical = self._canonicalize(skill)
            if canonical not in seen_canonicals:
                seen_canonicals.add(canonical)
                keywords.append(KeywordMatch(
                    keyword=skill,
                    canonical=canonical,
                    found=False,
                    is_must_have=True,
                    variations_checked=self._get_variations(skill),
                ))

        # Tech stack items
        tech = parsed_jd.tech_stack
        for category_items in [tech.languages, tech.frameworks, tech.databases, tech.tools, tech.cloud]:
            for item in category_items:
                canonical = self._canonicalize(item)
                if canonical not in seen_canonicals:
                    seen_canonicals.add(canonical)
                    keywords.append(KeywordMatch(
                        keyword=item,
                        canonical=canonical,
                        found=False,
                        is_must_have=item.lower() in {m.lower() for m in parsed_jd.must_have_skills},
                        variations_checked=self._get_variations(item),
                    ))

        # Nice-to-have skills
        for skill in parsed_jd.nice_to_have_skills:
            canonical = self._canonicalize(skill)
            if canonical not in seen_canonicals:
                seen_canonicals.add(canonical)
                keywords.append(KeywordMatch(
                    keyword=skill,
                    canonical=canonical,
                    found=False,
                    is_must_have=False,
                    variations_checked=self._get_variations(skill),
                ))

        # Soft skills
        for skill in parsed_jd.soft_skills:
            canonical = self._canonicalize(skill)
            if canonical not in seen_canonicals:
                seen_canonicals.add(canonical)
                keywords.append(KeywordMatch(
                    keyword=skill,
                    canonical=canonical,
                    found=False,
                    is_must_have=False,
                    variations_checked=self._get_variations(skill),
                ))

        return keywords

    def _check_keyword(
        self,
        kw: KeywordMatch,
        cv_lower: str,
        sections: dict[str, str],
    ) -> KeywordMatch:
        """Check if a keyword (or any of its variations) appears in the CV."""
        all_variations = [kw.keyword.lower()] + [v.lower() for v in kw.variations_checked]
        # De-duplicate
        all_variations = list(dict.fromkeys(all_variations))

        total_count = 0
        found_in_sections: set[str] = set()

        for variation in all_variations:
            # Use word boundary matching for short terms
            if len(variation) <= 3:
                pattern = rf'\b{re.escape(variation)}\b'
            else:
                pattern = re.escape(variation)

            # Check full CV
            matches = re.findall(pattern, cv_lower, re.IGNORECASE)
            total_count += len(matches)

            # Check which sections contain it
            for sec_name, sec_text in sections.items():
                if re.search(pattern, sec_text.lower(), re.IGNORECASE):
                    found_in_sections.add(sec_name)

        kw.found = total_count > 0
        kw.count = total_count
        kw.sections_found_in = list(found_in_sections)
        return kw

    def _canonicalize(self, keyword: str) -> str:
        """Get the canonical form of a keyword."""
        lower = keyword.lower().strip()
        return ALIAS_REVERSE.get(lower, lower)

    def _get_variations(self, keyword: str) -> list[str]:
        """Get all known variations/aliases of a keyword."""
        lower = keyword.lower().strip()
        canonical = ALIAS_REVERSE.get(lower, lower)

        variations = set()
        # Add the canonical form
        variations.add(canonical)

        # Add all aliases for this canonical form
        if canonical in TECH_ALIASES:
            variations.update(v.lower() for v in TECH_ALIASES[canonical])

        # Check if the keyword itself is an alias
        for canon, aliases in TECH_ALIASES.items():
            if lower in [a.lower() for a in aliases]:
                variations.add(canon)
                variations.update(a.lower() for a in aliases)

        variations.discard(lower)
        return list(variations)

    def _auto_detect_sections(self, cv_text: str) -> dict[str, str]:
        """Auto-detect CV sections based on common headings."""
        sections: dict[str, str] = {}
        current_section = "header"
        current_text: list[str] = []

        section_patterns = [
            r'(?i)^#{1,3}\s*(.+)$',           # Markdown headings
            r'(?i)^([A-Z][A-Z\s&]+)$',        # ALL CAPS HEADINGS
            r'(?i)^(summary|skills|experience|education|projects|certifications|technical)\s*:?\s*$',
        ]

        for line in cv_text.split('\n'):
            is_heading = False
            for pattern in section_patterns:
                match = re.match(pattern, line.strip())
                if match:
                    # Save previous section
                    if current_text:
                        sections[current_section] = '\n'.join(current_text)
                    current_section = match.group(1).strip().lower()
                    current_text = []
                    is_heading = True
                    break

            if not is_heading:
                current_text.append(line)

        # Save last section
        if current_text:
            sections[current_section] = '\n'.join(current_text)

        # If no sections detected, treat whole CV as one section
        if len(sections) <= 1:
            sections = {"full_cv": cv_text}

        return sections

    def _score_density(self, density_pct: float) -> float:
        """
        Score keyword density (0-100).
        Ideal range: 2-6%. Below = missing keywords. Above = stuffing.
        """
        if density_pct < 1.0:
            return 20.0  # Very few keywords
        elif density_pct < self.IDEAL_DENSITY_MIN:
            # Linear scale up to ideal min
            return 20.0 + (density_pct / self.IDEAL_DENSITY_MIN) * 60.0
        elif density_pct <= self.IDEAL_DENSITY_MAX:
            return 100.0  # Sweet spot
        elif density_pct <= self.STUFFING_THRESHOLD:
            # Start penalizing
            overage = density_pct - self.IDEAL_DENSITY_MAX
            range_size = self.STUFFING_THRESHOLD - self.IDEAL_DENSITY_MAX
            return 100.0 - (overage / range_size) * 40.0
        else:
            # Severe penalty for keyword stuffing
            return max(20.0, 60.0 - (density_pct - self.STUFFING_THRESHOLD) * 10.0)

    def _score_coverage(self, matched: list[KeywordMatch]) -> float:
        """
        Score how well keywords are distributed across CV sections.
        Bonus for keywords appearing in multiple sections.
        """
        if not matched:
            return 0.0

        multi_section_count = sum(1 for m in matched if len(m.sections_found_in) >= 2)
        single_section_count = sum(1 for m in matched if len(m.sections_found_in) == 1)

        total = len(matched)
        if total == 0:
            return 0.0

        # Multi-section presence is better (keyword reinforcement)
        score = ((single_section_count * 0.7 + multi_section_count * 1.0) / total) * 100
        return min(score, 100.0)

    def _assign_grade(self, score: float) -> tuple[str, str]:
        """Assign a letter grade from the score."""
        if score >= 90:
            return "A+", "Excellent — High ATS pass probability"
        elif score >= 80:
            return "A", "Strong — Should pass most ATS systems"
        elif score >= 70:
            return "B+", "Good — Competitive match rate"
        elif score >= 60:
            return "B", "Fair — May get filtered by strict ATS"
        elif score >= 50:
            return "C", "Below Average — Missing key requirements"
        elif score >= 40:
            return "D", "Weak — Significant keyword gaps"
        else:
            return "F", "Poor — Likely auto-rejected by ATS"

    def _generate_recommendations(
        self, report: ATSReport, parsed_jd: ParsedJobDescription
    ) -> list[str]:
        """Generate actionable recommendations based on the score."""
        recs: list[str] = []

        # ── Missing must-haves ───────────────────────────────
        missing_musts = [m for m in report.missing_keywords if m.is_must_have]
        if missing_musts:
            must_list = ", ".join(m.keyword for m in missing_musts[:5])
            recs.append(
                f"🚨 CRITICAL: Add these must-have keywords to your CV: {must_list}. "
                f"ATS systems will likely reject without them."
            )

        # ── Missing nice-to-haves ────────────────────────────
        missing_nices = [m for m in report.missing_keywords if not m.is_must_have]
        if missing_nices and len(missing_nices) <= 5:
            nice_list = ", ".join(m.keyword for m in missing_nices[:5])
            recs.append(
                f"💡 Consider adding: {nice_list} — these bonus keywords could improve your ranking."
            )

        # ── Density issues ───────────────────────────────────
        if report.keyword_density_pct < self.IDEAL_DENSITY_MIN:
            recs.append(
                f"📉 Keyword density is low ({report.keyword_density_pct:.1f}%). "
                f"Naturally weave more technical terms into your project descriptions."
            )
        elif report.keyword_density_pct > self.STUFFING_THRESHOLD:
            recs.append(
                f"⚠️ Keyword density is too high ({report.keyword_density_pct:.1f}%). "
                f"Reduce repetition to avoid ATS spam detection."
            )

        # ── Coverage issues ──────────────────────────────────
        single_section_only = [
            m for m in report.matched_keywords
            if len(m.sections_found_in) == 1 and m.is_must_have
        ]
        if single_section_only:
            kw_list = ", ".join(m.keyword for m in single_section_only[:3])
            recs.append(
                f"📋 Keywords [{kw_list}] only appear in one section. "
                f"Reinforce them in your Summary AND Project Experience for better ATS matching."
            )

        # ── Positive feedback ────────────────────────────────
        if report.overall_score >= 80:
            recs.append(
                "✅ Strong match! Your CV aligns well with this job description."
            )
        if report.must_have_score == 100:
            recs.append(
                "🎯 All must-have keywords present — excellent ATS compatibility."
            )

        # ── General advice ───────────────────────────────────
        if report.cv_word_count < 250:
            recs.append(
                "📄 Your CV seems short. Consider adding more detail to your project "
                "descriptions with measurable outcomes."
            )
        elif report.cv_word_count > 1200:
            recs.append(
                "📄 Your CV is quite long. Consider trimming to keep it concise "
                "and ATS-friendly (ideally under 1000 words for a 1-page CV)."
            )

        return recs

    def quick_score(self, cv_text: str, keywords: list[str]) -> float:
        """
        Quick score without a full ParsedJobDescription.
        Just checks what percentage of the given keywords are present.
        Returns 0-100.
        """
        if not keywords:
            return 100.0

        cv_lower = cv_text.lower()
        found = 0

        for kw in keywords:
            variations = [kw.lower()] + [v.lower() for v in self._get_variations(kw)]
            for v in variations:
                if len(v) <= 3:
                    pattern = rf'\b{re.escape(v)}\b'
                else:
                    pattern = re.escape(v)
                if re.search(pattern, cv_lower, re.IGNORECASE):
                    found += 1
                    break

        return (found / len(keywords)) * 100
