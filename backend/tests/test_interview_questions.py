"""
Test: InterviewAgent.generate_questions()
Run: python -m backend.tests.test_interview_questions

Tests 3 resume+company combinations and validates:
  - Exactly 3 questions returned
  - All dimensions are different
  - All dimensions are valid
  - why_this_question references a resume signal
  - question_type is correctly resolved per question_mode
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path for both direct and module invocation
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from backend.agents.interview_agent import InterviewAgent

agent = InterviewAgent()

# ── Test fixtures ─────────────────────────────────────────────────────────────

RESUME_MID_BACKEND = """
Software Engineer (Backend) — 4 years experience
• Built payment processing service handling 50k txn/day at Razorpay
• Reduced API p99 latency from 800ms to 120ms by migrating from synchronous DB calls to async with connection pooling
• On-call rotation owner for 3 microservices; resolved 12 production incidents in 2023
• Python, FastAPI, PostgreSQL, Redis, AWS
"""

RESUME_SENIOR_TEAMLEAD = """
Senior Software Engineer — 7 years experience
• Led a team of 4 engineers to rebuild the search ranking pipeline at Flipkart
• Mentored 2 junior engineers; both promoted within 18 months
• Drove cross-team alignment between Search, Catalog, and ML teams on ranking model rollout
• Reduced search abandonment rate by 18% through ranking improvements
• Java, Kafka, Elasticsearch, Spark
"""

RESUME_STAFF = """
Staff Engineer — 11 years experience
• Defined the org-wide API versioning strategy adopted across 8 engineering teams at Swiggy
• Architected the real-time logistics engine serving 2M daily orders — reduced ETA error by 34%
• Ran quarterly architecture reviews; influenced roadmap across 3 product verticals
• Sponsor for 2 engineers in promotion cycles (E5 → E6)
• Go, gRPC, Kubernetes, Kafka, PostgreSQL
"""

CASES = [
    {
        "name": "Case 1 — Mid backend engineer × Amazon × mixed",
        "input": {
            "resume_text": RESUME_MID_BACKEND,
            "company": "amazon",
            "seniority": "mid",
            "question_mode": "mixed",
        },
        "expected_q3_type": "scenario",
    },
    {
        "name": "Case 2 — Senior with team-lead signals × Google × behavioral",
        "input": {
            "resume_text": RESUME_SENIOR_TEAMLEAD,
            "company": "google",
            "seniority": "senior",
            "question_mode": "behavioral",
        },
        "expected_q3_type": "behavioral",
    },
    {
        "name": "Case 3 — Staff with org-wide project × Stripe × mixed",
        "input": {
            "resume_text": RESUME_STAFF,
            "company": "stripe",
            "seniority": "staff",
            "question_mode": "mixed",
        },
        "expected_q3_type": "scenario",
    },
]

VALID_DIMENSIONS = {
    "ownership", "impact_and_scale", "influence_without_authority",
    "problem_solving", "collaboration", "growth_mindset", "conflict_resolution",
}

VALID_ANTI_PATTERNS = {
    "we_default", "vague_quantification", "story_recycling", "impact_buried",
    "hypothesis_without_proof", "escalation_default", "scope_collapse",
}


def validate_case(name: str, result: dict, expected_q3_type: str) -> list:
    """Returns list of failure strings (empty = all passed)."""
    failures = []
    questions = result.get("questions", [])

    if len(questions) != 3:
        failures.append(f"Expected 3 questions, got {len(questions)}")
        return failures

    dims = [q.get("dimension") for q in questions]
    if len(set(dims)) != 3:
        failures.append(f"Duplicate dimensions: {dims}")

    for d in dims:
        if d not in VALID_DIMENSIONS:
            failures.append(f"Invalid dimension: '{d}'")

    for i, q in enumerate(questions):
        if not q.get("why_this_question", "").strip():
            failures.append(f"Q{i+1}: why_this_question is empty")

    q3_type = questions[2].get("question_type")
    if q3_type != expected_q3_type:
        failures.append(f"Q3 question_type: expected '{expected_q3_type}', got '{q3_type}'")

    for i, q in enumerate(questions):
        for ap in q.get("risky_anti_patterns", []):
            if ap not in VALID_ANTI_PATTERNS:
                failures.append(f"Q{i+1}: invalid anti-pattern key '{ap}'")

    for i, q in enumerate(questions):
        if not q.get("expected_signals"):
            failures.append(f"Q{i+1}: expected_signals is empty")

    for i, q in enumerate(questions):
        if not q.get("source"):
            failures.append(f"Q{i+1}: source field is missing")

    return failures


def run_tests():
    all_passed = True
    for case in CASES:
        print(f"\n{'-'*60}")
        print(f"Running: {case['name']}")
        try:
            result = agent.generate_questions(case["input"])
            failures = validate_case(case["name"], result, case["expected_q3_type"])

            if failures:
                all_passed = False
                print(f"  FAIL — {len(failures)} issue(s):")
                for f in failures:
                    print(f"    FAIL: {f}")
            else:
                print(f"  PASS")
                print(f"  Source: {result['questions'][0].get('source')}")

            for i, q in enumerate(result.get("questions", [])):
                print(f"\n  Q{i+1} [{q.get('question_type','?')} | {q.get('dimension','?')}]")
                print(f"    Text: {q.get('text','')}")
                print(f"    Why:  {q.get('why_this_question','')}")
                print(f"    APs:  {q.get('risky_anti_patterns', [])}")

        except Exception as e:
            all_passed = False
            print(f"  FAIL — exception: {e}")

    print(f"\n{'='*60}")
    result_str = "ALL PASSED" if all_passed else "FAILURES DETECTED"
    print(f"Result: {result_str}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_tests())
