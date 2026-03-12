"""
CV Tailoring Agent — LangChain-powered resume customization engine.

Takes the Master CV + Parsed Job Description and generates:
  1. A tailored Professional Summary aligned to the role
  2. Rewritten Project Experience bullets emphasizing relevant tech
  3. Reordered Skills section prioritizing JD keywords
  4. A personalized Cover Letter draft

The tailoring preserves factual accuracy while maximizing ATS relevance.
Every bullet point is rewritten to mirror the JD's language and tone.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from backend.config import settings
from backend.ai.llm_client import invoke_llm, invoke_llm_structured
from backend.ai.jd_parser import JDParser, ParsedJobDescription
from backend.ai.ats_scorer import ATSScorer, ATSReport

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Output Schemas
# ═══════════════════════════════════════════════════════════════

class TailoredSummary(BaseModel):
    """AI-generated professional summary tailored to a specific role."""
    summary: str = Field(..., description="3-4 sentence professional summary tailored to the job")
    tone: str = Field(default="professional", description="Tone used: professional, enthusiastic, technical")
    keywords_woven_in: list[str] = Field(default_factory=list, description="Priority keywords naturally included")


class TailoredProject(BaseModel):
    """A project rewritten to emphasize relevant technologies and outcomes."""
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="1-2 sentence project description tailored to the role")
    highlights: list[str] = Field(..., description="3-4 bullet points emphasizing relevant tech and outcomes")
    tech_stack_display: list[str] = Field(..., description="Tech stack to display, ordered by relevance to the JD")
    relevance_note: str = Field(default="", description="Why this project was selected/prioritized")


class TailoredExperience(BaseModel):
    """Work experience rewritten to align with job requirements."""
    title: str
    company: str
    period: str
    highlights: list[str] = Field(..., description="3-4 bullet points using action verbs and JD keywords")


class TailoredSkillsSection(BaseModel):
    """Skills section reordered and regrouped to match JD priorities."""
    primary_skills: list[str] = Field(..., description="Most relevant skills matching JD requirements, listed first")
    secondary_skills: list[str] = Field(default_factory=list, description="Other relevant skills")
    additional_skills: list[str] = Field(default_factory=list, description="Remaining skills worth mentioning")


class TailoredCV(BaseModel):
    """Complete tailored CV output."""
    target_job_title: str
    target_company: str
    tailored_title: str = Field(..., description="Your title line, adjusted to match the role")
    professional_summary: TailoredSummary
    skills: TailoredSkillsSection
    projects: list[TailoredProject]
    experience: list[TailoredExperience]
    education: list[dict] = Field(default_factory=list)
    ats_optimized_filename: str = Field(..., description="Suggested filename like 'Janith_Viranga_CompanyName_Role.pdf'")


class CoverLetterDraft(BaseModel):
    """AI-generated 3-paragraph cover letter email body.
    
    Structure:
      P1 (Hook)  — Reference a specific JD requirement or nice-to-have skill.
      P2 (Proof) — Connect that requirement to a concrete project from the CV.
      P3 (CTA)   — Mention the attached tailored PDF, interview availability.
    """
    subject_line: str = Field(..., description="Email subject line — concise, with role name")
    greeting: str = Field(default="Hi [Hiring Manager],", description="Use 'Hi' not 'Dear'. If name is unknown, use 'Hi there,'")
    hook_paragraph: str = Field(..., description="P1: Reference a specific responsibility or 'nice to have' from the JD. Show you actually read the posting.")
    proof_paragraph: str = Field(..., description="P2: Connect that JD point to a specific project from the CV with a concrete detail (tech, outcome, metric).")
    cta_paragraph: str = Field(..., description="P3: Mention the attached tailored CV PDF, state interview availability, and close confidently.")
    sign_off: str = Field(default="Best,\nJanith Viranga", description="Short sign-off — 'Best,' or 'Cheers,' not 'Sincerely yours,'")
    full_text: str = Field(default="", description="All paragraphs assembled into one continuous email body")


# ═══════════════════════════════════════════════════════════════
#  Prompt Templates
# ═══════════════════════════════════════════════════════════════

SUMMARY_SYSTEM_PROMPT = """You are an expert resume writer and career coach specializing in tech roles.

Your task is to write a PROFESSIONAL SUMMARY for a CV that will be submitted to an ATS (Applicant Tracking System).

⚠️ ONE-PAGE CV CONSTRAINT: The ENTIRE CV (summary + skills + projects + education) MUST fit
on a SINGLE A4 page. The summary MUST be kept SHORT — 2-3 sentences MAXIMUM.

ATS-FRIENDLY FORMAT RULES:
- Use standard section headings (no creative naming)
- Avoid tables, columns, or graphics
- Use standard bullet points
- Include exact keyword matches from the JD

