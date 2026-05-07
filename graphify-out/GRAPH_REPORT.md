# Graph Report - resume_platform  (2026-05-03)

## Corpus Check
- 58 files · ~44,528 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 525 nodes · 1157 edges · 41 communities detected
- Extraction: 54% EXTRACTED · 46% INFERRED · 0% AMBIGUOUS · INFERRED: 536 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]

## God Nodes (most connected - your core abstractions)
1. `SectionText` - 99 edges
2. `BaseAgent` - 60 edges
3. `SubEntry` - 45 edges
4. `RewriterAgent` - 44 edges
5. `Seniority` - 31 edges
6. `Orchestrator` - 25 edges
7. `Validate all 4 agents against CLAUDE.md requirements.` - 25 edges
8. `RewriterInput` - 21 edges
9. `GapAnalyzerAgent` - 20 edges
10. `ResumeUnderstandingAgent` - 20 edges

## Surprising Connections (you probably didn't know these)
- `Input contract for Agent 4.` --uses--> `RewriteStyle`  [INFERRED]
  schemas\agent4_schema.py → schemas\common.py
- `read_upload()` --calls--> `parse_resume()`  [INFERRED]
  app.py → parser.py
- `_export_to_docx()` --calls--> `_build_structured_resume()`  [INFERRED]
  gap_session.py → parser.py
- `_export_to_docx()` --calls--> `_build_docx()`  [INFERRED]
  gap_session.py → engine\resume_builder.py
