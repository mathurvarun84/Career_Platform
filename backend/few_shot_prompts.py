"""
RIP V2 — Role-Aware Few-Shot Prompt Library
============================================
Drop-in module for resume_understanding.py, gap_analyzer.py, and recruiter_sim.py.

Usage pattern:
    from backend.few_shot_prompts import get_role_context, build_few_shot_block
    role_ctx = get_role_context(detected_role_family)
    system_prompt = BASE_SYSTEM_PROMPT + role_ctx.system_addendum + build_few_shot_block(role)

Role families: ENGINEERING | PRODUCT | MARKETING | DATA_ANALYST | HR | FINANCE | DESIGN
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RoleFewShotExample:
    label: str
    resume_snippet: str
    expected_output: dict


@dataclass
class RoleContext:
    role_family: str
    seniority_signals: List[str]
    metric_vocabulary: List[str]
    domain_vocabulary: List[str]
    weakness_patterns: List[str]
    strength_signals: List[str]
    system_addendum: str
    few_shot_examples: List[RoleFewShotExample]


ENGINEERING_CONTEXT = RoleContext(
    role_family="ENGINEERING",
    seniority_signals=[
        "IC track: SDE → SDE2 → SDE3 → Staff → Principal",
        "Manager track: TL → EM → SDE-M → Director",
        "System design ownership signals (designed, architected, led migration)",
        "Team scope (individual, pair, squad, cross-org)",
        "On-call / incident commander mentions",
    ],
    metric_vocabulary=[
        "p99 latency", "throughput (RPS/QPS)", "uptime/SLA %",
        "infra cost reduction", "build time", "deploy frequency",
        "MTTR", "scale (DAU/MAU in millions)", "data volume (TB/PB)",
        "API response time", "error rate reduction",
    ],
    domain_vocabulary=[
        "microservices", "Kafka", "Redis", "Kubernetes", "CI/CD",
        "REST/gRPC", "distributed systems", "sharding", "caching",
        "load balancing", "observability", "IaC", "event-driven",
    ],
    weakness_patterns=[
        "No scale/volume numbers (just 'improved performance')",
        "Tool list without ownership context",
        "No system design or architecture contribution",
        "All IC bullets — no cross-team or mentorship for Sr roles",
        "Missing on-call / production ownership signals",
    ],
    strength_signals=[
        "Quantified latency/scale improvements",
        "Explicit 'designed' or 'architected' at component level",
        "Mentorship + tech talks for senior IC",
        "Migration or re-architecture with before/after metrics",
        "Cross-team unblocking or API contract ownership",
    ],
    system_addendum="""
You are evaluating a SOFTWARE ENGINEERING resume. Apply these domain-specific rules:

SENIORITY CALIBRATION:
- Junior (0-3yr): Look for project completion, code quality signals, testing hygiene
- Mid (3-7yr): Expect ownership of services/components, on-call, some design decisions
- Senior (7+yr IC): System-level thinking, cross-team impact, mentorship — NOT people managers
- Staff/Principal IC: Cross-org influence — title must say Staff/Principal Engineer
- EM (any YoE if title says Engineering Manager): team size, hiring, delivery, stakeholders
- Director: org-level scope, multi-team, strategy — NOT the same as Staff IC
- NEVER label Engineering Manager as 'staff' because years > 11

METRIC STANDARDS (mark 'has_metrics: false' if only qualitative):
- Acceptable: "reduced p99 latency from 800ms to 120ms", "scaled to 50M DAU", "cut infra cost by 30%"
- NOT acceptable: "improved performance", "optimized queries", "made system faster"

WEAKNESS DETECTION: Flag if senior/staff roles lack architecture ownership or team impact.
Red flag phrase list: "assisted with", "helped", "was part of", "contributed to" (without specifics).
""",
    few_shot_examples=[
        RoleFewShotExample(
            label="WEAK",
            resume_snippet="""
Senior Software Engineer @ Zomato (2019-2023)
- Worked on backend services for order management
- Used Java, Spring Boot, MySQL, Redis
- Improved system performance
- Part of the platform team
""",
            expected_output={
                "seniority_detected": "mid",
                "has_metrics": False,
                "ownership_level": "low",
                "missing_signals": [
                    "no quantified impact",
                    "no architecture ownership",
                    "no team scope",
                    "passive language throughout",
                ],
                "strengths": ["relevant domain (food-tech)", "tech stack present"],
                "overall_score": 3,
                "verdict": (
                    "WEAK — 4 years at a top company with zero quantified impact. "
                    "Reads like a job description, not an achievement record."
                ),
            },
        ),
        RoleFewShotExample(
            label="STRONG_EM",
            resume_snippet="""
