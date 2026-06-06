import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { AnalysisResult } from "../types";
import {
  buildActionableFixesList,
  deriveInfoOnlyScopeLabel,
  extractSubEntryFromRewrite,
  foreignCompanyMentioned,
  getAfterTextForFix,
  getBeforeTextForFix,
  isTabRoleFitLocked,
  parseInfoOnlyCardParts,
  resolvePatchForFix,
  shouldRenderStructuralApplyButton,
} from "./fixesPipeline";
import { gapReasonMatchesFixScope, isNoChangeReplacement, isUsableAfterText } from "./fixesCardLogic";

const fixtureDir = join(dirname(fileURLToPath(import.meta.url)), "../../../tests/fixtures");

const loadFixture = (name: string): AnalysisResult =>
  JSON.parse(readFileSync(join(fixtureDir, name), "utf-8")) as AnalysisResult;

const multiCompanyRewrite = [
  "##COMPANY##Flipkart##ROLE##Engineering Manager##END_HEADER##",
  "• Flipkart bullet one",
  "• Flipkart bullet two",
  "",
  "##COMPANY##Apttus##ROLE##Senior Consultant##END_HEADER##",
  "• Apttus bullet one",
].join("\n");

const apttusExcerpt = extractSubEntryFromRewrite(
  multiCompanyRewrite,
  "Senior Consultant | Apttus — Bengaluru, KA Jan 2019 – Aug 2020"
);
assert.ok(apttusExcerpt.includes("Apttus bullet"), "stops at next ##COMPANY## boundary");
assert.ok(!apttusExcerpt.includes("Flipkart bullet"), "must not bleed prior entry bullets");
assert.ok(!apttusExcerpt.includes("##COMPANY##"), "markers stripped from excerpt");

const plainTextRewrite = [
  "Head of Engineering | Smart Viz X — Bengaluru, KA Dec 2019 – Sep 2020",
  "• Led cross-functional teams for 3D design SaaS platform",
  "• Generated ₹4 Cr in incremental revenue",
  "Engineering Manager | Flipkart — Bengaluru, KA Sep 2020 – Present",
  "• Lead 5 teams with 32 engineers",
].join("\n");

const smartVizPlain = extractSubEntryFromRewrite(
  plainTextRewrite,
  "Head of Engineering | Smart Viz X — Bengaluru, KA"
);
assert.ok(smartVizPlain.includes("Smart Viz") || smartVizPlain.includes("3D design"));
assert.ok(!smartVizPlain.includes("Lead 5 teams with 32 engineers"), "Title-case header stops at Flipkart");

assert.equal(
  gapReasonMatchesFixScope({
    gap_reason: "Flipkart EM bullets 3-5 lack explicit team scope details",
    sub_label: "Head of Engineering | Smart Viz X — Bengaluru, KA",
    entry_id: "smart_viz_director_2018",
  }),
  false
);
assert.equal(
  gapReasonMatchesFixScope({
    gap_reason: "Flipkart EM bullets 3-5 lack explicit team scope details",
    sub_label: "Engineering Manager | Flipkart — Bengaluru, KA",
    entry_id: "flipkart_engineering_manager_2020",
  }),
  true
);