- `Orchestrator` --uses--> `GapAnalyzerAgent`  [INFERRED]
  orchestrator.py → agents\gap_analyzer.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (75): A single sub-entry within a resume section (one company role, one degree, one ce, One canonical section of a parsed resume with verbatim text and sub-entries., SectionText, SubEntry, Entry point for Agent 4 — rewrites resume sections based on gap analysis., Rewrites a section entry-by-entry using sub_changes from the gap analysis., Rewrites a SINGLE resume sub-entry with a focused LLM call.          Args:, Resolve a section by canonical name, then common aliases. (+67 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (43): ABC, DetailedEvalOutput, GapAnalyzerInput, GapAnalyzerOutput, A single sub-entry within a multi-entry resume section (e.g. one company in Expe, SectionGap, SubLocationChange, BaseAgent (+35 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (41): Pydantic schemas for Agent 1 — Resume Understanding.  Input: raw resume text (pr, Input contract for Agent 1. resume_text must be pre-cleaned by parser.py., A single seniority-level signal and whether it is present in the resume., Structured representation of a parsed resume.      All fields are required — Age, Seniority-aware resume health — does not require a JD., ResumeHealthOutput, ResumeUnderstandingInput, ResumeUnderstandingOutput (+33 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (25): Input contract for Agent 4., RewriterInput, Simple verification test for RewriterAgent improvements.  This test verifies the, Test that __init__ sets the correct model, max_tokens, and provider., Test that the system prompt includes explicit length requirements., Test that the user message includes explicit length instructions., Test that _validate_rewrite_depth method exists and checks content depth., test_content_depth_validation() (+17 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (37): _block_already_present(), _coerce_section_dict(), _coerce_sections(), _dedupe_entries(), _detect_sub_entries(), _empty_section(), _extract_all_sections_from_text(), _labels_overlap() (+29 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (29): ActionableChange, ChangeLocation, OverallAssessment, Pydantic schemas for Agent 3 - Gap Analyzer., ExperienceRewrite, ProjectRewrite, Pydantic schemas for Agent 4 — Rewriter.  Input: original resume text, gap analy, Structured rewrite of a single project entry. (+21 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (33): _add_contact_line(), _build_docx(), build_final_docx(), build_resume_docx(), _detect_title(), _extract_section_content(), _format_paragraph_runs(), _get_structured_value() (+25 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (25): analyze(), download(), gap_close(), GapCloseRequest, _json_event(), FastAPI backend for Resume Intelligence Platform V2., Stream job progress as Server-Sent Events., Return current job status and result for polling fallback. (+17 more)

### Community 8 - "Community 8"
Cohesion: 0.17
Nodes (16): _original(), read_upload(), _build_structured_resume(), _clean_text(), _extract_contact_line(), _extract_section_blocks(), _is_text_meaningful(), _parse_docx() (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.18
Nodes (13): _add_horizontal_rule(), _edit_section(), _export_to_docx(), Interactive gap-closing helper.  This module is purely terminal-interface and do, Open an editor for the user to modify the provided text.      Parameters     ---, Create a comprehensive r-sum- document with gap analysis metadata.      The stru, Insert a horizontal line using an XML border.      The function mutates the last, Run the interactive gap-closing session.      Parameters     ----------     gap_ (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (6): postAnalyze(), handleDrop(), handleFileChange(), handleSubmit(), isAcceptedFile(), validateAndSetFile()

### Community 11 - "Community 11"
Cohesion: 0.21
Nodes (13): _collect_issues(), _count_syllables(), ATS Scoring Engine — deterministic resume quality scorer.  Scores a resume on fo, Evaluates resume formatting (0-25):       - Checks for standard section headers, Calculates readability score (0-25):       - Uses Flesch-Kincaid formula (ideal:, Measures quantifiable achievements (0-25):       - Detects numbers (40% latency, Calculate the ATS (Applicant Tracking System) score for a resume.        The sco, Calculates keyword match score (0-25):       - Counts action verbs (led, built, (+5 more)

### Community 12 - "Community 12"
Cohesion: 0.27
Nodes (10): _ensure_users_dir(), load_session(), Memory layer – per‑user JSON store.  Stores session history, tracks runs, and ke, Return a fresh session scaffold for the given user_id., Load the JSON session file for *user_id*.      Returns an empty scaffold if the, Persist *session_data* for *user_id*.      Args:         user_id: Identifier for, Append *run_result* to the user's session history.      Maintains a maximum of 5, save_session() (+2 more)

### Community 13 - "Community 13"
Cohesion: 0.57
Nodes (6): get_company_tier_from_score(), get_positioning_statement(), _load_bands(), _percentile_label(), _rank_rationale(), Career positioning engine — NO LLM. Pure Python + static JSON.

### Community 14 - "Community 14"
Cohesion: 0.4
Nodes (5): extract_fingerprint(), Style fingerprint extractor.  Analyzes a user's session history and produces a s, Truncate *text* to *limit* characters without cutting in the middle of a word., Return a concise style fingerprint.      The fingerprint is a single sentence of, _truncate()

### Community 15 - "Community 15"
Cohesion: 0.5
Nodes (2): AnalysisProgress(), useSSE()

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Map variant section keys to canonical names.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Set font color on a docx run via w:color element.

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Build a .docx resume with exact style matching.      Args:         structured_re

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Build a complete download-ready resume docx.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Alias for build_final_docx (kept for backward compatibility).

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Extract text content for a section from structured resume dict.      Handles lis

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Read a canonical structured section, accepting common aliases.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Detect internal placeholder strings that should not be rendered.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Build the .docx document with exact color/font styling.      Args:         candi

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Extract title from contact line if present.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Add contact text with blue color for links (containing @ or URL-like tokens).

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Render the summary as one paragraph instead of splitting by PDF lines.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Write flat rewritten experience text with company, role, bullet, and stack style

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Render experience section. Content can be a list of role dicts (verbatim)     or

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Render a text block (summary, skills, education, etc.).     Handles both string

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Returns list of anomaly descriptions for the skills section.     Checks:     1.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Returns anomaly descriptions for summary section.     Checks:     1. full_text n

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Returns (repaired_full_text, anomalies).     Checks:     1. full_text non-empty

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Returns (repaired_section_data, anomalies).     Checks:     1. sub_entries count

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Returns (repaired_section_data, anomalies).     Checks:     1. sub_entries count

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Returns (repaired_section_data, anomalies).     Checks:     1. sub_entries count

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): For sections with no sub_entries structure (awards, publications, extracurricula

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Validates and repairs A1 (ResumeUnderstanding) output for ALL sections.      Run

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Entry point. Runs all section validators and returns repaired A1 output.

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Rewrites a whole section monolithically (fallback when no sub_changes available)

## Knowledge Gaps
- **124 isolated node(s):** `Interactive gap-closing helper.  This module is purely terminal-interface and do`, `Insert a horizontal line using an XML border.      The function mutates the last`, `Run the interactive gap-closing session.      Parameters     ----------     gap_`, `Open an editor for the user to modify the provided text.      Parameters     ---`, `Create a comprehensive r-sum- document with gap analysis metadata.      The stru` (+119 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (4 nodes): `AnalysisProgress()`, `AnalysisProgress.tsx`, `useSSE.ts`, `useSSE()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Map variant section keys to canonical names.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Set font color on a docx run via w:color element.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Build a .docx resume with exact style matching.      Args:         structured_re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Build a complete download-ready resume docx.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Alias for build_final_docx (kept for backward compatibility).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Extract text content for a section from structured resume dict.      Handles lis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Read a canonical structured section, accepting common aliases.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Detect internal placeholder strings that should not be rendered.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Build the .docx document with exact color/font styling.      Args:         candi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Extract title from contact line if present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Add contact text with blue color for links (containing @ or URL-like tokens).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Render the summary as one paragraph instead of splitting by PDF lines.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Write flat rewritten experience text with company, role, bullet, and stack style`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Render experience section. Content can be a list of role dicts (verbatim)     or`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Render a text block (summary, skills, education, etc.).     Handles both string`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Returns list of anomaly descriptions for the skills section.     Checks:     1.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Returns anomaly descriptions for summary section.     Checks:     1. full_text n`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Returns (repaired_full_text, anomalies).     Checks:     1. full_text non-empty`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Returns (repaired_section_data, anomalies).     Checks:     1. sub_entries count`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Returns (repaired_section_data, anomalies).     Checks:     1. sub_entries count`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Returns (repaired_section_data, anomalies).     Checks:     1. sub_entries count`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `For sections with no sub_entries structure (awards, publications, extracurricula`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Validates and repairs A1 (ResumeUnderstanding) output for ALL sections.      Run`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Entry point. Runs all section validators and returns repaired A1 output.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Rewrites a whole section monolithically (fallback when no sub_changes available)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SectionText` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.218) - this node is a cross-community bridge._
- **Why does `BaseAgent` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `RewriterAgent` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 7`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 96 inferred relationships involving `SectionText` (e.g. with `Orchestrator` and `Orchestrator module for Resume Intelligence Platform V2.`) actually correct?**
  _`SectionText` has 96 INFERRED edges - model-reasoned connections that need verification._
- **Are the 52 inferred relationships involving `BaseAgent` (e.g. with `Validate all 4 agents against CLAUDE.md requirements.` and `GapAnalyzerAgent`) actually correct?**
  _`BaseAgent` has 52 INFERRED edges - model-reasoned connections that need verification._
- **Are the 42 inferred relationships involving `SubEntry` (e.g. with `Verify Agent 4 merges gap-analysis sub_changes with ALL sectioner SubEntries.  R` and `Minimal valid SectionRewrite JSON for one entry.`) actually correct?**
  _`SubEntry` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `RewriterAgent` (e.g. with `Orchestrator` and `Orchestrator module for Resume Intelligence Platform V2.`) actually correct?**
  _`RewriterAgent` has 30 INFERRED edges - model-reasoned connections that need verification._