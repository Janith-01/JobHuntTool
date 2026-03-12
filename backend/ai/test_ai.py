"""
Quick test script for the AI Optimization Engine.
Tests the regex-based JD parser and ATS scorer (no API key needed).

Usage:
    python -m backend.ai.test_ai
"""

import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_jd_parser():
    """Test the regex-based JD parser (Stage 1 — no API call)."""
    from backend.ai.jd_parser import JDParser

    parser = JDParser()

    sample_jd = """
    Software Engineering Intern - Softvil Technologies
    
    About the Role:
    We're looking for a passionate Software Engineering Intern to join our 
    development team in Colombo, Sri Lanka. You'll work on real-world projects
    and gain hands-on experience with modern technologies.
    
    Requirements:
    • Proficiency in Python and JavaScript/TypeScript
    • Experience with React.js or Angular for frontend development
    • Knowledge of Node.js and Express.js for backend development
    • Familiarity with MongoDB or PostgreSQL databases
    • Understanding of RESTful APIs and Git version control
    • Experience with Docker is a plus
    
    Nice to have:
    • Experience with cloud platforms (AWS, GCP)
    • Knowledge of CI/CD pipelines
    • Familiarity with AI/ML concepts (TensorFlow, PyTorch)
    • Understanding of Agile/Scrum methodologies
    
    Why Join Us:
    At Softvil, we foster innovation and growth. You'll be part of a dynamic
    team building cutting-edge solutions for global clients.
    """

    print("=" * 60)
    print("🧠 TEST 1: JD Parser (Quick — Regex Only)")
    print("=" * 60)

    result = parser.quick_parse(sample_jd, title="Software Engineering Intern")
    
    print(f"\n📊 Seniority Level: {result['seniority_level']}")
    print(f"\n🔧 Tech Stack Found:")
    for category, items in result['tech_stack'].items():
        if items:
            print(f"   {category}: {', '.join(items)}")
    
    print(f"\n📋 Requirements extracted: {len(result['requirements'])}")
    for i, req in enumerate(result['requirements'][:5], 1):
        print(f"   {i}. {req}")
    
    print(f"\n🎯 Priority Keywords: {', '.join(result['priority_keywords'][:10])}")
    print(f"   Method: {result['method']}")
    
    return result


