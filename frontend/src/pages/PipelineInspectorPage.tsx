import { useCallback, useMemo, useState, type CSSProperties, type ReactElement } from "react";

import type {
  AnalysisResult,
  FixPlanItem,
  GapType,
  PriorityFix,
  ResumePatch,
  SectionGap,
  SubLocationChange,
} from "../types";

type InspectorTab =
  | "summary"
  | "fix_plan"
  | "priority_fixes"
  | "section_gaps"
  | "patches"
  | "cross_check";

type FlagLevel = "error" | "warn" | "info";

interface ValidationFlag {
  level: FlagLevel;
  message: string;
}

type PriorityFixRow = PriorityFix & {
  entry_id_confidence?: "none" | "derived" | "canonical";
};

type SubChangeRow = SubLocationChange & {
  gap_type?: GapType;
  coaching_question?: string | null;
  original_text?: string;
};

const C = {
  bg: "#f7f7fc",
  card: "#ffffff",
  border: "#e2e2ef",
  primary: "#5b5fc7",
  primaryLight: "#eef0fb",
  primaryMid: "#c4c8f0",
  floor: "#3a3d9a",
  text: "#1a1a2e",
  muted: "#6b7280",
  success: "#16a34a",
  successBg: "#f0fdf4",
  successBorder: "#bbf7d0",
  warn: "#d97706",
  warnBg: "#fffbeb",
  warnBorder: "#fcd34d",
  danger: "#dc2626",
  dangerBg: "#fef2f2",
  dangerBorder: "#fecaca",
  info: "#0369a1",
  infoBg: "#f0f9ff",
  infoBorder: "#bae6fd",
  mono: "'JetBrains Mono', 'Fira Mono', monospace",
} as const;

const TAB_LABELS: Record<InspectorTab, string> = {
  summary: "Summary",
  fix_plan: "fix_plan",
  priority_fixes: "priority_fixes",
  section_gaps: "section_gaps",
  patches: "patches",
  cross_check: "cross_check",
};

function badge(
  text: string,
  color: string,
  bg: string,
  border: string
): ReactElement {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 999,
        fontSize: "11px",
        fontWeight: 700,
        color,
        background: bg,
        border: `1px solid ${border}`,
        marginRight: "6px",
        marginBottom: "4px",
      }}
    >
      {text}
    </span>
  );
}

function kindBadge(kind: FixPlanItem["kind"]): ReactElement {
  const map: Record<FixPlanItem["kind"], [string, string, string, string]> = {
    surgical_patch: ["surgical_patch", C.success, C.successBg, C.successBorder],
    coaching: ["coaching", C.primary, C.primaryLight, C.primaryMid],
    surface_keyword: ["surface_keyword", C.warn, C.warnBg, C.warnBorder],
    rewrite_block: ["rewrite_block", C.info, C.infoBg, C.infoBorder],
    info_only: ["info_only", C.muted, "#f3f4f6", C.border],
  };
  const [label, color, bg, border] = map[kind];
  return badge(label, color, bg, border);
}

function gapTypeBadge(gapType: GapType | undefined): ReactElement {
  const gt = gapType ?? "structural";
  const map: Record<GapType, [string, string, string, string]> = {
    evidence: ["evidence", C.primary, C.primaryLight, C.primaryMid],
    structural: ["structural", C.info, C.infoBg, C.infoBorder],
    surface: ["surface", C.warn, C.warnBg, C.warnBorder],
  };
  const [label, color, bg, border] = map[gt];
  return badge(label, color, bg, border);
}

function confidenceBadge(
  confidence: FixPlanItem["entry_id_confidence"] | undefined
): ReactElement {
  const c = confidence ?? "none";
  if (c === "canonical") return badge("canonical", C.success, C.successBg, C.successBorder);
  if (c === "derived") return badge("derived", C.warn, C.warnBg, C.warnBorder);
  return badge("absent", C.danger, C.dangerBg, C.dangerBorder);
}

function flagList(flags: ValidationFlag[]): ReactElement | null {
  if (flags.length === 0) return null;
  return (
    <div style={{ marginTop: "10px" }}>
      {flags.map((f, i) => {
        const styles: Record<FlagLevel, { bg: string; border: string; color: string }> = {
          error: { bg: C.dangerBg, border: C.dangerBorder, color: C.danger },
          warn: { bg: C.warnBg, border: C.warnBorder, color: C.warn },
          info: { bg: C.infoBg, border: C.infoBorder, color: C.info },
        };
        const s = styles[f.level];
        return (
          <div
            key={i}
            style={{
              fontSize: "12px",
              color: s.color,
              background: s.bg,
              border: `1px solid ${s.border}`,
              borderRadius: "6px",
              padding: "6px 10px",
              marginBottom: "6px",
              lineHeight: 1.45,
            }}
          >
            {f.level === "error" ? "✕ " : f.level === "warn" ? "⚠ " : "ℹ "}
            {f.message}
          </div>
        );
      })}
    </div>
  );
}

