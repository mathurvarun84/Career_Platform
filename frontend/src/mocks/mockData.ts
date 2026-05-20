import type {
  AnalysisResult,
  HistoryResponse,
  SSEProgressEvent,
} from "../types";

if (!import.meta.env.DEV) {
  console.warn("mockData imported in production build — check import paths");
}

const toIsoDaysAgo = (daysAgo: number): string => {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString();
};

export const MOCK_ANALYSIS_RESULT: AnalysisResult = {
  job_id: "e2a871fb-5d3b-4f01-82a8-83cf0cff41bc",
  ats: {
    score: 68,
    breakdown: {
      keyword_match: 16,
      formatting: 20,
      readability: 18,
      impact_metrics: 14,
    },
    details: [
      {
        score: 16,
        benchmark: 20,
        gap: 4,
        gap_reason:
          "Missing 3 keywords from the JD — add Kubernetes and Kafka in skills plus one project bullet.",
        label: "Keyword Match",
        icon: "🔑",
      },
      {
        score: 20,
        benchmark: 21,
        gap: 1,
        gap_reason:
          "Minor formatting issue: section spacing is inconsistent between experience and certifications.",
        label: "Formatting",
        icon: "📐",
      },
      {
        score: 18,
        benchmark: 19,
        gap: 1,
        gap_reason:
          "Some sentences are too long — aim for under 25 words per bullet.",
        label: "Readability",
        icon: "📖",
      },
      {
        score: 14,
        benchmark: 18,
        gap: 4,
        gap_reason:
          "Add 2–3 more impact numbers: percentages, throughput (QPS/TPS), or business outcomes.",
        label: "Impact & Metrics",
        icon: "📊",
      },
    ],
    ats_issues: [
      "Most experience bullets describe responsibilities but miss quantified outcomes.",
      "Core backend and DevOps keywords from senior SDE JDs are not prominent in the skills section.",
      "Project impact is scattered across sections instead of a clear top summary with business metrics.",
    ],
  },
  resume: {
    experience_years: 5,
    seniority: "mid",
    role_family: "ENGINEERING",
    tech_stack: [
      "React",
      "TypeScript",
      "Node.js",
      "Python",
      "PostgreSQL",
      "Redis",
      "AWS",
      "Docker",
    ],
    domains: ["fintech", "e-commerce", "saas"],
    has_metrics: false,
    has_summary: true,
    sections_present: [
      "summary",
      "skills",
      "experience",
      "education",
      "certifications",
    ],
    resume_sections: {
      summary: {
        full_text:
          "Mid-level software engineer based in Bengaluru with 5 years of experience building customer-facing web products across fintech and commerce.",
      },
      skills: {
        full_text:
          "React, TypeScript, Node.js, Python, PostgreSQL, Redis, AWS, Docker",
      },
      experience: {
        full_text:
          "Software Engineer at PaySprint Labs (2023-Present); Software Engineer at KartPilot Commerce (2021-2023); Associate Engineer at CloudNook Systems (2020-2021)",
      },
      education: {
        full_text:
          "B.E. Computer Science, Visvesvaraya Technological University, 2020",
      },
      certifications: {
        full_text: "AWS Certified Developer - Associate",
      },
    },
  },
  gap: {
    jd_match_score_before: 73,
    jd_match_score_after: 88,
    section_gaps: [
      {
        section: "summary",
        needs_change: true,
        gap_reason:
          "Current summary is generic and does not emphasize senior-level ownership signals.",
        missing_keywords: ["system design", "ownership"],
        rewrite_instruction:
          "Rewrite summary to highlight architecture decisions, delivery ownership, and cross-team impact.",
        present_in_resume: true,
        sub_changes: [],
      },
      {
        section: "skills",
        needs_change: true,
        gap_reason:
          "JD expects distributed systems and delivery tooling that are not explicitly listed.",
        missing_keywords: ["Kafka", "CI/CD", "Docker"],
        rewrite_instruction:
          "Group skills by backend, cloud, and delivery practices; include missing JD terms naturally.",
        present_in_resume: true,
        sub_changes: [],
      },
      {
        section: "experience",
        needs_change: true,
        gap_reason:
          "Experience shows feature work but underplays scale, metrics, and architecture ownership.",
        missing_keywords: ["event-driven", "scalability", "observability"],
        rewrite_instruction:
          "Strengthen bullets with measurable outcomes and explicit ownership of high-scale systems.",
        present_in_resume: true,
        sub_changes: [
          {
            sub_id: "exp-paysprint-labs",
            sub_label: "PaySprint Labs - Software Engineer",
            needs_change: true,
            gap_reason:
              "Bullets mention implementation but not production scale, latency, or reliability outcomes.",
            rewrite_instruction:
              "Add metrics and senior-level ownership language for backend and cloud initiatives.",
            missing_keywords: ["Kafka", "SLA", "throughput"],
          },
          {
            sub_id: "exp-kartpilot-commerce",
            sub_label: "KartPilot Commerce - Software Engineer",
            needs_change: true,
            gap_reason:
              "Strong product work is present but lacks CI/CD and performance optimization keywords.",
            rewrite_instruction:
              "Highlight release automation, performance wins, and collaboration with product teams.",
            missing_keywords: ["CI/CD", "Docker", "performance tuning"],
          },
        ],
      },
      {
        section: "education",
        needs_change: false,
        gap_reason:
          "Education section is sufficient for a mid-level to senior transition profile.",
        missing_keywords: [],
        rewrite_instruction:
          "Keep education concise and unchanged unless space is required for experience content.",
        present_in_resume: true,
        sub_changes: [],
      },
      {
        section: "certifications",
        needs_change: true,
        gap_reason:
          "Only one certification is listed while target role favors cloud delivery depth.",
        missing_keywords: ["AWS", "Kubernetes"],
        rewrite_instruction:
          "Reframe certifications to align with production cloud operations and reliability practices.",
        present_in_resume: true,
        sub_changes: [],
      },
      {
        section: "awards",
        needs_change: false,
        gap_reason:
          "Awards are optional for this role and absence does not block shortlist outcomes.",
        missing_keywords: [],
        rewrite_instruction:
          "No rewrite required; keep section omitted unless meaningful recognition exists.",
        present_in_resume: false,
        sub_changes: [],
      },
    ],
    missing_keywords: [
      "Kafka",
      "CI/CD",
      "Docker",
      "system design",
      "observability",
    ],
    priority_fixes: [
      {
        section: "experience",
        gap_reason: "Few quantified achievements in experience bullets",
        rewrite_instruction: "Most experience bullets describe responsibilities but miss quantified outcomes. Add metrics like % improvements, team sizes, or business impact.",
        missing_keywords: ["impact", "metrics", "throughput"],
        needs_change: true,
      },
      {
        section: "skills",
        gap_reason: "Missing Kafka, CI/CD, and production-grade Docker keywords",
        rewrite_instruction: "JD expects distributed systems and delivery tooling that are not explicitly listed. Group skills by backend, cloud, and delivery practices.",
        missing_keywords: ["Kafka", "CI/CD", "Docker"],
        needs_change: true,
      },
      {
        section: "summary",
        gap_reason: "Summary misses ownership and scalability keywords",
        rewrite_instruction: "Rewrite summary to highlight architecture decisions, delivery ownership, and cross-team impact. Include: system design, ownership, scalability.",
        missing_keywords: ["system design", "ownership", "scalability"],
        needs_change: true,
      },
      {
        section: "certifications",
        gap_reason: "Only one certification; target role favors cloud delivery depth",
        rewrite_instruction: "Reframe certifications to align with production cloud operations and reliability practices.",
        missing_keywords: ["AWS", "Kubernetes"],
        needs_change: true,
      },
    ],
    changes: [
      {
        change_id: 1,
        location: { section: "experience", sub_location: "PaySprint Labs" },
        change_type: "strengthen_metric",
        priority: "critical",
        why: "Senior SDE screening requires concrete scale and impact outcomes.",
        original_text:
          "Built backend services for payment routing using Node.js and PostgreSQL.",
        suggested_text:
          "Built payment routing services that processed [N] transactions/day and reduced settlement delays by [X%].",
        keywords_added: ["throughput", "latency", "reliability"],
      },
      {
        change_id: 2,
        location: { section: "skills", sub_location: "Core Stack" },
        change_type: "add_keyword",
        priority: "critical",
        why: "JD must-have stack explicitly includes event streaming and delivery tooling.",
        original_text:
          "React, TypeScript, Node.js, Python, PostgreSQL, Redis, AWS, Docker",
        suggested_text:
          "React, TypeScript, Node.js, Python, PostgreSQL, Redis, AWS, Docker, Kafka, CI/CD",
        keywords_added: ["Kafka", "CI/CD"],
      },
      {
        change_id: 3,
        location: { section: "summary", sub_location: "Opening lines" },
        change_type: "rewrite_section",
        priority: "high",
        why: "Current summary undersells ownership and architecture responsibilities.",
        original_text:
          "Software engineer with experience building web applications and APIs.",
        suggested_text:
          "Mid-level engineer leading backend architecture and release quality for high-growth product teams.",
        keywords_added: ["ownership", "architecture", "scalability"],
      },
      {
        change_id: 4,
        location: { section: "experience", sub_location: "KartPilot Commerce" },
        change_type: "rewrite_bullet",
        priority: "high",
        why: "Needs stronger evidence of delivery speed and production quality improvements.",
        original_text:
          "Worked on checkout and order services with cross-functional teams.",
        suggested_text:
          "Owned checkout service enhancements that improved conversion by [X%] and reduced release rollback incidents by [X%].",
        keywords_added: ["CI/CD", "conversion", "incident reduction"],
      },
      {
        change_id: 5,
        location: { section: "certifications", sub_location: "Cloud credentials" },
        change_type: "add_section",
        priority: "medium",
        why: "Role values cloud reliability depth and visible upskilling trajectory.",
        original_text: "AWS Certified Developer - Associate",
        suggested_text:
          "AWS Certified Developer - Associate | Currently preparing for Certified Kubernetes Application Developer (CKAD).",
        keywords_added: ["Kubernetes", "cloud reliability"],
      },
    ],
  },
  rewrites: {
    summary: {
      balanced: `Software engineer with 5 years of experience in Bengaluru building backend-heavy product features for fintech and commerce platforms.
I work across React, Node.js, and cloud infrastructure to ship customer-facing capabilities with stable release quality.
I am now targeting senior SDE roles where I can own system design, execution quality, and cross-functional delivery outcomes.`,
      aggressive: `Product-focused engineer with 5 years of experience delivering high-impact backend systems using Node.js, AWS, Docker, and Kafka-aligned architectures.
Owned end-to-end feature delivery and improved release quality by [X%] through CI/CD and production observability practices.
Ready to drive senior SDE outcomes across scale, reliability, and velocity for [N users].`,
      top_1_percent: `Engineer with a track record of converting ambiguous product requirements into resilient, scalable platform capabilities.
Operate at the intersection of architecture, execution, and stakeholder alignment to deliver measurable business outcomes.
Positioned for senior ownership in high-bar product organizations that value speed with engineering rigor.`,
    },
    skills: {
      balanced: `Languages & Frameworks: TypeScript, JavaScript, Python, React, Node.js
Data & Messaging: PostgreSQL, Redis, Kafka
Cloud & Delivery: AWS, Docker, CI/CD`,
      aggressive: `Core Stack: React, TypeScript, Node.js, Python
Distributed Systems: Kafka, Redis, PostgreSQL
Production Engineering: AWS, Docker, CI/CD, monitoring, incident response`,
      top_1_percent: `Application Engineering: React, TypeScript, Node.js, Python
Distributed Data Systems: PostgreSQL, Redis, Kafka
Platform & Reliability: AWS, Docker, CI/CD, release governance, observability-first operations`,
    },
    experience: {
      balanced: `At PaySprint Labs, I built backend APIs and workflow orchestration for payment operations, collaborating closely with product and QA to improve reliability.
I led service-level enhancements that reduced recurring production issues and improved release confidence for critical transaction flows.
At KartPilot Commerce, I delivered checkout and order management improvements with cross-functional teams, ensuring stable rollouts and better customer experience.
I also contributed to internal engineering practices by documenting deployment standards and improving handoff quality between development and operations.
Across both roles, I consistently took ownership of delivery outcomes and production quality for user-facing systems.`,
      aggressive: `Led backend delivery for payment and checkout services handling [N users] and [N] daily transactions across high-growth product environments.
Improved API latency by [Xms], reduced failed transaction paths by [X%], and increased deployment success rate by [X%] through CI/CD hardening.
Introduced Docker-based environment parity and Kafka-friendly event workflows that cut release friction by [X%].
Owned incident follow-through with monitoring-driven fixes, reducing Sev-2 recurrences by [X%] while improving SLA consistency.
Partnered with product and QA to prioritize roadmap delivery with measurable business impact across conversion and retention metrics.`,
      top_1_percent: `Drove core backend architecture and execution for revenue-critical flows in fast-moving product teams, combining high ownership with strong engineering discipline.
Elevated platform reliability through systematic improvements in service design, release controls, and production observability.
Translated product goals into durable technical systems that balanced scale-readiness, developer velocity, and operational excellence.
Built trust across engineering, product, and quality functions by consistently delivering outcomes with clear accountability.
Prepared to operate as a senior-level force multiplier in organizations with a high bar for technical depth and business impact.`,
    },
  },
  sim: {
    personas: [
      {
        persona: "FAANG Technical Screener",
        first_impression:
          "Solid engineering base but the resume lacks concrete large-scale system outcomes.",
        noticed: ["Backend ownership", "Clean stack alignment"],
        ignored: ["Generic responsibility bullets", "Unquantified improvements"],
        rejection_reason:
          "Insufficient evidence of operating at very large scale or owning deep system design decisions.",
        shortlist_decision: false,
        fit_score: 52,
        flip_condition: "Add 2–3 system design examples with scale indicators (QPS, latency, user count).",
      },
      {
        persona: "Zepto/Blinkit Hiring Manager",
        first_impression:
          "Good speed-focused profile with relevant product and delivery exposure.",
        noticed: ["Checkout domain exposure", "Cross-functional execution"],
        ignored: ["Older education details"],
        rejection_reason: "",
        shortlist_decision: true,
        fit_score: 78,
        flip_condition: "",
      },
      {
        persona: "Series B Startup CTO",
        first_impression:
          "Candidate shows practical ownership and can likely handle senior IC scope with mentoring.",
        noticed: ["Hands-on backend delivery", "Cloud and deployment awareness"],
        ignored: ["Lack of awards section"],
        rejection_reason: "",
        shortlist_decision: true,
        fit_score: 74,
        flip_condition: "",
      },
      {
        persona: "Mid-Size Product Company HR",
        first_impression:
          "Strong match for a senior transition role in a product engineering team.",
        noticed: ["Relevant tech stack", "Career progression"],
        ignored: ["Missing explicit achievements section"],
        rejection_reason: "",
        shortlist_decision: true,
        fit_score: 70,
        flip_condition: "",
      },
      {
        persona: "Enterprise IT Recruiter",
        first_impression:
          "Technically competent profile, but enterprise signals and credential depth are limited.",
        noticed: ["AWS certification", "Stable role history"],
        ignored: ["Startup-style summary framing"],
        rejection_reason:
          "Would prefer stronger certification coverage for enterprise governance-heavy roles.",
        shortlist_decision: false,
        fit_score: 55,
        flip_condition: "Add cloud reliability certifications like CKAD or AWS Solutions Architect.",
      },
      {
        persona: "D2C Tech Lead",
        first_impression:
          "Relevant experience for conversion-critical journeys and rapid product iteration.",
        noticed: ["Checkout work", "Backend plus frontend versatility"],
        ignored: ["Academic history"],
        rejection_reason: "",
        shortlist_decision: true,
        fit_score: 72,
        flip_condition: "",
      },
      {
        persona: "FinTech Senior Engineer",
        first_impression:
          "Fintech-aligned profile with enough systems grounding to be impactful quickly.",
        noticed: ["Payment flow experience", "Reliability focus"],
        ignored: ["Awards and extracurricular sections"],
        rejection_reason: "",
        shortlist_decision: true,
        fit_score: 68,
        flip_condition: "",
      },
      {
        persona: "EdTech Hiring Manager",
        first_impression:
          "Balanced profile with product mindset and good execution potential.",
        noticed: ["Cross-team collaboration", "Modern web stack"],
        ignored: ["Limited teaching/mentorship mentions"],
        rejection_reason: "",
        shortlist_decision: true,
        fit_score: 65,
        flip_condition: "",
      },
      {
        persona: "Service Company Bench Manager",
        first_impression:
          "Candidate appears product-specialized and may not map cleanly to broad client rotation.",
        noticed: ["Product startup experience", "Ownership language"],
        ignored: ["Generalist service-delivery signals"],
        rejection_reason:
          "Domain focus is narrow for bench allocation across varied enterprise client projects.",
        shortlist_decision: false,
        fit_score: 48,
        flip_condition: "Show breadth across multiple project types and client-facing communication.",
      },
      {
        persona: "MAANG Referral Reviewer",
        first_impression:
          "Strong direction, but the profile needs harder impact metrics to pass a referral bar.",
        noticed: ["Relevant stack choices", "Consistent growth"],
        ignored: ["Non-quantified project statements"],
        rejection_reason:
          "Key achievements are not quantified, making impact difficult to calibrate against high-bar peer candidates.",
        shortlist_decision: false,
        fit_score: 50,
        flip_condition: "Add 3–5 quantified achievements with measurable business impact.",
      },
    ],
    shortlist_rate: 0.6,
    consensus_strengths: [
      "Relevant product engineering stack for senior SDE roles",
      "Clear ownership across backend and cross-functional delivery",
      "Good fit for fast-paced startup and mid-size product teams",
    ],
    consensus_weaknesses: [
      "Insufficient quantified impact metrics in experience bullets",
      "Distributed systems keywords are present but not emphasized consistently",
      "Certification depth is thin for enterprise-oriented evaluators",
    ],
    most_critical_fix:
      "Add quantified impact metrics to core experience bullets so reviewers can clearly assess scale and business outcomes.",
    probing_persona: null,
    probing_dimension: null,
  },
  percentile: { score: 62, label: "Top 38%", percentile: 62 },
  positioning: {
    current_tier: "product_mid",
    current_tier_label: "Mid-size Product",
    current_tier_examples: "Razorpay, Freshworks, Postman",
    next_tier_label: "Product Unicorn",
    next_tier_examples: "Zepto, Groww, Meesho",
    changes_needed: 3,
    current_ctc_min: 22,
    current_ctc_max: 35,
    potential_ctc_min: 35,
    potential_ctc_max: 55,
    ctc_delta_min: 13,
    ctc_delta_max: 20,
    positioning_line: "Your resume is competitive for Mid-size Product roles (Razorpay, Freshworks, Postman).",
    delta_line: "After fixes: ₹35–55 LPA (currently ₹22–35 LPA). Potential gain: ₹13–20 LPA/year.",
    cta_line: "3 changes needed to reach Product Unicorn (Zepto, Groww, Meesho).",
    rank_rationale: "Above Average because quantified impact metrics are thin. 2 targeted fixes can move you toward Top 25%.",
    fix_items: [
      "Add quantified impact metrics to top three experience bullets.",
      "Expand skills section with Kafka, CI/CD, and production-grade Docker usage.",
      "Rewrite summary to emphasize ownership of scalable backend architecture.",
    ],
  },
  validation: {
    safe_fix: {
      ats_check: "pass",
      jd_check: "pass",
      placeholder_check: "pass",
      truncation_check: "pass",
      overall: "pass",
      download_enabled: true,
    },
    full_rewrite: {
      ats_check: "pass",
      jd_check: "pass",
      placeholder_check: "pass",
      truncation_check: "pass",
      overall: "pass",
      download_enabled: true,
    },
    scores: {
      safe_fix: {
        ats_score: 71,
        ats_breakdown: {
          keyword_match: 19,
          formatting: 21,
          readability: 18,
          impact_metrics: 13,
        },
        delta_ats: 17,
      },
      full_rewrite: {
        ats_score: 76,
        ats_breakdown: {
          keyword_match: 21,
          formatting: 21,
          readability: 18,
          impact_metrics: 16,
        },
        delta_ats: 22,
      },
      original_ats: 54,
    },
  },
};