// entry_id-only fix (no sub_label) must not return Flipkart content for non-Flipkart entries
{
  const stubResult = {
    ats: { score: 60, breakdown: { keyword_match: 15, formatting: 15, readability: 15, impact_metrics: 15 }, details: [], ats_issues: [] },
    resume: { experience_years: 8, seniority: "senior", tech_stack: [], domains: [], has_metrics: false, has_summary: false, sections_present: [], resume_sections: { experience: { header: "experience", full_text: "", sub_entries: [] } } },
    gap: { resume_only_mode: false, jd_match_score_before: 50, jd_match_score_after: null, section_gaps: [], missing_keywords: [], priority_fixes: [] },
    rewrites: { experience: { balanced: multiCompanyRewrite, aggressive: "", top_1_percent: "" } },
    patches: [],
  } as unknown as import("../types").AnalysisResult;

  const apttusFixNoLabel = {
    section: "experience",
    entry_id: "apttus_senior_consultant_2019",
    gap_reason: "Apttus bullets lack metrics",
    rewrite_instruction: "add metrics",
    missing_keywords: [],
    needs_change: true,
    gap_type: "structural" as const,
  };
  const afterApttus = getAfterTextForFix(stubResult, apttusFixNoLabel);
  assert.ok(afterApttus.includes("Apttus bullet"), "entry_id-only Apttus fix returns Apttus content");
  assert.ok(!afterApttus.includes("Flipkart bullet"), "entry_id-only Apttus fix must not return Flipkart content");

  const flipkartFixNoLabel = {
    section: "experience",
    entry_id: "flipkart_engineering_manager_2020",
    gap_reason: "Flipkart bullets lack QPS",
    rewrite_instruction: "add QPS",
    missing_keywords: [],
    needs_change: true,
    gap_type: "structural" as const,
  };
  const afterFlipkart = getAfterTextForFix(stubResult, flipkartFixNoLabel);
  assert.ok(afterFlipkart.includes("Flipkart bullet"), "entry_id-only Flipkart fix returns Flipkart content");

  const cleartaxFixNoLabel = {
    section: "experience",
    entry_id: "cleartax_senior_engineer_2022",
    gap_reason: "Cleartax bullets lack scale",
    rewrite_instruction: "add scale",
    missing_keywords: [],
    needs_change: true,
    gap_type: "structural" as const,
  };
  const afterCleartax = getAfterTextForFix(stubResult, cleartaxFixNoLabel);
  assert.equal(afterCleartax, "", "entry_id-only fix not in rewrite returns empty string, not Flipkart content");
}

{
  const misScopedList = buildActionableFixesList({
    ...({
      ats: { score: 60, breakdown: { keyword_match: 15, formatting: 15, readability: 15, impact_metrics: 15 }, details: [], ats_issues: [] },
      resume: { experience_years: 10, seniority: "senior", tech_stack: [], domains: [], has_metrics: true, has_summary: true, sections_present: ["experience"], resume_sections: {} },
      gap: {
        resume_only_mode: false,
        jd_match_score_before: 50,
        jd_match_score_after: null,
        section_gaps: [],
        missing_keywords: [],
        priority_fixes: [
          {
            section: "experience",
            sub_label: "Engineering Manager | Flipkart — Bengaluru, KA",
            entry_id: "flipkart_engineering_manager_2020",
            gap_reason: "Flipkart EM bullets 3-5 lack explicit team scope details",
            rewrite_instruction: "add team dynamics",
            missing_keywords: [],
            needs_change: true,
            gap_type: "structural",
          },
          {
            section: "experience",
            sub_label: "Head of Engineering | Smart Viz X — Bengaluru, KA",
            entry_id: "smart_viz_director_2018",
            gap_reason: "Flipkart EM bullets 3-5 lack explicit team scope details",
            rewrite_instruction: "add team dynamics",
            missing_keywords: [],
            needs_change: true,
            gap_type: "structural",
          },
          {
            section: "experience",
            sub_label: "Engineering Manager | Apttus (via Altran — Consulting Engagement) — Bengaluru, KA",
            entry_id: "apttus_senior_consultant_2019",
            gap_reason: "Flipkart EM bullets 3-5 lack explicit team scope details",
            rewrite_instruction: "add team dynamics",
            missing_keywords: [],
            needs_change: true,
            gap_type: "structural",
          },
        ],
      },
      rewrites: { experience: { balanced: plainTextRewrite, aggressive: "", top_1_percent: "" } },
      patches: [],
    } as unknown as import("../types").AnalysisResult),
  });
  assert.equal(misScopedList.length, 1, "mis-scoped Flipkart gap_reason cards for other companies are dropped");
  assert.ok(misScopedList[0]?.sub_label?.includes("Flipkart"));
}

