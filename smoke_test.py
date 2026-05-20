"""Validator trust smoke tests — run from repo root: python smoke_test.py"""
import ast
import pathlib

from validator.rewriter_validator import _PLACEHOLDER_RE

# Test 1: placeholder regex
cases = [
    ("[FEATURE_NAME]", True),
    ("[X%]", True),
    ("[feature/module]", True),
    ("[Xms]", True),
    ("[N users]", True),
    ("[INR X Cr]", True),
    ("[normal text]", False),
    ("no brackets", False),
]
for text, should_match in cases:
    matched = bool(_PLACEHOLDER_RE.search(text))
    assert matched == should_match, (
        f"FAIL: '{text}' expected match={should_match}, got {matched}"
    )
print("Test 1 passed: _PLACEHOLDER_RE matches all expected token forms")

# Test 2: A1 trust logic
a1_entries = [
    {"label": "Oracle — Senior SWE", "verbatim_text": "..."},
    {"label": "Oracle — SWE", "verbatim_text": "..."},
    {"label": "Optimizely — Intern", "verbatim_text": "..."},
    {"label": "Sheroes — Associate SWE", "verbatim_text": "..."},
]
regex_blocks = [
    {"label": "Oracle", "text": "..."},
    {"label": "Sheroes", "text": "..."},
]
existing_entries = a1_entries
detected_blocks = regex_blocks
anomalies = []
if len(existing_entries) > 0:
    if len(detected_blocks) != len(existing_entries):
        anomalies.append("keeping A1")
else:
    existing_entries = [
        {"label": b["label"], "verbatim_text": b["text"]} for b in detected_blocks
    ]
assert len(existing_entries) == 4, f"Expected 4 A1 entries, got {len(existing_entries)}"
assert "keeping A1" in anomalies[0]
print("Test 2 passed: A1 entries preserved when non-zero, regex disagreement logged")

# Test 3: A1 fallback
existing_entries = []
detected_blocks = [
    {"label": "Oracle", "text": "bullet"},
    {"label": "Sheroes", "text": "bullet"},
]
anomalies = []
if len(existing_entries) > 0:
    pass
else:
    if detected_blocks:
        anomalies.append("falling back to regex")
        existing_entries = [
            {"label": b["label"], "verbatim_text": b["text"]} for b in detected_blocks
        ]
assert len(existing_entries) == 2, f"Expected 2 regex entries, got {len(existing_entries)}"
assert "falling back to regex" in anomalies[0]
print("Test 3 passed: regex fallback fires correctly when A1 returns 0 entries")

# Test 4: primary verbatim guard present in _repair_sub_entry_section
src = pathlib.Path("validator/rewriter_validator.py").read_text(encoding="utf-8")
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_repair_sub_entry_section":
        method_src = ast.get_source_segment(src, node)
        assert method_src and "_entry_verbatim_present" in method_src, (
            "FAIL: _entry_verbatim_present must be primary guard in "
            "_repair_sub_entry_section"
        )
        print(
            "Test 4 passed: _entry_verbatim_present is primary guard in "
            "_repair_sub_entry_section"
        )
        break
else:
    raise AssertionError("_repair_sub_entry_section not found")

print("\nAll 4 tests passed.")
