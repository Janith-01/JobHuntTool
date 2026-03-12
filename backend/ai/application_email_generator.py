"""
Application Email Generator — Drafts concise, professional 3-paragraph
application emails for job submissions.

Structure (Hook → Proof → CTA):
  1. Hook:  Reference a specific responsibility or skill from the JD.
  2. Proof: Connect it to a concrete project from the master CV.
  3. CTA:   Mention interview availability + attached tailored PDF.

Constraint: No generic phrases like "To whom it may concern" or
"I am a highly motivated individual." Tone is confident, technical, human.

Modes:
  - Template-based (instant, no API cost) — uses keyword matching to pick
    the best project and generates a deterministic email.
  - LLM-powered (Gemini via LangChain) — produces a fully original email
    from the JD + CV context. Requires GEMINI_API_KEY.

Usage:
    from backend.ai.application_email_generator import ApplicationEmailGenerator

    gen = ApplicationEmailGenerator()

    # Template-based (instant)
    email = gen.generate(
        job_title="AI Engineer Intern",
        company_name="Softvil Technologies",
        job_description="...full JD text...",
        contact_person="Dilshan",
    )
    print(email.full_text)

    # LLM-powered (uses Gemini)
    email = gen.generate(
        job_title="AI Engineer Intern",
        company_name="Softvil Technologies",
        job_description="...full JD text...",
        use_llm=True,
    )
"""

import json
import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Output Schema
# ═══════════════════════════════════════════════════════════════

class ApplicationEmail(BaseModel):
    """A generated application email."""
    subject_line: str = Field(..., description="Email subject line")
    greeting: str = Field(default="Hi there,", description="Greeting line")
    hook: str = Field(..., description="Paragraph 1: Hook referencing the JD")
    proof: str = Field(..., description="Paragraph 2: Proof from CV project")
    cta: str = Field(..., description="Paragraph 3: Call to action")
    sign_off: str = Field(default="Best,\nJanith Viranga", description="Sign-off")
    full_text: str = Field(default="", description="Complete assembled email")
    matched_skill: str = Field(default="", description="The JD skill/keyword that triggered the hook")
    matched_project: str = Field(default="", description="The CV project used as proof")
    generation_mode: str = Field(default="template", description="template or llm")


# ═══════════════════════════════════════════════════════════════
#  Skill → Project Mapping
# ═══════════════════════════════════════════════════════════════

