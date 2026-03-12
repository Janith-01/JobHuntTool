"""
Job Description Parser — Extracts structured requirements from raw JD text.

Uses a two-stage approach:
  1. Regex-based extraction for common patterns (fast, no API call)
  2. LLM-powered deep extraction for nuance & context (Gemini)

The parser identifies:
  - Technical skills (languages, frameworks, databases, tools, cloud)
  - Soft skills & requirements
  - Experience level expectations
  - Key responsibilities that can be mapped to CV bullet points
  - Priority keywords for ATS optimization
"""

import re
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

from backend.ai.llm_client import invoke_llm, invoke_llm_structured

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Structured Output Schemas
# ═══════════════════════════════════════════════════════════════

class ExtractedTechStack(BaseModel):
    """Technology stack extracted by the AI parser."""
    languages: list[str] = Field(default_factory=list, description="Programming languages mentioned (e.g. Python, JavaScript, TypeScript, Java, C++)")
    frameworks: list[str] = Field(default_factory=list, description="Frameworks and libraries (e.g. React, Django, FastAPI, Spring Boot, TensorFlow)")
    databases: list[str] = Field(default_factory=list, description="Database technologies (e.g. MongoDB, PostgreSQL, Redis, Elasticsearch)")
    tools: list[str] = Field(default_factory=list, description="DevOps, CI/CD, and tooling (e.g. Docker, Kubernetes, Git, Jenkins, Terraform)")
    cloud: list[str] = Field(default_factory=list, description="Cloud platforms and services (e.g. AWS, GCP, Azure, Vercel, Firebase)")
    methodologies: list[str] = Field(default_factory=list, description="Methodologies (e.g. Agile, Scrum, TDD, CI/CD)")


class ParsedRequirement(BaseModel):
    """A single parsed requirement with priority classification."""
    text: str = Field(..., description="The requirement text")
    category: str = Field(..., description="Category: 'must_have', 'nice_to_have', or 'bonus'")
    keywords: list[str] = Field(default_factory=list, description="Key technical terms in this requirement")


class ParsedJobDescription(BaseModel):
    """Complete structured output from parsing a job description."""
    job_title_normalized: str = Field(..., description="Cleaned, normalized job title")
    seniority_level: str = Field(default="entry", description="Seniority: intern, entry, junior, mid, senior")
    job_type: str = Field(default="full-time", description="Type: intern, full-time, part-time, contract")

    tech_stack: ExtractedTechStack = Field(default_factory=ExtractedTechStack)

    must_have_skills: list[str] = Field(default_factory=list, description="Non-negotiable skills explicitly required")
    nice_to_have_skills: list[str] = Field(default_factory=list, description="Preferred/bonus skills")

    key_responsibilities: list[str] = Field(default_factory=list, description="Primary responsibilities and duties")
    requirements: list[ParsedRequirement] = Field(default_factory=list, description="All requirements with priority")

    soft_skills: list[str] = Field(default_factory=list, description="Soft skills mentioned (e.g. communication, teamwork)")
    education_requirements: list[str] = Field(default_factory=list, description="Education/qualification requirements")

    priority_keywords: list[str] = Field(
        default_factory=list,
        description="Top 15 keywords to maximize in a tailored CV for ATS optimization, ranked by importance"
    )

    company_culture_notes: list[str] = Field(
        default_factory=list,
        description="Notes about company culture, values, or 'why join us' that can be leveraged in a cover letter"
    )

    role_summary: str = Field(default="", description="2-3 sentence summary of the role in your own words")


# ═══════════════════════════════════════════════════════════════
#  Regex-Based Pre-Parser (Stage 1 — No API Call)
# ═══════════════════════════════════════════════════════════════

