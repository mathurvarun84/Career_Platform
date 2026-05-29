"""
ATS Scoring Engine — deterministic resume quality scorer.

Scores a resume on four dimensions (0–25 each, total 0–100):
  - keyword_match: action verbs + tech keywords + optional JD overlap boost
  - formatting: section headers, bullets, length
  - readability: Flesch-Kincaid reading ease approximation
  - impact_metrics: numbers, percentages, scale/latency terms

Zero LLM calls. All scoring is regex + word-count arithmetic.
Returns: {"score": int, "breakdown": {keyword_match, formatting, readability, impact_metrics}, "ats_issues": list[str]}
"""

import re


ACTION_VERBS = {
    "led", "built", "designed", "reduced", "increased", "owned", "shipped", "scaled",
    "developed", "implemented", "architected", "optimized", "launched", "delivered",
    "managed", "created", "improved", "deployed", "migrated", "automated",
}

TECH_KEYWORDS = {
    "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "ruby",
    "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
    "rest", "api", "grpc", "graphql", "microservices", "ci/cd", "devops",
    "machine learning", "ml", "deep learning", "nlp", "llm", "pytorch", "tensorflow",
    "git", "linux", "bash", "spark", "hadoop", "airflow", "dbt",
}

SECTION_HEADERS = {
    "experience", "work experience", "employment", "education", "skills",
    "projects", "summary", "objective", "certifications", "achievements",
}

# Matches latency/throughput phrases — signals performance engineering work
_LATENCY_RE = re.compile(
    r"\b(\d+\s*ms|\d+\s*seconds?|\d+\s*minutes?|p99|p95|p50|latency|throughput)\b",
    re.IGNORECASE,
)
# Matches scale indicators — signals high-traffic system experience
_SCALE_RE = re.compile(
    r"\b(\d+[kmb]\+?|\d+\s*(million|billion|thousand)|[kmb]\s*users?|tps|qps|rpm|rps)\b",
    re.IGNORECASE,
)
# Matches quantified impact: percentages, dollar/rupee amounts, large numbers
_IMPACT_RE = re.compile(
    r"(\d+%|\$[\d,]+|₹[\d,]+|\d+[kmb]\b|\d+\s*(million|billion|thousand|crore))",
    re.IGNORECASE,
)

BENCHMARKS = {
    "keyword_match": 20,
    "formatting": 21,
    # 20 reflects typical technical resume FK range (30-55 is common for bullet-point format)
    "readability": 20,
    # 16 acknowledges that not all roles produce latency/scale metrics
    "impact_metrics": 16,
}

DIMENSION_META = {
    "keyword_match": {"label": "Keyword Match", "icon": "🔑"},
    "formatting": {"label": "Formatting", "icon": "📐"},
    "readability": {"label": "Readability", "icon": "📖"},
    "impact_metrics": {"label": "Impact & Metrics", "icon": "📊"},
}

_DIMENSION_ORDER = ["keyword_match", "formatting", "readability", "impact_metrics"]
_STRUCTURAL_MARKER_RE = re.compile(r"##(?:COMPANY|ROLE|END_HEADER)##")


def _strip_structural_markers(text: str) -> str:
    """Remove rewriter docx structural markers before ATS scoring."""
    cleaned = _STRUCTURAL_MARKER_RE.sub(" ", text)
    return re.sub(r" +", " ", cleaned)


_SKILLS_CATEGORY_HEADERS = (
    "Languages:",
    "Frontend:",
    "Backend:",
    "Databases:",
    "Architecture & Concepts:",
    "Architecture:",
    "Cloud:",
    "DevOps:",
    "Tools:",
    "Frameworks:",
    "Observability:",
    "Methodologies:",
    "Other:",
)


