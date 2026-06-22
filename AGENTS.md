# RIP V2 — Agents Reference

All AI agents in the system. Read this before touching any file in `backend/agents/`.

---

## Agent Roster

| ID | Name | File | Provider | Model | max_tokens |
|---|---|---|---|---|---|
| A1 | Resume Understanding | resume_understanding.py | OpenAI | gpt-4o-mini | 7000 |
| A2 | JD Intelligence | jd_intelligence.py | OpenAI | gpt-4.1-mini | 4000 |
| A3 | Gap Analyzer | gap_analyzer.py | OpenAI | gpt-4.1 | 4000 |
| A4 | Rewriter (legacy) | rewriter.py | OpenAI | gpt-4.1-mini | 6000 |
| A5 | Recruiter Sim | recruiter_sim.py | Anthropic | claude-haiku-4-5-20251001 | 6000 |
| A5b | Coaching | coaching_agent.py | Anthropic | claude-haiku-4-5-20251001 | 4000 |
| A6 | Interview Agent | interview_agent.py | Anthropic | claude-sonnet-4.6 | 8000 |
| — | JD Fetcher | jd_fetcher.py | Anthropic | claude-haiku-4-5-20251001 | — |

**Cost:** ~$0.074/full analysis | ~$0.06/A6 interview session

Key rules:
- **OpenAI keys** → A1, A2, A3, A4
- **Anthropic keys** → A5, A5b, A6, JDFetcher
- Model strings live only in agent `__init__` / `super().__init__`. Never hardcode elsewhere.
- Both key types come from `.env` only. Zero hardcoded credentials anywhere.

---

## Per-Agent Purpose & I/O

### A1 — Resume Understanding
**File:** `backend/agents/resume_understanding.py`
**Purpose:** Parse and structure raw resume text into typed sections.

```
Input:  raw resume text (string)
Output: structured sections, skills, experience, titles, seniority signals
Used by: Orchestrator → output feeds A3
```

### A2 — JD Intelligence
**File:** `backend/agents/jd_intelligence.py`
**Purpose:** Extract structured signals from a job description.

```
Input:  raw job description text (string)
Output: required skills, preferred skills, seniority level, company type signals
Used by: Orchestrator → output feeds A3
Trigger: only runs if user provides a JD; skipped otherwise
```

### A3 — Gap Analyzer
**File:** `backend/agents/gap_analyzer.py`
**Purpose:** Compare resume (A1) against JD (A2) to produce actionable gaps.

```
Input:  A1 output + A2 output
Output: SectionGap[] — each with gap_type, coaching_question, sub_changes[], auto_apply
Notes:  longest prompt in the system; has few-shot examples — NEVER shrink the few-shot block
        (removing examples degrades gap severity calibration silently)
```

### A4 — Rewriter (legacy)
**File:** `backend/agents/rewriter.py`
**Purpose:** Rewrite resume sections with a given style. Legacy path — surgical patching is now primary.

```
Input:  section text, rewrite_style (balanced | aggressive | top_1_percent)
Output: rewritten section text
Hard constraint: must NEVER invent companies, degrees, institutions, years, metrics, or project names.
                 Missing metrics → placeholders: [X%] [N users] [Xms] [₹X Cr ARR]
```

### A5 — Recruiter Sim
**File:** `backend/agents/recruiter_sim.py`
**Purpose:** Simulate 10 recruiter personas evaluating the resume against the JD.

```
Input:  resume text + JD text + analysis context
Output: SimResult — 10 persona verdicts with hire/pass/maybe + reasoning
Trigger: only if user requests recruiter simulation
```

### A5b — Coaching
**File:** `backend/agents/coaching_agent.py`
**Purpose:** Answer per-gap coaching questions and generate resume bullets from user input.

```
Input:  gap context + coaching_question + user's raw answer
Output: CoachingAnswer — polished resume bullet ready to apply
Trigger: per-gap Q&A flow in the gap tab, after analysis
```

### A6 — Interview Agent
**File:** `backend/agents/interview_agent.py`
**Purpose:** Run a full mock interview session with streaming feedback.

```
Input:  resume context + JD + question_mode (behavioral | scenario | mixed)
Output: questions, per-answer feedback (streamed), session summary, model answers
Trigger: session-based; user-initiated from mock_interview tab
Note:   runs entirely separately — NOT part of the orchestrator
```

### JD Fetcher
**File:** `backend/agents/jd_fetcher.py`
**Purpose:** Search for a real job description given a role + company, then extract structured signals.

```
Input:  role title, company name (optional), location (optional)
Output: FetchJDResponse — raw JD text + extracted structured fields
Uses:   Serper search API → Haiku extraction
Trigger: POST /api/fetch-jd
```

---

## Which Endpoints Trigger Which Agents

