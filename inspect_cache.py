import sys, json
sys.stdout.reconfigure(encoding='utf-8')

with open('backend/.job_cache/8a7e3271-bbde-44be-8401-822fe7d35274.json') as f:
    job = json.load(f)

result = job.get('result', {})
resume = result.get('resume', {})
rs = resume.get('resume_sections', {})

print("=== NAME ===")
print(repr(resume.get('name', '')))

exp = rs.get('experience', {})
subs = exp.get('sub_entries', []) if isinstance(exp, dict) else []
print(f"\n=== EXPERIENCE SUB_ENTRIES ({len(subs)}) ===")
for i, s in enumerate(subs, 1):
    lbl = s.get('label', '')[:70]
    vbt = s.get('verbatim_text', '')[:120].replace('\n', ' | ')
    print(f"{i:2}. label='{lbl}'")
    print(f"    verbatim='{vbt}'")

rewrites = job.get('rewrites') or result.get('rewrites') or {}
if isinstance(rewrites, dict) and 'rewrites' in rewrites:
    rewrites = rewrites['rewrites']

exp_rw = rewrites.get('experience', {}) if isinstance(rewrites, dict) else {}
balanced = exp_rw.get('balanced', '') if isinstance(exp_rw, dict) else ''
print("\n=== EXPERIENCE REWRITE balanced (first 2000 chars) ===")
print(balanced[:2000])

print("\n=== SKILLS rewrite balanced (first 300 chars) ===")
sk = rewrites.get('skills', {}) if isinstance(rewrites, dict) else {}
print((sk.get('balanced', '') if isinstance(sk, dict) else '')[:300])

print("\n=== STRUCTURED NAME/TITLE/CONTACT ===")
structured = result.get('resume') or {}
print('name:', repr(structured.get('name', '')))
print('title:', repr(structured.get('title', '')))
print('contact:', repr(structured.get('contact', '')))