CRITICAL RULES:
1. Write 2-3 sentences MAXIMUM. Keep it ultra-concise and powerful.
2. START with an action-oriented identity statement (e.g., "AI-focused Software Engineer...")
3. NATURALLY WEAVE IN the priority keywords — don't force them. They should read smoothly.
4. MIRROR the job description's language and tone.
5. HIGHLIGHT specific technologies that match the job requirements.
6. Include a QUANTIFIABLE achievement or impact if possible.
7. End with what value you bring to THIS specific company/role.
8. DO NOT lie or fabricate. Only reference skills/experience that exist in the master CV.
9. Write in FIRST PERSON IMPLIED (no "I" — standard resume style).

KEYWORD PRIORITY TIERS (this determines what gets into the summary):
  TIER 1 — USE THESE (domain-specific, architecture-level → interview triggers):
    Agentic AI, LangChain, RAG pipelines, event-driven, distributed systems,
    scalability, containerized microservices, CI/CD orchestration, observability,
    real-time data pipelines, inference optimization, prompt engineering.
  TIER 2 — OK TO USE (solid tech with moderate differentiation):
    React, Python, FastAPI, MongoDB, Docker, TypeScript, Node.js, PostgreSQL.
  TIER 3 — AVOID IN SUMMARY (everyone has these → zero differentiation):
    Full-Stack Developer, HTML/CSS, Git, REST API, Agile, team player.
  TIER 4 — NEVER USE (negative signal → actively hurts positioning):
    Student, beginner, familiar with, basic knowledge, exposure to, learning.

PREFER Tier 1 keywords in the summary. They are the strongest interview signals.
NEVER open with 'Full-Stack Developer' — it's the most commoditized title in tech.
Instead, lead with the SPECIFIC domain: 'AI/ML Engineer', 'Systems Engineer',
'Platform Engineer', etc. — whatever matches the JD best.

The summary should feel like it was written specifically for this one job."""


PROJECTS_SYSTEM_PROMPT = """You are an expert resume writer specializing in tech portfolios and project descriptions.

Your task is to REWRITE the candidate's project descriptions to maximize INTERVIEW conversion rate,
not just ATS score. Generic keyword stuffing gets past ATS but doesn't get interviews.

⚠️ ONE-PAGE CV CONSTRAINT: The ENTIRE CV must fit on a SINGLE A4 page.
Therefore you MUST:
- Select only the TOP 2-3 most relevant projects (NOT more)
- Keep only 2-3 bullet points per project (short and impactful)
- Keep project descriptions to 1 SHORT sentence
- Be ruthless about cutting — quality over quantity

CRITICAL RULES:
1. Select and REORDER projects by relevance to the target job. Most relevant first.
2. REWRITE each bullet point to emphasize the HIGHEST-TIER technologies matching the JD.
3. USE STRONG ACTION VERBS: Architected, Engineered, Orchestrated, Scaled, Optimized, Deployed, Automated.
   AVOID weak verbs: Made, Did, Worked on, Helped, Assisted.
4. ADD QUANTIFIABLE IMPACT where reasonable (e.g., "50+ concurrent users", "3x throughput", "sub-200ms latency").
5. MIRROR the JD's technical vocabulary. If they say "containerization", use "containerization" not just "Docker".
6. Each bullet should start with an action verb and naturally include a JD keyword.
7. Keep 2-3 bullets per project MAX. More is cluttered and won't fit on 1 page.
8. ONLY emphasize technologies and skills that ACTUALLY EXIST in the original project. Never fabricate.
9. If a project doesn't use any relevant tech, DE-PRIORITIZE it (move to the end or exclude).
10. Rewrite the short project description to emphasize the aspects most relevant to the target role.

KEYWORD STRATEGY FOR BULLETS:
  LEAD with architecture-level terms: "Designed an event-driven pipeline..." not "Used Python to..."
  EMBED scalability signals: concurrent users, throughput, latency, uptime.
  SUPPRESS generic filler: Don't waste bullet space on HTML/CSS, Git, or basic REST calls.
  FRAME projects as SYSTEMS, not scripts: "Orchestrated a multi-service data pipeline" > "Built a Python script."

The goal: A hiring manager scanning this CV should think 'this person builds real systems'
not 'this person completed tutorials.'"""


EXPERIENCE_SYSTEM_PROMPT = """You are an expert resume writer focusing on maximizing interview conversion.

Rewrite the work experience section to align with the target job's requirements.

⚠️ ONE-PAGE CV CONSTRAINT: The ENTIRE CV must fit on a SINGLE A4 page.
Keep experience entries very concise — 2-3 bullet points per role MAX.
If the candidate has no formal work experience, this section can be omitted entirely.

