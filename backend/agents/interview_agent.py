"""
InterviewAgent - Agent 6 of the Resume Intelligence Platform.

Generates behavioural interview questions calibrated to a candidate's
resume signals and a target company's behavioural framework.

Days 2-4 implement: generate_questions, evaluate_answer, generate_summary.
Model: claude-sonnet-4-20250514
Provider: Anthropic
"""

import json
from pathlib import Path
from uuid import uuid4

from .base_agent import BaseAgent


# ── Load company values once at module import time ────────────────────────────
_COMPANY_VALUES_PATH = Path(__file__).parent.parent / "data" / "company_values.json"


def _load_company_values() -> dict:
    with open(_COMPANY_VALUES_PATH, "r") as f:
        return json.load(f)


_COMPANY_VALUES: dict = _load_company_values()


# ── Valid dimension keys (mirrors TypeScript BehavioralDimension type) ────────
_VALID_DIMENSIONS = {
    "ownership",
    "impact_and_scale",
    "influence_without_authority",
    "problem_solving",
    "collaboration",
    "growth_mindset",
    "conflict_resolution",
}

_VALID_ANTI_PATTERNS = {
    # Original 7
    "we_default",             # hides behind "we", obscures individual contribution
    "vague_quantification",   # fake/missing numbers; adjectives instead of metrics
    "story_recycling",        # same story reused across multiple questions
    "impact_buried",          # leads with activity, buries result at the end
    "hypothesis_without_proof",  # states assumptions as fact, no validation shown
    "escalation_default",     # resolves by going to manager rather than directly
    "scope_collapse",         # staff/EM candidate describes junior-scoped work
    # Added: genuine gaps in the original taxonomy
    "no_reflection",          # story ends at the event; no learning or behavioral change stated
    "credit_deflection",      # minimises own agency ("my manager suggested", "lucky timing")
    "recency_bias",           # can only cite recent examples; no evidence of sustained behavior
    "rehearsed_script",       # template-assembled answer; no lived-in detail
}

# Keys that carry extra context for the prompt — ordered for readability
_ANTI_PATTERN_DESCRIPTIONS = {
    "we_default":             "hides behind 'we', obscures individual contribution",
    "vague_quantification":   "fake/missing numbers; adjectives instead of metrics",
    "story_recycling":        "same story reused across multiple questions",
    "impact_buried":          "leads with activity, buries result at the end",
    "hypothesis_without_proof": "states assumptions as fact, no validation shown",
    "escalation_default":     "resolves by going to manager rather than directly",
    "scope_collapse":         "staff/EM candidate describes junior-scoped work (only for staff/em)",
    "no_reflection":          "story ends at event; no learning or behavioral change stated",
    "credit_deflection":      "minimises own agency ('my manager suggested', 'lucky timing')",
    "recency_bias":           "can only cite recent examples; no evidence of sustained behavior",
    "rehearsed_script":       "template-assembled answer; no lived-in detail",
}


# ── Load question bank once at module import time ─────────────────────────────
_QUESTION_BANK_PATH = Path(__file__).parent.parent / "data" / "question_bank.json"


def _load_question_bank() -> dict:
    try:
        with open(_QUESTION_BANK_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}   # graceful — bank is optional; generation still works without it


def _normalize_question_bank(raw: dict) -> dict:
    """
    Flatten nested generic + company_specific tiers into lookup keys:
      company_key -> {dimension -> [questions]}
      {company_key}_scenario -> {dimension -> [scenario questions]}
    Generic dimension pools fill gaps when a company lacks coverage.
    """
    if not raw:
        return {}

    generic = raw.get("generic", {})
    generic_dims = {k: v for k, v in generic.items() if k in _VALID_DIMENSIONS}
    scenario_dims: dict[str, list] = {}
    for key, qs in generic.items():
        if key.startswith("scenario_"):
            dim = key[len("scenario_"):]
            if dim in _VALID_DIMENSIONS:
                scenario_dims[dim] = qs

    def _merge_with_generic(company_dims: dict) -> dict:
        merged: dict = {}
        for dim in _VALID_DIMENSIONS:
            if dim in company_dims:
                merged[dim] = company_dims[dim]
            elif dim in generic_dims:
                merged[dim] = generic_dims[dim]
        return merged

    banks: dict = {}
    for company, company_dims in raw.get("company_specific", {}).items():
        banks[company] = _merge_with_generic(company_dims)
        sc: dict = {}
        for dim, qs in company_dims.items():
            sq = [q for q in qs if q.get("question_type") == "scenario"]
            if sq:
                sc[dim] = sq
        for dim, qs in scenario_dims.items():
            sc.setdefault(dim, qs)
        if sc:
            banks[f"{company}_scenario"] = sc

    return banks


_QUESTION_BANK_RAW: dict = _load_question_bank()
_QUESTION_BANK: dict = _normalize_question_bank(_QUESTION_BANK_RAW)


# ── Seniority-level expectations injected into prompts ───────────────────────
_SENIORITY_EXPECTATIONS = {
    "junior": "Personal execution. Direct impact on one system or feature. Story should cover a 1-2 week scope.",
    "mid":    "Personal ownership across a feature or service. Measurable impact. Story scope 1-3 months.",
    "senior": "End-to-end ownership of a system or significant feature. Quantified team or system-level impact.",
    "staff":  "Cross-team influence, architectural decisions, org-level tradeoffs. Impact spans multiple teams.",
    "em":     "Organisational leverage: team outcomes, headcount decisions, clearing systemic blockers.",
}


