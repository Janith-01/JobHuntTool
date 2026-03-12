"""
Test script for the PDF Document Generator.
Generates a sample CV and Cover Letter PDF from mock data.

Usage:
    python -m backend.generator.test_pdf
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from backend.generator.pdf_generator import DocumentGenerator


def test_pdf_generation():
    """Generate test CV and Cover Letter PDFs from mock data."""

    print("\n" + "=" * 60)
    print("📄 PDF Document Generator — Test")
    print("=" * 60)

    # Mock tailored CV data (as if from the AI engine)
    tailored_cv = {
        "target_job_title": "Software Engineering Intern",
        "target_company": "Softvil Technologies",
        "tailored_title": "AI & Full Stack Developer",
        "ats_optimized_filename": "Janith_Viranga_Softvil_SWE_Intern.pdf",
        "professional_summary": {
            "summary": "Results-driven Full Stack Developer with hands-on experience building intelligent web applications using React, Node.js, Python, and MongoDB. Demonstrated expertise in implementing AI-powered solutions with LangChain and Google Gemini. Proven ability to architect end-to-end systems from RESTful APIs to production-ready UIs with a focus on clean code practices and scalable architectures.",
            "tone": "professional",
            "keywords_woven_in": ["React", "Node.js", "Python", "MongoDB", "AI"],
        },
        "skills": {
            "primary_skills": ["Python", "JavaScript", "React.js", "Node.js", "MongoDB", "Git"],
            "secondary_skills": ["TypeScript", "FastAPI", "Docker", "Express.js", "PostgreSQL"],
            "additional_skills": ["TensorFlow", "LangChain", "Three.js", "Tailwind CSS"],
        },
        "projects": [
            {
                "name": "LawNova — AI Legal Platform",
                "description": "AI-powered legal technology platform with mock trial simulations and judgment prediction.",
                "tech_stack_display": ["React", "Node.js", "Socket.io", "Google Gemini", "MongoDB"],
                "highlights": [
                    "Built an AI Legal Judgment Prediction module using TF-IDF similarity matching and Gemini AI, achieving 85% accuracy on test cases",
                    "Implemented real-time collaborative sessions with delta-based updates supporting 50+ concurrent users",
                    "Designed RESTful APIs using Express.js with role-based authentication and WebSocket integration",
                    "Deployed using Docker containers with CI/CD pipeline via GitHub Actions",
                ],
                "relevance_note": "Demonstrates full-stack and AI skills",
            },
            {
                "name": "JobHuntTool — AI Job Application Automation",
                "description": "Intelligent tool for scraping job boards, filtering with AI, and generating tailored CVs.",
                "tech_stack_display": ["Python", "FastAPI", "React", "MongoDB", "Playwright", "LangChain"],
                "highlights": [
                    "Engineered multi-platform web scraper using Python and Playwright with concurrent execution achieving 3x throughput",
                    "Built keyword-based filtering engine with weighted scoring for ATS optimization",
                    "Developed REST API with FastAPI for dashboard integration with async MongoDB driver",
                    "Integrated LangChain and Google Gemini for automated CV tailoring and cover letter generation",
                ],
                "relevance_note": "Shows Python/FastAPI backend + AI integration",
            },
            {
                "name": "3D Solar System Portfolio",
                "description": "Interactive 3D portfolio mapping projects to planets using React Three Fiber.",
                "tech_stack_display": ["React", "Three.js", "TypeScript", "Vite"],
                "highlights": [
                    "Procedurally generated planet textures with custom shader materials",
                    "Implemented click-to-zoom camera animations with smooth transitions using maath library",
                    "Built adaptive performance settings automatically adjusting for device capabilities",
                ],
                "relevance_note": "Frontend/React creativity",
            },
        ],
        "experience": [
            {
                "title": "Freelance Full Stack Developer",
                "company": "VertexStack",
                "period": "2024 - Present",
                "highlights": [
                    "Developed and deployed 5+ client projects using React.js and Node.js with 100% on-time delivery",
                    "Built AI-integrated solutions leveraging LangChain and Google Gemini for automated workflows",
                    "Managed end-to-end project delivery including Docker containerization and CI/CD pipelines",
                ],
            },
        ],
        "education": [
            {
                "degree": "BSc (Hons) in Software Engineering",
                "institution": "University of Sri Lanka",
                "period": "2022 - Present",
                "gpa": "3.7 / 4.0",
                "highlights": [
                    "Relevant coursework: Data Structures, Algorithms, AI, Software Architecture",
                    "Dean's List - Multiple Semesters",
                ],
            },
        ],
    }

    # Mock personal info
    personal = {
        "full_name": "Janith Viranga",
        "email": "janith@vertexstack.com",
        "phone": "+94 XX XXX XXXX",
        "location": "Sri Lanka",
        "linkedin": "linkedin.com/in/janithviranga",
        "github": "github.com/janithviranga",
        "title": "AI & Full Stack Developer",
    }

    # Mock cover letter (3-paragraph: Hook → Proof → CTA)
    cover_letter = {
        "subject_line": "Janith Viranga — Software Engineering Intern Application",
        "greeting": "Hi there,",
        "hook_paragraph": "Your posting for the SWE Intern role mentions building scalable web applications with React and Node.js — and I noticed LangChain listed as a nice-to-have. That's exactly what I've been shipping for the past year.",
        "proof_paragraph": "On LawNova, I built an AI judgment prediction module using LangChain and Gemini that handles 50+ concurrent mock trial sessions with delta-based real-time updates. The backend runs on Express.js with role-based auth and WebSocket integration — deployed via Docker with GitHub Actions CI/CD.",
        "cta_paragraph": "I've attached my CV (Janith_Viranga_Softvil_SWE_Intern.pdf) tailored to this role. I'm available for a call this week or next — happy to walk through LawNova's architecture or any of the other projects in detail.",
        "sign_off": "Best,\nJanith Viranga",
        "full_text": "",
    }

    # Generate PDFs
    output_dir = Path("output/pdfs/test")
    gen = DocumentGenerator(output_dir)

    print("\n📄 Generating CV PDF...")
    result = gen.generate_all(tailored_cv, cover_letter, personal)

    print(f"\n✅ Files generated:")
    for key, value in result.items():
        print(f"   {key}: {value}")

    # Verify files exist
    for path_key in ["cv_path", "cover_letter_path"]:
        if path_key in result:
            p = Path(result[path_key])
            if p.exists():
                size_kb = p.stat().st_size / 1024
                print(f"   ✓ {p.name} — {size_kb:.1f} KB")
            else:
                print(f"   ✗ {p.name} — FILE NOT FOUND")

    print("\n" + "=" * 60)
    print(f"✅ PDF generation test complete!")
    print(f"   Output directory: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    test_pdf_generation()