RULES:
1. Use STRONG ACTION VERBS: Architected, Engineered, Scaled, Deployed, Automated, Led.
   AVOID: Used, Worked with, Helped, Assisted, Participated in.
2. Naturally include relevant KEYWORDS from the job description — prioritize
   domain-specific and architecture-level terms over generic ones.
3. Emphasize transferable skills and relevant technologies.
4. Add quantifiable impacts where plausible (without fabricating).
5. Keep 2-3 bullet points per role MAX. Be concise.
6. DO NOT fabricate experience. Only rewrite what exists.

KEYWORD PRIORITY (in order of interview-conversion signal strength):
  STRONGEST → Domain-specific: Agentic AI, LangChain, RAG, prompt engineering
  STRONG    → Architecture: scalable, distributed, event-driven, microservices
  MODERATE  → Tech: React, Python, MongoDB, Docker, TypeScript
  WEAK      → Generic: Full-Stack, HTML/CSS, Git, REST API (skip these if space is limited)
  HARMFUL   → Junior signals: Student project, coursework, basic, beginner

FRAME experience at the SYSTEMS level, not the task level:
  ✅ 'Architected a real-time AI inference pipeline processing 10k requests/min'
  ❌ 'Used Python to process data'
  ✅ 'Led end-to-end delivery of 5 client projects with Docker-based CI/CD'
  ❌ 'Worked on several projects using various technologies'"""


COVER_LETTER_SYSTEM_PROMPT = """You are a senior software engineer writing a concise 3-paragraph email to a hiring manager.
You write like a real human — confident, technical, and direct.

STRUCTURE (exactly 3 paragraphs, no more):

Paragraph 1 — THE HOOK:
  Reference a SPECIFIC core responsibility or 'Nice to Have' skill from the job description.
  Show you actually read the posting — name the exact technology or requirement.
  Example: "Your posting mentions building agentic workflows with LangChain — that caught my eye because..."

Paragraph 2 — THE PROOF:
  Connect the hook to a SPECIFIC project from the candidate's CV.
  Name the project. Mention a concrete technical detail or outcome.
  Example: "On LawNova, I built an AI judgment prediction module using LangChain and Gemini that processes 50+ concurrent sessions with delta-based updates."

Paragraph 3 — THE CALL TO ACTION:
  Mention the attached tailored CV PDF by its filename.
  State concrete availability for an interview.
  Close with confidence — no begging or desperation.
  Example: "I've attached my CV (Janith_Viranga_Softvil_SWE_Intern.pdf) tailored to this role. I'm available for a call this week or next."

BANNED PHRASES (never use these):
  - "To whom it may concern"
  - "I am a highly motivated individual"
  - "I am writing to express my interest"
  - "I believe I would be a great fit"
  - "Dear Sir/Madam"
  - "I am excited about this opportunity"
  - "Thank you for considering my application"
  - Any sentence starting with "I am" back-to-back

TONE:
  - Confident, not arrogant. Technical, not buzzwordy. Human, not template.
  - Write like you're emailing a colleague you respect, not writing a formal letter.
  - Max 150 words total. Hiring managers scan, not read.
  - Use 'Hi' not 'Dear'. If you don't know the hiring manager's name, use 'Hi there,'
  - Sign off with 'Best,' or 'Cheers,' — not 'Sincerely yours,'"""


SKILLS_SYSTEM_PROMPT = """You are a resume optimization expert focused on maximizing interview conversion rates.

Reorganize the candidate's skills section to maximize BOTH ATS pass-through AND human reviewer interest.

⚠️ ONE-PAGE CV CONSTRAINT: The ENTIRE CV must fit on a SINGLE A4 page.
Keep skills lists compact — no more than 8 primary, 6 secondary, 5 additional.
Display as a comma-separated single line per tier to save vertical space.

ATS-FRIENDLY FORMAT: Use standard skill names that ATS systems can parse.

RULES:
1. Put the MOST RELEVANT skills first — match the JD's priorities.
2. Group into: Primary (exact JD matches), Secondary (related/complementary), Additional (other).
3. Use the EXACT terminology from the job description where it matches the candidate's skills.
4. Only include skills the candidate actually has (from the master CV).
5. If the JD mentions 'React.js' and the CV says 'React', use 'React.js' to match exactly.
6. Include no more than 8 primary skills, 6 secondary, 5 additional (to fit 1 page).

SKILL ORDERING WITHIN EACH GROUP (lead with highest-signal terms):
  ORDER BY:  Domain-specific > Architecture-level > Frameworks > Languages > Generic
  EXAMPLE:   'LangChain, Docker, Kubernetes, React.js, Python, TypeScript'
  NOT:       'HTML, CSS, Git, JavaScript, React, Python'

