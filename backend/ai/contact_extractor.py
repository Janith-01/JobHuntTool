"""
Contact Extractor — Extracts recipient email, company name, and
generates an email subject line from scraped job posting text.

Two-stage approach:
  Stage 1 (Regex):  Extract emails, infer company from domain/text
  Stage 2 (LLM):    Disambiguate when multiple emails found or company unclear

Usage:
    from backend.ai.contact_extractor import ContactExtractor

    extractor = ContactExtractor()
    result = extractor.extract("... scraped JD text ...")
    # {
    #   "recipient_email": "hr@softvil.com",
    #   "company_name": "Softvil Technologies",
    #   "subject_line": "Application for AI Engineer Intern — Janith Viranga",
    #   "contact_person": "John Doe",
    #   "confidence": "high",
    #   "all_emails_found": ["hr@softvil.com", "info@softvil.com"],
    # }
"""

import re
import json
import logging
from typing import Optional
from pathlib import Path

from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Output Schema
# ═══════════════════════════════════════════════════════════════

class ExtractedContact(BaseModel):
    """Structured output from contact extraction."""
    recipient_email: str = Field(default="", description="Best email to send application to")
    company_name: str = Field(default="", description="Company name")
    subject_line: str = Field(default="", description="Email subject line for application")
    contact_person: str = Field(default="", description="Name of the contact person if found")
    confidence: str = Field(default="low", description="Confidence level: high, medium, low")
    all_emails_found: list[str] = Field(default_factory=list, description="All emails found in text")
    extraction_method: str = Field(default="regex", description="Method used: regex, llm, or hybrid")


# ═══════════════════════════════════════════════════════════════
#  Regex Patterns
# ═══════════════════════════════════════════════════════════════

# RFC 5322-ish email pattern — covers 99% of real-world emails
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

# Patterns indicating an email is for applications (vs generic info)
APPLICATION_EMAIL_HINTS = [
    r'send\s+(?:your\s+)?(?:cv|resume|application)',
    r'apply\s+(?:via|through|to|at)',
    r'submit\s+(?:your\s+)?(?:cv|resume|application)',
    r'email\s+(?:your\s+)?(?:cv|resume|application)',
    r'forward\s+(?:your\s+)?(?:cv|resume)',
    r'applications?\s+(?:to|at|via)',
    r'send\s+to',
    r'contact\s*:',
    r'apply\s+(?:now|here)',
    r'HR\s*(?:department|team|manager)',
]

# Email prefixes that suggest application-related addresses
APPLICATION_PREFIXES = [
    'hr', 'careers', 'jobs', 'recruiting', 'recruitment', 'talent',
    'apply', 'applications', 'hiring', 'people', 'team', 'join',
]

# Email prefixes to deprioritize (generic / support)
LOW_PRIORITY_PREFIXES = [
    'info', 'support', 'help', 'admin', 'contact', 'hello',
    'sales', 'marketing', 'no-reply', 'noreply',
]

# Person name patterns near emails — NOT case-insensitive
# Requires proper capitalization: "Contact: Dilshan Perera"
# Uses [^\S\n] (whitespace excluding newlines) to avoid matching across lines
PERSON_NAME_PATTERN = re.compile(
    r'(?:[Cc]ontact|[Rr]each|[Ee]mail|[Ss]end\s+to|[Aa]ttention|[Aa]ttn)[^\S\n]*:?[^\S\n]*'
    r'([A-Z][a-z]{1,15}[^\S\n]+[A-Z][a-z]{1,15}(?:[^\S\n]+[A-Z][a-z]{1,15})?)',
)

# Words that look like names but aren't (false positive blocklist)
NAME_BLOCKLIST = {
    'email your', 'send your', 'reach out', 'apply now', 'contact us',
    'no direct', 'applications accepted', 'visit our', 'our website',
}

# Company name patterns
COMPANY_PATTERNS = [
    # "Company Name is hiring" / "at Company Name"
    re.compile(r'(?:^|\n)\s*(?:about\s+)?([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+is\s+(?:hiring|looking|seeking))', re.MULTILINE),
    re.compile(r'(?:at|@)\s+([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s*[,\.\n])', re.MULTILINE),
    re.compile(r'(?:company|employer|organization)\s*:\s*([A-Za-z0-9\s&\-\.]+)', re.IGNORECASE),
    re.compile(r'(?:about\s+us|who\s+we\s+are)\s*[:\-—]\s*([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+is\b)', re.IGNORECASE | re.MULTILINE),
    # "Join [Company Name]"
    re.compile(r'join\s+(?:the\s+)?([A-Z][A-Za-z0-9\s&\-\.]+?)(?:\s+team|\s*!|\s*\.\s)', re.IGNORECASE),
]