{
  const withOverview = buildActionableFixesList({
    ...({
      ats: { score: 60, breakdown: { keyword_match: 15, formatting: 15, readability: 15, impact_metrics: 15 }, details: [], ats_issues: [] },
      resume: {
        experience_years: 10,
        seniority: "senior",
        tech_stack: [],
        domains: [],
        has_metrics: true,
        has_summary: true,
        sections_present: ["experience"],
        weaknesses: [
          "Flipkart EM bullets 3-5 lack explicit team scope details → add team dynamics",
          "Smart Viz X revenue impact is thin → quantify ARR or user growth",
        ],
        improvement_areas: [],
        resume_sections: {
          experience: {
            header: "experience",
            full_text: "",
            sub_entries: [
              {
                label: "Engineering Manager | Flipkart — Bengaluru, KA",
                entry_id: "flipkart_engineering_manager_2020",
                verbatim_text: "Flipkart block",
              },
              {
                label: "Head of Engineering | Smart Viz X — Bengaluru, KA",
                entry_id: "smart_viz_director_2018",
                verbatim_text: "Smart Viz block",
              },
            ],
          },
        },
      },
      gap: {
        resume_only_mode: false,
        jd_match_score_before: 50,
        jd_match_score_after: null,
        section_gaps: [],
        missing_keywords: [],
        priority_fixes: [],
      },
      rewrites: { experience: { balanced: plainTextRewrite, aggressive: "", top_1_percent: "" } },
      patches: [],
    } as unknown as import("../types").AnalysisResult),
  });
  assert.equal(withOverview.length, 2, "Overview weaknesses backfill as fix cards in JD mode");
  assert.ok(
    withOverview.some((f) => (f.sub_label ?? "").includes("Flipkart")),
    "Flipkart overview weakness present"
  );
  assert.ok(
    withOverview.some((f) => (f.sub_label ?? "").includes("Smart Viz")),
    "Smart Viz overview weakness present"
  );
}

const fixtureA = loadFixture("fixture_a_multi_company_jd.json");
const fixtureB = loadFixture("fixture_b_resume_only.json");
const fixtureC = loadFixture("fixture_c_underqualified_gate.json");

// ── Fixture A: multi-company JD ───────────────────────────────────────────

const fixesA = buildActionableFixesList(fixtureA);
assert.equal(fixesA.length, 4, "Fixture A: expected 4 fix cards");

const entryIdsA = fixesA.map((f) => f.entry_id).filter(Boolean) as string[];
assert.equal(new Set(entryIdsA).size, 4, "Fixture A: no duplicate entry_id cards");

for (const fix of fixesA) {
  if (!fix.entry_id) continue;
  const before = getBeforeTextForFix(fixtureA, fix);
  const foreign = foreignCompanyMentioned(before, fix.entry_id, entryIdsA);
  assert.equal(foreign, null, `Fixture A: before text for ${fix.entry_id} mentions foreign company`);

  const patch = resolvePatchForFix(fix, fixtureA.patches, "experience");
  assert.ok(patch, `Fixture A: patch resolved for ${fix.entry_id}`);
  assert.equal(patch?.sub_entry_id, fix.entry_id);

  const after = getAfterTextForFix(fixtureA, fix, patch);
  assert.ok(after.includes(patch!.replacement_text.slice(0, 20)));
  const foreignAfter = foreignCompanyMentioned(after, fix.entry_id, entryIdsA);
  assert.equal(foreignAfter, null, `Fixture A: after text for ${fix.entry_id} mentions foreign company`);
}

// ── Fixture B: resume-only InfoOnlyCards ────────────────────────────────────

const fixesB = buildActionableFixesList(fixtureB);
const smartVizFix = fixesB.find((f) => f.entry_id === "smart_viz_director_2018");
assert.ok(smartVizFix, "Fixture B: Smart Viz fix card present");

const { wherePart, whatPart } = parseInfoOnlyCardParts(smartVizFix!.gap_reason);
assert.ok(wherePart?.includes("Smart Viz X"), "Fixture B: where-part scopes to Smart Viz X");
assert.ok(whatPart.includes("revenue"), "Fixture B: what-part is actionable instruction");
assert.notEqual(wherePart, whatPart, "Fixture B: scope and body must differ");

const scopeLabel = deriveInfoOnlyScopeLabel(smartVizFix!);
assert.ok(scopeLabel?.includes("Smart Viz X") || scopeLabel?.includes("Director"));
assert.notEqual(
  scopeLabel,
  "Add more quantified metrics in earlier roles",
  "Fixture B: scope must not echo generic improvement_area as title"
);

