import { useEffect } from "react";

import { useSSE } from "../../hooks/useSSE";
import { useResumeStore } from "../../store/useResumeStore";

const stepLabels = [
  "Reading your resume",
  "Analyzing gaps against JD",
  "Rewriting changed sections",
];

export default function AnalysisProgress() {
  const jobId = useResumeStore((state) => state.jobId);
  const isAnalyzing = useResumeStore((state) => state.isAnalyzing);
  const analysisError = useResumeStore((state) => state.analysisError);
  const setCurrentProgress = useResumeStore((state) => state.setCurrentProgress);
  const resetAnalysis = useResumeStore((state) => state.resetAnalysis);
  const { progress, error } = useSSE(jobId);
  const pct = Math.max(0, Math.min(100, progress?.pct ?? 0));
  const currentStep =
    progress?.status === "complete" ? stepLabels.length + 1 : progress?.step ?? 1;
  const displayError = error || analysisError;

  useEffect(() => {
    setCurrentProgress(progress);
  }, [progress, setCurrentProgress]);

  if (!isAnalyzing) {
    return null;
  }

  return (
    <section className="mx-auto max-w-[640px] bg-white px-6 pt-4 pb-10">
      <div className="mb-5 h-1.5 w-full rounded-full bg-[#f0ecff]">
        <div
          className="h-1.5 rounded-full bg-[#6c47ff] transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      <div>
        {stepLabels.map((label, index) => {
          const stepNumber = index + 1;
          const isComplete = stepNumber < currentStep;
          const isActive = stepNumber === currentStep;

          return (
            <div key={label} className="mb-4">
              <div className="flex items-center gap-3">
                <div
                  className={[
                    "flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold",
                    isComplete ? "bg-green-500 text-white" : "",
                    isActive ? "animate-pulse bg-[#6c47ff] text-white" : "",
                    !isComplete && !isActive ? "bg-gray-100 text-gray-400" : "",
                  ].join(" ")}
                >
                  {isComplete ? "✓" : stepNumber}
                </div>
                <span
                  className={[
                    "text-[14px]",
                    isComplete ? "text-gray-400 line-through" : "",
                    isActive ? "font-semibold text-[#1a1a2e]" : "",
                    !isComplete && !isActive ? "text-gray-400" : "",
                  ].join(" ")}
                >
                  {label}
                </span>
              </div>
              {isActive && progress?.label ? (
                <p className="ml-10 mt-0.5 text-[12px] italic text-[#6c47ff]">
                  {progress.label}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>

      {progress?.status === "complete" ? (
        <p className="mt-8 text-center text-[14px] font-semibold text-green-600">
          ✓ Complete
        </p>
      ) : null}

      {displayError ? (
        <div className="mt-8 rounded-lg border border-red-200 bg-red-50 p-4 text-center">
          <p className="mb-3 text-[14px] font-semibold text-red-700">
            Analysis failed. Please try again.
          </p>
          <p className="mb-4 text-[12px] text-red-600">{displayError}</p>
          <button
            type="button"
            className="rounded-lg bg-red-600 px-4 py-2 text-[13px] font-semibold text-white"
            onClick={resetAnalysis}
          >
            Retry
          </button>
        </div>
      ) : null}
    </section>
  );
}
