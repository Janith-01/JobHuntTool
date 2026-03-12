"""
Test script for the Application Email Generator.
Run: python -m backend.ai.test_application_email
"""

from backend.ai.application_email_generator import ApplicationEmailGenerator


# ─── Sample Job Descriptions ────────────────────────────────

SAMPLE_JD_SOFTVIL = """
AI Engineer Intern – Softvil Technologies (Pvt) Ltd

We are looking for an AI Engineer Intern to join our growing team.
You will work on building intelligent systems using Python, LangChain,
and large language models.

Responsibilities:
- Develop and deploy AI-powered features using LangChain and Python
- Build RAG pipelines and agentic workflows
- Integrate LLM APIs (OpenAI, Gemini) into production applications
- Collaborate with the full-stack team on API design

Requirements:
- Strong Python skills
- Experience with LangChain, LLM APIs, or similar frameworks
- Understanding of prompt engineering and RAG patterns
- Familiarity with MongoDB and REST APIs

Nice to Have:
- React.js or Node.js experience
- Docker and CI/CD knowledge
- Published projects using AI/ML
"""

SAMPLE_JD_SYNEXIS = """
Junior Frontend Developer – Synexis Solutions

Synexis Solutions is hiring a Junior Frontend Developer to help
build modern web applications.

Responsibilities:
- Build responsive UIs using React.js and TypeScript
- Collaborate with backend developers on API integration
- Write clean, maintainable, and well-tested code
- Participate in code reviews and sprint planning

Requirements:
- Proficiency in React.js, JavaScript, and CSS
- Experience with REST APIs and state management
- Understanding of responsive design principles
- Team collaboration skills

Nice to Have:
- Node.js backend experience
- Experience with Tailwind CSS
- Leadership or project management experience
"""

SAMPLE_JD_FULLSTACK = """
Full Stack Developer Intern – CodeGen International

Join CodeGen as a Full Stack Developer Intern and work on
enterprise-grade web applications.

Responsibilities:
- Develop features across the full MERN stack
- Design and implement RESTful APIs
- Work with MongoDB for data persistence
- Participate in agile development processes

Requirements:
- Experience with MongoDB, Express.js, React, and Node.js
- Understanding of MVC architecture
- Strong JavaScript skills
- Problem-solving ability

Nice to Have:
- WebSocket or real-time application experience
- Docker knowledge
- API documentation skills
"""


def main():
    gen = ApplicationEmailGenerator()
    print("=" * 70)
    print("  APPLICATION EMAIL GENERATOR — Test Suite")
    print("=" * 70)

    tests = [
        ("AI Engineer Intern", "Softvil Technologies", SAMPLE_JD_SOFTVIL, "Dilshan Perera"),
        ("Junior Frontend Developer", "Synexis Solutions", SAMPLE_JD_SYNEXIS, ""),
        ("Full Stack Developer Intern", "CodeGen International", SAMPLE_JD_FULLSTACK, "Amal"),
    ]

    for job_title, company, jd, contact in tests:
        print(f"\n{'─' * 70}")
        print(f"  📧 {job_title} @ {company}")
        print(f"{'─' * 70}\n")

        email = gen.generate(
            job_title=job_title,
            company_name=company,
            job_description=jd,
            contact_person=contact,
        )

        print(f"Subject: {email.subject_line}")
        print(f"Matched Skill: {email.matched_skill or '(general)'}")
        print(f"Matched Project: {email.matched_project or '(portfolio-wide)'}")
        print(f"Mode: {email.generation_mode}")
        print()
        print(email.full_text)
        print()

    print("=" * 70)
    print("  ✅ All tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
