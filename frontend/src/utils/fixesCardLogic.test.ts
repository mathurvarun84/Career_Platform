import assert from "node:assert/strict";

import {
  buildFixLocationKey,
  companyTokenFromGapReason,
  deriveExampleHint,
  extractCompanyTokenFromLabel,
  findFuzzyFixLocationKey,
  gapReasonMatchesFixScope,
  isNoChangeReplacement,
  isUsableAfterText,
  mergeFixLists,
  normalizeSubLabelKey,
  resolveSubChangeGapReason,
  structuralCardHasNoData,
  subEntryLabelMatches,
} from "./fixesCardLogic";
import type { PriorityFix } from "../types";

assert.equal(
  isNoChangeReplacement(
    "No changes required; original entry contains sufficient quantified metrics"
  ),
  true
);
assert.equal(isNoChangeReplacement("Reduced latency by 40% serving 2M QPS"), false);

assert.equal(
  extractCompanyTokenFromLabel("Engineering Manager | Flipkart — Bengaluru, KA Sep 2020"),
  "flipkart"
);
assert.equal(
  companyTokenFromGapReason("Flipkart EM bullets 3-5 lack explicit team scope details"),
  "flipkart"
);
assert.equal(
  gapReasonMatchesFixScope({
    gap_reason: "Flipkart EM bullets 3-5 lack explicit team scope details",
    sub_label: "Engineering Manager | Apttus — Bengaluru",
    entry_id: "apttus_senior_consultant_2019",
  }),
  false
);
assert.equal(extractCompanyTokenFromLabel("Flipkart — EM (2021–present)"), "flipkart");
assert.equal(
  extractCompanyTokenFromLabel("Apttus (via Altran — Consulting Engagement)"),
  "apttus (via altran"
);

assert.equal(
  subEntryLabelMatches(
    "Engineering Manager | Flipkart — Bengaluru, KA",
    "Flipkart — EM (2021–present)"
  ),
  true
);
assert.equal(
  subEntryLabelMatches(
    "Engineering Manager | Flipkart — Bengaluru, KA",
    "Engineering Manager | Apttus — Bengaluru"
  ),
  false
);
assert.equal(
  subEntryLabelMatches(
    "Engineering Manager | Apttus — Bengaluru",
    "Apttus (via Altran — Consulting Engagement)"
  ),
  true
);

assert.equal(
  resolveSubChangeGapReason(
    { rewrite_instruction: "Add QPS metrics", sub_label: "Flipkart — EM" },
    "Add metrics in Smart Viz X and Apttus roles"
  ),
  "Add QPS metrics"
);
assert.equal(
  resolveSubChangeGapReason(
    { sub_label: "Flipkart — EM" },
    "Add metrics in Smart Viz X and Apttus roles"
  ),
  "Review and strengthen this entry"
);
assert.equal(
  resolveSubChangeGapReason({}, "Section-level summary about all roles"),
  "Section-level summary about all roles"
);

assert.ok(deriveExampleHint("Add quantified metrics").includes("40%"));
assert.equal(deriveExampleHint("Improve formatting"), "");

assert.equal(isUsableAfterText("No changes required"), false);
assert.equal(isUsableAfterText("• Led team of 12"), true);

assert.equal(structuralCardHasNoData("", null), true);
assert.equal(
  structuralCardHasNoData("No changes required; original entry contains sufficient metrics", null),
  true
);
assert.equal(structuralCardHasNoData("• Improved checkout latency by 35%", null), false);

assert.equal(
  normalizeSubLabelKey("Engineering Manager | Flipkart — Bengaluru, KA Sep 2020 – Present"),
  "flipkart"
);
assert.equal(normalizeSubLabelKey("Flipkart — EM (2021–present)"), "flipkart");
assert.equal(
  buildFixLocationKey("experience", "Engineering Manager | Flipkart — Bengaluru, KA"),
  buildFixLocationKey("experience", "Flipkart — EM (2021–present)")
);
assert.equal(
  buildFixLocationKey("experience", "Flipkart — EM (2021–present)", "flipkart_em_2020"),
  "experience|flipkart_em_2020"
);
assert.notEqual(
  buildFixLocationKey("experience", "Flipkart — EM", "flipkart_em_2020"),
  buildFixLocationKey("experience", "Apttus — SC", "apttus_sc_2018")
);

const flipkartFromGap: PriorityFix = {
  section: "experience",
  sub_label: "Flipkart — EM (2021–present)",
  gap_reason: "Add QPS metrics",
  rewrite_instruction: "Add scale metrics",
  missing_keywords: [],
  needs_change: true,
  gap_type: "structural",
};
const flipkartFromPatch: PriorityFix = {
  section: "experience",
  sub_label: "Engineering Manager | Flipkart — Bengaluru, KA Sep 2020 – Present",
  gap_reason: "Patch: tighten bullets",
  rewrite_instruction: "Rewritten bullets",
  missing_keywords: ["QPS"],
  needs_change: true,
  gap_type: "structural",
};
const locationKey = (fix: PriorityFix) =>
  buildFixLocationKey("experience", fix.sub_label);
const merged = mergeFixLists(locationKey, [flipkartFromGap], [flipkartFromPatch]);
assert.equal(merged.length, 1);
assert.ok(merged[0].missing_keywords.includes("QPS"));

assert.equal(
  findFuzzyFixLocationKey("experience|flipkart supply chain", ["experience|flipkart"]),
  "experience|flipkart"
);

console.log("fixesCardLogic.test.ts: all assertions passed");