function cardBorderStyle(flags: ValidationFlag[]): CSSProperties {
  const hasError = flags.some((f) => f.level === "error");
  const hasWarn = flags.some((f) => f.level === "warn");
  if (hasError) return { borderColor: C.dangerBorder, background: C.dangerBg };
  if (hasWarn) return { borderColor: C.warnBorder, background: C.warnBg };
  return { borderColor: C.border, background: C.card };
}

function monoBox(
  label: string,
  text: string,
  variant: "default" | "before" | "after" = "default"
): ReactElement {
  const variantStyle: Record<typeof variant, CSSProperties> = {
    default: {
      background: "#f8f8fc",
      border: `1px solid ${C.border}`,
      color: C.text,
    },
    before: {
      background: C.dangerBg,
      border: `1px solid ${C.dangerBorder}`,
      color: "#991b1b",
    },
    after: {
      background: C.successBg,
      border: `1px solid ${C.successBorder}`,
      color: "#166534",
    },
  };
  return (
    <div style={{ marginTop: "8px" }}>
      <div
        style={{
          fontSize: "10px",
          fontWeight: 700,
          color: C.muted,
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          marginBottom: "4px",
        }}
      >
        {label}
      </div>
      <div
        style={{
          ...variantStyle[variant],
          borderRadius: variant === "default" ? 4 : 6,
          padding: variant === "default" ? "4px 8px" : "8px 10px",
          fontFamily: C.mono,
          fontSize: variant === "default" ? 12 : 11,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          lineHeight: 1.5,
        }}
      >
        {text}
      </div>
    </div>
  );
}

function fieldLine(label: string, value: string): ReactElement {
  return (
    <div style={{ marginTop: "6px", fontSize: "13px", lineHeight: 1.5 }}>
      <span style={{ fontWeight: 600, color: C.muted }}>{label}: </span>
      <span style={{ color: C.text }}>{value}</span>
    </div>
  );
}

function getPriorityFixes(result: AnalysisResult): PriorityFixRow[] {
  const raw = result.gap?.priority_fixes ?? [];
  return raw.filter(
    (f): f is PriorityFixRow =>
      typeof f === "object" && f !== null && "section" in f
  );
}

function validateFixPlanItem(item: FixPlanItem): ValidationFlag[] {
  const flags: ValidationFlag[] = [];

  if (item.kind === "coaching" && !item.coaching_question) {
    flags.push({
      level: "warn",
      message:
        "coaching_question null — card will use gap_reason as fallback question",
    });
  }

  if (item.kind === "surgical_patch" && !item.patch_id) {
    flags.push({
      level: "error",
      message:
        "patch_id null — getPatchDiff will show keyword fallback (Missing: X / Add: X)",
    });
  }

  if (item.kind === "surgical_patch" && !item.after_text) {
    flags.push({
      level: "error",
      message:
        "after_text null — StructuralPatchCard has no rewrite text to display",
    });
  }

  if (item.kind === "surgical_patch" && !item.before_text) {
    flags.push({
      level: "warn",
      message: "before_text null — no original text for diff display",
    });
  }

  if (item.entry_id_confidence === "none" && item.sub_label) {
    flags.push({
      level: "error",
      message:
        "confidence=absent but sub_label present — patch lookup blocked, _enrich_section_gaps may have missed this entry",
    });
  }

  if (item.entry_id_confidence === "derived") {
    flags.push({
      level: "warn",
      message:
        "confidence=derived — patch lookup blocked by design, verify _find_sub_entry matched correctly",
    });
  }

  if (item.gap_type === "evidence" && item.kind !== "coaching") {
    flags.push({
      level: "error",
      message: `gap_type=evidence but kind=${item.kind} — MISMATCH: will render as patch card instead of coaching card`,
    });
  }

  if (item.requires_user_input && item.kind !== "coaching") {
    flags.push({
      level: "error",
      message: `requires_user_input=true but kind=${item.kind} — fix_plan_builder missed evidence classification`,
    });
  }

  return flags;
}