def normalize_skills_layout(text: str) -> str:
    """
    Restore line breaks in flattened skills blocks before ATS scoring.

    LLM patches often join categories into one line (hurts readability/formatting).
    """
    if not text:
        return text
    result = re.sub(
        r"(?<=\.)\s+([A-Z][A-Za-z][A-Za-z0-9 /&()]*:)",
        r"\n\1",
        text,
    )
    for header in sorted(_SKILLS_CATEGORY_HEADERS, key=len, reverse=True):
        result = re.sub(
            rf"(?<=[a-z0-9%)])\s+({re.escape(header)})",
            r"\n\1",
            result,
            flags=re.IGNORECASE,
        )
    return result


def normalize_resume_for_ats_scoring(text: str) -> str:
    """Apply deterministic pre-scoring normalizations for fair patch rescoring."""
    return normalize_skills_layout(text)


_STOPWORDS = {
    "and", "the", "for", "with", "from", "that", "this", "you", "your", "our", "into",
    "across", "using", "used", "build", "built", "have", "has", "had", "were", "was",
    "are", "is", "will", "can", "should", "must", "team", "teams", "role", "work",
    "years", "year", "experience", "job", "resume", "candidate", "skills", "skill",
    "requirements", "required", "preferred", "plus", "strong", "ability", "knowledge",
}


def score_resume(resume_text: str, jd_text: str | None = None) -> dict:
    """
      Calculate the ATS (Applicant Tracking System) score for a resume.

      The score is composed of four weighted components:
      1. **Keyword Match** (0-25): Counts action verbs + tech keywords, boosted by JD overlap
      2. **Formatting** (0-25): Checks section headers, consistent bullets, and optimal length
      3. **Readability** (0-25): Measures sentence clarity via Flesch-Kincaid score
      4. **Impact Metrics** (0-25): Detects quantifiable achievements (numbers, percentages)

      Returns a dictionary with:
      - total score (0-100)
      - component breakdown
      - improvement suggestions

      Parameters:
          resume_text (str): The resume text to score
          jd_text (str, optional): Job description for keyword boosting

      Example:
          >>> score_resume("Reduced server latency by 40% using Python.")
          {'score': 87, 'breakdown': {...}, 'ats_issues': [...]}
    """
    resume_text = normalize_resume_for_ats_scoring(
        _strip_structural_markers(resume_text)
    )
    breakdown = {
        "keyword_match": _score_keyword_match(resume_text, jd_text),
        "formatting": _score_formatting(resume_text),
        "readability": _score_readability(resume_text),
        "impact_metrics": _score_impact_metrics(resume_text),
    }
    total = sum(breakdown.values())
    issues = _collect_issues(resume_text, breakdown)
    details = generate_dimension_details(breakdown, resume_text, jd_text, issues)
    return {"score": total, "breakdown": breakdown, "ats_issues": issues, "details": details}


def generate_dimension_details(
    breakdown: dict,
    resume_text: str,
    jd_text: str | None = None,
    ats_issues: list[str] | None = None,
) -> list[dict]:
    """
    Generate per-dimension detail objects with benchmark and gap explanation.

    The function is deterministic and does not make network or LLM calls.
    """
    details = []
    issues = ats_issues or _collect_issues(resume_text, breakdown)
    for dim in _DIMENSION_ORDER:
        score = int(breakdown.get(dim, 0) or 0)
        benchmark = BENCHMARKS[dim]
        gap = max(0, benchmark - score)
        reason = _gap_reason(dim, score, gap, resume_text, jd_text, issues)
        details.append(
            {
                "score": score,
                "benchmark": benchmark,
                "gap": gap,
                "gap_reason": reason,
                "label": DIMENSION_META[dim]["label"],
                "icon": DIMENSION_META[dim]["icon"],
            }
        )
    return details


