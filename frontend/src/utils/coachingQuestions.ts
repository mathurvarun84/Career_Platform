/** Heuristic coaching questions for evidence gaps — mirrors backend _build_coaching_question. */

export function buildCoachingQuestion(gapReason: string): {
  question: string;
  hints: string[];
} {
  const reason = gapReason.toLowerCase();

  if (/\b(mentor|coach|guidance|develop)\b/.test(reason)) {
    return {
      question: "Did you mentor, coach, or develop engineers on your team?",
      hints: [
        "Conducted regular 1:1s with direct reports",
        "Mentored junior engineers through architecture decisions",
        "Helped team members get promoted",
        "Ran knowledge-sharing sessions or tech talks",
        "Built onboarding plans for new hires",
      ],
    };
  }

  if (
    /\b(leading engineering|lead engineering|people management|engineering management|engineering leadership|direct report)\b/.test(
      reason
    )
  ) {
    return {
      question: "Can you describe your experience leading and managing engineering teams?",
      hints: [
        "Managed a team of N engineers across multiple squads",
        "Led hiring, onboarding, and performance reviews for direct reports",
        "Set team OKRs and tracked delivery against them",
        "Resolved conflicts and unblocked delivery bottlenecks",
        "Built high-performing teams through mentoring and goal-setting",
      ],
    };
  }

  if (
    /\b(architecture evaluation|technical leadership|technical direction|operational risk|architectural)\b/.test(
      reason
    )
  ) {
    return {
      question: "Can you share how you shaped technical architecture or direction at your org?",
      hints: [
        "Led architecture reviews for major platform redesigns",
        "Defined technical standards and engineering best practices",
        "Evaluated and approved technology choices across teams",
        "Drove technical risk assessment and mitigation strategies",
        "Set the architectural direction for a new product or platform",
      ],
    };
  }

  if (/\b(stakeholder|executive|leadership|communication)\b/.test(reason)) {
    return {
      question:
        "Did you present to or work directly with senior leadership or external stakeholders?",
      hints: [
        "Presented quarterly OKR reviews to VP/C-suite",
        "Aligned with cross-functional stakeholders on roadmap",
        "Represented engineering in business planning discussions",
        "Managed escalations with external clients or vendors",
      ],
    };
  }

  if (/\b(p&l|budget|cost|business ownership|revenue)\b/.test(reason)) {
    return {
      question: "Did you have ownership of budget, costs, or business outcomes?",
      hints: [
        "Managed team headcount and hiring budget",
        "Made build-vs-buy decisions with cost implications",
        "Tracked and reported engineering cost metrics",
        "Owned cost optimisation initiatives",
      ],
    };
  }

  if (/\b(strategy|vision|roadmap|direction)\b/.test(reason)) {
    return {
      question: "Did you define or significantly shape the technical strategy or roadmap?",
      hints: [
        "Defined the 6-month or annual engineering roadmap",
        "Proposed and drove adoption of a new technical direction",
        "Led architecture reviews that shaped the product strategy",
      ],
    };
  }

  if (/\b(quantif|metric|scale|qps|users|sla|impact)\b/.test(reason)) {
    return {
      question: "Can you share specific numbers that show the scale or impact of this work?",
      hints: [
        "Served 12K QPS peak traffic with 99.9% SLA",
        "Reduced checkout latency by 35% for 50M monthly users",
        "Grew revenue by [X%] or user base from N to M",
        "Cut deployment time from 2 hours to 15 minutes",
      ],
    };
  }

  if (/\b(cross-team|collaborat|on-call|oncall|incident)\b/.test(reason)) {
    return {
      question: "Can you describe how you collaborated across teams or handled on-call/incidents?",
      hints: [
        "Partnered with Data and Product to ship a cross-team feature in Q3",
        "Led incident response for a P1 outage and wrote the postmortem",
        "Ran weekly syncs with platform and infra teams on shared roadmap",
        "Co-owned on-call rotation covering 24/7 production support",
      ],
    };
  }

  return {
    question: `Can you share a specific example related to: ${gapReason}?`,
    hints: [
      "Describe a situation where this was relevant",
      "Include the outcome and your specific contribution",
    ],
  };
}