EVAL_SYSTEM_PROMPT = """
You are a senior behavioral interview evaluator trained in executive communication,
leadership hiring, and psychological coaching.

Your goal is NOT just to identify what was wrong. Your goal is to show the candidate
how their answer is being psychologically read by a hiring manager at a top-tier company
(Google, Amazon, Meta, Stripe, Flipkart, OpenAI), and to give them the exact language
to fix it — while preserving their confidence and psychological safety.

You are a combination of:
  - A senior hiring manager who has interviewed hundreds of candidates
  - An executive communication coach who understands how language signals seniority
  - A supportive mentor who wants this person to succeed

The candidate should leave feeling: challenged, respected, clearer, and motivated.

━━━ SECTION 1 — PSYCHOLOGICAL SAFETY RULES ━━━

These rules govern the TONE of every piece of feedback. Violating them undermines the
coaching value of the feedback, even if the content is accurate.

RULE 1 — CRITIQUE BEHAVIOR, NOT IDENTITY.
  Wrong: "You don't seem to take ownership."
  Right: "This sentence uses collective language that causes interviewers to mark
          ownership as 'unclear' in their scorecard."

RULE 2 — SHOW THE INTERVIEWER'S INTERNAL MONOLOGUE.
  Don't say a response is "weak." Explain the cognitive move the interviewer makes
  when they read it. Example: "When an interviewer reads 'we built X together,' they
  immediately ask: what did YOU specifically do? If the answer doesn't follow, the
  ownership box gets left blank — not marked down, just left blank. A blank is a miss."

RULE 3 — EVERY CRITIQUE MUST HAVE A VERBATIM FIX.
  Generic advice ("add more specifics") is not coaching. The fix must be a rewritten
  version of the actual weak sentence — one the candidate could deliver word for word.

RULE 4 — NAME WHAT'S GOOD FIRST, SPECIFICALLY.
  Not: "There were some strengths." Specifically: "The line 'I drove the migration
  timeline by anchoring it to the Q3 launch' is exactly the kind of first-person
  ownership signal interviewers are trained to score positively."

RULE 5 — FRAME GAPS AS LEARNABLE PATTERNS.
  Not: "You struggle with quantification."
  Right: "This is a very common gap — most candidates were never told that impact
  adjectives (significantly, greatly, much faster) are invisible to interviewers.
  Numbers are not. One practice: after every sentence with an adjective, ask yourself
  'what is the number behind this word?'"

━━━ SECTION 2 — EVALUATION DIMENSIONS ━━━

Evaluate the answer across these 12 dimensions. Score only those where you have
clear signal. Do not force scores on dimensions with insufficient evidence.

1. COMMUNICATION CLARITY
   Is the answer structured? Does it move from context → action → result?
   Does the candidate make complex ideas simple, or bury them in jargon?
   Senior signal: can communicate at altitude — concise, decisive, no hedging.

2. STORY STRUCTURE (STAR)
   Situation (context set quickly, 1-3 sentences)
   Task (candidate's specific role and ownership, not the team's)
   Action (first-person, specific steps — not "we decided to")
   Result (stated early, not buried, ideally with a number before the last sentence)

3. OWNERSHIP AND ACCOUNTABILITY
   Does "I" appear with clear decision verbs? (I decided, I drove, I owned, I escalated)
   Is the candidate the subject of their own story or a supporting character?
   Watch: heavy "we" without "I" follow-through, escalation to manager without
   explaining why escalation was the right call.

4. LEADERSHIP AND INFLUENCE
   Did the candidate move people, systems, or decisions — not just execute tasks?
   For senior+: evidence of stakeholder alignment, influence without authority,
   organizational navigation, persuasion of resistant audiences.

5. CONFLICT RESOLUTION
   When conflict appears in the story, did the candidate engage it directly?
   Or was it resolved by escalation, avoidance, or vague "we worked through it"?
   Strong signal: named the tension, described their specific approach, stated outcome.

6. BUSINESS IMPACT
   Does the result connect to business outcomes (revenue, cost, retention, latency,
   team velocity, customer satisfaction)?
   Missing signal: output described (shipped feature) without outcome (why it mattered).

7. DECISION-MAKING QUALITY
   Are tradeoffs mentioned? Was the decision between real alternatives?
   Strong signal: "I chose X over Y because Z constraint meant Y would have..."
   Weak signal: decision described as obvious or inevitable — no tradeoff visible.

8. SENIORITY SIGNAL
   Calibrate against the declared seniority level.
   junior/mid:  IC execution + direct result on a specific feature or system
   senior:      personal ownership + measurable team/system-level impact
   staff:       cross-team influence, architectural decisions, org-level tradeoffs
   em:          organizational leverage, team outcomes, headcount/revenue impact
   Flag mismatch between the story scope and the seniority being interviewed for.

9. CONFIDENCE AND EXECUTIVE PRESENCE
   Three components (weighted per research: gravitas 60%, communication 30%):
   Gravitas: Does the candidate own their decisions without defensiveness?
             Do they handle ambiguity with confidence rather than hedging?
   Communication: Concise? Structured? No unnecessary qualifiers?
   Authenticity: Does the delivery feel natural and lived-in, or rehearsed and hollow?

10. AUTHENTICITY VS. REHEARSED TONE
    Rehearsed signal: over-formal transitions ("Firstly, I would like to begin by..."),
    textbook STAR structure that sounds like it was assembled from a template,
    no specific names or details, results that are suspiciously round numbers,
    answers that could fit any company or any situation.
    Authentic signal: a specific name, a specific moment of doubt or tension,
    a result that is oddly precise, an unexpected detail that wasn't in the script.

11. EMOTIONAL INTELLIGENCE
    Does the candidate show awareness of how their actions affected others?
    Do they acknowledge the emotional stakes of conflict situations?
    Do they show self-awareness about their own blindspots or growth edges?
    This is a signal interviewers use as a proxy for "will this person be a good
    manager or collaborator" — especially at senior+ levels.

12. METRICS AND SPECIFICITY
    Are numbers present where they should be?
    Specificity rule: any sentence with an impact adjective (significant, major,
    great, huge, much, fast, better) is a candidate for quantification.
    Estimate ranges are valid: "approximately 35–45%", "roughly 3x", "from ~800ms to ~480ms."

━━━ SECTION 3 — ANTI-PATTERN DEFINITIONS ━━━

Fire an anti-pattern ONLY if you find clear evidence in the answer.
For every anti-pattern you fire, triggered_excerpt MUST be a verbatim substring of
the candidate's answer — copy the exact sentence. Do not paraphrase or reconstruct it.

For each anti-pattern, the rewrite_suggestion must model the corrected behavior as a
VERBATIM REPLACEMENT — a sentence the candidate could deliver word for word.

WE DEFAULT
  Signal: Collective language ("we built", "our team decided") without explicit personal
          ownership claim in the same sentence or the immediately following sentence.
  Interviewer reads this as: "Ownership: unclear" — not marked down, just blank.
          A blank on ownership is a miss for any level above junior.
  Score delta: -1 on Ownership dimension.
  triggered_excerpt: copy the FIRST "we" sentence without "I" follow-through. Verbatim.
  rewrite: Replace "we built X" with "I led the team that built X" or
           "I was the DRI for X — I wrote the spec, ran the reviews, and shipped it."

VAGUE QUANTIFICATION
  Signal: Impact described with adjectives without a number.
          Key words: significantly, greatly, much, faster, better, huge, major,
          substantial, dramatically, noticeably, considerably, improved.
  Interviewer reads this as: "I can't score this impact. Adjectives don't go in the
          scorecard box. Numbers do."
  Score delta: -1 on Metrics and Business Impact dimensions.
  triggered_excerpt: the phrase containing the vague adjective. Verbatim.
  rewrite: Replace the adjective with a number or an estimated range.

STORY RECYCLING
  Signal: Same story used across different dimension questions in this session.
          Use compressed_turns context to detect overlapping story excerpts.
  Interviewer reads this as: candidate has a limited story bank and is not
          demonstrating broad coverage of experiences.
  Score delta: -1 on any dimension.
  triggered_excerpt: opening sentence of the recycled story. Verbatim.

IMPACT BURIED
  Signal: The result appears only in the last sentence with no earlier signal.
          Strong answers surface impact in the first 40% of the response.
  Interviewer reads this as: I had to read to the end to understand why this
          story mattered. Interviewers often form impressions before the result arrives.
  Score delta: -1 on Communication Clarity and Business Impact.
  triggered_excerpt: the final sentence containing the buried result. Verbatim.
  rewrite: Move a single impact headline to the first or second sentence.

HYPOTHESIS WITHOUT PROOF
  Signal: Claimed impact without causal evidence.
          Key phrases: "probably helped", "should have improved", "I think it led to",
          "I believe it contributed", "might have", "would have".
  Interviewer reads this as: "This person doesn't know what their work actually did.
          That's either lack of follow-through or lack of business awareness."
  Score delta: -1 on Business Impact and Decision-Making.
  triggered_excerpt: the sentence containing the speculative language. Verbatim.

ESCALATION DEFAULT
  Signal: Conflict or ambiguity resolved by deferring to manager without explaining
          why that was the right call.
  Interviewer reads this as: candidate did not take ownership of the problem.
  Key phrases: "so I went to my manager", "we escalated it", "my lead decided",
               "I asked my manager what to do."
  Score delta: -1 on Ownership and Conflict Resolution.
  triggered_excerpt: the escalation sentence. Verbatim.
  rewrite: Show what the candidate tried first before escalating, or explain the
           reasoning: "I looped in my manager because this required budget sign-off
           that was outside my scope — but I came with a recommendation already formed."

SCOPE COLLAPSE
  Signal: Staff or EM candidate tells an IC-level story with no organizational
          leverage, cross-team coordination, or architectural scope visible.
  ONLY fire for seniority=staff or seniority=em. Never for junior/mid/senior.
  Interviewer reads this as: "This person operates at the individual level.
          I'm not seeing the organizational altitude I need for this role."
  Score delta: -1 on Seniority Signal and Leadership.
  triggered_excerpt: the opening sentence that establishes IC scope. Verbatim.

REHEARSED SCRIPT
  Signal: The answer sounds template-assembled rather than lived-in.
          No specific names. No moment of personal tension or doubt.
          Results are suspiciously round (exactly 50%, exactly 2x, exactly 3 months).
          Transitions sound like a framework ("Firstly, regarding the situation...").
  Interviewer reads this as: "I'm not learning anything real about this person.
          The answer fits any company and any situation — which means it signals nothing."
  Score delta: -1 on Authenticity and Executive Presence.
  triggered_excerpt: the most template-sounding sentence. Verbatim.

━━━ SECTION 4 — SENIORITY CALIBRATION ━━━

junior/mid: Expect personal execution + direct result on a single system or feature.
            IC-level stories are correct. Org scope is not expected.
senior:     Expect first-person ownership + measurable team or system-level impact.
            "We shipped" is weak; "I drove the roadmap for the team that shipped" is correct.
staff:      Expect cross-team influence, architectural decisions, org-level tradeoffs.
            Individual execution stories are a red flag — they signal premature leveling.
em:         Expect organizational leverage and team outcomes.
            Stories about coding or individual execution are almost always wrong.
            Strong EM signal: "I unblocked the team by resolving the dependency conflict
            with Platform, which let us ship two weeks early" — not "I fixed the bug."

━━━ SECTION 5 — OUTPUT FORMAT ━━━

Return ONLY this JSON. No markdown, no preamble, no trailing text.

{
  "dimension_score": {
    "dimension": "one of the 7 behavioral dimensions (ownership, impact_and_scale, influence_without_authority, problem_solving, collaboration, growth_mindset, conflict_resolution)",
    "signal_strength": "weak|developing|strong",
    "score_delta": "e.g. +1 on Ownership, -1 on Business Impact",
    "what_was_strong": "specific signal that was present — name the verbatim line",
    "what_was_missing": "specific signal absent — explain WHY the interviewer cares, not just that it's missing"
  },

  "anti_patterns_fired": [
    {
      "key": "snake_case_anti_pattern_key",
      "label": "Human Readable Name",
      "triggered_excerpt": "VERBATIM substring of the candidate answer — copy exactly",
      "interviewer_reads_as": "one sentence: how a real interviewer cognitively interprets this pattern",
      "rewrite_suggestion": "verbatim replacement sentence the candidate could deliver word for word"
    }
  ],

  "level_signal": {
    "signaled_level": "junior|mid|senior|staff|em",
    "declared_level": "(same as seniority input)",
    "match": true,
    "note": "one concrete sentence. If mismatch: name what organizational scope or language would close the gap."
  },

  "executive_presence": "strong|developing|low|not_assessable",

  "authenticity_note": "one concrete observation — does this sound real or rehearsed? Name the specific signal that drove this assessment.",

  "overall_verdict": "2-3 sentences. Written like a hiring manager summarizing this candidate to a committee. What level does this signal? What is the single most important thing to fix?",

  "best_line": "verbatim sentence from the answer that was strongest — the one the interviewer would highlight in their notes",

  "coaching_close": "2-3 sentences. Written like a mentor who is on the candidate's side. Growth-mindset framing. Name the one pattern to fix, frame it as learnable, end with a forward-looking observation."
}

anti_patterns_fired may be an empty array []. Never fabricate excerpts.
coaching_close must feel like it came from a person who respects the candidate and
wants them to succeed — not a rubric summary.

━━━ SECTION 6 — TONE CALIBRATION ━━━

The feedback you produce will be read by a human who has just spent effort on their answer.
Before generating the output, ask yourself:

  - Would a great mentor at Google or Stripe say this to someone they genuinely
    wanted to get the offer?
  - Does every critique have a clear "why it matters to the interviewer"?
  - Does every critique have a verbatim fix?
  - Is the coaching_close motivating — not just summarizing?
  - Would the candidate feel challenged AND respected after reading this?

If the answer to any of these is no, revise before returning.
"""


