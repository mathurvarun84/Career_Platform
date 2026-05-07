"""Career positioning engine — NO LLM. Pure Python + static JSON."""
import json, os
from typing import Dict, Any

def _load_bands() -> dict:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ctc_bands.json")
    with open(path) as f:
        return json.load(f)

def get_company_tier_from_score(ats: int, jd: int) -> str:
    bands = _load_bands()
    composite = ats if jd == 0 else int(0.4 * ats + 0.6 * jd)
    thresholds = sorted([(int(k), v) for k, v in bands["score_to_tier"].items()], reverse=True)
    for threshold, tier in thresholds:
        if composite >= threshold:
            return tier
    return "service"


def _percentile_label(percentile: int) -> str:
    if percentile >= 90:
        return "Top 10%"
    if percentile >= 75:
        return "Top 25%"
    if percentile >= 50:
        return "Above Average"
    if percentile >= 25:
        return "Below Average"
    return "Bottom 25%"


def _rank_rationale(
    rank_label: str,
    ats_breakdown: dict | None,
    ats_issues: list[str] | None,
    expected_signals: list[dict] | None,
    ats_score: int,
    jd_match_score: int,
) -> str:
    breakdown = ats_breakdown or {}
    issues = ats_issues or []
    signals = expected_signals or []

    subscore_reasons = {
        "keyword_match": "ATS keyword density is low",
        "formatting": "resume structure and formatting are below benchmark",
        "readability": "readability is holding the resume back",
        "impact_metrics": "quantified impact metrics are thin",
    }

    reasons = [
        reason
        for key, reason in subscore_reasons.items()
        if breakdown.get(key, 25) < 12
    ]
    if not reasons:
        reasons = [
            reason
            for key, reason in subscore_reasons.items()
            if breakdown.get(key, 25) < 18
        ]

    reason_blob = " ".join(reasons).lower()
    for issue in issues:
        normalized = issue.strip().rstrip(".")
        if normalized and normalized.lower() not in reason_blob:
            reasons.append(normalized[0].lower() + normalized[1:])
            reason_blob = " ".join(reasons).lower()
        if len(reasons) >= 3:
            break

    missing_signals = [
        s.get("signal", "").strip()
        for s in signals
        if not s.get("present") and s.get("signal")
    ]
    for signal in missing_signals:
        reasons.append(f"missing seniority signal: {signal}")
        if len(reasons) >= 3:
            break

    if not reasons:
        reasons = ["the composite score is below this seniority benchmark"]

    composite = ats_score if jd_match_score == 0 else int(0.4 * ats_score + 0.6 * jd_match_score)
    fix_count = max(1, min(3, len(reasons)))
    improved_label = _percentile_label(min(99, composite + (fix_count * 8)))
    fix_word = "fix" if fix_count == 1 else "fixes"
    reason_text = ", ".join(reasons[:2])
    if len(reasons) > 2:
        reason_text = f"{reason_text}, and {reasons[2]}"

    return (
        f"{rank_label} because {reason_text}. "
        f"{fix_count} targeted {fix_word} can move you toward {improved_label}."
    )


def get_positioning_statement(seniority: str, ats_score: int,
                               jd_match_score: int = 0,
                               sections_changed: int = 0,
                               ats_breakdown: dict | None = None,
                               ats_issues: list[str] | None = None,
                               expected_signals: list[dict] | None = None,
                               percentile: dict | None = None) -> Dict[str, Any]:
    bands = _load_bands()
    sen = seniority.lower() if seniority else "mid"
    if sen not in bands["ctc_bands"]: sen = "mid"
    tier_order = ["service","startup_early","product_mid","product_unicorn","faang"]
    current_tier = get_company_tier_from_score(ats_score, jd_match_score)
    ctc = bands["ctc_bands"][sen]
    tiers = bands["company_tiers"]
    curr_ctc = ctc.get(current_tier, ctc["service"])
    curr_idx = tier_order.index(current_tier) if current_tier in tier_order else 0
    next_tier = tier_order[min(curr_idx + 1, len(tier_order) - 1)]
    next_ctc = ctc.get(next_tier, ctc["product_unicorn"])
    composite = ats_score if jd_match_score == 0 else int(0.4*ats_score + 0.6*jd_match_score)
    rank_label = (percentile or {}).get("label") or _percentile_label(composite)
    rank_rationale = _rank_rationale(
        rank_label=rank_label,
        ats_breakdown=ats_breakdown,
        ats_issues=ats_issues,
        expected_signals=expected_signals,
        ats_score=ats_score,
        jd_match_score=jd_match_score,
    )
    score_gap = tiers[next_tier]["min_score"] - composite
    changes_needed = max(1, min(5, round(score_gap / 8))) if score_gap > 0 else 0
    curr_ex = ", ".join(tiers[current_tier]["examples"][:3])
    next_ex = ", ".join(tiers[next_tier]["examples"][:3])
    dm = max(0, next_ctc["min"] - curr_ctc["min"])
    dx = max(0, next_ctc["max"] - curr_ctc["max"])
    if current_tier == "faang":
        pos_line = "Your resume is competitive for FAANG-level roles."
        cta_line = "You are already at the top tier. Focus on interview prep."
        delta_line = f"Market range: ₹{curr_ctc['min']}–{curr_ctc['max']} LPA"
    else:
        pos_line = (f"Your resume is competitive for "
                    f"{tiers[current_tier]['label']} roles ({curr_ex}).")
        cta_line = (f"{changes_needed} change{'s' if changes_needed!=1 else ''} needed "
                    f"to reach {tiers[next_tier]['label']} ({next_ex}).")
        delta_line = (f"After fixes: ₹{next_ctc['min']}–{next_ctc['max']} LPA "
                      f"(currently ₹{curr_ctc['min']}–{curr_ctc['max']} LPA). "
                      f"Potential gain: ₹{dm}–{dx} LPA/year.")
    return {
        "current_tier": current_tier,
        "current_tier_label": tiers[current_tier]["label"],
        "current_tier_examples": curr_ex,
        "next_tier": next_tier,
        "next_tier_label": tiers[next_tier]["label"],
        "next_tier_examples": next_ex,
        "changes_needed": changes_needed,
        "current_ctc_min": curr_ctc["min"], "current_ctc_max": curr_ctc["max"],
        "potential_ctc_min": next_ctc["min"], "potential_ctc_max": next_ctc["max"],
        "ctc_delta_min": dm, "ctc_delta_max": dx,
        "positioning_line": pos_line,
        "delta_line": delta_line,
        "cta_line": cta_line,
        "rank_rationale": rank_rationale,
    }
