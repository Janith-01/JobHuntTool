"""
Test the Contact Extractor with sample scraped job posting text.

Usage:
    python -m backend.ai.test_contact_extractor
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.ai.contact_extractor import ContactExtractor


def test_extractor():
    print("\n" + "=" * 60)
    print("📧 Contact Extractor — Test Suite")
    print("=" * 60)

    extractor = ContactExtractor()

    # ── Test 1: Clear HR email with company ─────────────────
    print("\n━━ Test 1: HR email with company name ━━")
    text_1 = """
    Softvil Technologies is hiring!

    AI Engineer Intern — Join our innovative AI team

    Requirements:
    - Strong Python, LangChain experience
    - Familiarity with React.js and Node.js
    - Experience with MongoDB or PostgreSQL
    
    Nice to Have:
    - Docker and CI/CD pipeline experience
    - Three.js or WebGL knowledge

    Send your CV to: hr@softvil.com
    Applications close: March 15, 2026

    About Softvil Technologies:
    We build cutting-edge solutions for global clients.
    """
    result = extractor.extract(text_1, job_title="AI Engineer Intern")
    _print_result(result)

    # ── Test 2: Multiple emails, personal contact ──────────
    print("\n━━ Test 2: Multiple emails, named contact ━━")
    text_2 = """
    Full Stack Developer — Synexis (Pvt) Ltd

    We are looking for a passionate developer to join our team.

    Requirements:
    • React, TypeScript, Node.js
    • PostgreSQL or MongoDB
    • Git, GitHub Actions

    Contact: Dilshan Perera
    Email your application to: dilshan.perera@synexis.lk
    General inquiries: info@synexis.lk

    Website: https://synexis.lk
    """
    result = extractor.extract(text_2, job_title="Full Stack Developer")
    _print_result(result)

    # ── Test 3: Email in paragraph, no explicit "send to" ──
    print("\n━━ Test 3: Email embedded in paragraph ━━")
    text_3 = """
    Junior Software Engineer — WSO2

    WSO2 is seeking talented engineers. If you're interested,
    reach out to careers@wso2.com with your resume attached.

    We offer competitive salaries and a great work environment.
    """
    result = extractor.extract(text_3, job_title="Junior Software Engineer")
    _print_result(result)

    # ── Test 4: No email found ────────────────────────────
    print("\n━━ Test 4: No email in text ━━")
    text_4 = """
    Software Intern — Apply on our website

    Visit careers.google.com to apply.
    No direct email applications accepted.
    """
    result = extractor.extract(text_4, job_title="Software Intern", use_llm=False)
    _print_result(result)

    # ── Test 5: Company hint provided ─────────────────────
    print("\n━━ Test 5: Company hint override ━━")
    text_5 = """
    We're hiring a DevOps Engineer! Send your CV to jobs@acmetech.io.
    """
    result = extractor.extract(
        text_5,
        job_title="DevOps Engineer",
        company_name_hint="ACME Technologies (Pvt) Ltd",
    )
    _print_result(result)

    print("\n" + "=" * 60)
    print("✅ Contact Extractor tests complete!")
    print("=" * 60)


def _print_result(result):
    print(f"  📧 Email:      {result.recipient_email or '(not found)'}")
    print(f"  🏢 Company:    {result.company_name or '(not found)'}")
    print(f"  📝 Subject:    {result.subject_line}")
    print(f"  👤 Contact:    {result.contact_person or '(not found)'}")
    print(f"  🎯 Confidence: {result.confidence}")
    print(f"  📋 All emails: {result.all_emails_found}")
    print(f"  ⚙️  Method:     {result.extraction_method}")


if __name__ == "__main__":
    test_extractor()