function validatePriorityFix(fix: PriorityFixRow): ValidationFlag[] {
  const flags: ValidationFlag[] = [];

  if (!fix.entry_id && fix.sub_label) {
    flags.push({
      level: "warn",
      message:
        "sub_label present but entry_id empty — _enrich_section_gaps match failed for this sub_label",
    });
  }

  if (fix.entry_id && fix.entry_id_confidence === "none") {
    flags.push({
      level: "error",
      message:
        "entry_id non-empty but confidence=absent — logic mismatch in priority_fixes_from_gaps",
    });
  }

  if (fix.gap_type === "evidence" && !fix.requires_user_input) {
    flags.push({
      level: "error",
      message:
        "gap_type=evidence but requires_user_input=false — classify_gap failed to set coaching flag",
    });
  }

  if (fix.gap_type === "evidence" && !fix.coaching_question) {
    flags.push({
      level: "warn",
      message:
        "evidence gap has no coaching_question — EvidenceCoachingCard will use gap_reason as fallback",
    });
  }

  if (fix.gap_type === "structural" && !fix.rewrite_instruction) {
    flags.push({
      level: "error",
      message:
        "structural gap but rewrite_instruction empty — after_text will be null in fix_plan",
    });
  }

  if (fix.rewrite_instruction && fix.rewrite_instruction === fix.gap_reason) {
    flags.push({
      level: "warn",
      message:
        "rewrite_instruction === gap_reason — _resolve_after_text ≤60 char guard may discard this as a duplicate",
    });
  }

  if (!fix.original_text) {
    flags.push({
      level: "warn",
      message:
        "original_text empty — before_text will be null, no diff possible unless patch supplies it",
    });
  }

  return flags;
}

function validateSubChange(sub: SubChangeRow): ValidationFlag[] {
  const flags: ValidationFlag[] = [];

  if (!sub.entry_id) {
    flags.push({
      level: "error",
      message:
        "_enrich_section_gaps failed to match this sub_label to an A1 sub_entry",
    });
  }

  if (sub.rewrite_instruction === sub.gap_reason) {
    flags.push({
      level: "warn",
      message:
        "rewrite_instruction === gap_reason — will likely resolve to null after_text",
    });
  }

  if (!sub.original_text) {
    flags.push({
      level: "warn",
      message:
        "original_text empty — A1 verbatim lookup failed or section has no verbatim text",
    });
  }

  if (sub.gap_type === "evidence" && !sub.coaching_question) {
    flags.push({
      level: "warn",
      message: "evidence sub_change has no coaching_question",
    });
  }

  return flags;
}

function validatePatch(patch: ResumePatch): ValidationFlag[] {
  const flags: ValidationFlag[] = [];

  if (!patch.sub_entry_id) {
    flags.push({
      level: "warn",
      message:
        "sub_entry_id empty — lands in section pool, matched only to section-level fixes",
    });
  }

  if (!patch.original_text?.trim()) {
    flags.push({
      level: "error",
      message:
        "original_text empty — patch cannot be applied or used as before_text",
    });
  }

  if (!patch.replacement_text?.trim()) {
    flags.push({
      level: "error",
      message: "replacement_text empty — patch has no content",
    });
  }

  if (patch.op !== "replace_text") {
    flags.push({
      level: "warn",
      message: `op='${patch.op}' — only replace_text is used by fix_plan_builder`,
    });
  }

  return flags;
}

