"""
PatchEngine — deterministic patch applicator with rollback and audit trail.

No LLM calls. No external dependencies beyond what already exists.
Applies ResumePatch operations to resume text as surgical string replacements.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone

from backend.schemas.common import ResumePatch, PatchOp, PatchRisk

# ── Ordering: structural before content, content before insertion ──
PATCH_APPLY_ORDER: list[PatchOp] = [
    PatchOp.REORDER_BULLETS,
    PatchOp.SHORTEN_BULLET,
    PatchOp.REPLACE_TEXT,
    PatchOp.INSERT_KEYWORD,
    PatchOp.ADD_METRIC,
    PatchOp.ADD_BULLET,
]

METRIC_PATTERN = re.compile(
    r'(?:\$\d+[MKB]?|\d+\.?\d*\s*(?:%|x|X|\bk\b|\bK\b|Cr\b|L\b|ms\b))'
)

HALLUCINATION_RISK_OPS = {PatchOp.ADD_METRIC, PatchOp.ADD_BULLET}

_BULLET_SEP = re.compile(r'\s*[•\-\*]\s+')
_MULTI_NL = re.compile(r'\n{2,}')

_MIN_OVERLAP_TOKENS = 2
_MIN_SENTENCE_WORDS = 3
_EXPANSION_RATIO = 2.0


# ── Bullet / sentence helpers (module-level) ──────────────────────────────

def _normalise_bullets(text: str) -> str:
    """Collapse bullet separators and newline runs to canonical form."""
    collapsed = _BULLET_SEP.sub('\n', text)
    return _MULTI_NL.sub('\n', collapsed).strip()


def _normalise_bullets_spans(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Build normalised text; each norm char maps to [start, end) in original."""
    pieces: list[str] = []
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        m = _BULLET_SEP.match(text, i)
        if m:
            if not pieces or pieces[-1] != '\n':
                pieces.append('\n')
                spans.append((m.start(), m.end()))
            i = m.end()
            continue
        pieces.append(text[i])
        spans.append((i, i + 1))
        i += 1

    collapsed_chars: list[str] = []
    collapsed_spans: list[tuple[int, int]] = []
    j = 0
    norm = ''.join(pieces)
    while j < len(norm):
        if norm[j] == '\n':
            k = j
            while k < len(norm) and norm[k] == '\n':
                k += 1
            collapsed_chars.append('\n')
            collapsed_spans.append((spans[j][0], spans[k - 1][1]))
            j = k
        else:
            collapsed_chars.append(norm[j])
            collapsed_spans.append(spans[j])
            j += 1

    norm_str = ''.join(collapsed_chars)
    lead = len(norm_str) - len(norm_str.lstrip())
    trail = len(norm_str) - len(norm_str.rstrip())
    if lead:
        norm_str = norm_str[lead:]
        collapsed_spans = collapsed_spans[lead:]
    if trail:
        norm_str = norm_str[:-trail] if trail else norm_str
        collapsed_spans = collapsed_spans[:-trail] if trail else collapsed_spans
    return norm_str, collapsed_spans


def _find_normalised_span(needle: str, haystack: str) -> tuple[int, int] | None:
    """Locate needle in haystack via normalised view; return original (start, end)."""
    norm_needle = _normalise_bullets(needle)
    if not norm_needle:
        return None
    norm_hay, char_spans = _normalise_bullets_spans(haystack)
    pos = norm_hay.find(norm_needle)
    if pos == -1:
        return None
    end_pos = pos + len(norm_needle)
    if end_pos > len(char_spans):
        return None
    return (char_spans[pos][0], char_spans[end_pos - 1][1])