```
POST /api/analyze                              → Orchestrator (A1 + A2 parallel, then A3, then A5 if requested)
POST /api/fetch-jd                             → JDFetcher
POST /api/coaching/answer                      → A5b
POST /api/interview/questions                  → A6 (question generation only)
POST /api/interview/session/start              → A6
POST /api/interview/session/{id}/answer        → A6
POST /api/interview/session/{id}/answer/stream → A6 (SSE)
POST /api/interview/session/{id}/summary       → A6
POST /api/interview/session/{id}/model-answer/{q_id} → A6
POST /api/interview/evaluate                   → A6
POST /api/interview/follow-up                  → A6
```

All other endpoints (`/api/patches/*`, `/api/score-journey`, `/api/company-readiness`, `/api/gap-close`, `/api/download/*`) are **deterministic — no LLM**.

---

## Orchestrator Flow + Graceful Degradation

**File:** `orchestrator.py` (repo root)
**Concurrency:** `ThreadPoolExecutor`, no `asyncio`.

```
1. ATS score         — deterministic, always runs
2. A1 + A2 parallel  — if JD provided (max_workers=2)
3. A3 sequential     — needs A1 + A2 output
4. fix_plan_builder  — deterministic, from A3 output
5. A5 parallel       — if requested (recruiter sim)
6. Percentile + career_positioning — deterministic
7. Persistence       — save_analysis → Supabase
8. Return combined dict
```

**Graceful degradation:**
- A1 / A2 / A3 fail → **raise** (fatal — analysis is meaningless without them)
- A4 / A5 / memory fail → **warn + continue** (partial result returned)
- A6 runs entirely separately via `/api/interview/*` — not in orchestrator
- A5b runs entirely separately via `/api/coaching/*` — not in orchestrator

---

## Agent Contract

Every agent subclasses `BaseAgent` (`backend/agents/base_agent.py`).

```python
class MyAgent(BaseAgent):
    def run(self, input_dict: dict) -> dict:
        inp = InputModel(**input_dict)             # validate input
        raw = self._call_llm(SYS_PROMPT, inp.x)   # 1 auto-retry on JSON parse fail
        out = OutputModel(**self._parse_json(raw)) # validate output
        return out.model_dump()
```

- `response_format={"type":"json_object"}` on ALL OpenAI calls.
- 1 auto-retry on JSON parse failure (built into `_call_llm`).
- Functions >40 lines need a Google-style docstring.
- Output token cap: 200 tokens / 900 chars per style fingerprint.
- Agents **never import each other** — Orchestrator is the sole caller.

---

## System Prompt Locations

Each agent's `SYS_PROMPT` constant lives at the **top of its own file**. Read the file before editing.

| Agent | Prompt constant | Notes |
|---|---|---|
| A1 | `resume_understanding.py` — `SYS` | — |
| A2 | `jd_intelligence.py` — `SYS` | — |
| A3 | `gap_analyzer.py` — `SYS` | Longest; has few-shot examples |
| A4 | `rewriter.py` — `SYS` | Contains anti-hallucination guard |
| A5 | `recruiter_sim.py` — `SYS` | — |
| A5b | `coaching_agent.py` — `SYS` | — |
| A6 | `interview_agent.py` — `SYS` | — |

---

## Rules for Modifying System Prompts

1. **Output schema first** — the prompt's JSON schema section must exactly match the agent's Pydantic `OutputModel`. Change one → change the other in the same commit.
2. **Preserve the anti-hallucination guard in A4** — the line "Never invent companies, degrees, institutions, years, metrics, or project names" must remain verbatim. Missing metrics get placeholders: `[X%]` `[N users]` `[Xms]` `[₹X Cr ARR]`.
3. **Never shrink A3's few-shot block** — gap severity calibration depends on examples; removing them degrades output silently.
4. **Test after every prompt edit** — run the agent's test file in `backend/tests/` before committing. Prompt changes are not caught by type checkers.
5. **No prompt changes in a hotfix** — prompt edits must go through a feature branch with eval before merging.

---

## Test Files per Agent

```
A3   → backend/tests/test_gap_analyzer.py       (run after any A3 prompt edit)
CR   → backend/tests/test_company_readiness.py
All  → pytest backend/tests/ -v
```

---

## How to Add a New Agent

1. Create `backend/agents/my_agent.py` subclassing `BaseAgent`.
2. Define `InputModel` and `OutputModel` as Pydantic models in `backend/schemas/my_agent_schema.py`.
3. Write `SYS_PROMPT` at the top of the file. JSON schema in the prompt must match `OutputModel` exactly.
4. Add model string only in `__init__` / `super().__init__`. Never hardcode it elsewhere.
5. Wire into `orchestrator.py` (if part of core flow) or a new router in `backend/api/`.
6. Add mock data to the relevant `frontend/src/mocks/*.ts` file.
7. Update this file: add a row to the Roster table, a per-agent I/O section, and an endpoint entry.