FOLLOW_UP_SYSTEM_PROMPT = """
You are a behavioral interview coach generating targeted follow-up probe questions.

Your job: given an interview question and the candidate's answer, decide whether
a follow-up probe is warranted. If yes, return a single follow-up question as
plain text. If no, return the literal string NONE.

Generate a follow-up probe when ANY of the following gaps are present:
- Ownership unclear: heavy use of "we"/"our team" with no explicit "I" ownership claim
- Impact number missing: the story has a quantifiable outcome but no metric was stated
- Conflict mentioned but resolution unclear: candidate describes a disagreement but
  doesn't explain how it was resolved or what the outcome was
- Result positive but no learning: candidate says it went well but names no behavioral
  change or lesson learned
- Timeframe absent on a complex multi-month project: scale of effort is unclear

If the answer is complete and covers ownership + impact + resolution + learning,
return NONE.

Return ONLY the follow-up question text as a single sentence, or the string NONE.
No JSON, no markdown, no preamble.
"""


SUMMARY_SYSTEM_PROMPT = """
You are a behavioral interview coach generating a post-session summary for a candidate.
Your summary is shown directly in the product UI — be specific, honest, and actionable.

You receive:
- Compressed turn history (dimension, signal strength, anti-patterns, story excerpt per question)
- Per-question feedback summaries (what was strong, what was missing, patterns fired)
- Seniority and company context

━━━ OUTPUT FORMAT ━━━

Return ONLY this JSON. No markdown, no preamble, no trailing text.

{
  "dimension_scorecard": [
    {
      "dimension": "one of the 7 behavioral dimensions",
      "signal_strength": "weak|developing|strong",
      "expected_for_seniority": "weak|developing|strong",
      "gap": true,
      "note": "one concrete sentence on what made this strong or what to fix"
    }
  ],
  "anti_pattern_report": [
    {
      "key": "anti_pattern_key",
      "label": "Human Readable Name",
      "count": 2,
      "worst_excerpt": "verbatim excerpt from the worst instance across all questions",
      "fix": "one actionable sentence on how to fix this pattern"
    }
  ],
  "top_strength": "one sentence naming the single best signal across the session",
  "top_gap": "one sentence naming the single most impactful thing to improve",
  "recommended_next_dimension": "one of the 7 dimensions NOT covered in this session"
}

━━━ RULES ━━━

dimension_scorecard:
- Include ONLY dimensions that were actually covered this session (one entry per question).
- gap=true when signal_strength is below expected_for_seniority.
- expected_for_seniority must reflect the seniority context passed in, not a generic value.
- note must name something specific — not "good job" or "needs improvement".

anti_pattern_report:
- Include ONLY patterns that actually fired across the session.
- Deduplicate: if the same pattern fired in Q1 and Q2, one entry with count=2.
- worst_excerpt must be a verbatim sentence from the compressed turn history.
- If no patterns fired, return an empty array [].

top_strength and top_gap:
- Each is one sentence. Specific. Names the dimension or story element.
- top_gap must be something the candidate can act on — not generic.

recommended_next_dimension:
- Must be a dimension NOT present in the covered dimensions list.
- Must match the seniority: don't recommend conflict_resolution to a junior candidate
  whose gap is clearly impact_and_scale.
"""


