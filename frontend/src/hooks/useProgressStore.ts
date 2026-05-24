import { useCallback, useState } from "react";

import type {
  CareerMemoryEntry,
  ProgressSnapshot,
  ProgressStore,
} from "../types";

const STORAGE_KEY = "rip_v2_progress_store";

const createEmptyStore = (): ProgressStore => ({
  snapshots: [],
  career_record: [],
  last_updated: new Date().toISOString(),
});

const loadStore = (): ProgressStore => {
  if (typeof window === "undefined") {
    return createEmptyStore();
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return createEmptyStore();
    }

    const parsed = JSON.parse(raw) as Partial<ProgressStore>;
    return {
      snapshots: Array.isArray(parsed.snapshots) ? parsed.snapshots : [],
      career_record: Array.isArray(parsed.career_record)
        ? parsed.career_record
        : [],
      last_updated:
        typeof parsed.last_updated === "string"
          ? parsed.last_updated
          : new Date().toISOString(),
    };
  } catch {
    return createEmptyStore();
  }
};

const saveStore = (store: ProgressStore): void => {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
};

export function useProgressStore() {
  const [store, setStore] = useState<ProgressStore>(() => loadStore());

  const load = useCallback((): ProgressStore => {
    const nextStore = loadStore();
    setStore(nextStore);
    return nextStore;
  }, []);

  const addSnapshot = useCallback((snap: ProgressSnapshot): void => {
    setStore((prev) => {
      const nextStore: ProgressStore = {
        ...prev,
        snapshots: [...prev.snapshots, snap],
        last_updated: new Date().toISOString(),
      };
      saveStore(nextStore);
      return nextStore;
    });
  }, []);

  const addCareerEntry = useCallback((entry: CareerMemoryEntry): void => {
    setStore((prev) => {
      if (prev.career_record.some((existing) => existing.id === entry.id)) {
        return prev;
      }

      const nextStore: ProgressStore = {
        ...prev,
        career_record: [...prev.career_record, entry],
        last_updated: new Date().toISOString(),
      };
      saveStore(nextStore);
      return nextStore;
    });
  }, []);

  const clearAll = useCallback((): void => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_KEY);
    }

    setStore(createEmptyStore());
  }, []);

  const snapshots = store.snapshots;
  const career_record = store.career_record;
  const initialScore = snapshots[0]?.ats_score ?? null;
  const currentScore = snapshots[snapshots.length - 1]?.ats_score ?? null;
  const scoreDelta =
    initialScore === null || currentScore === null
      ? null
      : currentScore - initialScore;
  const totalPatches =
    snapshots[snapshots.length - 1]?.patches_applied ?? 0;
  const totalCoaching =
    snapshots[snapshots.length - 1]?.coaching_answers ?? 0;

  return {
    load,
    addSnapshot,
    addCareerEntry,
    clearAll,
    snapshots,
    career_record,
    initialScore,
    currentScore,
    scoreDelta,
    totalPatches,
    totalCoaching,
  };
}