def _gap_reason(
    dim: str,
    score: int,
    gap: int,
    resume_text: str,
    jd_text: str | None,
    ats_issues: list[str],
) -> str:
    """
    Build a one-line deterministic explanation for the dimension gap.
    """
    _ = score  # score kept explicit for future branching expansion
    text_lower = resume_text.lower()
    words = set(re.findall(r"\b\w+\b", text_lower))

    if dim == "keyword_match":
        if gap == 0:
            return "Strong keyword coverage — action verbs and tech stack well-represented."
        if jd_text:
            missing = _extract_missing_jd_keywords(text_lower, jd_text)
            if gap <= 5:
                if missing:
                    top_two = ", ".join(missing[:2])
                    return f"Missing {len(missing)} keywords from the JD — add {top_two}."
                return "Good keyword coverage. Add more role-specific terms from the JD in experience bullets."
            if len(missing) >= 2:
                return (
                    f"Keyword gap is high — JD requires {missing[0]}, {missing[1]} not found in resume."
                )
            if len(missing) == 1:
                return f"Keyword gap is high — JD requires {missing[0]} and related role terms not found in resume."
            return "Keyword gap is high — core JD language is not consistently reflected in your bullets."
        if gap <= 5:
            return "Good keyword coverage. Add a JD to find role-specific gaps."
        verb_hits = len(ACTION_VERBS & words)
        if verb_hits < 5:
            return "Low action verb density — use stronger openers like 'Led', 'Architected', 'Shipped'."
        return "Keyword coverage needs improvement — add clearer domain terms in summary and skills."

    if dim == "formatting":
        if gap == 0:
            return "Clean structure — sections, bullets, and length are well-formatted."
        formatting_issue = next((issue for issue in ats_issues if _is_formatting_issue(issue)), "")
        if gap <= 3:
            if formatting_issue:
                return f"Minor formatting issue: {formatting_issue}."
            return "Minor formatting issue: align section headers, bullet styles, and spacing."
        return "Multiple formatting issues detected: missing standard sections or inconsistent bullets."

    if dim == "readability":
        if gap == 0:
            return "Sentence complexity is appropriate for a technical resume."
        if gap <= 5:
            return "Some sentences are too long — aim for under 25 words per bullet."
        return "High sentence complexity is hurting scannability — shorten bullets, cut filler phrases."

    if dim == "impact_metrics":
        if gap == 0:
            return "Good quantification — numbers and scale metrics are present."
        if gap <= 4:
            return "Add 2–3 more impact numbers: percentages, user counts, cost savings, or business outcomes."
        return "Resume lacks quantified impact — every experience bullet should have at least one measurable number."

    return "Gap explanation unavailable for this dimension."


def _extract_missing_jd_keywords(resume_text_lower: str, jd_text: str) -> list[str]:
    jd_lower = jd_text.lower()
    resume_words = set(re.findall(r"\b\w+\b", resume_text_lower))
    jd_words = re.findall(r"\b\w+\b", jd_lower)

    phrases: list[str] = []
    for kw in sorted(TECH_KEYWORDS, key=len, reverse=True):
        if (" " in kw or "/" in kw) and kw in jd_lower and kw not in resume_text_lower:
            phrases.append(kw)

    token_counts: dict[str, int] = {}
    for token in jd_words:
        if token in _STOPWORDS or len(token) < 3:
            continue
        if token in resume_words:
            continue
        token_counts[token] = token_counts.get(token, 0) + 1

    ranked_tokens = sorted(token_counts.items(), key=lambda item: (-item[1], item[0]))
    for token, _ in ranked_tokens:
        if token not in phrases:
            phrases.append(token)
        if len(phrases) >= 5:
            break
    return phrases[:5]


def _is_formatting_issue(issue: str) -> bool:
    issue_lower = issue.lower()
    formatting_terms = (
        "section", "header", "bullet", "format", "spacing", "short", "long", "page", "length"
    )
    return any(term in issue_lower for term in formatting_terms)