# Common tech patterns for regex extraction
TECH_PATTERNS = {
    "languages": [
        r'\bPython\b', r'\bJavaScript\b', r'\bTypeScript\b', r'\bJava\b(?!\s*Script)',
        r'\bC\+\+\b', r'\bC#\b', r'\bRust\b', r'\bGo\b(?:lang)?\b', r'\bRuby\b',
        r'\bPHP\b', r'\bSwift\b', r'\bKotlin\b', r'\bScala\b', r'\bR\b(?=\s|,|;|\.|$)',
        r'\bSQL\b', r'\bHTML\d?\b', r'\bCSS\d?\b', r'\bDart\b', r'\bLua\b',
    ],
    "frameworks": [
        r'\bReact(?:\.js|js)?\b', r'\bAngular(?:\.js|js)?\b', r'\bVue(?:\.js|js)?\b',
        r'\bNext\.js\b', r'\bNuxt\.js\b', r'\bSvelte\b', r'\bNode\.js\b', r'\bExpress(?:\.js)?\b',
        r'\bDjango\b', r'\bFlask\b', r'\bFastAPI\b', r'\bSpring\s*Boot\b', r'\bSpring\b',
        r'\bRails\b', r'\bLaravel\b', r'\b\.NET\b', r'\bASP\.NET\b',
        r'\bTensorFlow\b', r'\bPyTorch\b', r'\bKeras\b', r'\bscikit-learn\b',
        r'\bLangChain\b', r'\bHugging\s*Face\b', r'\bOpenAI\b',
        r'\bTailwind\s*(?:CSS)?\b', r'\bBootstrap\b', r'\bMaterial\s*UI\b',
        r'\bjQuery\b', r'\bThree\.js\b', r'\bReact\s*Native\b', r'\bFlutter\b',
        r'\bSocket\.io\b', r'\bGraphQL\b', r'\bREST\s*API\b',
    ],
    "databases": [
        r'\bMongoDB\b', r'\bPostgreSQL\b', r'\bPostgres\b', r'\bMySQL\b',
        r'\bRedis\b', r'\bElasticsearch\b', r'\bCassandra\b', r'\bDynamoDB\b',
        r'\bFirebase\b', r'\bSupabase\b', r'\bSQLite\b', r'\bOracle\b',
        r'\bSQL\s*Server\b', r'\bPinecone\b', r'\bChroma\b', r'\bMilvus\b',
        r'\bNeo4j\b',
    ],
    "tools": [
        r'\bDocker\b', r'\bKubernetes\b', r'\bK8s\b', r'\bJenkins\b',
        r'\bGitHub\s*Actions\b', r'\bCI/CD\b', r'\bTerraform\b', r'\bAnsible\b',
        r'\bGit\b(?!Hub)', r'\bGitHub\b', r'\bGitLab\b', r'\bBitbucket\b',
        r'\bJira\b', r'\bConfluence\b', r'\bFigma\b', r'\bPostman\b',
        r'\bWebpack\b', r'\bVite\b', r'\bNginx\b', r'\bApache\b',
        r'\bLinux\b', r'\bBash\b', r'\bShell\b',
        r'\bPlaywright\b', r'\bSelenium\b', r'\bCypress\b', r'\bJest\b',
        r'\bPytest\b', r'\bMocha\b',
    ],
    "cloud": [
        r'\bAWS\b', r'\bAmazon\s*Web\s*Services\b', r'\bGCP\b',
        r'\bGoogle\s*Cloud\b', r'\bAzure\b', r'\bHeroku\b',
        r'\bVercel\b', r'\bNetlify\b', r'\bDigitalOcean\b',
        r'\bCloudflare\b', r'\bS3\b', r'\bEC2\b', r'\bLambda\b',
    ],
}


def regex_extract_tech(text: str) -> dict[str, list[str]]:
    """
    Stage 1: Fast regex-based tech stack extraction.
    Returns a dict of category -> list of matched technologies.
    """
    result = {}
    for category, patterns in TECH_PATTERNS.items():
        found = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                # Normalize: capitalize properly
                found.add(m.strip())
        result[category] = sorted(found)
    return result


def regex_extract_experience_level(title: str, description: str) -> str:
    """Infer seniority level from title and description patterns."""
    combined = f"{title} {description}".lower()

    if any(kw in combined for kw in ["intern", "internship", "trainee", "apprentice"]):
        return "intern"
    if any(kw in combined for kw in ["junior", "jr.", "entry level", "entry-level", "graduate", "fresh"]):
        return "junior"
    if any(kw in combined for kw in ["senior", "sr.", "lead", "principal", "staff"]):
        return "senior"
    if any(kw in combined for kw in ["mid-level", "mid level", "intermediate", "3+ years", "4+ years", "5+ years"]):
        return "mid"
    return "entry"


