"""
Keyword Intelligence — Centralized keyword tiering and optimization config
for the CV Tailoring pipeline.

Based on real-world application data:
  - Tier 1 keywords → 100% interview conversion (3/3)
  - Tier 3/4 keywords → 0% interview conversion (0/7)

This module provides:
  1. KEYWORD_TIERS: Ranked keyword classification
  2. BANNED_TITLE_WORDS: Words that actively hurt positioning
  3. TITLE_UPGRADES: Mapping from generic→specific titles
  4. classify_keywords(): Score and classify any keyword list
  5. optimize_keyword_order(): Reorder keywords by interview signal
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Keyword Tier Classification
# ═══════════════════════════════════════════════════════════════
#
#  Based on empirical data from 10 applications:
#    Tier 1 → 3 interviews / 3 applications  (100% conversion)
#    Tier 3 → 0 interviews / 5 applications  (0% conversion)
#    Tier 4 → 0 interviews / 2 applications  (0% conversion, negative signal)
#
#  The pattern: Domain-specific + architecture-level terms differentiate.
#  Generic development terms commoditize. Junior signals disqualify.

KEYWORD_TIERS = {
    # ─── TIER 1: Interview Triggers (100% conversion rate) ────
    # Domain-specific, architecture-level. Very few candidates use these.
    # Using them signals: "I build real systems, not tutorials."
    1: {
        "label": "Interview Triggers",
        "conversion_rate": "100%",
        "strategy": "ALWAYS use in summary, title, and first bullet of each project",
        "keywords": [
            # AI / ML
            "Agentic AI", "LangChain", "RAG pipelines", "prompt engineering",
            "LLM orchestration", "inference optimization", "multi-agent systems",
            "retrieval-augmented generation", "vector databases", "embeddings",
            "fine-tuning", "model serving",
            # Architecture
            "event-driven architecture", "distributed systems", "scalability",
            "containerized microservices", "service mesh", "message queues",
            "CQRS", "domain-driven design",
            # DevOps / Platform
            "CI/CD orchestration", "observability", "infrastructure as code",
            "Kubernetes", "container orchestration", "blue-green deployment",
            # Data
            "real-time data pipelines", "stream processing", "data mesh",
            "ETL orchestration",
            # Performance
            "sub-200ms latency", "horizontal scaling", "load balancing",
            "caching strategies", "connection pooling",
        ],
    },

    # ─── TIER 2: Solid Differentiators (moderate conversion) ──
    # Good tech skills. Worth mentioning in skills and project bullets.
    # Not strong enough for the summary lead.
    2: {
        "label": "Solid Differentiators",
        "conversion_rate": "30-50%",
        "strategy": "Use in skills section and project descriptions, not in summary lead",
        "keywords": [
            "React", "Python", "FastAPI", "MongoDB", "Docker", "TypeScript",
            "Node.js", "PostgreSQL", "Redis", "GraphQL", "WebSocket",
            "Socket.IO", "Next.js", "Express.js", "Tailwind CSS",
            "JWT authentication", "OAuth 2.0", "Playwright", "Selenium",
            "GitHub Actions", "Terraform", "AWS", "GCP", "Azure",
        ],
    },

    # ─── TIER 3: Zero Differentiation (0% conversion alone) ──
    # Every single applicant lists these. Using them in the summary
    # or title provides ZERO competitive advantage.
    3: {
        "label": "Zero Differentiation",
        "conversion_rate": "0% standalone",
        "strategy": "NEVER use in summary or title. OK in additional skills only",
        "keywords": [
            "Full-Stack Developer", "Full Stack", "HTML", "CSS", "Git",
            "GitHub", "REST API", "RESTful", "Agile", "Scrum",
            "team player", "problem solver", "Microsoft Office",
            "responsive design", "cross-browser", "version control",
            "JIRA", "Trello", "Slack", "communication skills",
        ],
    },

    # ─── TIER 4: Negative Signals (actively hurts) ────────────
    # These words trigger instant deprioritization by recruiters.
    # They signal inexperience and lack of professional framing.
    4: {
        "label": "Negative Signals",
        "conversion_rate": "NEGATIVE — hurts positioning",
        "strategy": "NEVER use anywhere. Actively remove if detected",
        "keywords": [
            "Student", "beginner", "junior developer", "entry-level",
            "familiar with", "basic knowledge", "exposure to",
            "learning", "aspiring", "passionate about", "eager to learn",
            "self-taught", "hobby project", "coursework", "assignment",
            "undergraduate project", "school project", "tutorial",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════
#  Title Mappings
# ═══════════════════════════════════════════════════════════════

# Generic titles that should NEVER appear in the CV summary lead
BANNED_TITLE_OPENERS = [
    "Full-Stack Developer",
    "Full Stack Developer",
    "Web Developer",
    "Software Developer",  # Too generic — use specific domain
    "Junior Developer",
    "Student Developer",
    "Aspiring Engineer",
]

# Better title alternatives based on JD domain
TITLE_UPGRADES = {
    # JD keyword → upgraded title
    "ai": "AI Systems Engineer",
    "ml": "ML Engineer",
    "machine learning": "ML & Data Engineer",
    "langchain": "AI Engineer | LangChain & LLM Systems",
    "llm": "AI Engineer | LLM Integration Specialist",
    "data": "Data & Platform Engineer",
    "frontend": "Frontend Engineer | React & TypeScript",
    "react": "Frontend Engineer | React Specialist",
    "backend": "Backend Engineer | Python & Node.js",
    "devops": "DevOps & Platform Engineer",
    "cloud": "Cloud & Infrastructure Engineer",
    "security": "Security-Focused Software Engineer",
    "mobile": "Mobile & Cross-Platform Developer",
    "blockchain": "Blockchain & Distributed Systems Engineer",
    "game": "Game Systems Developer",
    # Default (when no specific domain match)
    "_default": "Software Engineer",
}


# ═══════════════════════════════════════════════════════════════
#  Keyword Classification Engine
# ═══════════════════════════════════════════════════════════════

def classify_keyword(keyword: str) -> dict:
    """
    Classify a single keyword by tier.

    Returns:
        {"keyword": str, "tier": int, "label": str, "strategy": str}
    """
    kw_lower = keyword.lower().strip()

    for tier_num, tier_data in KEYWORD_TIERS.items():
        for tier_kw in tier_data["keywords"]:
            if kw_lower == tier_kw.lower() or tier_kw.lower() in kw_lower:
                return {
                    "keyword": keyword,
                    "tier": tier_num,
                    "label": tier_data["label"],
                    "strategy": tier_data["strategy"],
                }

    # Default: unclassified → treat as Tier 2
    return {
        "keyword": keyword,
        "tier": 2,
        "label": "Unclassified (treated as Tier 2)",
        "strategy": "Include in skills section, evaluate context for summary use",
    }


def classify_keywords(keywords: list[str]) -> dict:
    """
    Classify a list of keywords by tier.

    Returns:
        {
            "tier_1": [...],  # Interview triggers
            "tier_2": [...],  # Solid differentiators
            "tier_3": [...],  # Zero differentiation
            "tier_4": [...],  # Negative signals
            "summary": {"total": N, "tier_1_count": N, ...}
        }
    """
    result = {f"tier_{i}": [] for i in range(1, 5)}
    for kw in keywords:
        classified = classify_keyword(kw)
        tier_key = f"tier_{classified['tier']}"
        result[tier_key].append(classified)

    result["summary"] = {
        "total": len(keywords),
        "tier_1_count": len(result["tier_1"]),
        "tier_2_count": len(result["tier_2"]),
        "tier_3_count": len(result["tier_3"]),
        "tier_4_count": len(result["tier_4"]),
        "interview_signal_score": _calculate_signal_score(result),
    }

    return result


def optimize_keyword_order(keywords: list[str]) -> list[str]:
    """
    Reorder a list of keywords by interview signal strength.

    Tier 1 first, Tier 4 removed entirely.
    Returns the optimized list.
    """
    classified = [(kw, classify_keyword(kw)["tier"]) for kw in keywords]

    # Remove Tier 4 entirely
    filtered = [(kw, tier) for kw, tier in classified if tier <= 3]

    # Sort: Tier 1 → Tier 2 → Tier 3
    filtered.sort(key=lambda x: x[1])

    return [kw for kw, _ in filtered]


def get_best_title(jd_keywords: list[str], jd_title: str = "") -> str:
    """
    Determine the best professional title based on JD keywords.

    Never returns generic titles like 'Full-Stack Developer'.
    """
    combined = " ".join(jd_keywords + [jd_title]).lower()

    for keyword, title in TITLE_UPGRADES.items():
        if keyword == "_default":
            continue
        if keyword in combined:
            return title

    return TITLE_UPGRADES["_default"]


def _calculate_signal_score(classified: dict) -> float:
    """
    Calculate an interview signal score (0-100) based on keyword tiers.

    Scoring:
      Tier 1 keyword = +15 points (capped at 60)
      Tier 2 keyword = +5 points  (capped at 30)
      Tier 3 keyword = +0 points
      Tier 4 keyword = -10 points (penalty)
    """
    score = 0.0
    score += min(60, len(classified["tier_1"]) * 15)
    score += min(30, len(classified["tier_2"]) * 5)
    score -= len(classified["tier_4"]) * 10
    return max(0, min(100, score))


# ═══════════════════════════════════════════════════════════════
#  Prompt Enhancement
# ═══════════════════════════════════════════════════════════════

def get_keyword_tier_prompt_block() -> str:
    """
    Returns a formatted prompt block with keyword tier instructions.
    Ready to inject into any LLM system prompt.
    """
    return """
