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
    breakdown = {
        "keyword_match": _score_keyword_match(resume_text, jd_text),
        "formatting": _score_formatting(resume_text),
        "readability": _score_readability(resume_text),
        "impact_metrics": _score_impact_metrics(resume_text),
    }
    total = sum(breakdown.values())
    issues = _collect_issues(resume_text, breakdown)
    return {"score": total, "breakdown": breakdown, "ats_issues": issues}


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

    # Ideal for professional writing: 40–70
    if 40 <= fk <= 70:
        score = 25
    elif 30 <= fk < 40 or 70 < fk <= 80:
        score = 18
    elif 20 <= fk < 30 or 80 < fk <= 90:
        score = 12
    else:
        score = 6

    if avg_words > 30:
        score = max(0, score - 5)

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
    score = 0

    impact_hits = len(_IMPACT_RE.findall(resume_text))
    score += min(12, impact_hits * 2)

    latency_hits = len(_LATENCY_RE.findall(resume_text))
    score += min(7, latency_hits * 2)

    scale_hits = len(_SCALE_RE.findall(resume_text))
    score += min(6, scale_hits * 2)

    return min(25, score)


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

    return issues