# ═══════════════════════════════════════════════════════════════
#  LLM-Powered Deep Parser (Stage 2)
# ═══════════════════════════════════════════════════════════════

JD_PARSER_SYSTEM_PROMPT = """You are an expert HR Technology Analyst and ATS (Applicant Tracking System) specialist.

Your task is to deeply analyze a job description and extract ALL relevant structured information to help a job applicant tailor their CV for maximum ATS compatibility.

CRITICAL INSTRUCTIONS:
1. **Priority Keywords**: Identify the TOP 15 most important keywords that an ATS would scan for. Rank them by importance. Include both the exact terms used AND common synonyms/variations. For example, if "React" is mentioned, also include "React.js" and "ReactJS".

2. **Must-Have vs Nice-to-Have**: Clearly separate absolutely required skills from preferred/bonus skills. Look for language like "required", "must have", "mandatory" vs "preferred", "nice to have", "bonus", "plus".

3. **Tech Stack Extraction**: Be exhaustive. Extract every technology, tool, framework, language, and platform mentioned — even if only briefly.

4. **Responsibilities Mapping**: Extract key responsibilities that a candidate could map to their own experience. Phrase them as action-focused statements.

5. **Company Culture Notes**: Extract any "About Us", "Why Join Us", "Our Culture" content that could be used to personalize a cover letter.

6. **Be precise**: Don't hallucinate technologies not mentioned. Only extract what's actually in the text.

Respond with structured JSON matching the schema provided."""