# Maps JD keywords/skills → best-matching project from the master CV.
# Each entry: keyword → (project_name_substring, proof_sentence)
SKILL_PROJECT_MAP = {
    # AI / ML / LangChain
    "langchain": (
        "Lawnova",
        "In building Lawnova — an AI-powered legal mock-trial platform — "
        "I designed agentic LangChain workflows that evaluate courtroom "
        "arguments in real time, using structured output parsing and "
        "multi-step reasoning chains.",
    ),
    "ai": (
        "Lawnova",
        "Through Lawnova, my AI-driven legal education platform, I built "
        "argument-evaluation models and integrated LangChain to orchestrate "
        "multi-step reasoning pipelines end to end.",
    ),
    "machine learning": (
        "Lawnova",
        "My work on Lawnova involved building argument evaluation models "
        "and integrating LangChain-based AI pipelines to deliver real-time "
        "feedback during mock courtroom sessions.",
    ),
    "nlp": (
        "Lawnova",
        "Lawnova's core engine uses natural-language processing and LangChain "
        "to parse legal arguments, classify reasoning patterns, and generate "
        "structured courtroom feedback.",
    ),
    # React / Frontend
    "react": (
        "EduTimeSync",
        "As team leader on EduTimeSync, I architected a React-based scheduling "
        "platform with role-based dashboards, automated conflict detection, and "
        "real-time event management — coordinating a 4-person team from design "
        "through deployment.",
    ),
    "frontend": (
        "EduTimeSync",
        "Leading the EduTimeSync project, I built responsive React interfaces "
        "with role-based access control, enabling admins, lecturers, and "
        "coordinators to manage academic schedules seamlessly.",
    ),
    # Full Stack / MERN
    "full stack": (
        "Garage Management",
        "My Garage Management System is a full-stack MERN application with "
        "complete CRUD operations across inventory, customer, supplier, and "
        "financial modules — following MVC architecture and RESTful API design.",
    ),
    "fullstack": (
        "Garage Management",
        "I built a production-grade Garage Management System using the full "
        "MERN stack, implementing RESTful APIs, MVC architecture, and scalable "
        "module separation for six operational domains.",
    ),
    "mern": (
        "Garage Management",
        "The Garage Management project demonstrates my end-to-end MERN "
        "proficiency — from MongoDB schema design and Express middleware to "
        "a React dashboard managing six interconnected business modules.",
    ),
    # Node.js / Backend
    "node": (
        "PipChat",
        "PipChat, my real-time chat application, runs on a Node.js + Express "
        "backend with Socket.IO for instant messaging, JWT-based auth, and "
        "online presence tracking — demonstrating production-grade backend skills.",
    ),
    "express": (
        "PipChat",
        "In building PipChat I designed a Node.js/Express backend handling "
        "WebSocket connections, user authentication, and real-time state "
        "synchronization for concurrent chat sessions.",
    ),
    # WebSocket / Real-time
    "websocket": (
        "Codex",
        "Codex, my collaborative code editor, uses WebSockets and the Monaco "
        "Editor API to synchronize multi-user editing sessions in real time — "
        "similar to Google Docs but optimized for developer workflows.",
    ),
    "real-time": (
        "PipChat",
        "PipChat demonstrates my real-time systems expertise: Socket.IO for "
        "instant messaging, JWT authentication, online-status tracking, and a "
        "responsive Tailwind UI — all on the MERN stack.",
    ),
    "socket": (
        "PipChat",
        "I built PipChat with Socket.IO-powered real-time messaging, "
        "secure JWT authentication, and online presence tracking, delivering "
        "a polished chat experience on the MERN stack.",
    ),
    # Python
    "python": (
        "Lawnova",
        "Lawnova's AI engine is built in Python with LangChain orchestration, "
        "and I've since expanded my Python expertise through this JobHuntTool "
        "project — building FastAPI backends, Playwright scrapers, and "
        "automated PDF generation pipelines.",
    ),
    # Docker / DevOps
    "docker": (
        "Lawnova",
        "Lawnova uses a Dockerized microservices architecture, with separate "
        "containers for the Node.js API, Python AI engine, and MongoDB — "
        "giving me hands-on experience with containerized deployments.",
    ),
    # Leadership / Team
    "leadership": (
        "EduTimeSync",
        "As team leader on EduTimeSync, I coordinated a 4-person development "
        "team from requirements gathering through deployment, managing sprints, "
        "code reviews, and architecture decisions for a university scheduling platform.",
    ),
    "team": (
        "EduTimeSync",
        "Leading EduTimeSync gave me firsthand experience coordinating a "
        "development team — running standups, managing the backlog, mentoring "
        "teammates on React patterns, and delivering on schedule.",
    ),
    # API
    "api": (
        "Garage Management",
        "The Garage Management System exposes RESTful APIs across six modules "
        "(inventory, customers, suppliers, finances, employees, services) — "
        "following clean MVC separation with Express.js and MongoDB.",
    ),
    "rest": (
        "Garage Management",
        "My Garage Management System features a comprehensive RESTful API layer "
        "with Express.js middleware, supporting full CRUD across six operational "
        "domains with consistent error handling and validation.",
    ),
    # C# / .NET
    "c#": (
        "Weather Application",
        "My Weather Application, built with C# and ASP.NET Core, integrates "
        "the OpenWeatherMap API for real-time data retrieval and uses Chart.js "
        "for interactive 5-day forecast visualizations.",
    ),
    ".net": (
        "Weather Application",
        "The Weather App I built with ASP.NET Core demonstrates my ability to "
        "integrate external APIs, process real-time data, and present it through "
        "interactive charts and responsive interfaces.",
    ),
    # MongoDB / Database
    "mongodb": (
        "Garage Management",
        "Multiple projects in my portfolio use MongoDB extensively — from the "
        "Garage Management System's multi-collection schema to PipChat's "
        "real-time message storage and Lawnova's case-law database.",
    ),
    "database": (
        "Garage Management",
        "I've designed MongoDB schemas across multiple projects: the Garage "
        "Management System (6 modules), PipChat (messages + users), and "
        "Lawnova (legal case data with full-text search).",
    ),
}