Engineering Manager @ Flipkart (2020–Present)
- Lead 5 teams (32 engineers); owned supply-chain platform roadmap and delivery
- Drove ₹2,500+ crore cost savings; hired and coached 8+ engineering managers
- Architected observability rollout; cut MTTR 30% org-wide
""",
            expected_output={
                "seniority_detected": "em",
                "has_metrics": True,
                "ownership_level": "very_high",
                "missing_signals": [],
                "strengths": [
                    "explicit team scale (32 engineers)",
                    "business outcomes in ₹",
                    "hiring and coaching signal",
                ],
                "overall_score": 9,
                "verdict": (
                    "STRONG EM — management track. Do NOT classify as staff despite 17+ years."
                ),
            },
        ),
        RoleFewShotExample(
            label="STRONG_IC",
            resume_snippet="""
Staff Engineer @ Flipkart (2018-2024)
- Architected Flipkart's supply chain orchestration layer serving 500K sellers; reduced order processing latency from 4s to 340ms (p99)
- Led cross-functional redesign of inventory reservation system — eliminated 99.2% of oversell incidents (from ~800/day to <7/day)
- Defined and drove adoption of internal event-streaming standards across 6 product teams; reduced integration time by 60%
- Grew from SDE3 → Staff; mentored 4 engineers who were promoted to SDE3/Staff during tenure
""",
            expected_output={
                "seniority_detected": "staff",
                "has_metrics": True,
                "ownership_level": "very_high",
                "missing_signals": ["could add cost savings from infra optimization"],
                "strengths": [
                    "named system with scale numbers",
                    "before/after latency improvement",
                    "cross-org standards ownership",
                    "explicit career growth trajectory",
                ],
                "overall_score": 9,
                "verdict": "STRONG — Classic Staff IC profile. Title is Staff Engineer, not Engineering Manager.",
            },
        ),
    ],
)

PRODUCT_CONTEXT = RoleContext(
    role_family="PRODUCT",
    seniority_signals=[
        "IC track: APM → PM → SPM → GPM → Director of Product",
        "Scope signals: feature → product area → product line → platform",
        "Strategy signals: roadmap ownership, OKR setting, vision docs",
    ],
    metric_vocabulary=[
        "DAU/MAU", "D7/D30 retention", "conversion rate", "funnel drop-off",
        "NPS", "CSAT", "revenue impact (₹ or $)", "GMV", "feature adoption %",
        "activation rate", "churn reduction", "ARR",
    ],
    domain_vocabulary=[
        "PRD", "roadmap", "discovery", "A/B test", "hypothesis",
        "user research", "GTM", "launch", "north star metric", "OKRs",
    ],
    weakness_patterns=[
        "Feature shipped — no outcome metric",
        "No user research or discovery process mentioned",
        "Roadmap ownership unclear (did they set it or execute someone else's?)",
    ],
    strength_signals=[
        "North star metric ownership with quantified movement",
        "0→1 launches with adoption/retention data",
        "User research → insight → feature decision chain",
        "Business impact: revenue, GMV, cost savings",
    ],
    system_addendum="""
You are evaluating a PRODUCT MANAGEMENT resume.

METRIC STANDARDS (mark 'has_metrics: false' if only delivery-focused):
- Acceptable: "Grew D30 retention from 28% to 41%", "drove ₹12Cr incremental GMV"
- NOT acceptable: "launched feature X", "shipped 3 products", "improved user experience"

OWNERSHIP TEST: "defined/prioritized/proposed" = ownership; "built/implemented/worked on" = execution only.
""",
    few_shot_examples=[
        RoleFewShotExample(
            label="WEAK",
            resume_snippet="""
Product Manager @ Swiggy (2021-2023)
- Worked with engineering team to build features for the restaurant discovery page
- Wrote user stories and managed sprint backlogs
- Launched 4 features in 2022
""",
            expected_output={
                "has_metrics": False,
                "overall_score": 2,
                "verdict": "WEAK — features shipped, zero outcomes. No product thinking visible.",
            },
        ),
        RoleFewShotExample(
            label="STRONG",
            resume_snippet="""