function SummaryTab({ result }: { result: AnalysisResult }): ReactElement {
  const fixPlan = result.fix_plan ?? [];
  const priorityFixes = getPriorityFixes(result);
  const patches = result.patches ?? [];
  const coachingCount = fixPlan.filter((i) => i.kind === "coaching").length;
  const surgicalCount = fixPlan.filter((i) => i.kind === "surgical_patch").length;
  const patchIdLinked = fixPlan.filter((i) => i.patch_id).length;
  const apiVersion = result.api_version ?? 1;

  const stats: Array<{
    label: string;
    value: string | number;
    flagRed: boolean;
  }> = [
    { label: "api_version", value: apiVersion, flagRed: apiVersion < 2 },
    { label: "fix_plan items", value: fixPlan.length, flagRed: fixPlan.length === 0 },
    {
      label: "priority_fixes",
      value: priorityFixes.length,
      flagRed: priorityFixes.length === 0,
    },
    { label: "patches", value: patches.length, flagRed: false },
    {
      label: "coaching cards",
      value: coachingCount,
      flagRed: coachingCount === 0 && priorityFixes.length > 0,
    },
    { label: "surgical_patch", value: surgicalCount, flagRed: false },
    {
      label: "patch_id linked",
      value: patchIdLinked,
      flagRed: patchIdLinked < surgicalCount,
    },
    {
      label: "surface_keyword",
      value: fixPlan.filter((i) => i.kind === "surface_keyword").length,
      flagRed: false,
    },
    {
      label: "info_only",
      value: fixPlan.filter((i) => i.kind === "info_only").length,
      flagRed: false,
    },
    {
      label: "section_gaps",
      value: result.gap?.section_gaps?.length ?? 0,
      flagRed: false,
    },
  ];

  let verdict: "green" | "amber" | "red" = "amber";
  let verdictText = "";

  if (fixPlan.length === 0 || apiVersion < 2) {
    verdict = "red";
    verdictText =
      apiVersion < 2
        ? "api_version < 2 — legacy session, no fix_plan contract"
        : "fix_plan is empty — pipeline produced no actionable items";
  } else if (
    patchIdLinked === surgicalCount &&
    coachingCount > 0
  ) {
    verdict = "green";
    verdictText = "All surgical patches linked and coaching cards present";
  } else {
    verdict = "amber";
    verdictText = "fix_plan present but some linkages or coaching counts look off";
  }

  const verdictColors = {
    green: { bg: C.successBg, border: C.successBorder, color: C.success },
    amber: { bg: C.warnBg, border: C.warnBorder, color: C.warn },
    red: { bg: C.dangerBg, border: C.dangerBorder, color: C.danger },
  };
  const vc = verdictColors[verdict];

  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: "10px",
          marginBottom: "16px",
        }}
      >
        {stats.map((s) => (
          <div
            key={s.label}
            style={{
              border: `1.5px solid ${s.flagRed ? C.dangerBorder : C.border}`,
              borderRadius: "10px",
              padding: "12px 14px",
              background: s.flagRed ? C.dangerBg : C.card,
            }}
          >
            <div style={{ fontSize: "11px", color: C.muted, fontWeight: 600 }}>
              {s.label}
            </div>
            <div
              style={{
                fontSize: "22px",
                fontWeight: 800,
                color: s.flagRed ? C.danger : C.text,
                marginTop: "4px",
              }}
            >
              {s.value}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          border: `1.5px solid ${vc.border}`,
          background: vc.bg,
          borderRadius: "10px",
          padding: "14px 18px",
          fontSize: "14px",
          fontWeight: 600,
          color: vc.color,
        }}
      >
        {verdict === "green" ? "🟢" : verdict === "amber" ? "🟡" : "🔴"} {verdictText}
      </div>
    </div>
  );
}

function FixPlanTab({ result }: { result: AnalysisResult }): ReactElement {
  const items = result.fix_plan ?? [];

  if (items.length === 0) {
    return (
      <div style={{ color: C.muted, fontSize: "14px" }}>
        No fix_plan items in this response.
      </div>
    );
  }

  return (
    <div>
      {items.map((item, idx) => {
        const flags = validateFixPlanItem(item);
        const border = cardBorderStyle(flags);
        return (
          <div
            key={item.fix_id || idx}
            style={{
              border: "1.5px solid",
              borderRadius: "10px",
              padding: "14px 18px",
              marginBottom: "10px",
              ...border,
            }}
          >
            <div style={{ marginBottom: "8px" }}>
              <span style={{ fontSize: "15px", fontWeight: 700, color: C.text }}>
                {item.section}
              </span>
              {item.sub_label ? (
                <span style={{ fontSize: "14px", color: C.muted }}>
                  {" "}
                  · {item.sub_label}
                </span>
              ) : null}
            </div>
            <div style={{ marginBottom: "8px" }}>
              {kindBadge(item.kind)}
              {gapTypeBadge(item.gap_type)}
              {confidenceBadge(item.entry_id_confidence)}
              {item.patch_id
                ? badge("patch_id ✓", C.success, C.successBg, C.successBorder)
                : null}
            </div>

            {item.issue ? fieldLine("issue", item.issue) : null}
            {item.before_text ? monoBox("BEFORE", item.before_text, "before") : null}
            {item.after_text ? monoBox("AFTER", item.after_text, "after") : null}
            {item.kind === "coaching" && item.coaching_question
              ? fieldLine("coaching_question", item.coaching_question)
              : null}
            {item.coaching_hints?.length
              ? fieldLine("coaching_hints", item.coaching_hints.join(" · "))
              : null}
            {item.entry_id ? monoBox("entry_id", item.entry_id) : null}
            {item.patch_id ? monoBox("patch_id", item.patch_id) : null}
            {item.why ? (
              <div
                style={{
                  marginTop: "8px",
                  fontSize: "13px",
                  fontStyle: "italic",
                  color: C.muted,
                  lineHeight: 1.5,
                }}
              >
                {item.why}
              </div>
            ) : null}

            {flagList(flags)}
          </div>
        );
      })}
    </div>
  );
}