# Fallback when no specific skill match is found
FALLBACK_PROOF = (
    "My portfolio spans six end-to-end projects — from an AI-powered legal "
    "platform (Lawnova) using LangChain and Python, to a real-time chat app "
    "(PipChat) and a collaborative code editor (Codex) — each built with the "
    "MERN stack and deployed with production-grade architecture."
)


# ═══════════════════════════════════════════════════════════════
#  Generator
# ═══════════════════════════════════════════════════════════════

class ApplicationEmailGenerator:
    """
    Generates concise, 3-paragraph application emails.

    Structure:
        1. Hook  — Reference a specific JD requirement
        2. Proof — Connect it to a concrete CV project
        3. CTA   — Interview availability + attached PDF

    Two modes:
        - Template (default): Instant, no API cost, keyword-matched
        - LLM: Fully original via Gemini, requires API key
    """

    def __init__(self):
        self.cv_data = self._load_master_cv()
        self.candidate_name = self._get_candidate_name()

    def _load_master_cv(self) -> dict:
        """Load the master CV from disk."""
        try:
            with open(settings.MASTER_CV_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load master CV: {e}")
            return {}

    def _get_candidate_name(self) -> str:
        """Extract candidate name from CV data."""
        personal = self.cv_data.get("personal", self.cv_data.get("personal_info", {}))
        return personal.get("full_name", personal.get("name", "Candidate"))

    # ─── Skill Matching ──────────────────────────────────────

    def _find_best_skill_match(self, job_description: str) -> tuple[str, str, str]:
        """
        Scan the JD for keywords and return the best (skill, project, proof).

        Returns:
            (matched_skill, project_name, proof_paragraph)
        """
        jd_lower = job_description.lower()

        # Score each skill by how prominently it appears in the JD
        scored = []
        for skill, (project, proof) in SKILL_PROJECT_MAP.items():
            pattern = r'\b' + re.escape(skill) + r'\b'
            count = len(re.findall(pattern, jd_lower, re.IGNORECASE))
            if count > 0:
                # Bonus for appearing in first 500 chars (likely core requirements)
                early_match = re.search(pattern, jd_lower[:500], re.IGNORECASE)
                early_bonus = 3 if early_match else 0
                # Longer skill names are more specific → slight bonus
                specificity_bonus = len(skill) / 10
                score = count + early_bonus + specificity_bonus
                scored.append((score, skill, project, proof))

        if scored:
            scored.sort(reverse=True)
            _, skill, project, proof = scored[0]
            return skill, project, proof

        return "", "", FALLBACK_PROOF

    # ─── Template Generation ─────────────────────────────────

    def _generate_template(
        self,
        job_title: str,
        company_name: str,
        job_description: str,
        contact_person: str = "",
    ) -> ApplicationEmail:
        """Generate an email using keyword-matched templates."""

        matched_skill, matched_project, proof = self._find_best_skill_match(job_description)

        # Greeting
        if contact_person:
            first_name = contact_person.strip().split()[0]
            greeting = f"Hi {first_name},"
        else:
            greeting = f"Dear {company_name} Hiring Team,"

        # Hook — reference the specific JD requirement
        if matched_skill:
            hook = (
                f"I noticed your {job_title} role emphasizes {matched_skill} — "
                f"that's exactly where my recent project work has been focused, "
                f"and I'd love to bring that hands-on experience to {company_name}."
            )
        else:
            hook = (
                f"Your {job_title} opening caught my attention — the blend of "
                f"technical challenges and product impact at {company_name} aligns "
                f"closely with the kind of work I've been building toward."
            )

        # Proof — already matched from SKILL_PROJECT_MAP
        # (proof variable is set above)

        # CTA
        cta = (
            f"I've attached my tailored CV for your review. I'm available for a "
            f"technical interview or a quick call at your convenience — happy to "
            f"walk through any of these projects live. Looking forward to hearing "
            f"from you."
        )

        # Subject
        subject_line = f"Application: {job_title} — {self.candidate_name}"

        # Sign-off
        sign_off = f"Best regards,\n{self.candidate_name}"

        # Assemble
        full_text = (
            f"{greeting}\n\n"
            f"{hook}\n\n"
            f"{proof}\n\n"
            f"{cta}\n\n"
            f"{sign_off}"
        )

        return ApplicationEmail(
            subject_line=subject_line,
            greeting=greeting,
            hook=hook,
            proof=proof,
            cta=cta,
            sign_off=sign_off,
            full_text=full_text,
            matched_skill=matched_skill,
            matched_project=matched_project,
            generation_mode="template",
        )

    # ─── LLM Generation ─────────────────────────────────────

    def _generate_llm(
        self,
        job_title: str,
        company_name: str,
        job_description: str,
        contact_person: str = "",
    ) -> ApplicationEmail:
        """Generate an email using Gemini LLM for a fully original output."""
        from backend.ai.llm_client import invoke_llm

        # Build CV summary for the prompt
        projects_summary = ""
        for p in self.cv_data.get("projects", []):
            name = p.get("name", "")
            tech = p.get("technologies", "")
            desc = p.get("description", "")[:200]
            role = p.get("role", "")
            role_str = f" (Role: {role})" if role else ""
            projects_summary += f"  - {name}{role_str}: {desc}... [{tech}]\n"

        skills = ", ".join(self.cv_data.get("skills", []))

        greeting_instruction = ""
        if contact_person:
            greeting_instruction = f"Address the email to {contact_person} (use their first name)."
        else:
            greeting_instruction = f"Address it to the '{company_name} Hiring Team'. Do NOT use 'To Whom It May Concern'."

        system_prompt = (
            "You are a professional software engineer writing a job application email.\n"
            "Write EXACTLY 3 paragraphs. No more, no less.\n\n"
            "Structure:\n"
            "1. HOOK: Reference a SPECIFIC core responsibility, tech stack requirement, or "
            "'Nice to Have' skill from the job description. Show you actually read the JD.\n"
            "2. PROOF: Connect this to a SPECIFIC project from the candidate's CV. "
            "Name the project, mention concrete technologies used, and describe what was built. "
            "Do NOT be vague — cite the actual project.\n"
            "3. CTA: Mention availability for a technical interview or call, and reference "
            "the attached tailored CV/PDF.\n\n"
            "CONSTRAINTS:\n"
            "- Do NOT use 'To whom it may concern' or 'I am a highly motivated individual'\n"
            "- Do NOT use generic filler phrases\n"
            "- Keep tone confident, technical, and human\n"
            "- Total email should be 120-180 words\n"
            "- Do NOT include a subject line — only the email body\n"
            f"- {greeting_instruction}\n"
            "- Sign off with: Best regards,\\n" + self.candidate_name
        )

        user_prompt = (
            f"JOB TITLE: {job_title}\n"
            f"COMPANY: {company_name}\n\n"
            f"JOB DESCRIPTION:\n{job_description[:3000]}\n\n"
            f"CANDIDATE'S PROJECTS:\n{projects_summary}\n"
            f"CANDIDATE'S SKILLS: {skills}\n\n"
            "Write the 3-paragraph application email now."
        )

        try:
            raw_email = invoke_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.5,
                max_tokens=1024,
            )
        except Exception as e:
            logger.error(f"LLM email generation failed: {e}, falling back to template")
            return self._generate_template(job_title, company_name, job_description, contact_person)

        # Parse the LLM output into paragraphs
        paragraphs = [p.strip() for p in raw_email.strip().split("\n\n") if p.strip()]

        # Extract greeting if present
        greeting = ""
        body_paragraphs = []
        for p in paragraphs:
            if not greeting and (p.startswith("Hi ") or p.startswith("Dear ") or p.startswith("Hello ")):
                # Single-line greeting
                lines = p.split("\n", 1)
                greeting = lines[0].strip()
                if len(lines) > 1 and lines[1].strip():
                    body_paragraphs.append(lines[1].strip())
            elif p.startswith("Best") or p.startswith("Regards") or p.startswith("Sincerely"):
                # Sign-off — skip, we'll use our own
                continue
            else:
                body_paragraphs.append(p)

        if not greeting:
            greeting = f"Dear {company_name} Hiring Team,"

        # Ensure we have 3 paragraphs
        while len(body_paragraphs) < 3:
            body_paragraphs.append("")
        hook = body_paragraphs[0]
        proof = body_paragraphs[1]
        cta = body_paragraphs[2]

        subject_line = f"Application: {job_title} — {self.candidate_name}"
        sign_off = f"Best regards,\n{self.candidate_name}"

        full_text = (
            f"{greeting}\n\n"
            f"{hook}\n\n"
            f"{proof}\n\n"
            f"{cta}\n\n"
            f"{sign_off}"
        )

        # Try to detect matched skill from hook text
        matched_skill, matched_project, _ = self._find_best_skill_match(job_description)

        return ApplicationEmail(
            subject_line=subject_line,
            greeting=greeting,
            hook=hook,
            proof=proof,
            cta=cta,
            sign_off=sign_off,
            full_text=full_text,
            matched_skill=matched_skill,
            matched_project=matched_project,
            generation_mode="llm",
        )

    # ─── Public API ──────────────────────────────────────────

    def generate(
        self,
        job_title: str,
        company_name: str,
        job_description: str,
        contact_person: str = "",
        use_llm: bool = False,
    ) -> ApplicationEmail:
        """
        Generate a 3-paragraph application email.

        Args:
            job_title: The position being applied for
            company_name: Target company name
            job_description: Full job description text
            contact_person: Hiring manager or recruiter name (optional)
            use_llm: If True, uses Gemini for a fully original email

        Returns:
            ApplicationEmail with hook, proof, cta, and assembled full_text
        """
        if use_llm:
            result = self._generate_llm(job_title, company_name, job_description, contact_person)
        else:
            result = self._generate_template(job_title, company_name, job_description, contact_person)

        logger.info(
            f"📧 Application email generated for {job_title} @ {company_name} "
            f"[mode={result.generation_mode}, skill={result.matched_skill or 'general'}]"
        )
        return result

    def generate_from_job_data(self, job: dict, use_llm: bool = False) -> ApplicationEmail:
        """
        Generate an application email from a stored job document.

        Args:
            job: Job document from MongoDB
            use_llm: Whether to use Gemini LLM

        Returns:
            ApplicationEmail
        """
        title = job.get("title", "the position")
        company = job.get("company", {})
        company_name = company.get("name", "") if isinstance(company, dict) else str(company)
        description = job.get("job_description", "")
        contact = job.get("contact", {})
        contact_person = contact.get("contact_person", "") if isinstance(contact, dict) else ""

        return self.generate(
            job_title=title,
            company_name=company_name or "your company",
            job_description=description,
            contact_person=contact_person,
            use_llm=use_llm,
        )


# ═══════════════════════════════════════════════════════════════
#  Convenience function
# ═══════════════════════════════════════════════════════════════

def generate_application_email(
    job_title: str,
    company_name: str,
    job_description: str,
    contact_person: str = "",
    use_llm: bool = False,
) -> dict:
    """Quick convenience function for generating an application email."""
    gen = ApplicationEmailGenerator()
    result = gen.generate(
        job_title=job_title,
        company_name=company_name,
        job_description=job_description,
        contact_person=contact_person,
        use_llm=use_llm,
    )
    return result.model_dump()