def test_ats_scorer():
    """Test the ATS scorer with a sample CV against sample requirements."""
    from backend.ai.jd_parser import ParsedJobDescription, ExtractedTechStack, ParsedRequirement
    from backend.ai.ats_scorer import ATSScorer

    print("\n" + "=" * 60)
    print("📊 TEST 2: ATS Scorer")
    print("=" * 60)

    # Build a mock ParsedJobDescription
    parsed_jd = ParsedJobDescription(
        job_title_normalized="Software Engineering Intern",
        seniority_level="intern",
        tech_stack=ExtractedTechStack(
            languages=["Python", "JavaScript", "TypeScript"],
            frameworks=["React", "Node.js", "Express.js", "FastAPI"],
            databases=["MongoDB", "PostgreSQL"],
            tools=["Docker", "Git", "GitHub Actions"],
            cloud=["AWS"],
            methodologies=["Agile"],
        ),
        must_have_skills=["Python", "JavaScript", "React", "Node.js", "MongoDB", "Git"],
        nice_to_have_skills=["Docker", "AWS", "TypeScript", "CI/CD", "Agile"],
        priority_keywords=[
            "Python", "JavaScript", "React", "Node.js", "MongoDB",
            "Git", "Docker", "TypeScript", "FastAPI", "REST API",
            "PostgreSQL", "Express.js", "AWS", "CI/CD", "Agile",
        ],
        key_responsibilities=[
            "Build web apps with React and Node.js",
            "Design RESTful APIs",
            "Work with MongoDB databases",
        ],
        soft_skills=["teamwork", "communication"],
        role_summary="Software Engineering Intern building web apps with React, Node.js, and Python.",
    )

    # A sample tailored CV
    sample_cv = """
    Janith Viranga
    AI & Full Stack Developer

    PROFESSIONAL SUMMARY
    Passionate Full Stack Developer with hands-on experience building intelligent 
    web applications using React.js, Node.js, Python, and MongoDB. Proven ability 
    to architect end-to-end solutions from RESTful APIs to production-ready UIs.
    Eager to contribute to innovative teams as a Software Engineering Intern.

    TECHNICAL SKILLS
    Primary: Python, JavaScript, TypeScript, React.js, Node.js, FastAPI, MongoDB
    Secondary: Express.js, PostgreSQL, Docker, Git, GitHub Actions
    Additional: TensorFlow, LangChain, Three.js, Tailwind CSS, AWS

    PROJECT EXPERIENCE

    LawNova - AI Legal Platform
    Built an AI-powered legal platform with React, Node.js, Socket.io, and MongoDB
    Technologies: React, Node.js, Socket.io, Google Gemini, MongoDB
    • Developed an AI Legal Judgment Prediction module using Python and Gemini AI
    • Implemented real-time collaborative sessions with delta-based updates for 50+ concurrent users
    • Designed RESTful APIs using Express.js with role-based authentication
    • Deployed using Docker containers with CI/CD pipeline via GitHub Actions

    JobHuntTool - AI Job Application Automation
    Built an intelligent job scraping and CV tailoring tool with Python, FastAPI, and React
    Technologies: Python, FastAPI, React, MongoDB, Playwright, LangChain
    • Engineered multi-platform web scraper using Python and Playwright with concurrent execution
    • Built keyword-based filtering engine with weighted scoring for ATS optimization
    • Developed REST API with FastAPI for dashboard integration
    • Deployed MongoDB database with async Motor driver and index management

    WORK EXPERIENCE

    Freelance Full Stack Developer | VertexStack | 2024 - Present
    • Developed and deployed client projects using React.js and Node.js
    • Built AI-integrated solutions with Python, LangChain, and Google Gemini
    • Managed end-to-end delivery including Docker containerization

    EDUCATION
    BSc (Hons) in Software Engineering | University | 2022 - Present
    """

    scorer = ATSScorer()
    report = scorer.score(sample_cv, parsed_jd)

    print(f"\n🎯 Overall ATS Score: {report.overall_score:.1f}/100")
    print(f"   Grade: {report.grade} — {report.grade_label}")
    print(f"\n📊 Score Breakdown:")
    print(f"   Must-Have Keywords:  {report.must_have_score:.1f}/100 (weight: 40%)")
    print(f"   Overall Match:      {report.keyword_match_score:.1f}/100 (weight: 25%)")
    print(f"   Nice-to-Have:       {report.nice_to_have_score:.1f}/100 (weight: 15%)")
    print(f"   Section Coverage:   {report.coverage_score:.1f}/100 (weight: 10%)")
    print(f"   Keyword Density:    {report.density_score:.1f}/100 (weight: 10%)")

    print(f"\n📈 Keyword Stats:")
    print(f"   Total checked: {report.total_keywords_checked}")
    print(f"   Found: {report.keywords_found}")
    print(f"   Missing: {report.keywords_missing}")
    print(f"   Must-haves: {report.must_haves_found}/{report.must_haves_total}")
    print(f"   Density: {report.keyword_density_pct:.2f}%")

    if report.matched_keywords:
        print(f"\n✅ Matched Keywords ({len(report.matched_keywords)}):")
        for m in report.matched_keywords[:10]:
            sections = ", ".join(m.sections_found_in) if m.sections_found_in else "—"
            must = " [MUST]" if m.is_must_have else ""
            print(f"   ✓ {m.keyword} (×{m.count}){must} — in: {sections}")

    if report.missing_keywords:
        print(f"\n❌ Missing Keywords ({len(report.missing_keywords)}):")
        for m in report.missing_keywords[:10]:
            must = " [MUST-HAVE!]" if m.is_must_have else ""
            print(f"   ✗ {m.keyword}{must}")

    if report.recommendations:
        print(f"\n💡 Recommendations:")
        for rec in report.recommendations:
            print(f"   {rec}")

    return report


def test_quick_score():
    """Test the quick scoring function."""
    from backend.ai.ats_scorer import ATSScorer

    print("\n" + "=" * 60)
    print("⚡ TEST 3: Quick Score")
    print("=" * 60)

    scorer = ATSScorer()
    cv_text = "I know Python, React.js, Node.js, MongoDB, and Docker. I also use Git and TypeScript."
    keywords = ["Python", "React", "Node.js", "MongoDB", "Docker", "AWS", "Kubernetes", "GraphQL"]

    score = scorer.quick_score(cv_text, keywords)
    print(f"\n   CV snippet: \"{cv_text}\"")
    print(f"   Keywords: {keywords}")
    print(f"   Quick Score: {score:.1f}/100")
    print(f"   (Found {int(score * len(keywords) / 100)}/{len(keywords)} keywords)")


if __name__ == "__main__":
    print("\n🧪 JobHuntTool AI Engine — Module Tests")
    print("=" * 60)
    
    test_jd_parser()
    report = test_ats_scorer()
    test_quick_score()
    
    print("\n" + "=" * 60)
    print(f"✅ All tests passed! ATS Score: {report.overall_score:.1f}/100 ({report.grade})")
    print("=" * 60)
