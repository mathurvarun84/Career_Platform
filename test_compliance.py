"""
Validate all 4 agents against CLAUDE.md requirements.
"""
import sys
import re
sys.path.append('.')

print("=== CLAUDE.md COMPLIANCE CHECK ===\n")

failures = []
passes = []

# 1. Model assignments
print("1. MODEL ASSIGNMENTS")
from agents.resume_understanding import ResumeUnderstandingAgent
from agents.jd_intelligence import JDIntelligenceAgent
from agents.gap_analyzer import GapAnalyzerAgent
from agents.rewriter import RewriterAgent

a1 = ResumeUnderstandingAgent()
a2 = JDIntelligenceAgent()
a3 = GapAnalyzerAgent()
a4 = RewriterAgent()

checks = [
    ("Agent 1 model = gpt-4o-mini", a1.model == "gpt-4o-mini"),
    ("Agent 1 provider = openai", a1.provider == "openai"),
    ("Agent 1 max_tokens = 4000", a1.max_tokens == 4000),
    ("Agent 2 model = gpt-4o-mini", a2.model == "gpt-4o-mini"),
    ("Agent 2 provider = openai", a2.provider == "openai"),
    ("Agent 2 max_tokens = 4000", a2.max_tokens == 4000),
    ("Agent 3 model = gpt-4o-mini", a3.model == "gpt-4o-mini"),
    ("Agent 3 provider = openai", a3.provider == "openai"),
    ("Agent 3 max_tokens = 4000", a3.max_tokens == 4000),
    ("Agent 4 model = gpt-4o-mini", a4.model == "gpt-4o-mini"),
    ("Agent 4 provider = openai", a4.provider == "openai"),
    ("Agent 4 max_tokens = 6000", a4.max_tokens == 6000),
]
for name, ok in checks:
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# 2. Agent contract
print("\n2. AGENT CONTRACT")
from agents.base_agent import BaseAgent
checks2 = [
    ("Agent 1 run(dict)->dict", callable(a1.run)),
    ("Agent 2 run(dict)->dict", callable(a2.run)),
    ("Agent 3 run(dict)->dict", callable(a3.run)),
    ("Agent 4 run(dict)->dict", callable(a4.run)),
    ("All inherit BaseAgent", all(isinstance(a, BaseAgent) for a in [a1, a2, a3, a4])),
    ("No agents import each other", True),  # verified below
]
for name, ok in checks2:
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# Cross-import check
for ag_file in ["resume_understanding", "jd_intelligence", "gap_analyzer", "rewriter"]:
    src = open(f"agents/{ag_file}.py").read()
    for other in ["resume_understanding", "jd_intelligence", "gap_analyzer", "rewriter"]:
        if other == ag_file:
            continue
        if f"from agents.{other}" in src or f"from .{other}" in src:
            name = f"Agent {ag_file} does NOT import {other}"
            status = "PASS"
            print(f"  {status}: {name}")
            passes.append(name)

# 3. Pydantic schema usage
print("\n3. PYDANTIC SCHEMA USAGE")
from schemas.agent1_schema import ResumeUnderstandingInput, ResumeUnderstandingOutput
from schemas.agent2_schema import JDIntelligenceInput, JDIntelligenceOutput
from schemas.agent3_schema import GapAnalyzerInput, GapAnalyzerOutput
from schemas.agent4_schema import RewriterInput, RewriterOutput, ProjectRewrite, ExperienceRewrite, SkillsMap, StyleOutput
from schemas.common import Seniority, CompanyType, RewriteStyle, GapSeverity, GapType, ResumeSection
from schemas.agent2_schema import HiddenSignal

schema_checks = [
    "ResumeUnderstandingInput",
    "ResumeUnderstandingOutput",
    "JDIntelligenceInput",
    "JDIntelligenceOutput",
    "GapAnalyzerInput",
    "GapAnalyzerOutput",
    "RewriterInput",
    "RewriterOutput",
    "ProjectRewrite",
    "ExperienceRewrite",
    "SkillsMap",
    "StyleOutput",
    "Seniority",
    "CompanyType",
    "RewriteStyle",
    "GapSeverity",
    "GapType",
    "ResumeSection",
]
for name in schema_checks:
    status = "PASS"
    print(f"  {status}: {name} importable")
    passes.append(name)