SKILLS TO SUPPRESS (never list in Primary — they dilute the signal):
  HTML, CSS, Git, GitHub, REST API, Agile, Scrum, Microsoft Office, Windows, Linux (basic)
  These are assumed competencies. Listing them wastes prime real estate.

SKILLS TO PROMOTE (move to Primary whenever they match the JD):
  LangChain, Agentic AI, RAG, Prompt Engineering, Docker, Kubernetes,
  CI/CD, Observability, Event-driven Architecture, Microservices,
  Real-time Systems, Distributed Computing, Scalability Patterns

The skills section is the FIRST thing both ATS and humans scan. Lead with signal, not noise."""


# ═══════════════════════════════════════════════════════════════
#  CV Tailor Implementation
# ═══════════════════════════════════════════════════════════════

class CVTailor:
    """
    LangChain-powered CV tailoring agent.
    
    Takes a Master CV + Job Description → produces a fully tailored CV
    with optimized sections, ATS scoring, and a cover letter draft.
    
    Usage:
        tailor = CVTailor()
        result = tailor.tailor_full(
            job_description="...",
            job_title="AI Intern",
            company_name="Softvil",
        )
        print(f"ATS Score: {result['ats_report']['overall_score']}")
    """

    def __init__(self, master_cv_path: Optional[Path] = None):
        self.master_cv_path = master_cv_path or settings.MASTER_CV_PATH
        self.master_cv = self._load_master_cv()
        self.jd_parser = JDParser()
        self.ats_scorer = ATSScorer()

    def _load_master_cv(self) -> dict:
        """Load the master CV from JSON file."""
        try:
            with open(self.master_cv_path, 'r', encoding='utf-8') as f:
                cv = json.load(f)
            personal = cv.get('personal', cv.get('personal_info', {}))
            name = personal.get('full_name', personal.get('name', 'Candidate'))
            logger.info(f"📄 Master CV loaded: {name}")
            return cv
        except FileNotFoundError:
            logger.error(f"❌ Master CV not found at {self.master_cv_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in master CV: {e}")
            raise

    def _get_personal(self) -> dict:
        """Get personal info from master CV (supports both 'personal' and 'personal_info' keys)."""
        return self.master_cv.get('personal', self.master_cv.get('personal_info', {}))

    def _get_name(self) -> str:
        """Get candidate name (supports both 'full_name' and 'name' keys)."""
        personal = self._get_personal()
        return personal.get('full_name', personal.get('name', 'Candidate'))

    def _get_summary(self) -> str:
        """Get professional summary (supports both 'professional_summary' and 'summary' keys)."""
        return self.master_cv.get('professional_summary', self.master_cv.get('summary', ''))

    # ─────────────────────────────────────────────────────────
    #  Full Tailoring Pipeline
    # ─────────────────────────────────────────────────────────

    def tailor_full(
        self,
        job_description: str,
        job_title: str = "",
        company_name: str = "",
        include_cover_letter: bool = True,
    ) -> dict:
        """
        Execute the complete tailoring pipeline:
        
        1. Parse the job description (JDParser)
        2. Tailor the Professional Summary
        3. Rewrite Project Experience
        4. Rewrite Work Experience  
        5. Reorder Skills section
        6. Generate Cover Letter (optional)
        7. Run ATS scoring on the result
        8. Return everything with recommendations
        
        Returns:
            dict with keys: tailored_cv, cover_letter, ats_report, parsed_jd, metadata
        """
        start = datetime.utcnow()
        logger.info(f"🧠 Starting full CV tailoring for '{job_title}' @ {company_name}")

        # ── Step 1: Parse the JD ─────────────────────────────
        logger.info("   Step 1/7: Parsing job description...")
        parsed_jd = self.jd_parser.parse(job_description, job_title, company_name)

        # ── Step 2: Tailor Summary ───────────────────────────
        logger.info("   Step 2/7: Tailoring professional summary...")
        summary = self.tailor_summary(parsed_jd)

        # ── Step 3: Tailor Projects ──────────────────────────
        logger.info("   Step 3/7: Rewriting project experience...")
        projects = self.tailor_projects(parsed_jd)

        # ── Step 4: Tailor Experience ────────────────────────
        logger.info("   Step 4/7: Rewriting work experience...")
        experience = self.tailor_experience(parsed_jd)

        # ── Step 5: Reorder Skills ───────────────────────────
        logger.info("   Step 5/7: Optimizing skills section...")
        skills = self.tailor_skills(parsed_jd)

        # ── Step 6: Cover Letter ─────────────────────────────
        cover_letter = None
        if include_cover_letter:
            logger.info("   Step 6/7: Generating cover letter draft...")
            cover_letter = self.generate_cover_letter(parsed_jd, company_name)
        else:
            logger.info("   Step 6/7: Skipping cover letter (not requested)")

        # ── Build the tailored CV object ─────────────────────
        personal = self._get_personal()
        filename = self._generate_filename(self._get_name(), company_name, job_title)

        tailored_cv = TailoredCV(
            target_job_title=job_title or parsed_jd.job_title_normalized,
            target_company=company_name,
            tailored_title=self._adjust_title(parsed_jd),
            professional_summary=summary,
            skills=skills,
            projects=projects,
            experience=experience,
            education=self.master_cv.get("education", []),
            ats_optimized_filename=filename,
        )

        # ── Step 7: ATS Scoring ──────────────────────────────
        logger.info("   Step 7/7: Running ATS scoring...")
        cv_text = self._cv_to_text(tailored_cv)
        ats_report = self.ats_scorer.score(cv_text, parsed_jd)

        duration = (datetime.utcnow() - start).total_seconds()
        logger.info(
            f"✅ Tailoring complete in {duration:.1f}s | "
            f"ATS Score: {ats_report.overall_score:.1f}/100 ({ats_report.grade})"
        )

        return {
            "tailored_cv": tailored_cv.model_dump(),
            "cover_letter": cover_letter.model_dump() if cover_letter else None,
            "ats_report": ats_report.to_dict(),
            "parsed_jd": parsed_jd.model_dump(),
            "cv_as_text": cv_text,
            "metadata": {
                "duration_seconds": round(duration, 1),
                "master_cv_used": str(self.master_cv_path),
                "tailored_at": datetime.utcnow().isoformat(),
                "filename": filename,
            },
        }

    # ─────────────────────────────────────────────────────────
    #  Individual Section Tailors
    # ─────────────────────────────────────────────────────────

    def tailor_summary(self, parsed_jd: ParsedJobDescription) -> TailoredSummary:
        """Generate a tailored professional summary."""
        personal = self._get_personal()
        prompt = f"""**TARGET ROLE:** {parsed_jd.job_title_normalized}
