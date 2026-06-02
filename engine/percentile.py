import json
import os

_benchmarks_cache: dict | None = None

_BENCHMARKS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "benchmarks.json")

VALID_SENIORITY = {"junior", "mid", "senior", "staff", "em", "senior_em", "director"}


def load_benchmarks() -> dict:
    """
    Loads percentile benchmarks from data/benchmarks.json.

    Returns:
         dict: Structure:
          {
              "junior": {"avg": 48, "p25": 38, "p50": 48, "p75": 60, "p90": 72},
              "mid": {"avg": 55, "p25": 45, "p50": 55, "p75": 67, "p90": 78},
              "senior": {"avg": 63, "p25": 52, "p50": 63, "p75": 74, "p90": 83},
              "staff": {"avg": 70, "p25": 60, "p50": 70, "p75": 80, "p90": 88}
          }
    """
    global _benchmarks_cache
    if _benchmarks_cache is None:
        path = os.path.normpath(_BENCHMARKS_PATH)
        with open(path, "r", encoding="utf-8") as f:
            _benchmarks_cache = json.load(f)
    return _benchmarks_cache


def _coerce_seniority(seniority: object) -> str:
    """Normalize any seniority representation to a plain lowercase value string.

    Handles Python 3.11+ str-enum repr: str(Seniority.SENIOR) → 'Seniority.SENIOR'
    must become 'senior'. Works for enum objects, repr strings, and plain values.
    """
    if hasattr(seniority, "value"):
        return str(seniority.value).lower()
    s = str(seniority).lower()
    # "seniority.senior" or "seniority.staff" → strip class prefix
    if "." in s:
        s = s.rsplit(".", 1)[-1]
    return s


def get_percentile(composite_score: float, seniority: object) -> dict:
    """
    Converts ATS score to percentile rank using benchmarks.

    Parameters:
        composite_score (float): ATS/composite score (0-100)
        seniority: Seniority level — accepts enum object, repr string
            ('Seniority.SENIOR'), or plain value ('senior').

    Returns:
        dict: percentile, label, benchmark_avg, delta

    Example:
        >>> get_percentile(85, 'senior')
        {'percentile': ..., 'label': ..., ...}
    """
    seniority_norm = _coerce_seniority(seniority)
    if seniority_norm not in VALID_SENIORITY:
        raise ValueError(f"Invalid seniority '{seniority}'. Must be one of {sorted(VALID_SENIORITY)}.")

    benchmarks = load_benchmarks()
    band = benchmarks[seniority_norm]

    percentile = _interpolate_percentile(composite_score, band)
    label = _percentile_label(percentile)

    return {
        "percentile": percentile,
        "label": label,
        "benchmark_avg": band["avg"],
        "delta": round(composite_score - band["avg"], 2),
    }


def _interpolate_percentile(score: float, band: dict) -> int:
    # Anchor points: (score, percentile)
    anchors = [
        (0, 0),
        (band["p25"], 25),
        (band["p50"], 50),
        (band["p75"], 75),
        (band["p90"], 90),
        (100, 99),
    ]

    for i in range(len(anchors) - 1):
        lo_score, lo_pct = anchors[i]
        hi_score, hi_pct = anchors[i + 1]
        if lo_score <= score <= hi_score:
            if hi_score == lo_score:
                return lo_pct
            ratio = (score - lo_score) / (hi_score - lo_score)
            return round(lo_pct + ratio * (hi_pct - lo_pct))

    return 99 if score >= 100 else 0


def _percentile_label(percentile: int) -> str:
    if percentile >= 90:
        return "Top 10%"
    elif percentile >= 75:
        return "Top 25%"
    elif percentile >= 50:
        return "Above Average"
    elif percentile >= 25:
        return "Below Average"
    else:
        return "Bottom 25%"