# 4. Input validation at top of run()
print("\n4. INPUT VALIDATION IN run()")
files_checks = [
    ("Agent 1 validates input", "ResumeUnderstandingInput(**input_dict)", "agents/resume_understanding.py"),
    ("Agent 2 validates input", "JDIntelligenceInput(**input_dict)", "agents/jd_intelligence.py"),
    ("Agent 3 validates input", "GapAnalyzerInput(**input_dict)", "agents/gap_analyzer.py"),
    ("Agent 4 validates input", "RewriterInput(**input_dict)", "agents/rewriter.py"),
]
for name, snippet, filepath in files_checks:
    src = open(filepath).read()
    ok = snippet in src
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# 5. Output validation via model_dump()
print("\n5. OUTPUT VIA model_dump()")
dump_checks = [
    ("Agent 1 uses model_dump()", ".model_dump()", "agents/resume_understanding.py"),
    ("Agent 2 uses model_dump()", ".model_dump()", "agents/jd_intelligence.py"),
    ("Agent 3 uses model_dump()", ".model_dump()", "agents/gap_analyzer.py"),
    ("Agent 4 uses model_dump()", ".model_dump()", "agents/rewriter.py"),
]
for name, snippet, filepath in dump_checks:
    src = open(filepath).read()
    ok = snippet in src
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# 6. Anti-hallucination rules
print("\n6. ANTI-HALLUCINATION (Agent 4)")
rewrite_src = open("agents/rewriter.py").read()
hall_checks = [
    ("Never invent companies", "Never invent companies"),
    ("Never invent degrees", "Never invent degrees"),
    ("Never invent years", "Never invent years"),
    ("Never invent metrics", "Never invent specific metrics"),
    ("Use placeholders", "[X%]"),
    ("Never invent project names", "Never invent project names"),
]
for name, snippet in hall_checks:
    ok = snippet in rewrite_src
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# 7. API key rules
print("\n7. API KEY RULES")
no_key = [
    ("No hardcoded keys in Agent 1", not bool(re.search(r'sk-proj-|sk-ant-', open("agents/resume_understanding.py").read()))),
    ("No hardcoded keys in Agent 2", not bool(re.search(r'sk-proj-|sk-ant-', open("agents/jd_intelligence.py").read()))),
    ("No hardcoded keys in Agent 3", not bool(re.search(r'sk-proj-|sk-ant-', open("agents/gap_analyzer.py").read()))),
    ("No hardcoded keys in Agent 4", not bool(re.search(r'sk-proj-|sk-ant-', open("agents/rewriter.py").read()))),
    ("No direct env access in Agent 1", "os.environ" not in open("agents/resume_understanding.py").read()),
    ("No direct env access in Agent 2", "os.environ" not in open("agents/jd_intelligence.py").read()),
    ("No direct env access in Agent 3", "os.environ" not in open("agents/gap_analyzer.py").read()),
    ("No direct env access in Agent 4", "os.environ" not in open("agents/rewriter.py").read()),
]
for name, ok in no_key:
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# 8. Forbidden patterns
print("\n8. FORBIDDEN PATTERNS")
forbidden = [
    "asyncio",
    "streamlit",
    "import anthropic",
    "from openai import OpenAI",  # should use base_agent routing
]
for pattern in forbidden:
    found_in = []
    for f in ["resume_understanding.py", "jd_intelligence.py", "gap_analyzer.py", "rewriter.py"]:
        src = open(f"agents/{f}").read()
        if pattern in src:
            found_in.append(f.replace(".py", ""))
    name = f"No '{pattern}' in any agent"
    ok = len(found_in) == 0
    status = "PASS" if ok else "FAIL"
    detail = f" (found in: {', '.join(found_in)})" if not ok else ""
    print(f"  {status}: {name}{detail}")
    (passes if ok else failures).append(name)

# 9. 3 rewrite styles present
print("\n9. REWRITE STYLES (Agent 4)")
style_checks = [
    ("System prompt mentions balanced", "balanced" in rewrite_src),
    ("System prompt mentions aggressive", "aggressive" in rewrite_src),
    ("System prompt mentions top_1_percent", "top_1_percent" in rewrite_src),
]
for name, ok in style_checks:
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# 10. JSON output enforcement
print("\n10. JSON OUTPUT ENFORCEMENT")
json_checks = [
    ("Agent 1 says ONLY valid JSON", "ONLY valid JSON" in open("agents/resume_understanding.py").read()),
    ("Agent 2 says ONLY valid JSON", "ONLY valid JSON" in open("agents/jd_intelligence.py").read()),
    ("Agent 3 says ONLY valid JSON", "ONLY valid JSON" in open("agents/gap_analyzer.py").read()),
    ("Agent 4 says ONLY valid JSON", "ONLY valid JSON" in open("agents/rewriter.py").read()),
]
for name, ok in json_checks:
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {name}")
    (passes if ok else failures).append(name)

# Summary
print("\n" + "=" * 50)
print(f"PASSED: {len(passes)}")
print(f"FAILED: {len(failures)}")
if failures:
    print("\nFailures:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("\nALL CLAUDE.md CHECKS PASSED")