function PriorityFixesTab({ result }: { result: AnalysisResult }): ReactElement {
  const fixes = getPriorityFixes(result);

  if (fixes.length === 0) {
    return (
      <div style={{ color: C.muted, fontSize: "14px" }}>
        No priority_fixes objects in gap result.
      </div>
    );
  }

  return (
    <div>
      {fixes.map((fix, idx) => {
        const flags = validatePriorityFix(fix);
        const border = cardBorderStyle(flags);
        return (
          <div
            key={`${fix.section}-${fix.sub_label ?? idx}`}
            style={{
              border: "1.5px solid",
              borderRadius: "10px",
              padding: "14px 18px",
              marginBottom: "10px",
              ...border,
            }}
          >
            <div style={{ marginBottom: "8px" }}>
              <span style={{ fontSize: "15px", fontWeight: 700, color: C.text }}>
                {fix.section}
              </span>
              {fix.sub_label ? (
                <span style={{ fontSize: "14px", color: C.muted }}>
                  {" "}
                  · {fix.sub_label}
                </span>
              ) : null}
            </div>
            <div style={{ marginBottom: "8px" }}>
              {gapTypeBadge(fix.gap_type)}
              {confidenceBadge(fix.entry_id_confidence)}
            </div>

            {fieldLine("gap_reason", fix.gap_reason)}
            {fix.rewrite_instruction
              ? monoBox("rewrite_instruction", fix.rewrite_instruction)
              : null}
            {fix.original_text ? monoBox("original_text", fix.original_text) : null}
            {fix.entry_id ? monoBox("entry_id", fix.entry_id) : null}

            {flagList(flags)}
          </div>
        );
      })}
    </div>
  );
}