const PASS_VALIDATION_CHECKS = {
  ats_check: "pass" as const,
  jd_check: "pass" as const,
  placeholder_check: "pass" as const,
  truncation_check: "pass" as const,
  overall: "pass" as const,
  download_enabled: true,
};

/** Mock variant: safe fix passes, full rewrite fails ATS check (disabled download). */
export const MOCK_ANALYSIS_RESULT_FULL_REWRITE_FAIL: AnalysisResult = {
  ...MOCK_ANALYSIS_RESULT,
  validation: {
    safe_fix: PASS_VALIDATION_CHECKS,
    full_rewrite: {
      ats_check: "fail",
      jd_check: "pass",
      placeholder_check: "pass",
      truncation_check: "pass",
      overall: "fail",
      download_enabled: false,
    },
    scores: {
      safe_fix: {
        ats_score: 71,
        ats_breakdown: {
          keyword_match: 19,
          formatting: 21,
          readability: 18,
          impact_metrics: 13,
        },
        delta_ats: 17,
      },
      full_rewrite: {
        ats_score: 49,
        ats_breakdown: {
          keyword_match: 12,
          formatting: 18,
          readability: 10,
          impact_metrics: 9,
        },
        delta_ats: -5,
      },
      original_ats: 54,
    },
  },
};