for (const fix of fixesB.filter((f) => f.section === "experience")) {
  const patch = resolvePatchForFix(fix, fixtureB.patches, "experience");
  if (patch) continue;
  const after = getAfterTextForFix(fixtureB, fix);
  assert.equal(
    shouldRenderStructuralApplyButton(fix, after, null),
    false,
    `Fixture B: experience InfoOnly card must not show Apply (${fix.gap_reason.slice(0, 40)})`
  );
  assert.equal(isNoChangeReplacement(after), false);
}

assert.ok(
  !fixesB.some((f) => isNoChangeReplacement(getAfterTextForFix(fixtureB, f))),
  "Fixture B: no fix may surface a no-change replacement as after text"
);

// ── Fixture C: underqualified gate ──────────────────────────────────────────

assert.equal(isTabRoleFitLocked("fixes", fixtureC.role_fit), true);
assert.equal(isTabRoleFitLocked("gap", fixtureC.role_fit), true);
assert.equal(isTabRoleFitLocked("progress", fixtureC.role_fit), true);
assert.equal(isTabRoleFitLocked("overview", fixtureC.role_fit), false);
assert.equal(isTabRoleFitLocked("recruiter", fixtureC.role_fit), false);

const fixesC = buildActionableFixesList(fixtureC);
assert.equal(fixesC.length, 0, "Fixture C: no fix cards when priority_fixes empty");

const structuralManualEditFixture: AnalysisResult = {
  ...fixtureB,
  patches: [],
  rewrites: null,
  gap: {
    ...fixtureB.gap!,
    priority_fixes: [
      {
        section: "experience",
        entry_id: "flipkart_engineering_manager_2020",
        sub_label: "Engineering Manager | Flipkart — Bengaluru, KA Sep 2020 – Present",
        gap_reason: "In Experience > Flipkart bullet 3, add the QPS metric",
        rewrite_instruction: "Add peak QPS and SLA numbers to bullet 3",
        missing_keywords: [],
        needs_change: true,
        gap_type: "structural",
      },
    ],
  },
};
const manualEditFixes = buildActionableFixesList(structuralManualEditFixture);
assert.ok(
  manualEditFixes.some((f) =>
    (f.gap_reason ?? "").includes("Flipkart bullet 3")
  ),
  "Structural gap with no patch must render as InfoOnlyCard, not be dropped"
);

// Patch-derived fixes must survive even when issue_detected starts with "Original lacks…"
{
  const patchOnlyFixture: AnalysisResult = {
    ...fixtureB,
    gap: {
      ...fixtureB.gap!,
      priority_fixes: [
        {
          section: "experience",
          entry_id: null,
          sub_label: "Add more quantified",
          gap_reason: "Add more quantified metrics in Smart Viz X and Apttus roles",
          rewrite_instruction: "Add more quantified metrics in Smart Viz X and Apttus roles",
          missing_keywords: [],
          needs_change: true,
          gap_type: "evidence",
          requires_user_input: true,
        },
      ],
    },
    patches: [
      {
        patch_id: "p-smart",
        gap_id: "g-smart",
        section: "experience",
        sub_entry_label: "Head of Engineering | Smart Viz X — Bengaluru, KA",
        sub_entry_id: "head_engineering_smart",
        op: "replace_text",
        original_text: "• Led cross-functional teams for 3D design SaaS platform",
        replacement_text:
          "• Led cross-functional teams for 3D design SaaS platform serving [N] enterprise architects",
        risk: "safe",
        hallucination_risk: false,
        issue_detected:
          "Original lacks quantified cost savings in rupees and user scale metrics required for engineering leadership roles.",
        fix_rationale: "Add scale metrics",
        status: "pending",
      },
      {
        patch_id: "p-apttus",
        gap_id: "g-apttus",
        section: "experience",
        sub_entry_label:
          "Engineering Manager | Apttus (via Altran — Consulting Engagement) — Bengaluru, KA",
        sub_entry_id: "engineering_manager_apttus",
        op: "replace_text",
        original_text:
          "• Led architecture and delivery of a multi-tenant B2B chatbot on a microservices-based backend",
        replacement_text:
          "• Architected multi-tenant B2B chatbot on microservices backend scaling user base 65x",
        risk: "safe",
        hallucination_risk: false,
        issue_detected:
          "Original lacks quantified cost/revenue impact and uses passive 'led' instead of active 'architected'.",
        fix_rationale: "Strengthen impact",
        status: "pending",
      },
    ],
    rewrites: null,
  };

  const patchOnlyFixes = buildActionableFixesList(patchOnlyFixture);
  assert.ok(
    patchOnlyFixes.some((f) => f.entry_id === "head_engineering_smart"),
    "Smart Viz patch must appear on Fixes tab"
  );
  assert.ok(
    patchOnlyFixes.some((f) => f.entry_id === "engineering_manager_apttus"),
    "Apttus patch must appear on Fixes tab"
  );

  for (const entryId of ["head_engineering_smart", "engineering_manager_apttus"]) {
    const fix = patchOnlyFixes.find((f) => f.entry_id === entryId);
    assert.ok(fix, `patch fix present for ${entryId}`);
    const patch = resolvePatchForFix(fix!, patchOnlyFixture.patches, "experience");
    assert.ok(patch, `patch resolves for ${entryId}`);
    const after = getAfterTextForFix(patchOnlyFixture, fix!, patch);
    assert.ok(isUsableAfterText(after), `after text usable for ${entryId}`);
    assert.equal(
      shouldRenderStructuralApplyButton(fix!, after, null),
      true,
      `structural Apply button for ${entryId}`
    );
  }
}