function SectionGapsTab({ result }: { result: AnalysisResult }): ReactElement {
  const gaps = (result.gap?.section_gaps ?? []).filter(
    (g: SectionGap) => g.needs_change === true
  );

  if (gaps.length === 0) {
    return (
      <div style={{ color: C.muted, fontSize: "14px" }}>
        No section_gaps with needs_change=true.
      </div>
    );
  }

  return (
    <div>
      {gaps.map((gap, gIdx) => (
        <div
          key={`${gap.section}-${gIdx}`}
          style={{
            border: `1.5px solid ${C.border}`,
            borderRadius: "10px",
            padding: "14px 18px",
            marginBottom: "12px",
            background: C.card,
          }}
        >
          <div style={{ marginBottom: "8px" }}>
            <span style={{ fontSize: "15px", fontWeight: 700, color: C.text }}>
              {gap.section}
            </span>
            <span style={{ marginLeft: "8px" }}>{gapTypeBadge(gap.gap_type)}</span>
            {badge(
              `${gap.sub_changes?.length ?? 0} sub_changes`,
              C.info,
              C.infoBg,
              C.infoBorder
            )}
          </div>
          {fieldLine("gap_reason", gap.gap_reason)}

          {(gap.sub_changes ?? []).map((rawSub, sIdx) => {
            const sub = rawSub as SubChangeRow;
            const flags = validateSubChange(sub);
            const border = cardBorderStyle(flags);
            return (
              <div
                key={`${sub.sub_label}-${sIdx}`}
                style={{
                  border: "1.5px solid",
                  borderRadius: "8px",
                  padding: "12px 14px",
                  marginTop: "10px",
                  ...border,
                }}
              >
                <div style={{ marginBottom: "6px" }}>
                  <span style={{ fontWeight: 700, fontSize: "14px" }}>{sub.sub_label}</span>
                  <span style={{ marginLeft: "8px" }}>{gapTypeBadge(sub.gap_type)}</span>
                  {sub.entry_id
                    ? badge("entry_id ✓", C.success, C.successBg, C.successBorder)
                    : badge("entry_id ✕", C.danger, C.dangerBg, C.dangerBorder)}
                </div>
                {fieldLine("gap_reason", sub.gap_reason)}
                {sub.rewrite_instruction
                  ? monoBox("rewrite_instruction", sub.rewrite_instruction)
                  : null}
                {sub.original_text
                  ? monoBox("verbatim from A1", sub.original_text)
                  : null}
                {flagList(flags)}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function PatchesTab({ result }: { result: AnalysisResult }): ReactElement {
  const patches = result.patches ?? [];
  const withEntryId = patches.filter((p) => p.sub_entry_id).length;
  const withoutEntryId = patches.length - withEntryId;

  if (patches.length === 0) {
    return (
      <div style={{ color: C.muted, fontSize: "14px" }}>No patches in this response.</div>
    );
  }

  return (
    <div>
      <div
        style={{
          fontSize: "13px",
          color: C.muted,
          marginBottom: "14px",
          fontWeight: 600,
        }}
      >
        {withEntryId} entry-level patches · {withoutEntryId} in section pool
      </div>

      {patches.map((patch, idx) => {
        const flags = validatePatch(patch);
        const border = cardBorderStyle(flags);
        return (
          <div
            key={patch.patch_id || idx}
            style={{
              border: "1.5px solid",
              borderRadius: "10px",
              padding: "14px 18px",
              marginBottom: "10px",
              ...border,
            }}
          >
            <div style={{ marginBottom: "8px" }}>
              <span style={{ fontWeight: 700, color: C.text }}>{patch.section}</span>
              <span style={{ marginLeft: "8px" }}>
                {badge(patch.op, C.info, C.infoBg, C.infoBorder)}
              </span>
              {patch.sub_entry_id
                ? badge(patch.sub_entry_id, C.success, C.successBg, C.successBorder)
                : badge("section pool", C.warn, C.warnBg, C.warnBorder)}
              {badge(
                patch.risk,
                patch.risk === "safe" ? C.success : C.warn,
                patch.risk === "safe" ? C.successBg : C.warnBg,
                patch.risk === "safe" ? C.successBorder : C.warnBorder
              )}
            </div>
            {patch.issue_detected ? fieldLine("issue_detected", patch.issue_detected) : null}

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "10px",
                marginTop: "10px",
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    color: C.muted,
                    marginBottom: "4px",
                  }}
                >
                  ORIGINAL
                </div>
                <div
                  style={{
                    background: C.dangerBg,
                    border: `1px solid ${C.dangerBorder}`,
                    color: "#991b1b",
                    borderRadius: "6px",
                    padding: "8px 10px",
                    fontFamily: C.mono,
                    fontSize: "12px",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    lineHeight: 1.5,
                    minHeight: "40px",
                  }}
                >
                  {patch.original_text || "(empty)"}
                </div>
              </div>
              <div>
                <div
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    color: C.muted,
                    marginBottom: "4px",
                  }}
                >
                  REPLACEMENT
                </div>
                <div
                  style={{
                    background: C.successBg,
                    border: `1px solid ${C.successBorder}`,
                    color: "#166534",
                    borderRadius: "6px",
                    padding: "8px 10px",
                    fontFamily: C.mono,
                    fontSize: "12px",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    lineHeight: 1.5,
                    minHeight: "40px",
                  }}
                >
                  {patch.replacement_text || "(empty)"}
                </div>
              </div>
            </div>

            {flagList(flags)}
          </div>
        );
      })}
    </div>
  );
}

function CrossCheckTab({ result }: { result: AnalysisResult }): ReactElement {
  const fixPlan = result.fix_plan ?? [];
  const patches = result.patches ?? [];

  const patchById: Record<string, ResumePatch> = {};
  patches.forEach((p) => {
    if (p.patch_id) patchById[p.patch_id] = p;
  });

  const patchByEntryId: Record<string, ResumePatch> = {};
  patches.forEach((p) => {
    if (p.sub_entry_id) patchByEntryId[p.sub_entry_id.toLowerCase()] = p;
  });

  const allPatchEntryKeys = Object.keys(patchByEntryId);

  const nullPatchItems = fixPlan.filter(
    (i) => i.kind === "surgical_patch" && !i.patch_id
  );

  const brokenPatches = fixPlan
    .filter((i) => i.kind === "surgical_patch" && i.patch_id)
    .filter((i) => {
      const p = patchById[i.patch_id!];
      return p && !p.original_text?.trim();
    });

  const unreferencedPatches = patches.filter(
    (p) =>
      p.sub_entry_id &&
      !fixPlan.some(
        (i) => i.patch_id && patchById[i.patch_id]?.sub_entry_id === p.sub_entry_id
      )
  );

  const surgicalWithPatch = fixPlan.filter(
    (i) => i.kind === "surgical_patch" && i.patch_id
  ).length;
  const allClear =
    nullPatchItems.length === 0 &&
    brokenPatches.length === 0 &&
    surgicalWithPatch === fixPlan.filter((i) => i.kind === "surgical_patch").length;

  return (
    <div>
      <div style={{ marginBottom: "20px" }}>
        <div
          style={{
            fontSize: "14px",
            fontWeight: 700,
            color: C.text,
            marginBottom: "10px",
          }}
        >
          Section A — surgical_patch items with patch_id = null ({nullPatchItems.length})
        </div>
        {nullPatchItems.length === 0 ? (
          <div style={{ fontSize: "13px", color: C.success }}>
            No null patch_id surgical items.
          </div>
        ) : (
          nullPatchItems.map((item, idx) => {
            const lookupKey = item.entry_id?.toLowerCase() ?? "(none)";
            const prefix = item.entry_id?.slice(0, 15).toLowerCase() ?? "";
            return (
              <div
                key={item.fix_id || idx}
                style={{
                  border: `1.5px solid ${C.dangerBorder}`,
                  background: C.dangerBg,
                  borderRadius: "10px",
                  padding: "14px 18px",
                  marginBottom: "10px",
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: "6px" }}>
                  {item.section}
                  {item.sub_label ? ` · ${item.sub_label}` : ""}
                </div>
                <div style={{ fontSize: "13px", lineHeight: 1.6 }}>
                  <div>
                    <strong>entry_id:</strong>{" "}
                    <code style={{ fontFamily: C.mono }}>{item.entry_id ?? "(empty)"}</code>
                  </div>
                  <div>
                    <strong>entry_id_confidence:</strong> {item.entry_id_confidence ?? "none"}
                  </div>
                  <div>
                    <strong>sub_label:</strong> {item.sub_label ?? "(none)"}
                  </div>
                  <div>
                    <strong>lookup key:</strong>{" "}
                    <code style={{ fontFamily: C.mono }}>{lookupKey}</code>
                  </div>
                </div>

                <div style={{ marginTop: "10px", fontSize: "12px", color: C.muted }}>
                  Available patch entry keys:
                </div>
                <div style={{ marginTop: "6px" }}>
                  {allPatchEntryKeys.length === 0 ? (
                    <span style={{ color: C.danger, fontSize: "12px" }}>
                      No entry-level patches in response
                    </span>
                  ) : (
                    allPatchEntryKeys.map((key) => {
                      const nearMiss = prefix && key.startsWith(prefix);
                      return (
                        <code
                          key={key}
                          style={{
                            display: "inline-block",
                            fontFamily: C.mono,
                            fontSize: "11px",
                            padding: "2px 6px",
                            marginRight: "6px",
                            marginBottom: "4px",
                            borderRadius: "4px",
                            background: nearMiss ? C.warnBg : "#f3f4f6",
                            border: `1px solid ${nearMiss ? C.warnBorder : C.border}`,
                            color: nearMiss ? C.warn : C.text,
                          }}
                        >
                          {key}
                        </code>
                      );
                    })
                  )}
                </div>

                <div
                  style={{
                    marginTop: "10px",
                    fontSize: "12px",
                    color: C.danger,
                    fontWeight: 600,
                  }}
                >
                  {!item.entry_id
                    ? "entry_id absent — no canonical lookup possible"
                    : "entry_id present but no sub_entry_id matches — A4 may not have written a patch for this entry, or slug format diverged"}
                </div>
              </div>
            );
          })
        )}
      </div>

      <div style={{ marginBottom: "20px" }}>
        <div
          style={{
            fontSize: "14px",
            fontWeight: 700,
            color: C.text,
            marginBottom: "10px",
          }}
        >
          Section B — linked patches with empty original_text ({brokenPatches.length})
        </div>
        {brokenPatches.length === 0 ? (
          <div style={{ fontSize: "13px", color: C.success }}>None.</div>
        ) : (
          brokenPatches.map((item, idx) => (
            <div
              key={item.fix_id || idx}
              style={{
                border: `1.5px solid ${C.dangerBorder}`,
                background: C.dangerBg,
                borderRadius: "10px",
                padding: "12px 16px",
                marginBottom: "8px",
                fontSize: "13px",
              }}
            >
              ✕ patch_id {item.patch_id} linked but original_text is empty
            </div>
          ))
        )}
      </div>

      <div style={{ marginBottom: "20px" }}>
        <div
          style={{
            fontSize: "14px",
            fontWeight: 700,
            color: C.text,
            marginBottom: "10px",
          }}
        >
          Section C — unreferenced patches ({unreferencedPatches.length})
        </div>
        {unreferencedPatches.length === 0 ? (
          <div style={{ fontSize: "13px", color: C.muted }}>None.</div>
        ) : (
          unreferencedPatches.map((p, idx) => (
            <div
              key={p.patch_id || idx}
              style={{
                border: `1.5px solid ${C.infoBorder}`,
                background: C.infoBg,
                borderRadius: "10px",
                padding: "12px 16px",
                marginBottom: "8px",
                fontSize: "13px",
                color: C.info,
              }}
            >
              ℹ {p.section} · sub_entry_id={p.sub_entry_id} — exists but not linked to any
              fix_plan item (classified as coaching/surface, or entry_id lookup missed)
            </div>
          ))
        )}
      </div>

      <div
        style={{
          border: `1.5px solid ${allClear ? C.successBorder : C.warnBorder}`,
          background: allClear ? C.successBg : C.warnBg,
          borderRadius: "10px",
          padding: "14px 18px",
          fontSize: "14px",
          fontWeight: 700,
          color: allClear ? C.success : C.warn,
        }}
      >
        {allClear
          ? "✓ All patch linkages intact"
          : `${nullPatchItems.length + brokenPatches.length} linkage issue(s) found`}
      </div>
    </div>
  );
}

export default function PipelineInspectorPage(): ReactElement {
  const [rawJson, setRawJson] = useState<string>("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [parseError, setParseError] = useState<string>("");
  const [activeTab, setActiveTab] = useState<InspectorTab>("summary");

  const handleParse = useCallback(() => {
    setParseError("");
    try {
      const parsed = JSON.parse(rawJson) as AnalysisResult;
      setResult(parsed);
      setActiveTab("summary");
    } catch (e) {
      setParseError(`Invalid JSON: ${(e as Error).message}`);
      setResult(null);
    }
  }, [rawJson]);

  const tabContent = useMemo(() => {
    if (!result) return null;
    switch (activeTab) {
      case "summary":
        return <SummaryTab result={result} />;
      case "fix_plan":
        return <FixPlanTab result={result} />;
      case "priority_fixes":
        return <PriorityFixesTab result={result} />;
      case "section_gaps":
        return <SectionGapsTab result={result} />;
      case "patches":
        return <PatchesTab result={result} />;
      case "cross_check":
        return <CrossCheckTab result={result} />;
      default:
        return null;
    }
  }, [activeTab, result]);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        fontFamily: "system-ui, -apple-system, sans-serif",
        color: C.text,
      }}
    >
      <div
        style={{
          background: C.card,
          borderBottom: `1.5px solid ${C.border}`,
          padding: "16px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          rowGap: "8px",
        }}
      >
        <div>
          <div style={{ fontSize: "18px", fontWeight: 800, color: C.text }}>
            Pipeline Inspector
          </div>
          <div style={{ fontSize: "12px", color: C.muted, marginTop: "2px" }}>
            DEV-only · fix_plan debugger · paste /api/analyze response JSON
          </div>
        </div>
        <a
          href="/"
          style={{
            fontSize: "12px",
            fontWeight: 600,
            color: C.primary,
            textDecoration: "none",
          }}
        >
          ← Back to app
        </a>
      </div>

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "24px" }}>
        <div
          style={{
            border: `1.5px solid ${C.border}`,
            borderRadius: "10px",
            background: C.card,
            padding: "16px 18px",
            marginBottom: "16px",
          }}
        >
          <div
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: C.text,
              marginBottom: "8px",
            }}
          >
            Paste API response JSON
          </div>
          <textarea
            value={rawJson}
            onChange={(e) => setRawJson(e.target.value)}
            placeholder='Paste the full AnalysisResult JSON from Network → /api/analyze...'
            style={{
              width: "100%",
              minHeight: "140px",
              border: `1.5px solid ${C.border}`,
              borderRadius: "8px",
              padding: "10px 12px",
              fontFamily: C.mono,
              fontSize: "12px",
              lineHeight: 1.5,
              resize: "vertical",
              boxSizing: "border-box",
              background: "#fafafd",
              color: C.text,
            }}
          />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              rowGap: "8px",
              columnGap: "12px",
              marginTop: "10px",
            }}
          >
            <button
              type="button"
              onClick={handleParse}
              style={{
                border: "none",
                borderRadius: "8px",
                padding: "8px 18px",
                fontSize: "13px",
                fontWeight: 700,
                color: "#ffffff",
                background: C.primary,
                cursor: "pointer",
                boxShadow: `0 2px 0 ${C.floor}`,
              }}
            >
              Parse JSON
            </button>
            {parseError ? (
              <span style={{ fontSize: "13px", color: C.danger, fontWeight: 600 }}>
                {parseError}
              </span>
            ) : null}
          </div>
        </div>

        {result ? (
          <>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                rowGap: "8px",
                columnGap: "8px",
                marginBottom: "16px",
              }}
            >
              {(Object.keys(TAB_LABELS) as InspectorTab[]).map((tab) => {
                const isActive = activeTab === tab;
                return (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveTab(tab)}
                    style={{
                      border: isActive ? "none" : `1.5px solid ${C.border}`,
                      borderRadius: 999,
                      padding: "6px 14px",
                      fontSize: "12px",
                      fontWeight: 700,
                      cursor: "pointer",
                      background: isActive ? C.primary : C.card,
                      color: isActive ? "#ffffff" : C.text,
                    }}
                  >
                    {TAB_LABELS[tab]}
                  </button>
                );
              })}
            </div>

            <div
              style={{
                border: `1.5px solid ${C.border}`,
                borderRadius: "10px",
                background: C.card,
                padding: "18px 20px",
              }}
            >
              {tabContent}
            </div>
          </>
        ) : (
          <div
            style={{
              border: `1.5px dashed ${C.border}`,
              borderRadius: "10px",
              padding: "32px",
              textAlign: "center",
              color: C.muted,
              fontSize: "14px",
            }}
          >
            Paste and parse a response to inspect the fix_plan pipeline.
          </div>
        )}
      </div>
    </div>
  );
}