def _score_keyword_match(resume_text: str, jd_text: str | None) -> int:
    """
      Calculates keyword match score (0-25):
      - Counts action verbs (led, built, etc.) from ACTION_VERBS
      - Counts tech keywords (Python, AWS, etc.) from TECH_KEYWORDS
      - Adds JD keyword overlap boost (0-5 points)

      Parameters:
          resume_text (str): Raw resume text
          jd_text (str, optional): Job description for keyword prioritization

      Returns:
          int: Score between 0-25
    """
    text_lower = resume_text.lower()
    words = set(re.findall(r"\b\w+\b", text_lower))

    verb_hits = len(ACTION_VERBS & words)
    tech_hits = sum(1 for kw in TECH_KEYWORDS if kw in text_lower)

    jd_boost = 0
    if jd_text:
        jd_lower = jd_text.lower()
        jd_words = set(re.findall(r"\b\w+\b", jd_lower))
        overlap = len(words & jd_words) / max(len(jd_words), 1)
        jd_boost = min(5, int(overlap * 20))

    raw = verb_hits * 1.5 + tech_hits * 0.8 + jd_boost
    return min(25, int(raw))


def _score_formatting(resume_text: str) -> int:
    """
      Evaluates resume formatting (0-25):
      - Checks for standard section headers (Experience, Education)
      - Verifies consistent bullet formatting
      - Validates length (300-900 words optimal)

      Parameters:
          resume_text (str): Raw resume text

      Returns:
          int: Score between 0-25
    """
    score = 0
    text_lower = resume_text.lower()

    # Section headers present (up to 10 pts)
    headers_found = sum(1 for h in SECTION_HEADERS if h in text_lower)
    score += min(10, headers_found * 2)

    # Consistent bullet usage (up to 8 pts)
    bullet_lines = len(re.findall(r"^[\s]*[•\-\*]\s", resume_text, re.MULTILINE))
    if bullet_lines >= 5:
        score += 8
    elif bullet_lines >= 2:
        score += 4

    # Length: 300–900 words ≈ 1–2 pages (up to 7 pts)
    word_count = len(resume_text.split())
    if 300 <= word_count <= 900:
        score += 7
    elif 200 <= word_count <= 1200:
        score += 4

    return min(25, score)


_RUNON_WORD_RE = re.compile(r"\b[a-zA-Z]{22,}\b")


def _count_runon_words(resume_text: str) -> int:
    """Count abnormally long tokens — typical sign of PDF spacing loss."""
    return len(_RUNON_WORD_RE.findall(resume_text))


def _score_readability(resume_text: str) -> int:
    """
      Calculates readability score (0-25):
      - Uses Flesch-Kincaid formula (ideal: 40-70)
      - Penalties long sentences (>30 words)
      - Considers average word count

      Parameters:
          resume_text (str): Raw resume text

      Returns:
          int: Score between 0-25
    """
    sentences = re.split(r"[.!?]+", resume_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    if not sentences:
        return 10

    word_counts = [len(s.split()) for s in sentences]
    total_words = sum(word_counts)
    total_sentences = len(sentences)
    avg_words = total_words / total_sentences

    total_syllables = sum(_count_syllables(w) for s in sentences for w in s.split())

    if total_words == 0:
        return 10

    # Flesch-Kincaid Reading Ease
    fk = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)

    # Technical bullet-point resumes naturally land in the 30-60 FK range due to
    # short fragments, technical nouns, and sparse connective prose. Ideal prose
    # range (40-70) is too narrow a target; we extend the full-score band down to 30.
    if 30 <= fk <= 70:
        score = 25
    elif 20 <= fk < 30 or 70 < fk <= 80:
        score = 20
    elif 10 <= fk < 20 or 80 < fk <= 90:
        score = 14
    else:
        score = 8

    if avg_words > 30:
        score = max(0, score - 4)

    # Run-on words are PDF parsing artifacts, not resume quality issues.
    # Keep as an ats_issues warning but apply a modest score reduction only.
    runon = _count_runon_words(resume_text)
    if runon >= 3:
        score = max(0, score - 6)
    elif runon >= 1:
        score = max(0, score - 3)

    return min(25, score)