**SENIORITY:** {parsed_jd.seniority_level}
**MUST-HAVE SKILLS:** {', '.join(parsed_jd.must_have_skills[:10])}
**PRIORITY KEYWORDS (weave these in):** {', '.join(parsed_jd.priority_keywords[:12])}
**KEY RESPONSIBILITIES:** {chr(10).join('• ' + r for r in parsed_jd.key_responsibilities[:5])}

**ROLE SUMMARY:** {parsed_jd.role_summary}

---

**CANDIDATE'S MASTER CV:**
**Current Title:** {personal.get('title', 'Developer')}
**Summary:** {self._get_summary()}
**Key Skills:** {json.dumps(self.master_cv.get('skills', {}), indent=None)}
**Projects:** {', '.join(p['name'] for p in self.master_cv.get('projects', []))}

---

⚠️ IMPORTANT: The final CV MUST fit on a SINGLE A4 page. Keep the summary to 2-3 sentences MAX.
The CV must be ATS-friendly with standard formatting.

Write a tailored professional summary for this specific role. Remember:
- 2-3 sentences max (ONE PAGE CV constraint)
- Naturally include the priority keywords
- Mirror the JD's language and tone
- Reference specific relevant technologies
- No first person "I" """

        try:
            result: TailoredSummary = invoke_llm_structured(
                system_prompt=SUMMARY_SYSTEM_PROMPT,
                user_prompt=prompt,
                output_schema=TailoredSummary,
                temperature=0.4,
            )
            return result
        except Exception as e:
            logger.error(f"Summary tailoring failed: {e}")
            return TailoredSummary(
                summary=self._get_summary(),
                tone="default",
                keywords_woven_in=[],
            )

    def tailor_projects(self, parsed_jd: ParsedJobDescription) -> list[TailoredProject]:
        """Rewrite and reorder projects for the target job."""
        projects_json = json.dumps(self.master_cv.get("projects", []), indent=2)

        prompt = f"""**TARGET ROLE:** {parsed_jd.job_title_normalized}
**MUST-HAVE TECH:** {', '.join(parsed_jd.must_have_skills[:10])}
**FULL TECH STACK REQUIRED:**
  Languages: {', '.join(parsed_jd.tech_stack.languages)}
  Frameworks: {', '.join(parsed_jd.tech_stack.frameworks)}
  Databases: {', '.join(parsed_jd.tech_stack.databases)}
  Tools: {', '.join(parsed_jd.tech_stack.tools)}
  Cloud: {', '.join(parsed_jd.tech_stack.cloud)}

