"""
PDF Document Generator — ReportLab-based ATS-friendly PDF creation.

Generates clean, single-column, machine-readable PDF documents:
  - Tailored CV (1-2 pages, optimized for ATS parsing)
  - Cover Letter (single page, professional layout)

Design principles:
  - Single column (ATS parsers fail on multi-column layouts)
  - Standard fonts (Helvetica family — universally recognized by ATS)
  - No tables, text boxes, or graphics that confuse parsers
  - Clean section headers with subtle visual hierarchy
  - Proper metadata (title, author, subject) for PDF indexing
  - Consistent spacing for professional appearance
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    ListFlowable, ListItem, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Color Palette — Professional dark accents
# ═══════════════════════════════════════════════════════════════

COLORS = {
    "primary":     HexColor("#1a1a2e"),   # Dark navy — headings
    "secondary":   HexColor("#16213e"),   # Slightly lighter navy
    "accent":      HexColor("#0f3460"),   # Blue accent — section lines
    "text":        HexColor("#1a1a1a"),   # Near-black text
    "text_light":  HexColor("#4a4a5a"),   # Gray text for subtitles
    "link":        HexColor("#0f3460"),   # Link color
    "line":        HexColor("#c4c4d4"),   # Subtle horizontal rules
    "bullet":      HexColor("#0f3460"),   # Bullet point color
}

# Page dimensions
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 18 * mm
RIGHT_MARGIN = 18 * mm
TOP_MARGIN = 15 * mm
BOTTOM_MARGIN = 15 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN


# ═══════════════════════════════════════════════════════════════
#  Style Factory
# ═══════════════════════════════════════════════════════════════

def build_styles() -> dict:
    """Build all paragraph styles for the CV PDF."""
    styles = {}

    # Name — large, bold, centered
    styles["name"] = ParagraphStyle(
        "Name",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=COLORS["primary"],
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )

    # Title line — subtitle under name
    styles["title"] = ParagraphStyle(
        "Title",
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        textColor=COLORS["text_light"],
        alignment=TA_CENTER,
        spaceAfter=1.5 * mm,
    )

    # Contact info — small, centered
    styles["contact"] = ParagraphStyle(
        "Contact",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=COLORS["text_light"],
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )

    # Section heading — bold, uppercase-ish, with accent color
    styles["section_heading"] = ParagraphStyle(
        "SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=COLORS["accent"],
        spaceBefore=5 * mm,
        spaceAfter=1.5 * mm,
        borderPadding=(0, 0, 1, 0),
    )

    # Subsection title — bold, for project/job names
    styles["subsection_title"] = ParagraphStyle(
        "SubsectionTitle",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=COLORS["primary"],
        spaceBefore=2.5 * mm,
        spaceAfter=0.5 * mm,
    )

    # Subtitle — italic details (company, dates, tech)
    styles["subtitle"] = ParagraphStyle(
        "Subtitle",
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=11,
        textColor=COLORS["text_light"],
        spaceAfter=1 * mm,
    )

    # Body text — normal paragraph
    styles["body"] = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9.5,
        leading=12.5,
        textColor=COLORS["text"],
        alignment=TA_JUSTIFY,
        spaceAfter=1 * mm,
    )

    # Bullet text — for list items
    styles["bullet"] = ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=9.5,
        leading=12.5,
        textColor=COLORS["text"],
        leftIndent=4 * mm,
        spaceAfter=0.5 * mm,
    )

    # Skills inline — compact for skill lists
    styles["skills"] = ParagraphStyle(
        "Skills",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=COLORS["text"],
        spaceAfter=1 * mm,
    )

    # Cover letter styles
    styles["cl_body"] = ParagraphStyle(
        "CLBody",
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=COLORS["text"],
        alignment=TA_JUSTIFY,
        spaceAfter=3 * mm,
    )

    styles["cl_signoff"] = ParagraphStyle(
        "CLSignoff",
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=COLORS["text"],
        spaceBefore=4 * mm,
    )

    return styles


# ═══════════════════════════════════════════════════════════════
#  CV PDF Generator
# ═══════════════════════════════════════════════════════════════

class CVPDFGenerator:
    """
    Generates an ATS-friendly, single-column PDF from a tailored CV dict.

    Usage:
        gen = CVPDFGenerator()
        path = gen.generate(tailored_cv_dict, personal_info_dict)
        print(f"PDF saved to: {path}")
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.PDF_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = build_styles()

    def generate(
        self,
        tailored_cv: dict,
        personal: dict,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Generate a PDF from the tailored CV data.

        Args:
            tailored_cv: The tailored_cv dict from CVTailor.tailor_full()
            personal: Personal info dict from master_cv.json
            filename: Override filename (default: uses tailored_cv.ats_optimized_filename)

        Returns:
            Path to the generated PDF file
        """
        fname = filename or tailored_cv.get("ats_optimized_filename", "CV.pdf")
        if not fname.endswith(".pdf"):
            fname += ".pdf"

        output_path = self.output_dir / fname

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=LEFT_MARGIN,
            rightMargin=RIGHT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOTTOM_MARGIN,
            title=f"CV - {personal.get('full_name', personal.get('name', 'Candidate'))}",
            author=personal.get("full_name", personal.get("name", "")),
            subject=f"Application for {tailored_cv.get('target_job_title', 'Position')}",
        )

        story = []

        # ── Header: Name + Title + Contact ────────────────
        story.extend(self._build_header(personal, tailored_cv))

        # ── Professional Summary ──────────────────────────
        summary_data = tailored_cv.get("professional_summary", {})
        summary_text = summary_data.get("summary", "") if isinstance(summary_data, dict) else str(summary_data)
        if summary_text:
            story.extend(self._build_section("Professional Summary"))
            story.append(Paragraph(self._sanitize(summary_text), self.styles["body"]))
            story.append(Spacer(1, 1 * mm))

        # ── Technical Skills ──────────────────────────────
        skills = tailored_cv.get("skills", {})
        story.extend(self._build_skills_section(skills))

        # ── Project Experience ────────────────────────────
        projects = tailored_cv.get("projects", [])
        if projects:
            story.extend(self._build_section("Project Experience"))
            for proj in projects:
                story.extend(self._build_project(proj))

        # ── Work Experience ───────────────────────────────
        experience = tailored_cv.get("experience", [])
        if experience:
            story.extend(self._build_section("Work Experience"))
            for exp in experience:
                story.extend(self._build_experience(exp))

        # ── Education ─────────────────────────────────────
        education = tailored_cv.get("education", [])
        if education:
            story.extend(self._build_section("Education"))
            for edu in education:
                story.extend(self._build_education(edu))

        # Build the PDF
        try:
            doc.build(story)
            logger.info(f"📄 CV PDF generated: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"❌ PDF generation failed: {e}")
            raise

    def _build_header(self, personal: dict, cv: dict) -> list:
        """Build the name/title/contact header."""
        elements = []
        name = personal.get("full_name", personal.get("name", "Candidate"))
        title = cv.get("tailored_title", personal.get("title", ""))

        elements.append(Paragraph(self._sanitize(name), self.styles["name"]))

        if title:
            elements.append(Paragraph(self._sanitize(title), self.styles["title"]))

        # Contact line
        contact_parts = []
        if personal.get("email"):
            contact_parts.append(personal["email"])
        if personal.get("phone"):
            contact_parts.append(personal["phone"])
        if personal.get("location"):
            contact_parts.append(personal["location"])
        if personal.get("linkedin"):
            contact_parts.append(personal["linkedin"])
        if personal.get("github"):
            contact_parts.append(personal["github"])

        if contact_parts:
            contact_str = "  •  ".join(contact_parts)
            elements.append(Paragraph(self._sanitize(contact_str), self.styles["contact"]))

        # Header separator line
        elements.append(HRFlowable(
            width="100%",
            thickness=0.8,
            color=COLORS["accent"],
            spaceAfter=2 * mm,
            spaceBefore=1 * mm,
        ))

        return elements

    def _build_section(self, title: str) -> list:
        """Build a section heading with a subtle line."""
        return [
            Paragraph(self._sanitize(title.upper()), self.styles["section_heading"]),
            HRFlowable(
                width="100%",
                thickness=0.4,
                color=COLORS["line"],
                spaceAfter=2 * mm,
            ),
        ]

    def _build_skills_section(self, skills: dict) -> list:
        """Build the technical skills section."""
        elements = self._build_section("Technical Skills")

        primary = skills.get("primary_skills", [])
        secondary = skills.get("secondary_skills", [])
        additional = skills.get("additional_skills", [])

        if primary:
            text = f'<b>Core:</b>  {", ".join(primary)}'
            elements.append(Paragraph(text, self.styles["skills"]))

        if secondary:
            text = f'<b>Proficient:</b>  {", ".join(secondary)}'
            elements.append(Paragraph(text, self.styles["skills"]))

        if additional:
            text = f'<b>Familiar:</b>  {", ".join(additional)}'
            elements.append(Paragraph(text, self.styles["skills"]))

        elements.append(Spacer(1, 1 * mm))
        return elements

    def _build_project(self, project: dict) -> list:
        """Build a single project block."""
        elements = []

        name = project.get("name", "Project")
        desc = project.get("description", "")
        tech = project.get("tech_stack_display", [])
        highlights = project.get("highlights", [])

        # Project name
        elements.append(Paragraph(self._sanitize(name), self.styles["subsection_title"]))

        # Tech stack + description subtitle
        subtitle_parts = []
        if tech:
            subtitle_parts.append(", ".join(tech[:8]))
        if desc:
            subtitle_parts.append(desc)
        if subtitle_parts:
            elements.append(Paragraph(
                self._sanitize(" — ".join(subtitle_parts)),
                self.styles["subtitle"],
            ))

        # Bullet points
        for h in highlights[:4]:
            bullet_text = f'<bullet>&bull;</bullet> {self._sanitize(h)}'
            elements.append(Paragraph(bullet_text, self.styles["bullet"]))

        elements.append(Spacer(1, 1.5 * mm))

        return elements

    def _build_experience(self, exp: dict) -> list:
        """Build a single work experience block."""
        elements = []

        title = exp.get("title", "")
        company = exp.get("company", "")
        period = exp.get("period", "")
        highlights = exp.get("highlights", [])

        # Title line: Role | Company | Period
        title_line = f'{self._sanitize(title)}'
        if company:
            title_line += f'  <font color="{COLORS["text_light"].hexval()}">|  {self._sanitize(company)}</font>'
        elements.append(Paragraph(title_line, self.styles["subsection_title"]))

        if period:
            elements.append(Paragraph(self._sanitize(period), self.styles["subtitle"]))

        for h in highlights[:4]:
            bullet_text = f'<bullet>&bull;</bullet> {self._sanitize(h)}'
            elements.append(Paragraph(bullet_text, self.styles["bullet"]))

        elements.append(Spacer(1, 1.5 * mm))
        return elements

    def _build_education(self, edu: dict) -> list:
        """Build an education entry."""
        elements = []

        degree = edu.get("degree", "")
        institution = edu.get("institution", "")
        period = edu.get("period", "")
        gpa = edu.get("gpa", "")
        highlights = edu.get("highlights", [])

        if degree:
            elements.append(Paragraph(self._sanitize(degree), self.styles["subsection_title"]))

        subtitle_parts = []
        if institution:
            subtitle_parts.append(institution)
        if period:
            subtitle_parts.append(period)
        if gpa:
            subtitle_parts.append(f"GPA: {gpa}")
        if subtitle_parts:
            elements.append(Paragraph(
                self._sanitize("  |  ".join(subtitle_parts)),
                self.styles["subtitle"],
            ))

        for h in highlights[:3]:
            bullet_text = f'<bullet>&bull;</bullet> {self._sanitize(h)}'
            elements.append(Paragraph(bullet_text, self.styles["bullet"]))

        return elements

    @staticmethod
    def _sanitize(text: str) -> str:
        """Sanitize text for ReportLab XML parsing."""
        if not text:
            return ""
        # Escape XML special chars (but preserve our inline tags)
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        # Restore allowed tags
        for tag in ["b", "i", "u", "font", "bullet", "br"]:
            text = text.replace(f"&lt;{tag}&gt;", f"<{tag}>")
            text = text.replace(f"&lt;{tag} ", f"<{tag} ")
            text = text.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
        # Restore color attributes
        import re
        text = re.sub(r'color=&amp;quot;(.*?)&amp;quot;', r'color="\1"', text)
        text = re.sub(r'color=&quot;(.*?)&quot;', r'color="\1"', text)
        return text


# ═══════════════════════════════════════════════════════════════
#  Cover Letter PDF Generator
# ═══════════════════════════════════════════════════════════════

class CoverLetterPDFGenerator:
    """
    Generates a professional cover letter PDF.

    Usage:
        gen = CoverLetterPDFGenerator()
        path = gen.generate(cover_letter_dict, personal_dict, company_name)
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.PDF_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = build_styles()

    def generate(
        self,
        cover_letter: dict,
        personal: dict,
        company_name: str = "",
        job_title: str = "",
        filename: Optional[str] = None,
    ) -> Path:
        """Generate a cover letter PDF."""
        if not filename:
            name_part = personal.get("full_name", personal.get("name", "Candidate")).replace(" ", "_")
            company_part = (company_name or "Company").replace(" ", "_")
            filename = f"{name_part}_{company_part}_Cover_Letter.pdf"

        if not filename.endswith(".pdf"):
            filename += ".pdf"

        output_path = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=25 * mm,
            rightMargin=25 * mm,
            topMargin=25 * mm,
            bottomMargin=25 * mm,
            title=f"Cover Letter - {personal.get('full_name', personal.get('name', ''))}",
            author=personal.get("full_name", personal.get("name", "")),
            subject=f"Cover Letter for {job_title}",
        )

        story = []

        # ── Header ────────────────────────────────────────
        name = personal.get("full_name", personal.get("name", ""))
        elements_header = []
        elements_header.append(Paragraph(
            self._sanitize(name), self.styles["name"]
        ))

        contact_parts = []
        if personal.get("email"):
            contact_parts.append(personal["email"])
        if personal.get("phone"):
            contact_parts.append(personal["phone"])
        if personal.get("location"):
            contact_parts.append(personal["location"])
        if contact_parts:
            elements_header.append(Paragraph(
                self._sanitize("  •  ".join(contact_parts)),
                self.styles["contact"],
            ))

        elements_header.append(HRFlowable(
            width="100%", thickness=0.5, color=COLORS["accent"],
            spaceAfter=6 * mm, spaceBefore=2 * mm,
        ))

        story.extend(elements_header)

        # ── Date ──────────────────────────────────────────
        date_str = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(self._sanitize(date_str), self.styles["subtitle"]))
        story.append(Spacer(1, 4 * mm))

        # ── Letter Body ───────────────────────────────────
        full_text = cover_letter.get("full_text", "")

        if full_text:
            # Split by double newlines into paragraphs
            paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
            for para in paragraphs:
                # Replace single newlines within a paragraph
                para = para.replace("\n", "<br/>")
                story.append(Paragraph(self._sanitize(para), self.styles["cl_body"]))
        else:
            # Build from structured fields (supports both old and new schema)
            greeting = cover_letter.get("greeting", "")
            if greeting:
                story.append(Paragraph(self._sanitize(greeting), self.styles["cl_body"]))

            # New 3-paragraph structure: Hook → Proof → CTA
            for field in ["hook_paragraph", "proof_paragraph", "cta_paragraph",
                          # Fallback to old field names
                          "opening_paragraph", "body_paragraph",
                          "company_alignment", "closing_paragraph"]:
                text = cover_letter.get(field, "")
                if text:
                    story.append(Paragraph(self._sanitize(text), self.styles["cl_body"]))

            sign_off = cover_letter.get("sign_off", "Best,\nJanith Viranga")
            if sign_off:
                sign_off = sign_off.replace("\n", "<br/>")
                story.append(Paragraph(self._sanitize(sign_off), self.styles["cl_signoff"]))

        try:
            doc.build(story)
            logger.info(f"✉️ Cover Letter PDF generated: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"❌ Cover Letter PDF failed: {e}")
            raise

    @staticmethod
    def _sanitize(text: str) -> str:
        """Sanitize text for ReportLab."""
        if not text:
            return ""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;").replace(">", "&gt;")
        for tag in ["b", "i", "u", "br", "font"]:
            text = text.replace(f"&lt;{tag}&gt;", f"<{tag}>")
            text = text.replace(f"&lt;{tag}/&gt;", f"<{tag}/>")
            text = text.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
        return text


# ═══════════════════════════════════════════════════════════════
#  Unified Generator (CV + Cover Letter)
# ═══════════════════════════════════════════════════════════════

class DocumentGenerator:
    """
    Unified document generator that produces both CV and Cover Letter PDFs.

    Usage:
        gen = DocumentGenerator()
        result = gen.generate_all(tailored_cv, cover_letter, personal)
        # result = {"cv_path": Path, "cover_letter_path": Path}
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.cv_gen = CVPDFGenerator(output_dir)
        self.cl_gen = CoverLetterPDFGenerator(output_dir)

    def generate_all(
        self,
        tailored_cv: dict,
        cover_letter: Optional[dict],
        personal: dict,
    ) -> dict:
        """Generate both CV and Cover Letter PDFs."""
        result = {}

        # Generate CV
        cv_path = self.cv_gen.generate(tailored_cv, personal)
        result["cv_path"] = str(cv_path)
        result["cv_filename"] = cv_path.name

        # Generate Cover Letter if available
        if cover_letter:
            cl_path = self.cl_gen.generate(
                cover_letter,
                personal,
                company_name=tailored_cv.get("target_company", ""),
                job_title=tailored_cv.get("target_job_title", ""),
            )
            result["cover_letter_path"] = str(cl_path)
            result["cover_letter_filename"] = cl_path.name

        return result