{
  const architectureRiskPatch = {
    patch_id: "p-arch-risk",
    gap_id: "g-arch-risk",
    section: "experience",
    sub_entry_label: "Engineering Manager | Flipkart — Bengaluru, KA",
    sub_entry_id: "engineering_manager_flipkart",
    op: "replace_text" as const,
    original_text:
      "Designed and executed platform scalability initiatives including DB sharding, Kubernetes adoption, and queue migration — scaling systems to 15K QPS and reducing MTTR by 30% through improved observability.",
    replacement_text:
      "Designed and executed platform scalability initiatives including DB sharding, Kubernetes adoption, and queue migration—scaling systems to 15K QPS and reducing MTTR by 30% through improved observability. • Oversaw architecture evaluation and operational risk assessment for all supply chain platforms, ensuring system reliability and scalability at 15K+ QPS.",
    risk: "safe" as const,
    hallucination_risk: false,
    issue_detected:
      "missing explicit mention of architecture evaluation and operational risk assessment",
    fix_rationale:
      "Added a bullet explicitly stating architecture evaluation and operational risk",
    status: "pending" as const,
  };

  const archFixture: AnalysisResult = {
    ...fixtureB,
    gap: {
      ...fixtureB.gap!,
      priority_fixes: [
        {
          section: "experience",
          entry_id: "engineering_manager_flipkart",
          sub_label: "Engineering Manager | Flipkart — Bengaluru, KA",
          gap_reason:
            "missing explicit mention of architecture evaluation and operational risk assessment",
          rewrite_instruction: "Add architecture evaluation and operational risk bullets",
          missing_keywords: ["architecture evaluation", "operational risk"],
          needs_change: true,
          gap_type: "evidence",
          requires_user_input: true,
        },
      ],
    },
    patches: [architectureRiskPatch],
    rewrites: null,
  };

  const archFixes = buildActionableFixesList(archFixture);
  const archFix = archFixes.find((f) => f.entry_id === "engineering_manager_flipkart");
  assert.ok(archFix, "architecture/risk patch must appear on Fixes tab");
  assert.notEqual(
    archFix!.gap_type,
    "evidence",
    "surgical patch must not be classified as evidence coaching"
  );
  assert.equal(
    archFix!.fix_rationale,
    architectureRiskPatch.fix_rationale,
    "fix_rationale preserved for Why line"
  );
  assert.equal(archFix!.requires_user_input, false, "patch-derived fix must not require coaching");
}

console.log("fixesPipeline.test.ts: all fixture assertions passed");
