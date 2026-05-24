import type { PriorityFix } from "../../types";

export type ApplyState = "idle" | "loading" | "applied" | "failed";

export interface CardHandlers {
  applyState: Record<string, ApplyState>;
  getBeforeText: (fix: PriorityFix) => string;
  getAfterText: (fix: PriorityFix) => string;
  getPatchDiff: (fix: PriorityFix) => { original: string; replacement: string } | null;
  scoreDelta: (fix: PriorityFix) => number;
  onApply: (fix: PriorityFix, fixKey: string) => Promise<void>;
  onUndo: (fix: PriorityFix, fixKey: string) => Promise<void>;
  onCoachingSubmit: (
    fix: PriorityFix,
    rawAnswer: string,
    fixKey: string
  ) => Promise<string | null>;
}