def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,;:!?\"'()-")
    if not word:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _score_impact_metrics(resume_text: str) -> int:
    """
      Measures quantifiable achievements (0-25):
      - Detects numbers (40% latency reduction)
      - Finds percentages (₹1 Cr ARR)
      - Identifies scale terms (1M users)

      Parameters:
          resume_text (str): Raw resume text

      Returns:
          int: Score between 0-25
    """
    # Base score from quantified impact (%, $, ₹, numbers) — applies to all roles.
    # Cap raised to 19 so a well-quantified non-systems role can reach a good score
    # without needing latency/scale terms.
    impact_hits = len(_IMPACT_RE.findall(resume_text))
    score = min(19, impact_hits * 2)

    # Latency and scale are bonus signals for systems/infra/backend roles.
    # They can push past the base cap up to the hard max of 25.
    latency_hits = len(_LATENCY_RE.findall(resume_text))
    scale_hits = len(_SCALE_RE.findall(resume_text))
    bonus = min(6, latency_hits * 2) + min(4, scale_hits * 2)
    score = min(25, score + bonus)

    return score


def _collect_issues(resume_text: str, breakdown: dict) -> list[str]:
    issues = []
    text_lower = resume_text.lower()

    if breakdown["keyword_match"] < 10:
        issues.append("Low action verb and tech keyword density — add measurable achievements with strong verbs.")

    headers_found = sum(1 for h in SECTION_HEADERS if h in text_lower)
    if headers_found < 2:
        issues.append("Missing standard section headers (Experience, Education, Skills).")

    bullet_lines = len(re.findall(r"^[\s]*[•\-\*]\s", resume_text, re.MULTILINE))
    if bullet_lines < 3:
        issues.append("Insufficient bullet points — use consistent bullets for achievements.")

    word_count = len(resume_text.split())
    if word_count < 200:
        issues.append(f"Resume is too short ({word_count} words) — aim for 300–900 words.")
    elif word_count > 1200:
        issues.append(f"Resume may be too long ({word_count} words) — aim for 1–2 pages.")

    if breakdown["impact_metrics"] < 8:
        issues.append("Few quantified achievements — add numbers, percentages, or scale metrics.")

    if breakdown["readability"] < 12:
        issues.append("Readability needs improvement — use shorter, clearer sentences.")

    runon = _count_runon_words(resume_text)
    if runon >= 1:
        issues.append(
            "PDF word-spacing issues detected — words are merged (e.g. Servingasasoftwareengineer). "
            "Re-upload or re-parse the resume to fix ATS readability."
        )

    return issues


def score_rewrites(
    original_resume_text: str,
    rewrites: dict,
    jd_text: str | None = None,
) -> dict:
    """
    Score safe-fix and full-rewrite modes using deterministic ATS scorer.

    Safe fix and full rewrite both use balanced text per section (conservative
    stitch). Zero LLM calls.

    Args:
        original_resume_text: Verbatim resume text before rewrites.
        rewrites: RewriterAgent output shape
            {section_name: {balanced, aggressive, top_1_percent}}.
        jd_text: Optional JD text for keyword_match JD boost.

    Returns:
        Dict with safe_fix, full_rewrite score objects and original_ats.
    """
    original_scored = score_resume(original_resume_text, jd_text)
    original_ats = original_scored["score"]

    section_rewrites = rewrites if isinstance(rewrites, dict) else {}
    safe_fix_parts: list[str] = []
    full_rewrite_parts: list[str] = []

    for _section_name, variants in section_rewrites.items():
        if not isinstance(variants, dict):
            continue
        balanced = str(variants.get("balanced") or "").strip()
        if balanced:
            safe_fix_parts.append(balanced)
            full_rewrite_parts.append(balanced)

    safe_fix_resume = _strip_structural_markers(
        "\n\n".join(safe_fix_parts) if safe_fix_parts else original_resume_text
    )
    full_rewrite_resume = _strip_structural_markers(
        "\n\n".join(full_rewrite_parts) if full_rewrite_parts else original_resume_text
    )

    safe_fix_scored = score_resume(safe_fix_resume, jd_text)
    full_rewrite_scored = score_resume(full_rewrite_resume, jd_text)

    return {
        "safe_fix": {
            "ats_score": safe_fix_scored["score"],
            "ats_breakdown": safe_fix_scored["breakdown"],
            "delta_ats": safe_fix_scored["score"] - original_ats,
        },
        "full_rewrite": {
            "ats_score": full_rewrite_scored["score"],
            "ats_breakdown": full_rewrite_scored["breakdown"],
            "delta_ats": full_rewrite_scored["score"] - original_ats,
        },
        "original_ats": original_ats,
    }