**PRIORITY KEYWORDS:** {', '.join(parsed_jd.priority_keywords[:15])}
**KEY RESPONSIBILITIES:** {chr(10).join('• ' + r for r in parsed_jd.key_responsibilities[:5])}

---

**CANDIDATE'S PROJECTS (from Master CV):**
{projects_json}

---

⚠️ ONE-PAGE CV CONSTRAINT: The ENTIRE CV must fit on 1 page. Be VERY concise.

INSTRUCTIONS:
1. Select ONLY the TOP 2-3 most relevant projects (NOT more — 1-page limit!)
2. Reorder them by relevance to the target job (most relevant first)
3. Rewrite bullets to emphasize matching technologies — keep 2-3 bullets per project MAX
4. Use action verbs and include quantifiable impact
5. Keep project descriptions to 1 SHORT sentence
6. Mirror the JD's language in your descriptions
7. Reorder each project's tech_stack to put JD matches first
8. NEVER fabricate features or technologies not in the original project"""

        try:
            # Use free-form LLM call then parse, because structured output
            # with lists of complex objects can be unreliable
            raw_response = invoke_llm(
                system_prompt=PROJECTS_SYSTEM_PROMPT,
                user_prompt=prompt + "\n\nRespond with a JSON array of project objects with keys: name, description, highlights (list), tech_stack_display (list), relevance_note.",
                temperature=0.3,
            )

            # Parse the JSON from the response
            projects = self._extract_json_array(raw_response)
            return [TailoredProject(**p) for p in projects]

        except Exception as e:
            logger.error(f"Project tailoring failed: {e}")
            # Fallback: return original projects with minimal formatting
            return [
                TailoredProject(
                    name=p["name"],
                    description=p.get("description", ""),
                    highlights=p.get("highlights", []),
                    tech_stack_display=p.get("tech_stack", []),
                    relevance_note="Original — not AI-tailored",
                )
                for p in self.master_cv.get("projects", [])
            ]

    def tailor_experience(self, parsed_jd: ParsedJobDescription) -> list[TailoredExperience]:
        """Rewrite work experience bullets."""
        experience_json = json.dumps(self.master_cv.get("experience", []), indent=2)

        prompt = f"""**TARGET ROLE:** {parsed_jd.job_title_normalized}
**PRIORITY KEYWORDS:** {', '.join(parsed_jd.priority_keywords[:12])}
**KEY REQUIREMENTS:** {', '.join(parsed_jd.must_have_skills[:8])}

---

**CANDIDATE'S EXPERIENCE:**
{experience_json}

---

Rewrite each experience entry to align with the target role.
Respond with a JSON array of objects with keys: title, company, period, highlights (list of strings)."""

        try:
            raw = invoke_llm(
                system_prompt=EXPERIENCE_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.3,
            )
            entries = self._extract_json_array(raw)
            return [TailoredExperience(**e) for e in entries]
        except Exception as e:
            logger.error(f"Experience tailoring failed: {e}")
            return [
                TailoredExperience(
                    title=exp.get("title", ""),
                    company=exp.get("company", ""),
                    period=exp.get("period", ""),
                    highlights=exp.get("highlights", []),
                )
                for exp in self.master_cv.get("experience", [])
            ]

    def tailor_skills(self, parsed_jd: ParsedJobDescription) -> TailoredSkillsSection:
        """Reorder and regroup skills by JD relevance."""
        all_skills = self.master_cv.get("skills", {})

        prompt = f"""**TARGET JOB REQUIREMENTS:**
Must-have: {', '.join(parsed_jd.must_have_skills[:10])}
Nice-to-have: {', '.join(parsed_jd.nice_to_have_skills[:10])}
Tech Stack: Languages={', '.join(parsed_jd.tech_stack.languages)}, Frameworks={', '.join(parsed_jd.tech_stack.frameworks)}, DBs={', '.join(parsed_jd.tech_stack.databases)}

**CANDIDATE'S SKILLS (from Master CV):**
{json.dumps(all_skills, indent=2)}

---