Group Product Manager @ Meesho (2019-2024)
- Grew active supplier base from 180K to 1.1M; contributed ₹340Cr annual GMV
- D30 activation improved 2.3x in 18 months via north star metric restructuring
- 0→1 Smart Catalog: 68% adoption in 90 days; listing time 12min → 3min
""",
            expected_output={
                "has_metrics": True,
                "overall_score": 9,
                "verdict": "STRONG — north star ownership, discovery rigor, 0→1, business impact.",
            },
        ),
    ],
)

MARKETING_CONTEXT = RoleContext(
    role_family="MARKETING",
    seniority_signals=[
        "IC: Executive → Manager → Sr Manager → Head → VP",
        "Budget ownership: 'managed ₹X budget'",
        "Brand vs. performance marketing distinction",
    ],
    metric_vocabulary=[
        "CAC", "CPL", "CPC/CPA", "ROAS", "MQL/SQL conversion",
        "pipeline contribution (₹/$)", "brand awareness lift (%)", "campaign ROI",
    ],
    domain_vocabulary=[
        "GTM", "demand generation", "content marketing", "SEO/SEM",
        "ABM", "brand equity", "paid media", "customer journey", "ICP",
    ],
    weakness_patterns=[
        "Campaign without ROAS or ROI",
        "Vanity metrics only (impressions, followers)",
        "No budget ownership for Manager+ roles",
    ],
    strength_signals=[
        "Revenue or pipeline contribution in ₹/$",
        "ROAS or ROI clearly quantified",
        "Budget allocation with efficiency improvement",
    ],
    system_addendum="""
You are evaluating a MARKETING resume.
Performance marketing: expect ROAS, CAC, CPL, pipeline ₹.
Brand marketing: awareness %, share of voice — must be quantified.
NOT acceptable: "increased brand presence", "ran successful campaigns".
""",
    few_shot_examples=[],
)

DATA_ANALYST_CONTEXT = RoleContext(
    role_family="DATA_ANALYST",
    seniority_signals=[
        "Analyst → Sr Analyst → Lead Analyst → Analytics Manager",
        "Self-serve infra vs ad hoc analysis",
        "'analysis informed' vs 'analysis drove'",
    ],
    metric_vocabulary=[
        "dashboard adoption (MAU)", "model accuracy (AUC/F1)",
        "A/B test lift", "revenue impact of recommendation",
        "time saved (analyst hrs/week)", "cohort retention delta",
    ],
    domain_vocabulary=[
        "SQL", "Python", "Tableau", "Power BI", "Looker", "dbt", "Airflow",
        "A/B testing", "cohort analysis", "causal inference", "ETL/ELT",
    ],
    weakness_patterns=[
        "Dashboard built but no adoption metric",
        "Model built but no accuracy or business outcome",
        "A/B test with no lift or significance",
    ],
    strength_signals=[
        "Analysis tied to decision and outcome",
        "Model accuracy + business impact paired",
        "Self-serve tooling with adoption metric",
        "Proactive insight ('identified', 'surfaced')",
    ],
    system_addendum="""
You are evaluating a DATA ANALYST or DATA SCIENCE resume.
Analysis work: show business impact of insight.
Model/ML: accuracy metric + business outcome.
Dashboards: adoption (teams/MAU), not just "built dashboard".
""",
    few_shot_examples=[],
)

HR_CONTEXT = RoleContext(
    role_family="HR",
    seniority_signals=[
        "Executive → HRBP → Sr HRBP → Head of HR → CHRO",
        "Org size: employees supported, hires/year",
        "Transactional HR vs strategic advisory",
    ],
    metric_vocabulary=[
        "time-to-hire (days)", "offer acceptance rate (%)",
        "attrition rate", "eNPS", "cost-per-hire", "headcount managed",
    ],
    domain_vocabulary=[
        "HRBP", "talent acquisition", "onboarding", "performance management",
        "succession planning", "L&D", "HRIS", "Workday", "Darwinbox", "DEI",
    ],
    weakness_patterns=[
        "Hiring without time-to-hire or acceptance rate",
        "Attrition without % points improvement",
        "Engagement survey without eNPS outcome",
    ],
    strength_signals=[
        "Attrition reduced with % and timeframe",
        "eNPS with before/after",
        "HRIS implementation with adoption metric",
    ],
    system_addendum="""