def _count_normalised_occurrences(needle: str, haystack: str) -> int:
    """Count non-overlapping normalised occurrences of needle in haystack."""
    norm_needle = _normalise_bullets(needle)
    if not norm_needle:
        return 0
    norm_hay = _normalise_bullets(haystack)
    count = 0
    pos = 0
    while True:
        idx = norm_hay.find(norm_needle, pos)
        if idx == -1:
            break
        count += 1
        pos = idx + 1
    return count


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentence-like fragments for overlap checks."""
    return [p.strip() for p in re.split(r'[.•\n]+', text) if p.strip()]


def _tokenise_sentence(sentence: str) -> set[str]:
    """Lowercase alphanumeric tokens (length > 1) from a sentence."""
    return {
        w for w in re.findall(r'[a-zA-Z0-9]+', sentence.lower())
        if len(w) > 1
    }


def _has_hallucinated_sentences(original: str, replacement: str) -> bool:
    """True if replacement adds sentences with insufficient token overlap."""
    orig_sents = _split_into_sentences(original)
    repl_sents = _split_into_sentences(replacement)
    if not repl_sents:
        return False
    orig_token_sets = [_tokenise_sentence(s) for s in orig_sents]
    for repl in repl_sents:
        repl_tokens = _tokenise_sentence(repl)
        if len(repl_tokens) < _MIN_SENTENCE_WORDS:
            continue
        best_overlap = 0
        for orig_tokens in orig_token_sets:
            overlap = len(repl_tokens & orig_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
        if best_overlap < _MIN_OVERLAP_TOKENS:
            return True
    return False


# ── PatchClassifier (deterministic, zero LLM) ─────────────────────────────

def classify_patch(patch: ResumePatch) -> ResumePatch:
    """Classify patch as SAFE or NEEDS_CONFIRMATION. Never calls LLM."""
    if patch.op in HALLUCINATION_RISK_OPS:
        patch.risk = PatchRisk.NEEDS_CONFIRMATION
        patch.hallucination_risk = True
        return patch

    if patch.op == PatchOp.REPLACE_TEXT:
        orig_metrics = set(METRIC_PATTERN.findall(patch.original_text))
        repl_metrics = set(METRIC_PATTERN.findall(patch.replacement_text))
        if repl_metrics - orig_metrics:
            patch.risk = PatchRisk.NEEDS_CONFIRMATION
            patch.hallucination_risk = True
            return patch
        if _has_hallucinated_sentences(
            patch.original_text, patch.replacement_text
        ):
            patch.risk = PatchRisk.NEEDS_CONFIRMATION
            patch.hallucination_risk = True
            return patch
        orig_words = len(patch.original_text.split())
        repl_words = len(patch.replacement_text.split())
        if orig_words > 0 and repl_words > orig_words * _EXPANSION_RATIO:
            patch.risk = PatchRisk.NEEDS_CONFIRMATION
            return patch

    patch.risk = PatchRisk.SAFE
    return patch


# ── PatchEngine ────────────────────────────────────────────────────────────

class PatchEngine:
    """
    Applies patches as surgical text operations. All ops reversible.
    Thread-safety: one engine per request session (not shared).
    """

    def __init__(self, resume_text: str, resume_sections: dict | None = None):
        self._original_text = resume_text
        self.current_text = resume_text
        self._applied_log: dict[str, str] = {}
        self._applied_replacements: dict[str, str] = {}
        self._applied_spans: dict[str, tuple[int, int]] = {}
        self._modified_ranges: list[tuple[int, int]] = []
        self._resume_sections = resume_sections or {}

    def apply_with_result(self, patch: ResumePatch) -> dict:
        """
        Apply one patch and verify replacement landed in current_text.

        Returns:
            applied: patch committed on engine
            found_in_doc: replacement_text present in current_text
            rejection_reason: fix_rationale when not applied
        """
        if patch.status != "pending":
            return {
                "applied": False,
                "found_in_doc": False,
                "rejection_reason": patch.fix_rationale or "patch not pending",
            }
        ok = self.apply(patch)
        if not ok:
            return {
                "applied": False,
                "found_in_doc": False,
                "rejection_reason": patch.fix_rationale,
            }
        repl = patch.replacement_text or ""
        found_in_doc = (repl in self.current_text) if repl else True
        if not found_in_doc:
            self.rollback(patch.patch_id)
            patch.status = "rejected"
            patch.fix_rationale += " [SKIP: replacement not verified in document]"
            return {
                "applied": False,
                "found_in_doc": False,
                "rejection_reason": patch.fix_rationale,
            }
        return {
            "applied": True,
            "found_in_doc": True,
            "rejection_reason": None,
        }

    def apply(self, patch: ResumePatch) -> bool:
        """Apply one patch. Returns True if applied, False if skipped/rejected."""
        if patch.status != "pending":
            return False
        dispatch = {
            PatchOp.REPLACE_TEXT:    self._apply_replace,
            PatchOp.INSERT_KEYWORD:  self._apply_insert_keyword,
            PatchOp.SHORTEN_BULLET:  self._apply_shorten,
            PatchOp.REORDER_BULLETS: self._apply_reorder,
            PatchOp.ADD_METRIC:      self._apply_replace,
            PatchOp.ADD_BULLET:      self._apply_replace,
        }
        handler = dispatch.get(patch.op)
        return handler(patch) if handler else False

    def apply_batch(self, patches: list[ResumePatch]) -> list[str]:
        """Apply patches in canonical order. Returns list of applied patch_ids."""
        ordered = sorted(
            patches,
            key=lambda p: PATCH_APPLY_ORDER.index(p.op)
            if p.op in PATCH_APPLY_ORDER else 99
        )
        applied = []
        for p in ordered:
            if p.status != "pending":
                continue
            if self.apply(p):
                applied.append(p.patch_id)
                self._reanchor_remaining(p, ordered)
        return applied

    def rollback(self, patch_id: str) -> bool:
        """Revert a single patch. Restores text to pre-patch snapshot."""
        if patch_id not in self._applied_log:
            return False
        self.current_text = self._applied_log.pop(patch_id)
        self._applied_replacements.pop(patch_id, None)
        self._applied_spans.pop(patch_id, None)
        self._rebuild_ranges()
        return True

    def rollback_all(self) -> None:
        """Full reset to original."""
        self.current_text = self._original_text
        self._applied_log.clear()
        self._applied_replacements.clear()
        self._applied_spans.clear()
        self._modified_ranges.clear()

    def get_current_text(self) -> str:
        return self.current_text

    @staticmethod
    def dedup(patches: list[ResumePatch]) -> list[ResumePatch]:
        """Remove patches targeting the same original_text. Keep first."""
        seen: dict[str, str] = {}
        out = []
        for p in patches:
            key = p.original_text.strip() if p.original_text else p.patch_id
            if key in seen:
                logging.warning(
                    "Duplicate patch dropped: %s (same text as %s)",
                    p.patch_id, seen[key]
                )
                p.status = "rejected"
                p.fix_rationale += " [SKIP: duplicate target]"
            else:
                seen[key] = p.patch_id
                out.append(p)
        return out

    def _reanchor_remaining(
        self, applied_patch: ResumePatch, remaining: list[ResumePatch]
    ) -> None:
        """Update pending patches whose original_text still references replaced text."""
        old = applied_patch.original_text
        new = applied_patch.replacement_text
        if not old:
            return
        for p in remaining:
            if p.status != "pending" or p.patch_id == applied_patch.patch_id:
                continue
            if old in p.original_text:
                p.original_text = p.original_text.replace(old, new)

    def _resolve_replace_span(self, patch: ResumePatch) -> tuple[int, int] | None:
        """Resolve (start, end) in current_text for patch.original_text."""
        text = patch.original_text
        if not text:
            return None

        if text in self.current_text:
            count = self.current_text.count(text)
            if count == 1:
                start = self.current_text.index(text)
                return (start, start + len(text))
            if patch.section:
                start = self._find_occurrence_in_section(
                    text, patch.section, patch.sub_entry_label
                )
                if start >= 0:
                    return (start, start + len(text))
            return None

        norm_count = _count_normalised_occurrences(text, self.current_text)
        if norm_count == 0:
            return None
        if norm_count == 1:
            return _find_normalised_span(text, self.current_text)
        if patch.section:
            return self._find_normalised_span_in_section(
                text, patch.section, patch.sub_entry_label
            )
        return None

    def _apply_replace(self, patch: ResumePatch) -> bool:
        text = patch.original_text
        span = self._resolve_replace_span(patch)
        if span is None:
            patch.status = "rejected"
            if text and (
                text in self.current_text
                or _count_normalised_occurrences(text, self.current_text) > 1
            ):
                patch.fix_rationale += (
                    " [SKIP: ambiguous text; no section context to disambiguate]"
                )
            else:
                patch.fix_rationale += (
                    " [SKIP: original_text not found — text may have changed]"
                )
            return False

        start, end = span

        if (patch.section or "").lower() == "skills" and patch.replacement_text:
            from engine.ats_scorer import normalize_skills_layout

            patch.replacement_text = normalize_skills_layout(patch.replacement_text)

        for ms, me in self._modified_ranges:
            if not (end <= ms or start >= me):
                patch.status = "rejected"
                patch.fix_rationale += " [SKIP: overlaps already-patched region]"
                return False

        snapshot = self.current_text
        self.current_text = (
            self.current_text[:start] +
            patch.replacement_text +
            self.current_text[end:]
        )
        self._applied_log[patch.patch_id] = snapshot
        self._applied_replacements[patch.patch_id] = patch.replacement_text
        new_end = start + len(patch.replacement_text)
        self._applied_spans[patch.patch_id] = (start, new_end)
        self._modified_ranges.append((start, new_end))
        patch.status = "applied"
        patch.applied_at = datetime.now(timezone.utc).isoformat()
        return True

    def _apply_insert_keyword(self, patch: ResumePatch) -> bool:
        anchor = patch.insert_after_text
        keyword = patch.keyword
        if not anchor or not keyword:
            patch.status = "rejected"
            patch.fix_rationale += " [SKIP: missing anchor or keyword]"
            return False
        if anchor not in self.current_text:
            patch.status = "rejected"
            patch.fix_rationale += " [SKIP: anchor text not found]"
            return False
        replacement = anchor + f", {keyword}"
        patch.original_text = anchor
        patch.replacement_text = replacement
        return self._apply_replace(patch)

    def _apply_shorten(self, patch: ResumePatch) -> bool:
        return self._apply_replace(patch)

    def _apply_reorder(self, patch: ResumePatch) -> bool:
        keywords = [k.lower() for k in patch.priority_keywords]
        if not keywords or not patch.original_text:
            patch.status = "rejected"
            return False

        block = patch.original_text
        if block not in self.current_text:
            patch.status = "rejected"
            patch.fix_rationale += " [SKIP: bullet block not found]"
            return False

        lines = block.splitlines()
        bullets = [l for l in lines if l.strip().startswith(('•', '-', '*'))]
        non_bullets = [l for l in lines if not l.strip().startswith(('•', '-', '*'))]

        priority, rest = [], []
        for b in bullets:
            if any(kw in b.lower() for kw in keywords):
                priority.append(b)
            else:
                rest.append(b)

        reordered = '\n'.join(non_bullets + priority + rest)
        patch.replacement_text = reordered
        return self._apply_replace(patch)

    def _find_occurrence_in_section(
        self, text: str, section: str, sub_entry_label: str = ""
    ) -> int:
        if section not in self._resume_sections:
            return -1

        section_data = self._resume_sections[section]
        if isinstance(section_data, dict):
            section_text = section_data.get("full_text", "")
        else:
            section_text = str(section_data)

        if not section_text or text not in section_text:
            return -1

        if section_text not in self.current_text:
            return -1

        section_start = self.current_text.index(section_text)
        text_in_section = section_text.index(text)
        return section_start + text_in_section

    def _find_normalised_span_in_section(
        self, text: str, section: str, sub_entry_label: str = ""
    ) -> tuple[int, int] | None:
        if section not in self._resume_sections:
            return None

        section_data = self._resume_sections[section]
        if isinstance(section_data, dict):
            section_text = section_data.get("full_text", "")
        else:
            section_text = str(section_data)

        if not section_text:
            return None
        if section_text not in self.current_text:
            return None

        section_start = self.current_text.index(section_text)
        local = _find_normalised_span(text, section_text)
        if local is None:
            return None
        ls, le = local
        return (section_start + ls, section_start + le)

    def _rebuild_ranges(self) -> None:
        """Recalculate _modified_ranges from stored per-patch spans."""
        self._modified_ranges.clear()
        for patch_id in self._applied_log:
            span = self._applied_spans.get(patch_id)
            if span:
                self._modified_ranges.append(span)
                continue
            replacement = self._applied_replacements.get(patch_id, "")
            if not replacement:
                continue
            start = self.current_text.find(replacement)
            if start == -1:
                logging.warning(
                    "PatchEngine: could not rebuild range for %s", patch_id
                )
                continue
            end = start + len(replacement)
            self._applied_spans[patch_id] = (start, end)
            self._modified_ranges.append((start, end))


def rescore(
    engine: PatchEngine,
    jd_text: str | None = None,
    baseline_score: int | None = None,
) -> dict:
    """Rescore using existing deterministic ats_scorer. Zero LLM calls."""
    from engine.ats_scorer import normalize_resume_for_ats_scoring, score_resume

    normalized_text = normalize_resume_for_ats_scoring(engine.get_current_text())
    result = score_resume(normalized_text, jd_text)
    raw_score = int(result["score"])
    display_score = raw_score
    if baseline_score is not None:
        display_score = max(int(baseline_score), raw_score)
    return {
        "score": display_score,
        "raw_score": raw_score,
        "breakdown": result.get("breakdown", {}),
        "ats_issues": result.get("ats_issues", []),
    }