KEYWORD PRIORITY TIERS (CRITICAL — this determines interview conversion):

  TIER 1 — INTERVIEW TRIGGERS (100% conversion in our data):
    USE THESE FIRST in summary, title, and project bullets.
    Examples: Agentic AI, LangChain, RAG pipelines, event-driven architecture,
    distributed systems, scalability, containerized microservices, CI/CD
    orchestration, observability, real-time data pipelines, inference optimization,
    prompt engineering, Kubernetes, vector databases.
    → These are RARE keywords that stop a recruiter mid-scroll.

  TIER 2 — SOLID DIFFERENTIATORS (30-50% conversion):
    Use in skills section and project descriptions.
    Examples: React, Python, FastAPI, MongoDB, Docker, TypeScript, Node.js,
    WebSocket, Redis, GraphQL, JWT auth, GitHub Actions.
    → Good tech, but not strong enough to lead a summary.

  TIER 3 — ZERO DIFFERENTIATION (0% conversion alone):
    NEVER use in summary or title. OK only in 'Additional Skills'.
    Examples: Full-Stack, HTML/CSS, Git, REST API, Agile, team player.
    → Every applicant has these. They are invisible to recruiters.

  TIER 4 — NEGATIVE SIGNALS (actively hurts):
    NEVER USE ANYWHERE. Remove if detected.
    Examples: Student, beginner, familiar with, basic knowledge, learning,
    aspiring, coursework, tutorial, hobby project.
    → Instant deprioritization by hiring managers.

RULE: Lead every section with Tier 1 keywords. Suppress Tier 3.
      Eliminate Tier 4. Frame projects as SYSTEMS, not assignments.
"""