MODEL_ANSWER_SYSTEM_PROMPT = """
You are a senior interviewer helping a candidate understand what a stronger version of their answer would sound like.

Rules you must follow without exception:
1. Only use facts, numbers, and details the candidate already provided.
2. Do not invent metrics, team sizes, timeframes, or outcomes they did not mention.
3. Structure the answer in STAR format: Situation, Task, Action, Result.
4. Fix the specific weaknesses identified in the feedback.
5. Match the candidate's seniority level.
6. Target 200-350 words. Do not pad. Do not truncate the result.
7. Write in first person, natural spoken English — not LinkedIn prose.

Return JSON only: { "text": "...", "what_changed": "..." }

The goal is to show the candidate the shape of a strong answer, not to hand them a script to memorize.
"""


_SENIORITY_SCOPE_HINTS = {
    "junior": "Focus on clarity, personal execution, and learning — not org-wide scope.",
    "mid": "Show personal ownership with direct, measurable impact on your team.",
    "senior": "Emphasize cross-functional influence, system-level decisions, and team outcomes.",
    "staff": "Frame systemic scope: multi-team tradeoffs, architectural decisions, org leverage.",
    "em": "Emphasize organizational outcomes, people leadership, and strategic tradeoffs — not IC execution.",
}


QUESTION_GEN_SYSTEM = """\
You are a behavioural interview question designer for a career coaching platform.

You generate exactly 3 interview questions for a specific candidate at a specific company.

RULES — follow every rule or the output is unusable:
1. Exactly 3 questions. No more, no less.
2. Each question targets a DIFFERENT dimension. Never repeat a dimension.
   Valid dimensions: ownership, impact_and_scale, influence_without_authority,
   problem_solving, collaboration, growth_mindset, conflict_resolution
3. Each question must be grounded in a specific resume signal from the candidate.
   The why_this_question field must name the signal being probed.
4. Questions must feel natural and conversational — not like a textbook exercise.
5. risky_anti_patterns: pick 1-3 keys ONLY from this list (do not invent new keys):
   we_default            — hides behind "we", obscures individual contribution
   vague_quantification  — fake/missing numbers; adjectives instead of metrics
   story_recycling       — same story reused across multiple questions
   impact_buried         — leads with activity, buries result at the end
   hypothesis_without_proof — states assumptions as fact, no validation shown
   escalation_default    — resolves by going to manager rather than directly
   scope_collapse        — staff/EM candidate describes junior-scoped work
   no_reflection         — story ends at event; no learning or behavioral change stated
   credit_deflection     — minimises own agency ("my manager suggested", "lucky timing")
   recency_bias          — can only cite recent examples; no evidence of sustained behavior
6. scope_collapse: only include for seniority=staff or seniority=em
7. Respect the question_type in the prompt:
   behavioral → "Tell me about a time when..."
   scenario   → "Imagine you are..." or "Suppose you..."
8. company_value_ref: format as "{Framework Name}: {Value Name}"
   e.g. "Amazon LP: Ownership" or "Google Googleyness: Leadership"
9. answer_risk_note: use ONLY when you spot a candidate-specific risk that none of
   the 10 keys above can capture — e.g. "candidate's only experience is at a 3-person
   startup; may lack scale reference" or "all projects are solo; no collaborative
   signal to draw on". Max 120 characters. Set to null when the taxonomy covers it.

OUTPUT — return ONLY this JSON. No markdown. No preamble. No trailing text.
{
  "questions": [
    {
      "id": "q1",
      "text": "the actual interview question — conversational, specific to this candidate",
      "question_type": "behavioral",
      "dimension": "one of the 7 valid dimensions",
      "why_this_question": "which resume signal is being probed and why this dimension matters for this company",
      "expected_signals": ["3-5 specific signals a Strong answer would contain"],
      "risky_anti_patterns": ["1-3 keys from the 10-key list above"],
      "answer_risk_note": null,
      "company_value_ref": "Framework Name: Value Name"
    }
  ]
}
"""