Reorganize these skills into primary (exact JD matches), secondary (related), and additional.
Use exact JD terminology where matching. Only include skills the candidate actually has.
Respond as JSON with keys: primary_skills (list), secondary_skills (list), additional_skills (list)."""

        try:
            raw = invoke_llm(
                system_prompt=SKILLS_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.2,
            )
            data = self._extract_json_object(raw)
            return TailoredSkillsSection(**data)
        except Exception as e:
            logger.error(f"Skills tailoring failed: {e}")
            # Fallback: flatten all skills
            flat = []
            for category_skills in all_skills.values():
                if isinstance(category_skills, list):
                    flat.extend(category_skills)
            return TailoredSkillsSection(
                primary_skills=flat[:15],
                secondary_skills=flat[15:25],
                additional_skills=flat[25:],
            )

    def generate_cover_letter(
        self,
        parsed_jd: ParsedJobDescription,
        company_name: str = "",
    ) -> CoverLetterDraft:
        """Generate a 3-paragraph cover letter email: Hook → Proof → CTA."""
        personal = self._get_personal()
        candidate_name = self._get_name()
        projects = self.master_cv.get("projects", [])

        # Build project summaries for context
        project_summaries = []
        for p in projects[:4]:
            tech = ', '.join(p.get('tech_stack', p.get('technologies', '').split(', ') if isinstance(p.get('technologies', ''), str) else p.get('technologies', []))[:5])
            highlights = '; '.join(p.get('highlights', [p.get('description', '')])[:2])
            project_summaries.append(
                f"  • {p['name']} [{tech}]: {highlights}"
            )
        projects_block = chr(10).join(project_summaries)

        # Build nice-to-haves for the "hook" paragraph to reference
        nice_to_haves = parsed_jd.nice_to_have_skills[:5]
        nice_to_have_str = ', '.join(nice_to_haves) if nice_to_haves else 'N/A'

        # ATS filename for CTA reference
        filename = self._generate_filename(
            candidate_name, company_name,
            parsed_jd.job_title_normalized,
        )

        company_culture = ""
        if parsed_jd.company_culture_notes:
            company_culture = "\nCompany Culture Notes:\n" + "\n".join(f"  • {n}" for n in parsed_jd.company_culture_notes[:3])

        prompt = f"""Write a 3-paragraph cover letter email for this specific role.

**ROLE:** {parsed_jd.job_title_normalized} at {company_name or 'the company'}
**CORE RESPONSIBILITIES (pick one for the hook):**
{chr(10).join('  • ' + r for r in parsed_jd.key_responsibilities[:5])}
**MUST-HAVE SKILLS:** {', '.join(parsed_jd.must_have_skills[:8])}
**NICE-TO-HAVE SKILLS (great hook material):** {nice_to_have_str}
**PRIORITY TECH KEYWORDS:** {', '.join(parsed_jd.priority_keywords[:10])}
{company_culture}

---

**CANDIDATE:**
Name: {candidate_name}
Title: {personal.get('title', 'Developer')}
Email: {personal.get('email', '')}
Portfolio: {personal.get('portfolio', '')}

**CANDIDATE'S PROJECTS (pick one for the proof paragraph):**
{projects_block}

**ATTACHED CV FILENAME (reference this in the CTA):** {filename}

---

Remember:
- P1 (Hook): Name a SPECIFIC JD requirement or nice-to-have. Show you read the posting.
- P2 (Proof): Connect it to a SPECIFIC project by name. Include a concrete technical detail.
- P3 (CTA): Reference the attached PDF filename. State you're available for a call this week.
- Max 150 words total. No banned phrases.