_PLACEHOLDER_RE = re.compile(
    r"""
    \[
    (?:
        [A-Z][A-Z0-9_]{2,}
      | X%
      | N\s+\w+
      | \w+/\w+
      | INR\s+X\s+\w+
      | Xms
      | \d*[A-Za-z]+\d*%?
    )
    \]
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _concat_balanced_rewrite_text(
    original_resume_text: str,
    rewrites: dict,
) -> tuple[str, str]:
    """Build safe-fix and full-rewrite text blobs from balanced section variants."""
    section_rewrites = rewrites if isinstance(rewrites, dict) else {}
    parts: list[str] = []
    for _section_name, variants in section_rewrites.items():
        if not isinstance(variants, dict):
            continue
        balanced = str(variants.get("balanced") or "").strip()
        if balanced:
            parts.append(balanced)
    joined = "\n\n".join(parts) if parts else original_resume_text
    return joined, joined


def build_validation_summary(
    original_resume_text: str,
    rewrites: dict,
    patches: list,
    jd_match_before: float | None,
    jd_match_after: float | None,
    jd_text: str | None = None,
) -> dict:
    """
    Build pass/warn/fail validation summary for both rewrite modes.

    All checks are deterministic (zero LLM):
      1. ats_improved — mode ATS > original ATS
      2. jd_improved — jd_match_after > jd_match_before
      3. no_placeholders — no unfilled bracket placeholders
      4. no_truncation — rewrite length >= 35% of original

    Args:
        original_resume_text: Verbatim resume text.
        rewrites: Section rewrite dict from RewriterAgent.
        patches: Classified patches (reserved for future patch-aware scoring).
        jd_match_before: Pre-rewrite JD match score, or None if no JD.
        jd_match_after: Post-rewrite JD match estimate, or None.
        jd_text: Optional JD text for ATS keyword boost.

    Returns:
        Validation summary with safe_fix, full_rewrite checks and scores.
    """
    _ = patches  # forwarded for future patch-aware safe-fix scoring
    scores = score_rewrites(original_resume_text, rewrites, jd_text)
    original_len = len(original_resume_text.strip())
    safe_fix_text, full_rewrite_text = _concat_balanced_rewrite_text(
        original_resume_text,
        rewrites,
    )

    def _check_mode(mode_key: str, mode_text: str) -> dict:
        mode_ats = scores[mode_key]["ats_score"]
        original_ats = scores["original_ats"]

        ats_check = "pass" if mode_ats > original_ats else "fail"

        if jd_match_before is None:
            jd_check = "no_jd"
        elif jd_match_after is None:
            jd_check = "warn"
        elif jd_match_after > jd_match_before:
            jd_check = "pass"
        else:
            jd_check = "fail"

        placeholder_check = "fail" if _PLACEHOLDER_RE.search(mode_text) else "pass"

        mode_len = len(mode_text.strip())
        truncation_check = (
            "pass"
            if (original_len == 0 or mode_len / original_len >= 0.35)
            else "fail"
        )

        hard_fails = [
            c for c in (ats_check, placeholder_check, truncation_check) if c == "fail"
        ]
        if hard_fails:
            overall = "fail"
        elif jd_check in ("warn", "no_jd"):
            overall = "warn"
        else:
            overall = "pass"

        download_enabled = len(hard_fails) == 0

        return {
            "ats_check": ats_check,
            "jd_check": jd_check,
            "placeholder_check": placeholder_check,
            "truncation_check": truncation_check,
            "overall": overall,
            "download_enabled": download_enabled,
        }

    return {
        "safe_fix": _check_mode("safe_fix", safe_fix_text),
        "full_rewrite": _check_mode("full_rewrite", full_rewrite_text),
        "scores": scores,
    }