"""One-shot acceptance test for the three rewriter pipeline fixes."""
import sys
sys.path.insert(0, '.')

from validator.resume_understanding_validator import (
    _detect_sub_entries,
    _detect_experience_by_date_ranges,
    _normalize_spaced_heading,
    _extract_all_sections_from_text,
)

# ── Fix 2: spaced heading normalisation ──────────────────────────────────────
assert _normalize_spaced_heading('C E R T I F I C A T I O N S') == 'CERTIFICATIONS'
assert _normalize_spaced_heading('E X P E R I E N C E') == 'EXPERIENCE'
assert _normalize_spaced_heading('Engineering Manager | Flipkart') == 'Engineering Manager | Flipkart'
print('OK  _normalize_spaced_heading')

# ── Fix 2: backward-walk stop conditions — 7 experience blocks ───────────────
EXPERIENCE_BLOCK = """Engineering Manager | Flipkart — Bengaluru, KA
Sep 2020 – Present
• Led a team of 20 engineers
• Drove 3x growth in platform reliability

Head of Engineering | SmartVizX — Bengaluru, KA
Dec 2019 – Sep 2020
• Built AR/VR product from scratch
• Hired 15-person engineering team

Engineering Manager | Apttus (via Altran) — Bengaluru, KA
Nov 2018 – Dec 2019
• Managed CPQ module delivery
• Reduced release cycle by 40%

Engineering Manager | ClearTax (via Altran) — Bengaluru, KA
Dec 2016 – Oct 2018
• Led tax-filing platform feature dev

Senior Consultant | British Telecom — Bengaluru, KA
Sep 2013 – Dec 2016
• Delivered OSS/BSS integrations

Tech Consultant | Microsoft — Bengaluru, KA
Sep 2011 – Sep 2013
• Built SharePoint solutions

Lead Software Engineer | Mindtree — Bengaluru, KA
Jul 2007 – Oct 2011
• Delivered multiple enterprise projects
"""

blocks = _detect_experience_by_date_ranges(EXPERIENCE_BLOCK)
labels = [b['label'] for b in blocks]
print(f"  date-range fallback found {len(blocks)} blocks: {labels}")
assert len(blocks) == 7, f"Expected 7 experience blocks, got {len(blocks)}: {labels}"
print('OK  _detect_experience_by_date_ranges (7 blocks)')

# ── Fix 1: _detect_sub_entries always runs fallback ──────────────────────────
entries = _detect_sub_entries(EXPERIENCE_BLOCK, 'experience')
entry_labels = [e['label'] for e in entries]
print(f"  _detect_sub_entries found {len(entries)} entries: {entry_labels}")
assert len(entries) == 7, f"Expected 7 entries, got {len(entries)}: {entry_labels}"

# Verify chronological order is preserved
expected_companies = [
    'Flipkart', 'SmartVizX', 'Apttus', 'ClearTax',
    'British Telecom', 'Microsoft', 'Mindtree',
]
for expected, actual_label in zip(expected_companies, entry_labels):
    assert expected.lower() in actual_label.lower(), (
        f"Order mismatch: expected company '{expected}' in label '{actual_label}'"
    )
print('OK  _detect_sub_entries (7 entries, correct order)')

# Verify bullets do not bleed across entries: each block's text should
# not contain the specific company name of a *different* entry.
UNIQUE_COMPANY_TOKENS = {
    'Flipkart': 'Flipkart',
    'SmartVizX': 'SmartVizX',
    'Apttus': 'Apttus',
    'ClearTax': 'ClearTax',
    'British Telecom': 'British Telecom',
    'Microsoft': 'Microsoft',
    'Mindtree': 'Mindtree',
}
for entry in entries:
    text = entry['text']
    # Find which company this entry belongs to
    own_company = next(
        (tok for tok in UNIQUE_COMPANY_TOKENS if tok.lower() in entry['label'].lower()),
        None,
    )
    if own_company is None:
        continue
    for company_tok in UNIQUE_COMPANY_TOKENS:
        if company_tok == own_company:
            continue
        # The unique company token of a *different* entry must NOT appear in this block
        assert company_tok not in text, (
            f"Bullet bleed detected: '{company_tok}' found in block for '{own_company}'"
        )
print("OK  No bullet bleed across experience entries")

# ── Fix 3: spaced heading in section extraction ───────────────────────────────
RESUME_STUB = """Varun Mathur
varun@example.com | +91-9999999999

EXPERIENCE
Engineering Manager | Flipkart — Bengaluru, KA
Sep 2020 – Present
• Led a team of 20 engineers

C E R T I F I C A T I O N S
Agentic AI for Engineers and Managers — IISc | Pursuing
Google Project Management Certificate — Google | Oct 2024
Leading High-Performing Teams — University of Queensland | Aug 2020
Blockchain Technology — University at Buffalo | May 2023
Product Management — Udemy | May 2020
"""

sections = _extract_all_sections_from_text(RESUME_STUB)
assert 'certifications' in sections, (
    f"certifications section not found; got sections: {list(sections.keys())}"
)
cert_text = sections['certifications']
cert_lines = [ln.strip() for ln in cert_text.splitlines() if ln.strip()]
print(f"  cert section lines ({len(cert_lines)}): {cert_lines}")
assert len(cert_lines) == 5, f"Expected 5 cert lines, got {len(cert_lines)}: {cert_lines}"
print('OK  _extract_all_sections_from_text (spaced heading detected, 5 certs)')

print()
print('=' * 55)
print('ALL ACCEPTANCE ASSERTIONS PASSED')
print('=' * 55)