Respond as JSON with keys: subject_line, greeting, hook_paragraph, proof_paragraph, cta_paragraph, sign_off, full_text."""

        try:
            raw = invoke_llm(
                system_prompt=COVER_LETTER_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.6,
            )
            data = self._extract_json_object(raw)

            # Handle the old schema keys gracefully (in case LLM uses them)
            if 'opening_paragraph' in data and 'hook_paragraph' not in data:
                data['hook_paragraph'] = data.pop('opening_paragraph')
            if 'body_paragraph' in data and 'proof_paragraph' not in data:
                data['proof_paragraph'] = data.pop('body_paragraph')
            if 'closing_paragraph' in data and 'cta_paragraph' not in data:
                data['cta_paragraph'] = data.pop('closing_paragraph')
            # Drop fields that no longer exist in the schema
            data.pop('company_alignment', None)

            cover = CoverLetterDraft(**data)

            # Build full_text if not provided by LLM
            if not cover.full_text:
                cover.full_text = (
                    f"{cover.greeting}\n\n"
                    f"{cover.hook_paragraph}\n\n"
                    f"{cover.proof_paragraph}\n\n"
                    f"{cover.cta_paragraph}\n\n"
                    f"{cover.sign_off}"
                )

            return cover
        except Exception as e:
            logger.error(f"Cover letter generation failed: {e}")
            # Fallback — still follows the 3-paragraph structure
            top_project = projects[0] if projects else {}
            top_tech = ', '.join(parsed_jd.must_have_skills[:3])
            return CoverLetterDraft(
                subject_line=f"{candidate_name} — {parsed_jd.job_title_normalized} Application",
                greeting="Hi there,",
                hook_paragraph=(
                    f"Your posting for {parsed_jd.job_title_normalized} mentions {top_tech} "
                    f"as core requirements — that lines up exactly with what I've been building."
                ),
                proof_paragraph=(
                    f"On {top_project.get('name', 'a recent project')}, I worked with "
                    f"{', '.join(top_project.get('tech_stack', ['similar technologies'])[:4])} "
                    f"to {top_project.get('highlights', ['deliver production-ready solutions'])[0].lower()}."
                ),
                cta_paragraph=(
                    f"I've attached my CV ({filename}) tailored to this role. "
                    f"I'm available for a call this week or next — happy to walk through any of the details."
                ),
                sign_off=f"Best,\n{candidate_name}",
                full_text="",
            )

    # ─────────────────────────────────────────────────────────
    #  Utility Methods
    # ─────────────────────────────────────────────────────────

    def _adjust_title(self, parsed_jd: ParsedJobDescription) -> str:
        """Adjust the candidate's title line to mirror the target role."""
        personal = self._get_personal()
        original_title = personal.get("title", "Developer")
        jd_title = parsed_jd.job_title_normalized

        # If the JD title is very different, blend both
        if any(kw in jd_title.lower() for kw in ["ai", "ml", "machine learning", "data"]):
            return "AI & Full Stack Developer"
        elif "full stack" in jd_title.lower() or "fullstack" in jd_title.lower():
            return "Full Stack Developer"
        elif "frontend" in jd_title.lower() or "front-end" in jd_title.lower():
            return "Frontend Developer | React Specialist"
        elif "backend" in jd_title.lower() or "back-end" in jd_title.lower():
            return "Backend Developer | Python & Node.js"
        elif "devops" in jd_title.lower():
            return "DevOps & Full Stack Engineer"
        else:
            return original_title

    def _generate_filename(self, name: str, company: str, role: str) -> str:
        """Generate ATS-friendly PDF filename."""
        clean_name = name.replace(" ", "_")
        clean_company = (company or "General").replace(" ", "_").replace(".", "")
        clean_role = (role or "Application").replace(" ", "_")
        return f"{clean_name}_{clean_company}_{clean_role}.pdf"

    def _cv_to_text(self, cv: TailoredCV) -> str:
        """Convert the tailored CV to plain text for ATS scoring."""
        lines = []

        # Header
        personal = self._get_personal()
        lines.append(self._get_name())
        lines.append(cv.tailored_title)
        lines.append("")

        # Summary
        lines.append("PROFESSIONAL SUMMARY")
        lines.append(cv.professional_summary.summary)
        lines.append("")

        # Skills
        lines.append("TECHNICAL SKILLS")
        lines.append(f"Primary: {', '.join(cv.skills.primary_skills)}")
        if cv.skills.secondary_skills:
            lines.append(f"Secondary: {', '.join(cv.skills.secondary_skills)}")
        if cv.skills.additional_skills:
            lines.append(f"Additional: {', '.join(cv.skills.additional_skills)}")
        lines.append("")

        # Projects
        lines.append("PROJECT EXPERIENCE")
        for proj in cv.projects:
            lines.append(f"\n{proj.name}")
            lines.append(proj.description)
            lines.append(f"Technologies: {', '.join(proj.tech_stack_display)}")
            for h in proj.highlights:
                lines.append(f"• {h}")
        lines.append("")

        # Experience
        lines.append("WORK EXPERIENCE")
        for exp in cv.experience:
            lines.append(f"\n{exp.title} | {exp.company} | {exp.period}")
            for h in exp.highlights:
                lines.append(f"• {h}")
        lines.append("")

        # Education
        lines.append("EDUCATION")
        for edu in cv.education:
            lines.append(f"{edu.get('degree', '')} | {edu.get('institution', '')} | {edu.get('period', '')}")

        return "\n".join(lines)

    @staticmethod
    def _extract_json_array(text: str) -> list[dict]:
        """Extract a JSON array from LLM response text."""
        import re
        # Try to find JSON array in the response
        # First try: look for ```json code block
        code_block = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', text)
        if code_block:
            return json.loads(code_block.group(1))

        # Second try: find array directly
        array_match = re.search(r'(\[[\s\S]*\])', text)
        if array_match:
            try:
                return json.loads(array_match.group(1))
            except json.JSONDecodeError:
                pass

        # Last resort: parse the whole text
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        logger.warning("Could not extract JSON array from LLM response")
        return []

    @staticmethod
    def _extract_json_object(text: str) -> dict:
        """Extract a JSON object from LLM response text."""
        import re
        # Try code block first
        code_block = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if code_block:
            return json.loads(code_block.group(1))

        # Try finding an object directly
        obj_match = re.search(r'(\{[\s\S]*\})', text)
        if obj_match:
            try:
                return json.loads(obj_match.group(1))
            except json.JSONDecodeError:
                pass

        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        logger.warning("Could not extract JSON object from LLM response")
        return {}