# Known domain → company name mappings (expandable)
DOMAIN_COMPANY_MAP = {
    'softvil': 'Softvil Technologies',
    'synexis': 'Synexis',
    'wso2': 'WSO2',
    'virtusa': 'Virtusa',
    'sysco': 'Sysco Labs',
    'google': 'Google',
    'microsoft': 'Microsoft',
    'meta': 'Meta',
    'amazon': 'Amazon',
    'apple': 'Apple',
    'netflix': 'Netflix',
    'shopify': 'Shopify',
    'stripe': 'Stripe',
    'uber': 'Uber',
    'airbnb': 'Airbnb',
    'spotify': 'Spotify',
    'slack': 'Slack',
    'gitlab': 'GitLab',
    'github': 'GitHub',
    'atlassian': 'Atlassian',
    'twilio': 'Twilio',
    'cloudflare': 'Cloudflare',
    'vercel': 'Vercel',
    'supabase': 'Supabase',
    'datastax': 'DataStax',
}


# ═══════════════════════════════════════════════════════════════
#  Contact Extractor
# ═══════════════════════════════════════════════════════════════

class ContactExtractor:
    """
    Extracts recipient email, company name, and generates subject line
    from scraped job posting text.

    Usage:
        extractor = ContactExtractor()
        result = extractor.extract(scraped_text, job_title="AI Intern")
        print(result.recipient_email, result.company_name, result.subject_line)
    """

    def __init__(self, candidate_name: Optional[str] = None):
        """
        Args:
            candidate_name: Override candidate name for subject line.
                           Defaults to master_cv.json full_name.
        """
        self.candidate_name = candidate_name or self._load_candidate_name()

    def _load_candidate_name(self) -> str:
        """Load candidate name from master CV."""
        try:
            with open(settings.MASTER_CV_PATH, 'r', encoding='utf-8') as f:
                cv = json.load(f)
            personal = cv.get("personal", cv.get("personal_info", {}))
            return personal.get("full_name", personal.get("name", "Candidate"))
        except Exception:
            return "Candidate"

    # ─────────────────────────────────────────────────────────
    #  Main extraction pipeline
    # ─────────────────────────────────────────────────────────

    def extract(
        self,
        scraped_text: str,
        job_title: str = "",
        company_name_hint: str = "",
        use_llm: bool = True,
    ) -> ExtractedContact:
        """
        Extract contact information from scraped job posting text.

        Args:
            scraped_text: Raw scraped text from the job posting
            job_title: Job title (if already known from scraping)
            company_name_hint: Company name hint (from scraper metadata)
            use_llm: Whether to use LLM for disambiguation

        Returns:
            ExtractedContact with email, company, subject line
        """
        if not scraped_text or not scraped_text.strip():
            return ExtractedContact(
                confidence="low",
                subject_line=self._build_subject_line(job_title, ""),
            )

        logger.info(f"📧 Extracting contact info from text ({len(scraped_text)} chars)")

        # ── Stage 1: Regex extraction ────────────────────────
        all_emails = self._extract_emails(scraped_text)
        best_email, email_confidence = self._rank_emails(all_emails, scraped_text)
        company = self._extract_company_name(scraped_text, best_email, company_name_hint)
        contact_person = self._extract_contact_person(scraped_text, best_email)

        # Determine confidence
        if best_email and company:
            confidence = "high" if email_confidence >= 0.7 else "medium"
        elif best_email:
            confidence = "medium"
        else:
            confidence = "low"

        method = "regex"

        # ── Stage 2: LLM disambiguation (if needed) ─────────
        if use_llm and confidence == "low" and scraped_text.strip():
            try:
                llm_result = self._llm_extract(scraped_text, job_title)
                if llm_result:
                    if llm_result.get("recipient_email") and not best_email:
                        best_email = llm_result["recipient_email"]
                    if llm_result.get("company_name") and not company:
                        company = llm_result["company_name"]
                    if llm_result.get("contact_person") and not contact_person:
                        contact_person = llm_result["contact_person"]
                    confidence = "medium"
                    method = "hybrid"
            except Exception as e:
                logger.warning(f"   LLM extraction failed: {e}")

        # ── Build subject line ───────────────────────────────
        subject_line = self._build_subject_line(job_title, company)

        result = ExtractedContact(
            recipient_email=best_email,
            company_name=company,
            subject_line=subject_line,
            contact_person=contact_person,
            confidence=confidence,
            all_emails_found=all_emails,
            extraction_method=method,
        )

        logger.info(
            f"   ✅ Extracted: email={best_email or 'N/A'}, "
            f"company={company or 'N/A'}, confidence={confidence}"
        )

        return result

    # ─────────────────────────────────────────────────────────
    #  Email extraction & ranking
    # ─────────────────────────────────────────────────────────

    def _extract_emails(self, text: str) -> list[str]:
        """Find all unique email addresses in text."""
        raw = EMAIL_PATTERN.findall(text)

        # Deduplicate while preserving order, lowercase
        seen = set()
        emails = []
        for email in raw:
            lower = email.lower().strip()
            # Filter obvious non-emails
            if (
                lower not in seen
                and not lower.endswith('.png')
                and not lower.endswith('.jpg')
                and not lower.endswith('.svg')
                and '@' in lower
                and len(lower) > 5
            ):
                seen.add(lower)
                emails.append(lower)

        return emails

    def _rank_emails(self, emails: list[str], text: str) -> tuple[str, float]:
        """
        Rank emails by likelihood of being the application recipient.
        Returns (best_email, confidence_score).
        """
        if not emails:
            return "", 0.0

        if len(emails) == 1:
            return emails[0], 0.8  # Single email = likely the right one

        scores = {}
        text_lower = text.lower()

        for email in emails:
            score = 0.0
            prefix = email.split('@')[0].lower()
            domain = email.split('@')[1].lower() if '@' in email else ''

            # 1. Application-related prefix → high score
            if any(prefix.startswith(p) for p in APPLICATION_PREFIXES):
                score += 0.4

            # 2. Low-priority prefix → penalize
            if any(prefix.startswith(p) for p in LOW_PRIORITY_PREFIXES):
                score -= 0.2

            # 3. Near application-related language
            email_pos = text_lower.find(email)
            if email_pos >= 0:
                context_window = text_lower[max(0, email_pos - 200):email_pos + 100]
                for hint_pattern in APPLICATION_EMAIL_HINTS:
                    if re.search(hint_pattern, context_window, re.IGNORECASE):
                        score += 0.3
                        break

            # 4. Personal name prefix (e.g. john.doe@) slightly higher than generic
            if re.match(r'^[a-z]+\.[a-z]+$', prefix):
                score += 0.1

            # 5. Non-free-provider domain → business email (good)
            free_providers = ['gmail', 'yahoo', 'hotmail', 'outlook', 'protonmail']
            if not any(fp in domain for fp in free_providers):
                score += 0.15

            scores[email] = score

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_email = ranked[0][0]
        best_score = max(0.3, min(1.0, ranked[0][1] + 0.5))  # Normalize to 0.3-1.0

        return best_email, best_score

    # ─────────────────────────────────────────────────────────
    #  Company name extraction
    # ─────────────────────────────────────────────────────────

    def _extract_company_name(
        self, text: str, email: str, hint: str
    ) -> str:
        """Extract company name from text, email domain, and hints."""

        # Priority 1: Use the provided hint if available
        if hint and hint.strip():
            return hint.strip()

        # Priority 2: Infer from email domain
        if email:
            domain = email.split('@')[1] if '@' in email else ''
            domain_parts = domain.split('.')
            if domain_parts:
                base_domain = domain_parts[0].lower()
                # Check known mapping
                if base_domain in DOMAIN_COMPANY_MAP:
                    return DOMAIN_COMPANY_MAP[base_domain]
                # Capitalize the domain as a fallback company name
                if base_domain not in ['gmail', 'yahoo', 'hotmail', 'outlook', 'protonmail', 'aol']:
                    # Try to find a better name in the text
                    text_company = self._find_company_in_text(text, base_domain)
                    if text_company:
                        return text_company
                    return base_domain.capitalize()

        # Priority 3: Regex patterns in text
        for pattern in COMPANY_PATTERNS:
            match = pattern.search(text)
            if match:
                name = match.group(1).strip()
                # Clean up common suffixes
                name = re.sub(r'\s+(Pvt|Private|Ltd|Limited|Inc|LLC|Corp|Corporation)\s*\.?\s*$', '', name, flags=re.IGNORECASE).strip()
                if len(name) > 2 and len(name) < 60:
                    return name

        return ""

    def _find_company_in_text(self, text: str, domain_hint: str) -> str:
        """Try to find the full company name in text given a domain hint."""
        # Look for the domain word in context
        pattern = re.compile(
            rf'\b({re.escape(domain_hint)}[A-Za-z0-9\s]*?(?:Technologies|Tech|Labs|Solutions|Software|Systems|Digital|Group|Corp|Inc)?)\b',
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            found = match.group(1).strip()
            if len(found) > len(domain_hint):
                # Capitalize words
                return ' '.join(w.capitalize() for w in found.split())
        return ""

    # ─────────────────────────────────────────────────────────
    #  Contact person extraction
    # ─────────────────────────────────────────────────────────

    def _extract_contact_person(self, text: str, email: str) -> str:
        """Try to extract the contact person's name."""
        # Method 1: Explicit "Contact: Name" patterns
        match = PERSON_NAME_PATTERN.search(text)
        if match:
            name = match.group(1).strip()
            # Verify it looks like an actual name (not a false positive)
            name_lower = name.lower()
            is_blocked = any(blocked in name_lower for blocked in NAME_BLOCKLIST)
            if not is_blocked and 4 < len(name) < 40:
                return name

        # Method 2: Infer from email prefix like "john.doe@company.com"
        if email:
            prefix = email.split('@')[0]
            parts = re.split(r'[._\-]', prefix)
            if len(parts) >= 2:
                # Check if parts look like name components (all alpha, reasonable length)
                if all(p.isalpha() and 2 <= len(p) <= 15 for p in parts[:2]):
                    # Filter out common non-name prefixes
                    non_names = {'hr', 'info', 'jobs', 'careers', 'admin', 'team',
                                 'support', 'contact', 'hello', 'apply', 'hiring',
                                 'recruitment', 'recruiting', 'talent', 'people'}
                    if parts[0].lower() not in non_names:
                        return ' '.join(p.capitalize() for p in parts[:2])

        return ""

    # ─────────────────────────────────────────────────────────
    #  Subject line generation
    # ─────────────────────────────────────────────────────────

    def _build_subject_line(self, job_title: str, company: str) -> str:
        """Generate a professional email subject line."""
        title = job_title.strip() if job_title else "Software Engineer"
        name = self.candidate_name

        if company:
            return f"Application for {title} — {name}"
        return f"Application for {title} — {name}"

    # ─────────────────────────────────────────────────────────
    #  LLM fallback
    # ─────────────────────────────────────────────────────────

    def _llm_extract(self, text: str, job_title: str) -> Optional[dict]:
        """Use LLM to extract contact info when regex fails."""
        from backend.ai.llm_client import invoke_llm

        prompt = f"""Extract the recipient email address and company name from this job posting.

**Job Posting Text (first 2000 chars):**
{text[:2000]}

---

Respond with JSON only:
{{
    "recipient_email": "email@company.com or empty string if not found",
    "company_name": "Company Name or empty string",
    "contact_person": "Person's name or empty string"
}}"""

        system = (
            "You are an expert at extracting contact information from job postings. "
            "Only extract what is explicitly stated — do not guess or fabricate. "
            "If you cannot find an email, return an empty string."
        )

        try:
            raw = invoke_llm(
                system_prompt=system,
                user_prompt=prompt,
                temperature=0.0,
            )
            # Parse JSON from response
            json_match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"LLM contact extraction failed: {e}")

        return None


# ═══════════════════════════════════════════════════════════════
#  Convenience function
# ═══════════════════════════════════════════════════════════════

def extract_contact_from_text(
    text: str,
    job_title: str = "",
    company_hint: str = "",
    use_llm: bool = False,
) -> dict:
    """
    Quick convenience function for extracting contact info.

    Returns a dict with: recipient_email, company_name, subject_line, etc.
    """
    extractor = ContactExtractor()
    result = extractor.extract(text, job_title, company_hint, use_llm)
    return result.model_dump()