class JDParser:
    """
    Job Description Parser with two-stage extraction:
      Stage 1: Regex (instant, free)
      Stage 2: LLM deep analysis (Gemini)
    
    Usage:
        parser = JDParser()
        result = parser.parse(job_description_text, job_title="Software Intern")
        # or regex-only for speed:
        quick = parser.quick_parse(text)
    """

    def __init__(self):
        self._cache: dict[str, ParsedJobDescription] = {}

    def quick_parse(self, description: str, title: str = "") -> dict:
        """
        Stage 1 only: Fast regex-based extraction (no API call).
        Good for batch analysis or when API quota is limited.
        """
        tech = regex_extract_tech(description)
        level = regex_extract_experience_level(title, description)

        # Extract requirements-like lines
        requirements = []
        for line in description.split('\n'):
            line = line.strip()
            if line and (
                line.startswith(('•', '-', '●', '▪', '◦', '*', '✓', '→'))
                or re.match(r'^\d+[\.\)]\s', line)
            ):
                clean = re.sub(r'^[•\-●▪◦\*✓→\d\.\)\s]+', '', line).strip()
                if clean and len(clean) > 10:
                    requirements.append(clean)

        # Build flat keyword list from tech extraction
        all_keywords = []
        for category_items in tech.values():
            all_keywords.extend(category_items)

        return {
            "tech_stack": tech,
            "seniority_level": level,
            "requirements": requirements,
            "priority_keywords": all_keywords[:15],
            "method": "regex",
        }

    def parse(
        self,
        description: str,
        title: str = "",
        company_name: str = "",
        use_cache: bool = True,
    ) -> ParsedJobDescription:
        """
        Full two-stage parsing:
          1. Regex pre-scan for baseline tech extraction
          2. LLM deep analysis for nuanced understanding
          
        Returns a ParsedJobDescription with everything the CV tailor needs.
        """
        # Check cache
        cache_key = f"{title}:{description[:200]}"
        if use_cache and cache_key in self._cache:
            logger.debug("📎 Returning cached JD parse result")
            return self._cache[cache_key]

        logger.info(f"🧠 Parsing JD: '{title}' @ {company_name}")

        # ── Stage 1: Regex baseline ──────────────────────────
        regex_result = self.quick_parse(description, title)
        logger.debug(f"   Stage 1 found: {len(regex_result['priority_keywords'])} tech keywords")

        # ── Stage 2: LLM deep extraction ─────────────────────
        user_prompt = self._build_parse_prompt(description, title, company_name, regex_result)

        try:
            parsed: ParsedJobDescription = invoke_llm_structured(
                system_prompt=JD_PARSER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                output_schema=ParsedJobDescription,
                temperature=0.1,  # Low temp for factual extraction
            )

            # Merge regex results into LLM output (regex catches things LLM might miss)
            parsed = self._merge_regex_into_parsed(parsed, regex_result)

            logger.info(
                f"   ✅ Parsed: {len(parsed.must_have_skills)} must-haves, "
                f"{len(parsed.nice_to_have_skills)} nice-to-haves, "
                f"{len(parsed.priority_keywords)} priority keywords"
            )

            # Cache the result
            if use_cache:
                self._cache[cache_key] = parsed

            return parsed

        except Exception as e:
            logger.warning(f"   ⚠️ LLM parsing failed, falling back to regex: {e}")
            return self._regex_to_parsed(regex_result, title, description)

    def _build_parse_prompt(
        self,
        description: str,
        title: str,
        company: str,
        regex_result: dict,
    ) -> str:
        """Build the user prompt for the LLM parser."""
        regex_info = ""
        if regex_result["priority_keywords"]:
            regex_info = (
                f"\n\nPre-scan detected these technologies (verify and expand on these): "
                f"{', '.join(regex_result['priority_keywords'])}"
            )

        return f"""Analyze the following job description in depth.

**Job Title:** {title or 'Not specified'}
**Company:** {company or 'Not specified'}
{regex_info}

---
**FULL JOB DESCRIPTION:**

{description}
---

Extract ALL structured information as specified. Be thorough with the priority_keywords list — 
these will be used to optimize a CV for ATS scanning. Include exact terms from the description."""

    def _merge_regex_into_parsed(
        self, parsed: ParsedJobDescription, regex_result: dict
    ) -> ParsedJobDescription:
        """Merge regex-extracted tech into the LLM-parsed result to ensure completeness."""
        regex_tech = regex_result.get("tech_stack", {})

        for category in ["languages", "frameworks", "databases", "tools", "cloud"]:
            regex_items = set(item.lower() for item in regex_tech.get(category, []))
            parsed_items = set(item.lower() for item in getattr(parsed.tech_stack, category, []))
            missing = regex_items - parsed_items

            if missing:
                current = getattr(parsed.tech_stack, category, [])
                # Add missing items (use the original casing from regex)
                for item in regex_tech.get(category, []):
                    if item.lower() in missing:
                        current.append(item)
                setattr(parsed.tech_stack, category, current)

        # Ensure priority keywords include all tech
        existing_kw = set(kw.lower() for kw in parsed.priority_keywords)
        for kw in regex_result.get("priority_keywords", []):
            if kw.lower() not in existing_kw:
                parsed.priority_keywords.append(kw)
                existing_kw.add(kw.lower())

        return parsed

    def _regex_to_parsed(
        self, regex_result: dict, title: str, description: str
    ) -> ParsedJobDescription:
        """Fallback: Convert regex-only result into a ParsedJobDescription."""
        tech = regex_result.get("tech_stack", {})
        return ParsedJobDescription(
            job_title_normalized=title or "Unknown Position",
            seniority_level=regex_result.get("seniority_level", "entry"),
            tech_stack=ExtractedTechStack(
                languages=tech.get("languages", []),
                frameworks=tech.get("frameworks", []),
                databases=tech.get("databases", []),
                tools=tech.get("tools", []),
                cloud=tech.get("cloud", []),
            ),
            must_have_skills=regex_result.get("priority_keywords", []),
            requirements=[
                ParsedRequirement(text=r, category="must_have", keywords=[])
                for r in regex_result.get("requirements", [])
            ],
            priority_keywords=regex_result.get("priority_keywords", []),
            role_summary=f"Position: {title}" if title else "Role details extracted via regex only.",
        )

    def get_all_tech_keywords(self, parsed: ParsedJobDescription) -> list[str]:
        """Get a flat deduplicated list of all tech keywords from a parsed JD."""
        keywords = set()
        ts = parsed.tech_stack
        for category in [ts.languages, ts.frameworks, ts.databases, ts.tools, ts.cloud, ts.methodologies]:
            keywords.update(item.lower() for item in category)
        keywords.update(kw.lower() for kw in parsed.must_have_skills)
        keywords.update(kw.lower() for kw in parsed.priority_keywords)
        return sorted(keywords)