class InterviewAgent(BaseAgent):
    """
    Agent 6 — Behavioural Interview.

    Methods (Days 2-4):
      generate_questions(input_dict)  → dict   Day 2
      evaluate_answer(input_dict)     → dict   Day 3
      generate_summary(input_dict)    → dict   Day 4

    Model: claude-sonnet-4-20250514 (Anthropic)
    Max tokens: 2000 for questions, 1500 for evaluation, 1000 for summary
    """

    def __init__(self):
        super().__init__(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            provider="anthropic",
        )

    def run(self, input_dict: dict) -> dict:
        """Route to generate_questions as the primary Day 2 entry point."""
        return self.generate_questions(input_dict)

    # ── Day 2 ─────────────────────────────────────────────────────────────────

    def generate_questions(self, input_dict: dict) -> dict:
        """
        Generate exactly 3 behavioural interview questions.

        Input keys:
          resume_signals: dict   — ResumeUnderstandingAgent output (or resume_text: str)
          company:        str    — key into company_values.json (e.g. "amazon")
          seniority:      str    — junior | mid | senior | staff | em
          question_mode:  str    — behavioral | scenario | mixed
                                   mixed → 2 behavioral + 1 scenario (scenario is Q3)

        Output:
          { "questions": [ InterviewQuestion dict × 3 ] }
          Each question targets a DIFFERENT dimension.
          question_type resolved: behavioral questions use "Tell me about a time..."
          scenario questions use "Imagine you are..." framing.

        Raises:
          ValueError: if LLM returns < 3 questions or duplicate dimensions.
        """
        company_key = input_dict.get("company", "").lower().strip()
        seniority = input_dict.get("seniority", "senior").lower().strip()
        question_mode = input_dict.get("question_mode", "mixed").lower().strip()

        company_data = _COMPANY_VALUES.get(company_key)
        if not company_data:
            company_data = {
                "display_name": input_dict.get("company", "the target company"),
                "framework": "General Behavioural Framework",
                "values": [],
                "ic_focus_dimensions": ["ownership", "problem_solving", "impact_and_scale"],
                "em_focus_dimensions": ["influence_without_authority", "collaboration", "impact_and_scale"],
            }

        focus_key = "em_focus_dimensions" if seniority == "em" else "ic_focus_dimensions"
        focus_dimensions = company_data.get(focus_key, ["ownership", "problem_solving", "impact_and_scale"])

        prompt = self._build_question_gen_prompt(
            input_dict=input_dict,
            company_data=company_data,
            focus_dimensions=focus_dimensions,
            seniority=seniority,
            question_mode=question_mode,
        )

        try:
            raw = self._call_llm(QUESTION_GEN_SYSTEM, prompt)
            result = self._parse_and_validate_questions(raw, question_mode)
            for q in result["questions"]:
                q["source"] = "generated"
            return result

        except (ValueError, RuntimeError):
            fallback = self._get_fallback_questions(
                company_key=company_key,
                focus_dimensions=focus_dimensions,
                question_mode=question_mode,
                seniority=seniority,
            )
            if fallback:
                return fallback
            raise

    def _get_bank_examples(
        self,
        company_key: str,
        target_dimensions: list[str],
        question_mode: str,
    ) -> str:
        """
        Fetches 1 example question per target dimension from the question bank.
        Returns a formatted string for injection into the question generation prompt.

        Lookup order:
          1. Exact company key (e.g. "amazon")
          2. "{company}_scenario" key for scenario questions (e.g. "google_scenario")
          3. Skip silently if no match — bank is optional

        Returns empty string if bank has no relevant examples (generation still works).
        """
        if not _QUESTION_BANK:
            return ""

        examples = []
        for dim in target_dimensions:
            lookup_keys = [company_key]
            if question_mode in ("scenario", "mixed"):
                lookup_keys.append(f"{company_key}_scenario")

            found = None
            for key in lookup_keys:
                company_bank = _QUESTION_BANK.get(key, {})
                dim_questions = company_bank.get(dim, [])
                if dim_questions:
                    found = dim_questions[0]
                    break

            if found:
                examples.append(
                    f'DIMENSION: {found["dimension"]}\n'
                    f'TYPE: {found["question_type"]}\n'
                    f'QUESTION: {found["question"]}\n'
                    f'WHAT THEY EVALUATE: {found["what_they_evaluate"]}\n'
                    f'STRONG SIGNALS: {"; ".join(found["strong_answer_signals"][:3])}\n'
                )

        if not examples:
            return ""

        header = (
            "EXAMPLE QUESTIONS FROM THE QUESTION BANK (for reference — do not copy verbatim):\n"
            "These show the style, depth, and evaluation criteria expected for this company.\n"
            "Your generated questions must be grounded in the candidate's resume signals below.\n\n"
        )
        return header + "\n---\n".join(examples)

    def _get_fallback_questions(
        self,
        company_key: str,
        focus_dimensions: list[str],
        question_mode: str,
        seniority: str,
    ) -> dict | None:
        """
        Returns up to 3 questions from the question bank as a fallback.
        Questions are marked source='bank' so the UI can show a subtle indicator.
        Returns None if the bank has fewer than 3 questions for this company+dimensions.
        """
        if not _QUESTION_BANK:
            return None

        questions = []
        dims_used = set()

        for dim in focus_dimensions:
            if len(questions) >= 3:
                break
            company_bank = _QUESTION_BANK.get(company_key, {})
            dim_qs = company_bank.get(dim, [])
            if dim_qs and dim not in dims_used:
                q = dict(dim_qs[0])
                q["id"] = f"bank_{company_key}_{dim}"
                q["source"] = "bank"
                q["text"] = q.pop("question", q.get("text", ""))
                if question_mode == "behavioral":
                    q["question_type"] = "behavioral"
                elif question_mode == "scenario":
                    q["question_type"] = "scenario"
                else:
                    q["question_type"] = "scenario" if len(questions) == 2 else "behavioral"
                q.setdefault(
                    "why_this_question",
                    f"From question bank — targeting {dim} for {company_key}",
                )
                q.setdefault("expected_signals", q.get("strong_answer_signals", [])[:4])
                q.setdefault("risky_anti_patterns", [])
                q.setdefault("answer_risk_note", None)
                q.setdefault("company_value_ref", "")
                questions.append(q)
                dims_used.add(dim)

        if len(questions) < 3:
            return None

        return {"questions": questions[:3]}

    def _build_question_gen_prompt(
        self,
        input_dict: dict,
        company_data: dict,
        focus_dimensions: list,
        seniority: str,
        question_mode: str,
    ) -> str:
        resume_signals = input_dict.get("resume_signals") or {}
        resume_text = input_dict.get("resume_text", "")

        # A4 — If resume is sparse (< 100 words or no signals), use generic questions
        if resume_signals:
            signal_lines = []
            for k, v in resume_signals.items():
                if v:
                    signal_lines.append(f"  {k}: {v}")
            resume_block = "CANDIDATE RESUME SIGNALS:\n" + "\n".join(signal_lines)
        elif resume_text and len(resume_text.split()) >= 100:
            resume_block = f"CANDIDATE RESUME (raw text):\n{resume_text[:3000]}"
        else:
            resume_block = "CANDIDATE RESUME SIGNALS: (sparse or minimal — generate dimension-generic questions)"

        values_block = (
            f"TARGET COMPANY: {company_data['display_name']}\n"
            f"BEHAVIOURAL FRAMEWORK: {company_data['framework']}\n"
            f"FOCUS DIMENSIONS FOR THIS SENIORITY ({seniority}): {', '.join(focus_dimensions)}\n"
            f"COMPANY VALUES:\n"
        )
        for v in company_data.get("values", []):
            values_block += f"  - {v['name']} → maps to dimension: {v['maps_to_dimension']}\n"

        if question_mode == "mixed":
            mode_instruction = (
                "QUESTION MODE: mixed\n"
                "Q1 and Q2 must be BEHAVIORAL questions ('Tell me about a time...').\n"
                "Q3 must be a SCENARIO question ('Imagine you are...', 'Suppose you...').\n"
                "Set question_type='behavioral' for Q1/Q2 and question_type='scenario' for Q3."
            )
        elif question_mode == "scenario":
            mode_instruction = (
                "QUESTION MODE: scenario\n"
                "All 3 questions must be SCENARIO questions ('Imagine you are...', 'Suppose you...').\n"
                "Set question_type='scenario' for all 3."
            )
        else:
            mode_instruction = (
                "QUESTION MODE: behavioral\n"
                "All 3 questions must be BEHAVIORAL questions ('Tell me about a time...').\n"
                "Set question_type='behavioral' for all 3."
            )

        seniority_note = _SENIORITY_EXPECTATIONS.get(seniority, _SENIORITY_EXPECTATIONS["senior"])

        bank_examples = self._get_bank_examples(
            company_key=input_dict.get("company", "").lower().strip(),
            target_dimensions=focus_dimensions,
            question_mode=question_mode,
        )

        return f"""{resume_block}

{values_block}
SENIORITY: {seniority}
SENIORITY EXPECTATION: {seniority_note}

{mode_instruction}

{bank_examples}Generate exactly 3 questions. Each must target a DIFFERENT dimension.
Prioritise these dimensions first (but use any 3 from the 7 valid dimensions if better fit):
{', '.join(focus_dimensions)}

Each question MUST be grounded in a specific signal from the candidate's resume.
The why_this_question field must name the resume signal being probed."""

    def _parse_and_validate_questions(self, raw: str, question_mode: str) -> dict:
        """Parse LLM response, validate structure, assign IDs and question_type."""
        data = self._parse_json(raw)

        # A2 — Check for JSON parse error
        if data.get("_parse_error"):
            raise ValueError(f"Failed to parse LLM generate_questions response after retry: {data.get('raw', '')[:100]}")

        questions = data.get("questions", [])

        if len(questions) != 3:
            raise ValueError(
                f"generate_questions: expected 3 questions, got {len(questions)}"
            )

        dimensions_used = [q.get("dimension") for q in questions]
        if len(set(dimensions_used)) != 3:
            raise ValueError(
                f"generate_questions: duplicate dimensions found: {dimensions_used}. "
                "All 3 questions must target different dimensions."
            )

        for d in dimensions_used:
            if d not in _VALID_DIMENSIONS:
                raise ValueError(f"generate_questions: invalid dimension '{d}'")

        for q in questions:
            # Strip any invented anti-pattern keys; keep only valid taxonomy keys.
            q["risky_anti_patterns"] = [
                k for k in q.get("risky_anti_patterns", [])
                if k in _VALID_ANTI_PATTERNS
            ]

            # Preserve free-text escape hatch; discard if the LLM returns a non-string
            # or an empty/whitespace string (treat as null).
            raw_note = q.get("answer_risk_note")
            if isinstance(raw_note, str) and raw_note.strip():
                q["answer_risk_note"] = raw_note.strip()[:120]
            else:
                q["answer_risk_note"] = None

        # A5 — Mixed mode order enforcement: deterministically enforce [behavioral, behavioral, scenario]
        if question_mode == "mixed":
            behavioral = [q for q in questions if q.get("question_type") == "behavioral"]
            scenario = [q for q in questions if q.get("question_type") == "scenario"]

            # Pad or trim to ensure exactly 2 behavioral + 1 scenario
            while len(behavioral) < 2 and len(scenario) > 1:
                behavioral.append(scenario.pop(0))
            while len(scenario) < 1 and len(behavioral) > 2:
                scenario.append(behavioral.pop())

            behavioral = behavioral[:2]
            scenario = scenario[:1]

            questions = behavioral + scenario  # Always [B, B, S]

        for i, q in enumerate(questions):
            q["id"] = q.get("id") or f"q{i+1}_{uuid4().hex[:8]}"

            if question_mode == "behavioral":
                q["question_type"] = "behavioral"
            elif question_mode == "scenario":
                q["question_type"] = "scenario"
            elif question_mode == "mixed":
                q["question_type"] = "scenario" if i == 2 else "behavioral"

        return {"questions": questions}

    # ── Day 3 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_eval_feedback(feedback: dict, seniority: str) -> dict:
        """
        Ensure coaching-schema fields exist with safe defaults after LLM parse.
        Strips deprecated weakest_line if present.
        """
        declared = seniority.lower().strip()
        valid_levels = {"junior", "mid", "senior", "staff", "em"}
        level = feedback.get("level_signal")
        if not isinstance(level, dict):
            level = {}
        signaled = str(level.get("signaled_level", declared)).lower().strip()
        if signaled not in valid_levels:
            signaled = declared
        feedback["level_signal"] = {
            "signaled_level": signaled,
            "declared_level": str(level.get("declared_level", declared)).lower().strip()
            if str(level.get("declared_level", declared)).lower().strip() in valid_levels
            else declared,
            "match": bool(level.get("match", signaled == declared)),
            "note": str(level.get("note", "")),
        }

        ep = feedback.get("executive_presence", "not_assessable")
        if ep not in {"strong", "developing", "low", "not_assessable"}:
            ep = "not_assessable"
        feedback["executive_presence"] = ep
        feedback["authenticity_note"] = str(feedback.get("authenticity_note", ""))
        feedback["coaching_close"] = str(feedback.get("coaching_close", ""))
        feedback.pop("weakest_line", None)

        cleaned_aps = []
        for ap in feedback.get("anti_patterns_fired", []):
            if not isinstance(ap, dict):
                continue
            key = ap.get("key")
            if key and key not in _VALID_ANTI_PATTERNS:
                continue
            cleaned_aps.append({
                "key": key,
                "label": str(ap.get("label", "")),
                "triggered_excerpt": str(ap.get("triggered_excerpt", "")),
                "interviewer_reads_as": str(ap.get("interviewer_reads_as", "")),
                "rewrite_suggestion": str(ap.get("rewrite_suggestion", "")),
            })
        feedback["anti_patterns_fired"] = cleaned_aps
        return feedback

    @staticmethod
    def _closest_verbatim_match(excerpt: str, answer: str) -> str | None:
        """
        A6 — Attempts to find a sentence in answer that contains the most words
        from excerpt. Returns the sentence if overlap > 50%, else None.
        Falls back gracefully — never raises.
        """
        try:
            excerpt_words = set(excerpt.lower().split())
            sentences = [s.strip() for s in answer.replace('!', '.').replace('?', '.').split('.') if s.strip()]
            best_sentence, best_overlap = None, 0.0
            for sentence in sentences:
                sentence_words = set(sentence.lower().split())
                if not excerpt_words:
                    continue
                overlap = len(excerpt_words & sentence_words) / len(excerpt_words)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_sentence = sentence
            return best_sentence if best_overlap > 0.5 else None
        except Exception:
            return None

    def evaluate_answer(self, input_dict: dict) -> dict:
        """
        Evaluate a candidate's answer with the evaluator-optimizer loop.

        Inputs:
          question:          InterviewQuestion dict
          answer_text:       str
          compressed_turns:  list[str]   — compressed summaries of prior Q&A turns
          seniority:         str         — junior | mid | senior | staff | em

        Output:
          PerQuestionFeedback dict — guaranteed validated (no hallucinated excerpts).

        Agentic patterns used:
          - Evaluator-optimizer: one retry if triggered_excerpt fails verbatim
            membership check
          - Context compression: previous turns passed as compressed summaries
        """
        # A1 — Short answer guard: too little content to evaluate meaningfully
        answer = input_dict["answer_text"]
        word_count = len(answer.split())

        if word_count < 50:
            dimension = input_dict["question"].get("dimension", "unknown")
            seniority = input_dict.get("seniority", "senior").lower().strip()
            return {
                "dimension_score": {
                    "dimension": dimension,
                    "signal_strength": "weak",
                    "score_delta": "0",
                    "what_was_missing": (
                        "Interviewers cannot score STAR elements they cannot hear. "
                        "Aim for at least 2–3 sentences per Situation, Task, Action, and Result."
                    ),
                    "what_was_strong": "",
                },
                "anti_patterns_fired": [],
                "level_signal": {
                    "signaled_level": seniority,
                    "declared_level": seniority,
                    "match": True,
                    "note": "Answer too short to assess seniority signal from story scope.",
                },
                "executive_presence": "not_assessable",
                "authenticity_note": "Answer too short to assess delivery tone.",
                "overall_verdict": (
                    "This reads as incomplete in a real interview — the interviewer would "
                    "ask you to expand before scoring. Add 150–400 words with clear STAR structure."
                ),
                "best_line": "",
                "coaching_close": (
                    "This is a learnable format gap, not a capability gap. Pick one strong story "
                    "from your resume and practice a 3-minute version with Situation, your Task, "
                    "your Actions, and a quantified Result — then retry."
                ),
            }

        raw_feedback = self._call_llm(
            EVAL_SYSTEM_PROMPT,
            self._build_eval_prompt(input_dict),
            call_label="evaluate_answer",
        )
        feedback = self._parse_json(raw_feedback)

        # A2 — Check for JSON parse error
        if feedback.get("_parse_error"):
            raise ValueError(f"Failed to parse LLM evaluate_answer response after retry: {feedback.get('raw', '')[:100]}")

        # ── Evaluator-optimizer loop ──────────────────────────────────────────
        # Every triggered_excerpt must be a verbatim substring of answer_text.
        # If any fail, retry once with an explicit repair constraint injected.
        answer = input_dict["answer_text"]
        failed = [
            ap for ap in feedback.get("anti_patterns_fired", [])
            if ap.get("triggered_excerpt", "") not in answer
        ]

        # A6 — Attempt closest-match repair before second LLM call
        if failed:
            for ap in failed:
                match = self._closest_verbatim_match(ap["triggered_excerpt"], answer)
                if match:
                    ap["triggered_excerpt"] = match  # repair in-place
            failed_still = [f for f in failed if f["triggered_excerpt"] not in answer]
            failed = failed_still

        if failed:
            bad_excerpts = [ap["triggered_excerpt"] for ap in failed]
            repair_note = (
                "CORRECTION REQUIRED: The following triggered_excerpt values were not "
                "found verbatim in the candidate's answer. You must either:\n"
                "  (a) Find the ACTUAL sentence from the answer that triggered this pattern, or\n"
                "  (b) Remove the anti_pattern entry if no verbatim sentence qualifies.\n\n"
                "Hallucinated excerpts to fix:\n" +
                "\n".join(f'  - "{e}"' for e in bad_excerpts)
            )
            raw_feedback_2 = self._call_llm(
                EVAL_SYSTEM_PROMPT,
                self._build_eval_prompt(input_dict) + f"\n\n{repair_note}",
                call_label="evaluate_answer_repair",
            )
            feedback = self._parse_json(raw_feedback_2)

            # Second pass: hard-drop any AP that still fails — never show hallucinated excerpts
            feedback["anti_patterns_fired"] = [
                ap for ap in feedback.get("anti_patterns_fired", [])
                if ap.get("triggered_excerpt", "") in answer
            ]

        return self._normalize_eval_feedback(feedback, input_dict.get("seniority", "senior"))

    def _build_eval_prompt(self, input_dict: dict) -> str:
        """Build the user-turn prompt for answer evaluation."""
        question = input_dict["question"]
        answer_text = input_dict["answer_text"]
        seniority = input_dict["seniority"]
        compressed_turns = input_dict.get("compressed_turns", [])

        prior_context = ""
        if compressed_turns:
            prior_context = (
                "Previous turns in this session (compressed):\n" +
                "\n".join(compressed_turns) +
                "\n\n"
            )

        return (
            f"{prior_context}QUESTION BEING EVALUATED:\n"
            f"Dimension: {question['dimension']}\n"
            f"Company value ref: {question.get('company_value_ref', 'N/A')}\n"
            f"Question text: {question['text']}\n"
            f"Expected signals: {', '.join(question.get('expected_signals', []))}\n"
            f"Risky anti-patterns to watch: {', '.join(question.get('risky_anti_patterns', []))}\n"
            f"\nCANDIDATE ANSWER:\n{answer_text}\n"
            f"\nCANDIDATE SENIORITY: {seniority}\n"
            f"\nEvaluate this answer. Return only the JSON specified in your system prompt."
        )

    @staticmethod
    def compress_turn(question_index: int, answer_text: str, feedback: dict) -> str:
        """
        Compresses one completed Q&A turn to ~100 tokens for context passing.
        Called after each evaluation completes.
        Result is stored in the session and passed as compressed_turns to
        subsequent evaluate_answer() calls.

        Args:
            question_index: 1-indexed (1, 2, 3)
            answer_text:    candidate's full answer
            feedback:       PerQuestionFeedback dict (already validated)

        Returns:
            Single-line compressed summary string (~100 tokens).
        """
        dim = feedback["dimension_score"]["dimension"]
        strength = feedback["dimension_score"]["signal_strength"]
        aps = [ap["key"] for ap in feedback.get("anti_patterns_fired", [])]
        ap_str = ", ".join(aps) if aps else "none"
        # 120-char story excerpt for story recycling detection
        excerpt = answer_text[:120].replace("\n", " ").strip()

        return (
            f"Q{question_index}: dimension={dim} | signal={strength} | "
            f"anti_patterns={ap_str} | "
            f'story_excerpt="{excerpt}..."'
        )

    async def evaluate_answer_stream(self, input_dict: dict):
        """
        Streaming version of evaluate_answer().
        Runs the full evaluator-optimizer loop first (quality guaranteed),
        then yields structured JSON chunks in UI render order.

        Chunk emission order:
          verdict → best_line → level_signal → presence → dimension → missing (if not strong)
          → ap_fired × N → coaching_close → done
          error on failure.
        """
        try:
            # Step 1: run full validated evaluation (optimizer loop included)
            feedback = self.evaluate_answer(input_dict)

            # Step 2: emit in UI render order
            yield {"type": "verdict", "content": feedback["overall_verdict"]}
            yield {"type": "best_line", "content": feedback["best_line"]}
            yield {"type": "level_signal", "content": feedback["level_signal"]}
            yield {
                "type": "presence",
                "content": {
                    "executive_presence": feedback["executive_presence"],
                    "authenticity_note": feedback["authenticity_note"],
                },
            }
            yield {"type": "dimension", "content": feedback["dimension_score"]}

            if feedback["dimension_score"]["signal_strength"] != "strong":
                yield {"type": "missing", "content": feedback["dimension_score"]["what_was_missing"]}

            for ap in feedback.get("anti_patterns_fired", []):
                yield {"type": "ap_fired", "content": ap}

            yield {"type": "coaching_close", "content": feedback.get("coaching_close", "")}

            yield {"type": "done", "content": None}
        except Exception as exc:
            yield {"type": "error", "content": str(exc)}

    def generate_follow_up(self, input_dict: dict) -> dict | None:
        """
        Generates a follow-up probe question when the original answer is incomplete.

        Hard cap: returns None immediately if follow_up_count >= 2 (no LLM call).

        Triggers a probe when any of:
        - Ownership unclear (heavy "we", no "I" ownership claim)
        - Impact number missing from a quantifiable story
        - Conflict mentioned but resolution unclear
        - Result positive but no learning stated
        - Timeframe absent on complex multi-month project

        Similarity gate: if the generated probe is too similar to the original question
        (word overlap > 0.7), return None — the answer was complete enough.

        Input:
          question:         InterviewQuestion dict
          answer_text:      str
          follow_up_count:  int   — current count for this question (max 2)

        Output:
          FollowUpQuestion dict, or None
        """
        if input_dict.get("follow_up_count", 0) >= 2:
            return None

        follow_up_text = self._call_llm(
            FOLLOW_UP_SYSTEM_PROMPT,
            self._build_follow_up_prompt(input_dict),
            call_label="generate_follow_up",
        )

        if not follow_up_text or follow_up_text.strip().upper() == "NONE":
            return None

        # Similarity gate — simple word overlap check
        q_words = set(input_dict["question"]["text"].lower().split())
        f_words = set(follow_up_text.lower().split())
        if len(q_words) > 0 and len(q_words & f_words) / len(q_words) > 0.7:
            return None

        return {
            "id": str(uuid4()),
            "text": follow_up_text.strip(),
            "trigger_reason": "ownership_or_impact_unclear",
        }

    def _build_follow_up_prompt(self, input_dict: dict) -> str:
        """Build the user-turn prompt for follow-up question generation."""
        question = input_dict["question"]
        answer_text = input_dict["answer_text"]
        follow_up_count = input_dict.get("follow_up_count", 0)

        return (
            f"ORIGINAL QUESTION:\n{question['text']}\n"
            f"DIMENSION: {question['dimension']}\n"
            f"\nCANDIDATE ANSWER:\n{answer_text}\n"
            f"\nFOLLOW-UP PROBES ALREADY ASKED: {follow_up_count}\n"
            f"\nDecide if a follow-up probe is needed. "
            f"Return the probe question as plain text, or return NONE."
        )

    # ── Day 4 ─────────────────────────────────────────────────────────────────

    def generate_summary(self, input_dict: dict) -> dict:
        """
        Generates a post-session summary across all 3 Q&A turns.

        Input:
          questions:         list[InterviewQuestion dict]
          answers:           list[AnswerTurn dict]
          all_feedback:      list[PerQuestionFeedback dict]
          compressed_turns:  list[str]   # all 3 compressed turn strings from compress_turn()
          seniority:         str
          company:           str

        Output: SessionSummary dict — see SUMMARY_OUTPUT_FORMAT below.

        Context compression in use:
          compressed_turns replaces raw answer text in the prompt.
          all_feedback dicts carry the dimension scores and anti-pattern data.
          The LLM never re-reads thousands of tokens of raw answer history.
        """
        prompt = self._build_summary_prompt(input_dict)
        raw = self._call_llm(SUMMARY_SYSTEM_PROMPT, prompt, call_label="generate_summary")
        summary = self._parse_json(raw)

        # A2 — Check for JSON parse error
        if summary.get("_parse_error"):
            raise ValueError(f"Failed to parse LLM generate_summary response after retry: {summary.get('raw', '')[:100]}")

        covered = [
            fb["dimension_score"]["dimension"]
            for fb in input_dict.get("all_feedback", [])
        ]
        return self._validate_summary(summary, covered)

    def _validate_summary(self, summary: dict, covered_dimensions: list[str]) -> dict:
        """Ensure summary fields match the 7-dimension contract."""
        signal_values = {"weak", "developing", "strong"}
        scorecard = summary.get("dimension_scorecard", [])
        if not isinstance(scorecard, list):
            scorecard = []
            summary["dimension_scorecard"] = scorecard

        cleaned_scorecard = []
        for entry in scorecard:
            if not isinstance(entry, dict):
                continue
            dim = entry.get("dimension")
            if dim not in _VALID_DIMENSIONS:
                continue
            signal = entry.get("signal_strength")
            expected = entry.get("expected_for_seniority")
            if signal not in signal_values:
                signal = "developing"
            if expected not in signal_values:
                expected = "strong"
            cleaned_scorecard.append({
                "dimension": dim,
                "signal_strength": signal,
                "expected_for_seniority": expected,
                "gap": bool(entry.get("gap", False)),
                "note": str(entry.get("note", "")).strip() or "No note provided.",
            })
        summary["dimension_scorecard"] = cleaned_scorecard

        ap_report = summary.get("anti_pattern_report", [])
        if not isinstance(ap_report, list):
            ap_report = []
        cleaned_report = []
        for entry in ap_report:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            if key not in _VALID_ANTI_PATTERNS:
                continue
            cleaned_report.append({
                "key": key,
                "label": str(entry.get("label", key.replace("_", " ").title())),
                "count": max(1, int(entry.get("count", 1))),
                "worst_excerpt": str(entry.get("worst_excerpt", "")),
                "fix": str(entry.get("fix", "")).strip() or "Replace the pattern with a specific, owned action.",
            })
        summary["anti_pattern_report"] = cleaned_report

        uncovered = [d for d in _VALID_DIMENSIONS if d not in covered_dimensions]
        recommended = summary.get("recommended_next_dimension")
        if recommended not in uncovered:
            recommended = uncovered[0] if uncovered else "growth_mindset"
        summary["recommended_next_dimension"] = recommended

        summary["top_strength"] = str(summary.get("top_strength", "")).strip()
        summary["top_gap"] = str(summary.get("top_gap", "")).strip()
        return summary

    def generate_model_answer(self, input_dict: dict) -> dict:
        """
        Restructure the candidate's answer using STAR framing without inventing facts.

        Input:
          question:    InterviewQuestion dict
          answer_text: str
          feedback:    PerQuestionFeedback dict
          seniority:   str
          company:     str

        Output:
          { "text": str, "what_changed": str }
        """
        feedback = input_dict.get("feedback") or {}
        seniority = str(input_dict.get("seniority", "senior")).lower().strip()
        anti_patterns = feedback.get("anti_patterns_fired") or []
        ap_descriptions = [
            f"{ap.get('label', ap.get('key', ''))}: {ap.get('rewrite_suggestion', '')}"
            for ap in anti_patterns
            if isinstance(ap, dict)
        ]
        anti_patterns_description = (
            "; ".join(ap_descriptions) if ap_descriptions else "none identified"
        )
        scope_hint = _SENIORITY_SCOPE_HINTS.get(
            seniority, _SENIORITY_SCOPE_HINTS["senior"]
        )

        dim_score = feedback.get("dimension_score") or {}
        is_strong = (
            dim_score.get("signal_strength") == "strong"
            and not anti_patterns
        )

        user_prompt = (
            f"COMPANY: {input_dict.get('company', '')}\n"
            f"SENIORITY: {seniority}\n"
            f"SENIORITY SCOPE HINT: {scope_hint}\n"
            f"QUESTION:\n{input_dict['question']['text']}\n\n"
            f"CANDIDATE ANSWER:\n{input_dict['answer_text']}\n\n"
            f"FEEDBACK WEAKNESSES TO FIX:\n{anti_patterns_description}\n\n"
            f"DIMENSION NOTE — missing: {dim_score.get('what_was_missing', '')}\n"
            f"DIMENSION NOTE — strong: {dim_score.get('what_was_strong', '')}\n"
        )

        raw = self._call_llm(
            MODEL_ANSWER_SYSTEM_PROMPT,
            user_prompt,
            call_label="generate_model_answer",
        )
        parsed = self._parse_json(raw)
        if parsed.get("_parse_error"):
            raise ValueError(
                "Failed to parse model answer response: "
                f"{parsed.get('raw', '')[:100]}"
            )

        text = str(parsed.get("text", "")).strip()
        what_changed = str(parsed.get("what_changed", "")).strip()
        if is_strong and text:
            text = (
                "Your answer was already strong. Here's a slightly tightened version.\n\n"
                + text
            )
        return {"text": text, "what_changed": what_changed}

    def _build_summary_prompt(self, input_dict: dict) -> str:
        all_feedback = input_dict["all_feedback"]
        compressed = input_dict["compressed_turns"]
        seniority = input_dict["seniority"]
        company = input_dict["company"]

        turns_block = "\n".join(compressed) if compressed else "No compressed turns available."

        feedback_lines = []
        for i, fb in enumerate(all_feedback, start=1):
            ds = fb["dimension_score"]
            aps = [ap["key"] for ap in fb.get("anti_patterns_fired", [])]
            feedback_lines.append(
                f"Q{i} ({ds['dimension']}): signal={ds['signal_strength']} | "
                f"anti_patterns={', '.join(aps) if aps else 'none'} | "
                f"what_was_strong: {ds['what_was_strong']} | "
                f"what_was_missing: {ds['what_was_missing']}"
            )

        covered_dimensions = [fb["dimension_score"]["dimension"] for fb in all_feedback]

        return f"""SESSION CONTEXT
Company: {company}
Seniority: {seniority}
Dimensions covered this session: {', '.join(covered_dimensions)}

COMPRESSED TURN HISTORY
{turns_block}

PER-QUESTION FEEDBACK SUMMARY
{chr(10).join(feedback_lines)}

SENIORITY EXPECTATIONS (for gap scoring)
junior/mid:  strong = personal execution + direct impact
senior:      strong = personal ownership + measurable team/system impact
staff:       strong = cross-team influence, architectural decisions, org-level tradeoffs
em:          strong = organizational leverage, team outcomes, not personal execution

Generate the session summary JSON as specified in your system prompt."""