You are evaluating a HUMAN RESOURCES resume.
Hiring: time-to-hire + acceptance rate required.
Attrition: before/after % required.
HRBP+: state headcount supported.
""",
    few_shot_examples=[],
)

FINANCE_CONTEXT = RoleContext(
    role_family="FINANCE",
    seniority_signals=[
        "Analyst → Manager → VP Finance → CFO",
        "BU finance → P&L owner → corporate finance",
        "FP&A, M&A, fundraising signals",
    ],
    metric_vocabulary=[
        "cost reduction (₹ / %)", "EBITDA impact", "forecast accuracy",
        "working capital", "ROI / IRR / NPV", "unit economics", "DSO reduction",
    ],
    domain_vocabulary=[
        "FP&A", "P&L", "MIS", "variance analysis", "unit economics",
        "fundraising", "M&A", "Ind AS", "SEBI", "capex/opex",
    ],
    weakness_patterns=[
        "Reports prepared — no insight outcome",
        "Cost optimization without ₹ savings",
        "Budget managed without size stated",
    ],
    strength_signals=[
        "Cost savings in ₹ with initiative name",
        "Forecast accuracy with %",
        "Model supporting a strategic decision",
    ],
    system_addendum="""
You are evaluating a FINANCE resume (FP&A, corporate finance, controllership).
All savings must include ₹ or %.
Budget work: state size managed.
NOT acceptable: "prepared reports", "assisted with analysis".
""",
    few_shot_examples=[],
)

DESIGN_CONTEXT = RoleContext(
    role_family="DESIGN",
    seniority_signals=[
        "Designer → Sr Designer → Lead → Principal → Design Manager",
        "Scope: screen → flow → product → design system",
        "Research depth and system thinking",
    ],
    metric_vocabulary=[
        "task completion rate (%)", "time-on-task reduction",
        "SUS score", "conversion rate lift", "design system coverage (%)",
        "feature adoption (%)", "accessibility score",
    ],
    domain_vocabulary=[
        "Figma", "user research", "usability testing", "design system",
        "information architecture", "accessibility (WCAG)", "design tokens",
    ],
    weakness_patterns=[
        "Redesign without usability or conversion metric",
        "Research without insight driving design change",
        "No design system for Lead+ roles",
    ],
    strength_signals=[
        "Design outcome tied to conversion or task success",
        "Design system ownership with adoption metric",
        "Research → insight → design change chain",
    ],
    system_addendum="""