export const MOCK_SSE_EVENTS: SSEProgressEvent[] = [
  {
    step: 1,
    label: "Reading your resume...",
    pct: 10,
    status: "running",
  },
  {
    step: 1,
    label: "Resume parsed successfully",
    pct: 30,
    status: "running",
  },
  {
    step: 2,
    label: "Analyzing gaps against JD...",
    pct: 45,
    status: "running",
  },
  {
    step: 2,
    label: "Gap analysis complete",
    pct: 65,
    status: "running",
  },
  {
    step: 3,
    label: "Rewriting changed sections...",
    pct: 75,
    status: "running",
  },
  {
    step: 3,
    label: "Resume rewritten successfully",
    pct: 95,
    status: "running",
  },
];

export const MOCK_HISTORY: HistoryResponse = {
  runs: [
    {
      run_id: "run-45d-ago",
      timestamp: toIsoDaysAgo(45),
      ats_score: 52,
      jd_match: 61,
      percentile: 49,
    },
    {
      run_id: "run-20d-ago",
      timestamp: toIsoDaysAgo(20),
      ats_score: 61,
      jd_match: 68,
      percentile: 58,
    },
    {
      run_id: "run-today",
      timestamp: toIsoDaysAgo(0),
      ats_score: 68,
      jd_match: 73,
      percentile: 64,
    },
  ],
};