You are evaluating a UX/PRODUCT DESIGN resume.
Acceptable: "reduced checkout abandonment from 68% to 41%".
NOT acceptable: "redesigned checkout for better UX".
Lead+: design system ownership expected.
""",
    few_shot_examples=[],
)

ROLE_CONTEXT_REGISTRY: Dict[str, RoleContext] = {
    "ENGINEERING": ENGINEERING_CONTEXT,
    "PRODUCT": PRODUCT_CONTEXT,
    "MARKETING": MARKETING_CONTEXT,
    "DATA_ANALYST": DATA_ANALYST_CONTEXT,
    "HR": HR_CONTEXT,
    "FINANCE": FINANCE_CONTEXT,
    "DESIGN": DESIGN_CONTEXT,
}

ROLE_DETECTION_KEYWORDS: Dict[str, List[str]] = {
    "ENGINEERING": [
        "software engineer", "sde", "backend", "frontend", "fullstack", "full stack",
        "devops", "sre", "infrastructure", "platform engineer", "tech lead",
        "staff engineer", "principal engineer", "engineering manager",
    ],
    "PRODUCT": [
        "product manager", "apm", "spm", "gpm", "product lead",
        "product owner", "head of product", "chief product", "vp product",
    ],
    "MARKETING": [
        "marketing manager", "digital marketing", "growth", "brand manager",
        "content marketing", "seo", "sem", "performance marketing",
        "head of marketing", "vp marketing", "cmo", "demand generation",
    ],
    "DATA_ANALYST": [
        "data analyst", "data scientist", "analytics", "business intelligence",
        "bi analyst", "data engineer", "ml engineer", "machine learning",
        "ai engineer", "quantitative analyst",
    ],
    "HR": [
        "human resources", "hr manager", "hrbp", "talent acquisition",
        "recruiter", "hr business partner", "head of hr", "chro",
        "people operations", "people manager", "l&d", "learning and development",
    ],
    "FINANCE": [
        "finance manager", "financial analyst", "fp&a", "cfo", "vp finance",
        "controller", "chartered accountant", "treasury", "corporate finance",
    ],
    "DESIGN": [
        "ux designer", "ui designer", "product designer", "interaction designer",
        "visual designer", "design lead", "head of design", "design manager",
        "ux researcher", "design system",
    ],
}

GAP_PATTERNS_BY_ROLE: Dict[str, dict] = {
    "ENGINEERING": {
        "critical_gaps": [
            "No system design or architecture ownership for Senior+ roles",
            "Scale numbers absent (traffic/data volume?)",
            "Impact metrics missing (latency, cost, reliability)",
        ],
        "quick_wins": [
            "Add p99 latency or throughput to every owned service",
            "Convert 'worked on' to 'owned' or 'designed' where accurate",
            "Add scale context: users, RPS, data volume",
        ],
        "jd_keywords_to_watch": ["distributed systems", "system design", "scale", "latency", "reliability"],
    },
    "PRODUCT": {
        "critical_gaps": [
            "Feature shipped with no outcome metric",
            "No user research or discovery visible",
            "Roadmap ownership unclear",
        ],
        "quick_wins": [
            "Add before/after metrics for every major feature",
            "Mention user research method and sample size",
            "Use 'defined', 'owned', 'drove' instead of 'built', 'shipped'",
        ],
        "jd_keywords_to_watch": ["product strategy", "roadmap", "OKRs", "user research", "A/B testing", "GTM"],
    },
    "MARKETING": {
        "critical_gaps": [
            "Campaign without ROAS, CAC, or revenue impact",
            "Vanity metrics only without conversion",
            "Budget ownership absent for Manager+ roles",
        ],
        "quick_wins": [
            "Add ROAS or CAC to every paid campaign",
            "State budget managed with amount",
        ],
        "jd_keywords_to_watch": ["performance marketing", "ROAS", "CAC", "demand generation", "GTM", "funnel"],
    },
    "DATA_ANALYST": {
        "critical_gaps": [
            "Dashboard without adoption metric",
            "Model without accuracy and business impact",
            "A/B test without lift or significance",
        ],
        "quick_wins": [
            "Add MAU to every dashboard",
            "Pair models with AUC/F1 + business outcome",
        ],
        "jd_keywords_to_watch": ["SQL", "Python", "A/B testing", "experimentation", "business intelligence", "ML"],
    },
    "HR": {
        "critical_gaps": [
            "Hiring without time-to-hire or acceptance rate",
            "Attrition without % improvement",
            "Org size missing for HRBP roles",
        ],
        "quick_wins": [
            "Add headcount supported per HRBP role",
            "Convert 'reduced attrition' to 'from X% to Y%'",
        ],
        "jd_keywords_to_watch": ["HRBP", "talent acquisition", "attrition", "engagement", "workforce planning", "HRIS"],
    },
    "FINANCE": {
        "critical_gaps": [
            "Cost savings without ₹ amount",
            "Budget managed without size",
            "Model without decision it supported",
        ],
        "quick_wins": [
            "Add ₹ to every cost saving",
            "State budget size for FP&A work",
        ],
        "jd_keywords_to_watch": ["FP&A", "P&L", "unit economics", "fundraising", "EBITDA", "working capital"],
    },
    "DESIGN": {
        "critical_gaps": [
            "Redesign without usability or conversion metric",
            "Research without insight driving design change",
            "Design system absent for Lead+ roles",
        ],
        "quick_wins": [
            "Add task completion or conversion improvement per redesign",
            "State research → insight → design change chain",
        ],
        "jd_keywords_to_watch": ["design system", "user research", "usability", "Figma", "accessibility"],
    },
}

VALID_ROLE_FAMILIES = frozenset(ROLE_CONTEXT_REGISTRY.keys())


def detect_role_family(resume_text: str, job_title: str = "") -> str:
    """Keyword-based role family detector. Defaults to ENGINEERING."""
    combined = (resume_text[:2000] + " " + job_title).lower()
    scores: Dict[str, int] = {family: 0 for family in ROLE_DETECTION_KEYWORDS}

    for family, keywords in ROLE_DETECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[family] += 1

    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "ENGINEERING"


def get_role_context(role_family: str) -> RoleContext:
    """Return RoleContext for role family; fallback ENGINEERING."""
    return ROLE_CONTEXT_REGISTRY.get(role_family.upper(), ENGINEERING_CONTEXT)


def get_gap_patterns(role_family: str) -> dict:
    """Gap analysis patterns for gap_analyzer.py."""
    return GAP_PATTERNS_BY_ROLE.get(role_family.upper(), GAP_PATTERNS_BY_ROLE["ENGINEERING"])


def build_few_shot_block(role_family: str, num_examples: int = 2) -> str:
    """
    Few-shot block for agent system prompt.
    num_examples=2 → WEAK + STRONG when 3 examples exist; else all available.
    """
    ctx = get_role_context(role_family)
    lines = [
        f"\n\n{'=' * 60}",
        f"ROLE-SPECIFIC CONTEXT: {ctx.role_family}",
        f"{'=' * 60}",
        "\nSENIORITY SIGNALS FOR THIS ROLE:",
        *[f"  • {s}" for s in ctx.seniority_signals],
        "\nEXPECTED METRIC VOCABULARY:",
        "  " + ", ".join(ctx.metric_vocabulary[:8]),
        "\nDOMAIN VOCABULARY:",
        "  " + ", ".join(ctx.domain_vocabulary[:10]),
        "\nCOMMON WEAKNESS PATTERNS TO FLAG:",
        *[f"  ⚠ {w}" for w in ctx.weakness_patterns],
        "\n" + ctx.system_addendum.strip(),
    ]

    if not ctx.few_shot_examples:
        lines.append(f"\n{'=' * 60}\n")
        return "\n".join(lines)

    lines.extend([
        f"\n{'─' * 60}",
        "FEW-SHOT CALIBRATION EXAMPLES",
        f"{'─' * 60}",
        "Use the following examples to calibrate your output.\n",
    ])

    examples = ctx.few_shot_examples
    if num_examples < 3 and len(examples) >= 2:
        weak = next((e for e in examples if e.label == "WEAK"), examples[0])
        strong = next(
            (e for e in examples if e.label in ("STRONG_EM", "STRONG")),
            examples[-1],
        )
        examples_to_use = [weak, strong]
    else:
        examples_to_use = examples[:num_examples] if num_examples else examples

    for ex in examples_to_use:
        lines.append(f"[EXAMPLE — {ex.label}]")
        lines.append("RESUME SNIPPET:")
        lines.append(ex.resume_snippet.strip())
        lines.append("EXPECTED OUTPUT:")
        for key, val in ex.expected_output.items():
            if isinstance(val, list):
                lines.append(f"  {key}:")
                for item in val:
                    lines.append(f"    - {item}")
            else:
                lines.append(f"  {key}: {val}")
        lines.append("")

    lines.append(f"{'=' * 60}")
    lines.append("Now evaluate the actual resume following the same calibration standards.")
    lines.append(f"{'=' * 60}\n")
    return "\n".join(lines)


def build_role_gap_addendum(role_family: str) -> str:
    """Role-specific gap hints appended to gap analyzer system prompt."""
    patterns = get_gap_patterns(role_family)
    critical = "\n".join(f"  - {g}" for g in patterns["critical_gaps"])
    quick = "\n".join(f"  - {q}" for q in patterns["quick_wins"])
    keywords = ", ".join(patterns["jd_keywords_to_watch"])
    return f"""
ROLE-SPECIFIC GAP PATTERNS ({role_family.upper()}):
Critical gaps to prioritize:
{critical}

Quick wins to suggest in priority_fixes when relevant:
{quick}

JD keywords to watch for this role family: {keywords}
"""


def build_recruiter_role_addendum(role_family: str) -> str:
    """Vocabulary block for recruiter_sim system prompt."""
    ctx = get_role_context(role_family)
    return (
        f"\nROLE EVALUATION LENS: {ctx.role_family}\n"
        f"When assessing fit, weight these metric types: {', '.join(ctx.metric_vocabulary[:6])}\n"
        f"Strength signals to reward: {', '.join(ctx.strength_signals[:4])}\n"
        f"Weakness patterns to penalize: {', '.join(ctx.weakness_patterns[:4])}\n"
    )
