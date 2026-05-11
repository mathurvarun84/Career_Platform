import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";

import { analyzeResume } from "../../api/analyze";
import { TOP_COMPANIES, TOP_ROLES_BY_GROUP } from "../../constants/jdFetchData";
import type { FetchJDResult } from "../../types";
import { useWindowSize } from "../../hooks/useWindowSize";
import { useResumeStore } from "../../store/useResumeStore";
import { hydrateWithFallback } from "../../utils/analysisFallback";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];

const isAcceptedFile = (candidate: File): boolean => {
  const lowerName = candidate.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((extension) => lowerName.endsWith(extension));
};

function formatFetchTime(isoTimestamp: string): string {
  const fetchedAt = new Date(isoTimestamp);
  const diffMs = new Date().getTime() - fetchedAt.getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  if (Number.isNaN(fetchedAt.getTime())) {
    return "";
  }
  if (diffMin < 1) {
    return "just now";
  }
  if (diffMin < 60) {
    return `${diffMin} minute${diffMin === 1 ? "" : "s"} ago`;
  }

  return fetchedAt.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function extractDomain(url: string | null): string | null {
  if (!url) {
    return null;
  }

  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

interface FreshnessPillProps {
  fetchedAt: string | null;
  sourceUrl: string | null;
  isCached: boolean;
}

function FreshnessPill({ fetchedAt, sourceUrl, isCached }: FreshnessPillProps) {
  if (!fetchedAt) {
    return null;
  }

  const timeLabel = formatFetchTime(fetchedAt);
  const domainLabel = extractDomain(sourceUrl);
  const parts = [
    isCached ? "🗃️ From cache" : "📡 Fetched live",
    isCached && timeLabel ? `Originally fetched ${timeLabel}` : timeLabel,
    domainLabel,
  ]
    .filter(Boolean)
    .join(" · ");
  const pillStyle = isCached
    ? {
        background: "#fffbeb",
        border: "1px solid #fde68a",
        color: "#92400e",
      }
    : {
        background: "#f0fdf4",
        border: "1px solid #bbf7d0",
        color: "#166534",
      };

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        borderRadius: "6px",
        padding: "5px 10px",
        fontSize: "12px",
        fontWeight: 500,
        marginTop: "6px",
        ...pillStyle,
      }}
    >
      {parts}
    </div>
  );
}

export default function UploadZone() {
  const [file, setFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitProgress, setSubmitProgress] = useState(0);
  const [loadingStepIndex, setLoadingStepIndex] = useState(0);
  const [jdTab, setJdTab] = useState<"paste" | "fetch">("paste");
  const [company, setCompany] = useState("");
  const [customCompany, setCustomCompany] = useState("");
  const [role, setRole] = useState("");
  const [customRole, setCustomRole] = useState("");
  const [fetchStatus, setFetchStatus] = useState<
    "idle" | "loading" | "found" | "not_found" | "multiple" | "error"
  >("idle");
  const [fetchResult, setFetchResult] = useState<FetchJDResult | null>(null);
  const [jdLoadedFromFetch, setJdLoadedFromFetch] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { isMobile, isTablet } = useWindowSize();
  const jdFetchUrl = `${import.meta.env.VITE_API_URL ?? ""}/api/fetch-jd`;
  const loadingSteps = [
    "Analyzing your resume...",
    "Running recruiter simulation...",
    "Calculating market position...",
  ];

  const setJobId = useResumeStore((state) => state.setJobId);
  const setAnalysisResult = useResumeStore((state) => state.setAnalysisResult);
  const setFallbackInfo = useResumeStore((state) => state.setFallbackInfo);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const setIsAnalyzing = useResumeStore((state) => state.setIsAnalyzing);
  const setIsLoading = useResumeStore((state) => state.setIsLoading);
  const setAnalysisError = useResumeStore((state) => state.setAnalysisError);
  const setCurrentProgress = useResumeStore((state) => state.setCurrentProgress);
  const mergePartialResult = useResumeStore((state) => state.mergePartialResult);

  useEffect(() => {
    if (!isSubmitting) {
      return;
    }

    const progressTimer = window.setInterval(() => {
      setSubmitProgress((prev) => Math.min(90, prev + 3));
    }, 270);
    const copyTimer = window.setInterval(() => {
      setLoadingStepIndex((prev) => (prev + 1) % loadingSteps.length);
    }, 3000);

    return () => {
      window.clearInterval(progressTimer);
      window.clearInterval(copyTimer);
    };
  }, [isSubmitting]);

  const validateAndSetFile = (candidate: File | null): void => {
    setSubmitError(null);
    if (!candidate) {
      setFile(null);
      return;
    }
    if (!isAcceptedFile(candidate)) {
      setSubmitError("Please upload a PDF, DOCX, or TXT resume.");
      return;
    }
    if (candidate.size > MAX_FILE_SIZE_BYTES) {
      setSubmitError("Resume must be under 5MB.");
      return;
    }
    setFile(candidate);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>): void => {
    validateAndSetFile(event.target.files?.[0] ?? null);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (): void => {
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragging(false);
    validateAndSetFile(event.dataTransfer.files[0] ?? null);
  };

  const handleSubmit = async (): Promise<void> => {
    setSubmitError(null);
    setAnalysisError(null);
    setCurrentProgress(null);
    setFallbackInfo({});

    if (!file) {
      setSubmitError("Please upload your resume before analyzing.");
      return;
    }

    try {
      setIsSubmitting(true);
      setSubmitProgress(0);
      setLoadingStepIndex(0);
      setIsLoading(true);
      const result = await analyzeResume(file, jdText, {
        onJobCreated: (jobId) => {
          setJobId(jobId);
          setIsAnalyzing(true);
        },
        onProgress: (progress) => {
          setCurrentProgress(progress);
        },
        onPartial: (partial) => {
          mergePartialResult(partial);
        },
      });
      const hydrated = hydrateWithFallback(result);
      setSubmitProgress(100);
      setAnalysisResult(hydrated.analysis);
      setFallbackInfo(hydrated.debugByTab);
      setJobId(hydrated.analysis.job_id);
      setIsAnalyzing(false);
      setActiveTab("overview");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to start analysis.";
      setSubmitError(message);
      setAnalysisError(message);
    } finally {
      window.setTimeout(() => {
        setIsSubmitting(false);
        setSubmitProgress(0);
      }, 400);
      setIsLoading(false);
    }
  };

  const effectiveCompany = company === "other" ? customCompany : company;
  const effectiveRole = role === "other" ? customRole : role;
  const canFetch =
    effectiveCompany.trim().length > 0 && effectiveRole.trim().length > 0;
  const hasSelectedCompany = effectiveCompany.trim().length > 0;
  const hasSelectedRole = effectiveRole.trim().length > 0;

  const handleFetchJD = async (targetRole?: string): Promise<void> => {
    const requestedCompany = effectiveCompany.trim();
    const requestedRole = (targetRole ?? effectiveRole).trim();
    if (!requestedCompany || !requestedRole) {
      return;
    }

    setFetchStatus("loading");
    setFetchResult(null);
    setJdLoadedFromFetch(false);

    try {
      const response = await fetch(jdFetchUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: requestedCompany, role: requestedRole }),
      });
      const data = (await response.json()) as FetchJDResult;
      setFetchResult(data);
      setFetchStatus(data.status);

      if (data.status === "found" && data.jd_text) {
        setJdText(data.jd_text);
      }
    } catch {
      setFetchStatus("error");
      setJdLoadedFromFetch(false);
      setFetchResult({
        status: "error",
        jd_text: null,
        source_url: null,
        fetched_at: null,
        is_cached: false,
        company: requestedCompany,
        role: requestedRole,
        error_message: "Network error. Please try again.",
      });
    }
  };

  return (
    <div
      style={{
        maxWidth: "960px",
        margin: "0 auto",
        padding: isMobile ? "40px 16px 48px" : "40px 32px 48px",
      }}
    >
      {isSubmitting && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            height: "3px",
            zIndex: 100,
            width: `${submitProgress}%`,
            background: "linear-gradient(90deg, #6366f1, #7c3aed)",
            transition: "width 0.2s ease",
          }}
        />
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={handleFileChange}
        className="hidden"
      />

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexWrap: "wrap",
          gap: "12px",
          marginBottom: "36px",
        }}
      >
        {([
          { icon: "🎯", label: "ATS Score Analysis", bg: "#fef2f2" },
          { icon: "👥", label: "Recruiter View", bg: "#eff6ff" },
          { icon: "✦", label: "Actionable Fixes", bg: "#fefce8" },
          { icon: "📊", label: "JD Matching", bg: "#f0fdf4" },
        ] as const).map(({ icon, label, bg }) => (
          <div
            key={label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: "999px",
              padding: "8px 18px",
              fontSize: "13px",
              fontWeight: 700,
              color: "#374151",
              boxShadow: "0 2px 0 #d1d5db, 0 3px 8px rgba(0,0,0,0.08)",
              userSelect: "none",
            }}
          >
            <span
              style={{
                width: "22px",
                height: "22px",
                borderRadius: "50%",
                background: bg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "12px",
                flexShrink: 0,
              }}
            >
              {icon}
            </span>
            {label}
          </div>
        ))}
      </div>

      {submitError && (
        <div
          style={{
            background: "#fef2f2",
            border: "1.5px solid #fecaca",
            borderRadius: "12px",
            padding: "12px 14px",
            marginBottom: "16px",
            color: "#dc2626",
            fontSize: "13px",
            lineHeight: 1.55,
          }}
        >
          <span style={{ fontWeight: 700 }}>Unable to analyze resume: </span>
          {submitError}
        </div>
      )}

      <div
        style={{
          background: "#ffffff",
          border: "1.5px solid #e5e7eb",
          borderRadius: "24px",
          padding: "40px",
          boxShadow: "0 4px 0 #e5e7eb, 0 8px 24px rgba(0,0,0,0.06)",
          marginBottom: "20px",
        }}
      >
        {isSubmitting && (
          <div style={{ marginBottom: "18px" }}>
            <div
              style={{
                height: "8px",
                background: "#f3f4f6",
                borderRadius: "999px",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${submitProgress}%`,
                  height: "100%",
                  background: "linear-gradient(90deg, #6366f1, #7c3aed)",
                  transition: "width 0.25s ease",
                }}
              />
            </div>
            <div style={{ marginTop: "8px", fontSize: "13px", color: "#6b7280" }}>
              {loadingSteps[loadingStepIndex]}
            </div>
          </div>
        )}
        <div
          style={{
            display: isTablet ? "flex" : "grid",
            flexDirection: isTablet ? "column" : undefined,
            gridTemplateColumns: isTablet ? undefined : "1fr 1fr",
            gap: isTablet ? "16px" : "40px",
          }}
        >
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "14px",
                marginBottom: "18px",
              }}
            >
              <div
                style={{
                  width: "42px",
                  height: "42px",
                  borderRadius: "12px",
                  background: "#eef2ff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                  <rect
                    x="4"
                    y="2"
                    width="14"
                    height="18"
                    rx="2.5"
                    fill="#6366f1"
                    fillOpacity=".18"
                    stroke="#6366f1"
                    strokeWidth="1.5"
                  />
                  <rect x="7" y="7.5" width="8" height="1.8" rx=".9" fill="#6366f1" />
                  <rect x="7" y="11" width="8" height="1.8" rx=".9" fill="#6366f1" />
                  <rect x="7" y="14.5" width="5" height="1.8" rx=".9" fill="#6366f1" />
                </svg>
              </div>
              <div>
                <div
                  style={{
                    fontSize: "17px",
                    fontWeight: 700,
                    color: "#111827",
                    letterSpacing: "-0.01em",
                  }}
                >
                  Upload Resume
                </div>
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 400,
                    color: "#6b7280",
                    marginTop: "2px",
                  }}
                >
                  PDF, DOC, or DOCX
                </div>
              </div>
            </div>

            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              style={{
                border: `2px dashed ${isDragging ? "#6366f1" : file ? "#6366f1" : "#d1d5db"}`,
                borderRadius: "16px",
                background: isDragging ? "#f5f3ff" : file ? "#f0fdf4" : "#fafafa",
                cursor: "pointer",
                minHeight: "190px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "32px 24px",
                textAlign: "center",
                transition: "all 0.2s",
              }}
            >
              {file ? (
                <>
                  <div
                    style={{
                      width: "48px",
                      height: "48px",
                      borderRadius: "50%",
                      background: "#dcfce7",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "22px",
                      fontWeight: 700,
                      color: "#16a34a",
                      marginBottom: "12px",
                    }}
                  >
                    ✓
                  </div>
                  <div
                    style={{
                      fontSize: "15px",
                      fontWeight: 700,
                      color: "#111827",
                      wordBreak: "break-all",
                      padding: "0 8px",
                      marginBottom: "4px",
                    }}
                  >
                    {file.name}
                  </div>
                  <div style={{ fontSize: "13px", color: "#6b7280", marginBottom: "10px" }}>
                    {(file.size / 1024).toFixed(1)} KB
                  </div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      fileInputRef.current?.click();
                    }}
                    style={{
                      fontSize: "13px",
                      fontWeight: 700,
                      color: "#6366f1",
                      background: "transparent",
                      border: "none",
                      cursor: "pointer",
                    }}
                  >
                    Change file
                  </button>
                </>
              ) : (
                <>
                  <div
                    style={{
                      width: "48px",
                      height: "48px",
                      borderRadius: "50%",
                      background: "#f0f0f8",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      marginBottom: "14px",
                    }}
                  >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path
                        d="M12 16V6M12 6L8 10M12 6L16 10"
                        stroke="#6b7280"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M3 18v1.5A1.5 1.5 0 004.5 21h15A1.5 1.5 0 0021 19.5V18"
                        stroke="#6b7280"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                      />
                    </svg>
                  </div>
                  <div
                    style={{
                      fontSize: "16px",
                      fontWeight: 700,
                      color: "#111827",
                      marginBottom: "6px",
                    }}
                  >
                    Drop your resume here
                  </div>
                  <div style={{ fontSize: "13px", color: "#9ca3af" }}>or click to browse</div>
                </>
              )}
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                background: "#eef2ff",
                borderRadius: "12px",
                padding: "13px 15px",
                marginTop: "14px",
              }}
            >
              <div
                style={{
                  width: "18px",
                  height: "18px",
                  borderRadius: "50%",
                  background: "#c7d2fe",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "10px",
                  fontWeight: 800,
                  color: "#3730a3",
                  flexShrink: 0,
                  marginTop: "1px",
                }}
              >
                i
              </div>
              <p style={{ fontSize: "12.5px", color: "#4b5563", lineHeight: 1.55, margin: 0 }}>
                Your resume is analyzed locally and securely. We don't store your data.
              </p>
            </div>
          </div>

          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "14px",
                marginBottom: "18px",
              }}
            >
              <div
                style={{
                  width: "42px",
                  height: "42px",
                  borderRadius: "12px",
                  background: "#f5f0ff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                  <path
                    d="M4 11h14M4 7h9M4 15h7"
                    stroke="#7c3aed"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                  <circle cx="17.5" cy="7" r="3.5" fill="#fbbf24" />
                  <path
                    d="M16 7l1.2 1.2L19 6"
                    stroke="white"
                    strokeWidth="1.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <div>
                <div
                  style={{
                    fontSize: "17px",
                    fontWeight: 700,
                    color: "#111827",
                    letterSpacing: "-0.01em",
                  }}
                >
                  Job Description
                </div>
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 400,
                    color: "#6b7280",
                    marginTop: "2px",
                  }}
                >
                  Paste the target role
                </div>
              </div>
            </div>

            <div
              style={{
                border: "1.5px solid #e5e7eb",
                borderRadius: "10px",
                overflow: "hidden",
                display: "flex",
                marginBottom: "12px",
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setJdTab("paste");
                  setFetchResult(null);
                  setJdLoadedFromFetch(false);
                }}
                style={{
                  flex: 1,
                  background: jdTab === "paste" ? "#6366f1" : "#ffffff",
                  color: jdTab === "paste" ? "#ffffff" : "#6b7280",
                  fontSize: "13px",
                  fontWeight: 600,
                  padding: "9px 14px",
                  border: "none",
                  borderRight: "1px solid #e5e7eb",
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                📋 Paste JD manually
              </button>
              <button
                type="button"
                onClick={() => setJdTab("fetch")}
                style={{
                  flex: 1,
                  background: jdTab === "fetch" ? "#6366f1" : "#ffffff",
                  color: jdTab === "fetch" ? "#ffffff" : "#6b7280",
                  fontSize: "13px",
                  fontWeight: 600,
                  padding: "9px 14px",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                🔍 Auto-fetch by company &amp; role
              </button>
            </div>

            {jdTab === "paste" && (
              <>
                <textarea
                  value={jdText}
                  onChange={(event) => {
                    const nextText = event.target.value;
                    setJdText(nextText);
                    if (!nextText.trim()) {
                      setFetchResult(null);
                      setJdLoadedFromFetch(false);
                    }
                  }}
                  placeholder="Paste the job description here..."
                  rows={8}
                  style={{
                    width: "100%",
                    border: "1.5px solid #e5e7eb",
                    borderRadius: "14px",
                    padding: "15px 18px",
                    fontSize: "14px",
                    fontFamily: "inherit",
                    color: "#374151",
                    lineHeight: 1.65,
                    background: "#ffffff",
                    resize: "none",
                    outline: "none",
                    display: "block",
                    boxSizing: "border-box",
                    minHeight: "190px",
                  }}
                  onFocus={(event) => {
                    event.currentTarget.style.borderColor = "#6366f1";
                  }}
                  onBlur={(event) => {
                    event.currentTarget.style.borderColor = "#e5e7eb";
                  }}
                  className="placeholder:text-[#c4b5fd]"
                />

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: "8px",
                    padding: "0 2px",
                  }}
                >
                  <span style={{ fontSize: "12px", color: "#9ca3af" }}>{jdText.length} characters</span>
                  <span style={{ fontSize: "12px", color: "#9ca3af" }}>Minimum 50 characters</span>
                </div>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    background: "#faf5ff",
                    border: "1px solid #ede9fe",
                    borderRadius: "10px",
                    padding: "11px 15px",
                    marginTop: "12px",
                  }}
                >
                  <span style={{ fontSize: "15px", color: "#7c3aed", flexShrink: 0 }}>✦</span>
                  <span style={{ fontSize: "13px", fontWeight: 600, fontStyle: "italic", color: "#7c3aed" }}>
                    The more detailed the job description, the better the analysis.
                  </span>
                </div>
              </>
            )}

            {jdTab === "fetch" && (
              <div
                style={{
                  background: "#faf5ff",
                  border: "1.5px solid #ede9fe",
                  borderRadius: "14px",
                  padding: "16px",
                }}
              >
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
                    gap: "12px",
                    marginBottom: "12px",
                  }}
                >
                  <div>
                    <label
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#6366f1",
                        letterSpacing: "0.5px",
                        textTransform: "uppercase",
                        marginBottom: "5px",
                        display: "block",
                      }}
                    >
                      Company
                    </label>
                    <select
                      value={company}
                      onChange={(event) => {
                        setCompany(event.target.value);
                        setCustomCompany("");
                      }}
                      style={{
                        width: "100%",
                        border: hasSelectedCompany ? "1.5px solid #6366f1" : "1.5px solid #e5e7eb",
                        borderRadius: "10px",
                        padding: "9px 12px",
                        fontSize: "13px",
                        fontFamily: "inherit",
                        color: company ? "#374151" : "#9ca3af",
                        background: hasSelectedCompany ? "#eef2ff" : "#ffffff",
                        outline: "none",
                        boxShadow: hasSelectedCompany ? "0 0 0 3px rgba(99,102,241,0.12)" : "none",
                      }}
                      onFocus={(event) => {
                        event.currentTarget.style.borderColor = "#6366f1";
                      }}
                      onBlur={(event) => {
                        event.currentTarget.style.borderColor = "#e5e7eb";
                      }}
                    >
                      <option value="">— Select company —</option>
                      <optgroup label="Top Indian Companies">
                        {TOP_COMPANIES.map((companyOption) => (
                          <option key={companyOption} value={companyOption}>
                            {companyOption}
                          </option>
                        ))}
                      </optgroup>
                      <option value="other">Other (type manually)</option>
                    </select>
                    {hasSelectedCompany && (
                      <div
                        style={{
                          marginTop: "8px",
                          display: "inline-flex",
                          alignItems: "center",
                          background: "#eef2ff",
                          color: "#4338ca",
                          border: "1px solid #c7d2fe",
                          borderRadius: "999px",
                          padding: "5px 10px",
                          fontSize: "12px",
                          fontWeight: 700,
                        }}
                      >
                        Selected: {effectiveCompany}
                      </div>
                    )}
                    {company === "other" && (
                      <input
                        type="text"
                        value={customCompany}
                        onChange={(event) => setCustomCompany(event.target.value)}
                        placeholder="Type company name..."
                        style={{
                          width: "100%",
                          marginTop: "8px",
                          border: "1.5px solid #e5e7eb",
                          borderRadius: "10px",
                          padding: "9px 12px",
                          fontSize: "13px",
                          fontFamily: "inherit",
                          color: "#374151",
                          background: "#ffffff",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                        onFocus={(event) => {
                          event.currentTarget.style.borderColor = "#6366f1";
                        }}
                        onBlur={(event) => {
                          event.currentTarget.style.borderColor = "#e5e7eb";
                        }}
                      />
                    )}
                  </div>

                  <div>
                    <label
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        color: "#6366f1",
                        letterSpacing: "0.5px",
                        textTransform: "uppercase",
                        marginBottom: "5px",
                        display: "block",
                      }}
                    >
                      Role
                    </label>
                    <select
                      value={role}
                      onChange={(event) => {
                        setRole(event.target.value);
                        setCustomRole("");
                      }}
                      style={{
                        width: "100%",
                        border: hasSelectedRole ? "1.5px solid #6366f1" : "1.5px solid #e5e7eb",
                        borderRadius: "10px",
                        padding: "9px 12px",
                        fontSize: "13px",
                        fontFamily: "inherit",
                        color: role ? "#374151" : "#9ca3af",
                        background: hasSelectedRole ? "#eef2ff" : "#ffffff",
                        outline: "none",
                        boxShadow: hasSelectedRole ? "0 0 0 3px rgba(99,102,241,0.12)" : "none",
                      }}
                      onFocus={(event) => {
                        event.currentTarget.style.borderColor = "#6366f1";
                      }}
                      onBlur={(event) => {
                        event.currentTarget.style.borderColor = "#e5e7eb";
                      }}
                    >
                      <option value="">— Select role —</option>
                      {Object.entries(TOP_ROLES_BY_GROUP).map(([group, roles]) => (
                        <optgroup key={group} label={group}>
                          {roles.map((roleOption) => (
                            <option key={roleOption} value={roleOption}>
                              {roleOption}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                      <option value="other">Other (type manually)</option>
                    </select>
                    {hasSelectedRole && (
                      <div
                        style={{
                          marginTop: "8px",
                          display: "inline-flex",
                          alignItems: "center",
                          background: "#eef2ff",
                          color: "#4338ca",
                          border: "1px solid #c7d2fe",
                          borderRadius: "999px",
                          padding: "5px 10px",
                          fontSize: "12px",
                          fontWeight: 700,
                        }}
                      >
                        Selected: {effectiveRole}
                      </div>
                    )}
                    {role === "other" && (
                      <input
                        type="text"
                        value={customRole}
                        onChange={(event) => setCustomRole(event.target.value)}
                        placeholder="Type role title..."
                        style={{
                          width: "100%",
                          marginTop: "8px",
                          border: "1.5px solid #e5e7eb",
                          borderRadius: "10px",
                          padding: "9px 12px",
                          fontSize: "13px",
                          fontFamily: "inherit",
                          color: "#374151",
                          background: "#ffffff",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                        onFocus={(event) => {
                          event.currentTarget.style.borderColor = "#6366f1";
                        }}
                        onBlur={(event) => {
                          event.currentTarget.style.borderColor = "#e5e7eb";
                        }}
                      />
                    )}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    void handleFetchJD();
                  }}
                  disabled={!canFetch || fetchStatus === "loading"}
                  style={{
                    width: "100%",
                    background: canFetch && fetchStatus !== "loading" ? "#6366f1" : "#f3f4f6",
                    color: canFetch && fetchStatus !== "loading" ? "#ffffff" : "#9ca3af",
                    borderRadius: "10px",
                    padding: "10px 18px",
                    fontSize: "13px",
                    fontWeight: 700,
                    border: "none",
                    cursor: canFetch && fetchStatus !== "loading" ? "pointer" : "not-allowed",
                    boxShadow:
                      canFetch && fetchStatus !== "loading"
                        ? "0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.25)"
                        : "0 3px 0 #d1d5db",
                    fontFamily: "inherit",
                    transition: "transform 0.1s",
                  }}
                  onMouseDown={(event) => {
                    if (canFetch) {
                      event.currentTarget.style.transform = "translateY(3px)";
                    }
                  }}
                  onMouseUp={(event) => {
                    event.currentTarget.style.transform = "translateY(0)";
                  }}
                >
                  {fetchStatus === "loading" ? "⏳ Searching..." : "🔍 Find Job Description"}
                </button>

                <div
                  style={{
                    fontSize: "12.5px",
                    color: "#7c3aed",
                    fontStyle: "italic",
                    marginTop: "8px",
                    textAlign: "center",
                  }}
                >
                  {canFetch
                    ? `Will search for "${effectiveRole}" at ${effectiveCompany}`
                    : "Select company and role to auto-fetch the JD from the web"}
                </div>

                {fetchStatus === "loading" && (
                  <div
                    style={{
                      background: "#faf5ff",
                      border: "1.5px solid #ede9fe",
                      borderRadius: "10px",
                      padding: "12px 14px",
                      marginTop: "12px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <style>{`
                      @keyframes jdDotPulse {
                        0%, 100% { transform: scale(0.6); opacity: 0.5; }
                        50% { transform: scale(1); opacity: 1; }
                      }
                    `}</style>
                    {[0, 0.2, 0.4].map((delay, index) => (
                      <span
                        key={index}
                        style={{
                          width: "6px",
                          height: "6px",
                          borderRadius: "50%",
                          background: "#6366f1",
                          display: "inline-block",
                          animation: `jdDotPulse 1.2s ease-in-out ${delay}s infinite`,
                        }}
                      />
                    ))}
                    <span style={{ fontSize: "13px", color: "#374151", fontWeight: 500 }}>
                      Searching for JD... checking {effectiveCompany} careers page and job boards
                    </span>
                  </div>
                )}

                {fetchStatus === "found" && fetchResult && (
                  <div
                    style={{
                      background: "#f0fdf4",
                      border: "1.5px solid #86efac",
                      borderRadius: "10px",
                      padding: "12px 14px",
                      marginTop: "12px",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827", marginBottom: "4px" }}>
                      ✅ JD Found — {fetchResult.company} · {fetchResult.role}
                    </div>
                    {fetchResult.source_url && (
                      <div style={{ fontSize: "11px", color: "#6b7280", marginBottom: "8px" }}>
                        Source:{" "}
                        <a
                          href={fetchResult.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: "#6366f1" }}
                        >
                          {fetchResult.source_url.replace(/^https?:\/\//, "").split("/")[0]}
                        </a>
                      </div>
                    )}
                    {fetchResult.jd_text && (
                      <div
                        style={{
                          fontSize: "12px",
                          color: "#374151",
                          lineHeight: 1.55,
                          background: "#ffffff",
                          borderRadius: "8px",
                          padding: "10px 12px",
                          border: "1px solid #e5e7eb",
                          maxHeight: "180px",
                          overflowY: "auto",
                          whiteSpace: "pre-wrap",
                          marginBottom: "10px",
                        }}
                      >
                        {fetchResult.jd_text}
                      </div>
                    )}
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        type="button"
                        onClick={() => {
                          if (fetchResult.jd_text) {
                            setJdText(fetchResult.jd_text);
                          }
                          setFetchStatus("found");
                          setJdLoadedFromFetch(true);
                        }}
                        style={{
                          background: "#16a34a",
                          color: "#ffffff",
                          borderRadius: "8px",
                          padding: "7px 14px",
                          fontSize: "12px",
                          fontWeight: 700,
                          border: "none",
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        ✓ Use This JD
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setFetchStatus("idle");
                          setFetchResult(null);
                          setJdLoadedFromFetch(false);
                        }}
                        style={{
                          background: "#ffffff",
                          color: "#6b7280",
                          border: "1.5px solid #e5e7eb",
                          borderRadius: "8px",
                          padding: "6px 12px",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        🔄 Search Again
                      </button>
                    </div>
                  </div>
                )}

                {fetchStatus === "multiple" && fetchResult?.alternatives && (
                  <div
                    style={{
                      background: "#fffbeb",
                      border: "1.5px solid #fde68a",
                      borderRadius: "10px",
                      padding: "12px 14px",
                      marginTop: "12px",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827", marginBottom: "8px" }}>
                      ⚠️ Multiple roles found at {fetchResult.company}
                    </div>
                    <div style={{ fontSize: "12px", color: "#6b7280", marginBottom: "10px" }}>
                      Which level matches your target?
                    </div>
                    {fetchResult.alternatives.map((alt, index) => (
                      <div
                        key={`${alt.title}-${index}`}
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e5e7eb",
                          borderRadius: "8px",
                          padding: "10px 12px",
                          marginBottom: "8px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <div>
                          <div style={{ fontSize: "13px", fontWeight: 600, color: "#111827" }}>{alt.title}</div>
                          <div style={{ fontSize: "11px", color: "#6b7280" }}>{alt.level}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            void handleFetchJD(alt.title);
                          }}
                          style={{
                            background: "#6366f1",
                            color: "#ffffff",
                            borderRadius: "6px",
                            padding: "5px 10px",
                            fontSize: "12px",
                            fontWeight: 600,
                            border: "none",
                            cursor: "pointer",
                            fontFamily: "inherit",
                          }}
                        >
                          →
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {fetchStatus === "not_found" && fetchResult && (
                  <div
                    style={{
                      background: "#fef2f2",
                      border: "1.5px solid #fecaca",
                      borderRadius: "10px",
                      padding: "12px 14px",
                      marginTop: "12px",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827", marginBottom: "4px" }}>
                      ❌ JD not found
                    </div>
                    <div style={{ fontSize: "12px", color: "#6b7280", marginBottom: "10px" }}>
                      Couldn't find an active posting for "{fetchResult.role}" at "{fetchResult.company}".
                      Searched official careers page, LinkedIn, Naukri, and Indeed — no active posting found.
                    </div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        type="button"
                        onClick={() => {
                          setFetchStatus("idle");
                          setFetchResult(null);
                          setJdLoadedFromFetch(false);
                        }}
                        style={{
                          background: "#ffffff",
                          color: "#6b7280",
                          border: "1.5px solid #e5e7eb",
                          borderRadius: "8px",
                          padding: "6px 12px",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        🔄 Try Again
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setJdTab("paste");
                          setFetchResult(null);
                          setJdLoadedFromFetch(false);
                        }}
                        style={{
                          background: "#ffffff",
                          color: "#6b7280",
                          border: "1.5px solid #e5e7eb",
                          borderRadius: "8px",
                          padding: "6px 12px",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        📋 Paste JD Manually
                      </button>
                    </div>
                  </div>
                )}

                {fetchStatus === "error" && fetchResult && (
                  <div
                    style={{
                      background: "#fef2f2",
                      border: "1.5px solid #fecaca",
                      borderRadius: "10px",
                      padding: "12px 14px",
                      marginTop: "12px",
                    }}
                  >
                    <div style={{ fontSize: "13px", fontWeight: 700, color: "#111827", marginBottom: "4px" }}>
                      ❌ Something went wrong
                    </div>
                    <div style={{ fontSize: "12px", color: "#6b7280", marginBottom: "10px" }}>
                      {fetchResult.error_message || "An unexpected error occurred."}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setFetchStatus("idle");
                        setFetchResult(null);
                        setJdLoadedFromFetch(false);
                      }}
                      style={{
                        background: "#ffffff",
                        color: "#6b7280",
                        border: "1.5px solid #e5e7eb",
                        borderRadius: "8px",
                        padding: "6px 12px",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        fontFamily: "inherit",
                      }}
                    >
                      🔄 Try Again
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div style={{ borderTop: "1.5px solid #f3f4f6", marginTop: "28px", paddingTop: "24px" }}>
          {jdText && jdText.length > 100 && (
            <div
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "#16a34a",
                textAlign: "center",
                marginBottom: "8px",
                marginTop: "8px",
              }}
            >
              ✓ JD loaded · Ready to analyze
            </div>
          )}
          {jdLoadedFromFetch && fetchResult?.status === "found" && (
            <div style={{ marginBottom: "8px", textAlign: "center" }}>
              <FreshnessPill
                fetchedAt={fetchResult.fetched_at}
                sourceUrl={fetchResult.source_url}
                isCached={fetchResult.is_cached}
              />
            </div>
          )}
          <button
            type="button"
            onClick={() => {
              void handleSubmit();
            }}
            disabled={!file || isSubmitting}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "10px",
              background: file && !isSubmitting ? "#6366f1" : "#f3f4f6",
              color: file && !isSubmitting ? "#ffffff" : "#9ca3af",
              border: "none",
              borderRadius: "14px",
              padding: "17px",
              fontSize: "16px",
              fontWeight: 700,
              cursor: file && !isSubmitting ? "pointer" : "not-allowed",
              boxShadow:
                file && !isSubmitting
                  ? "0 4px 0 #4338ca, 0 6px 16px rgba(99,102,241,0.25)"
                  : "0 4px 0 #d1d5db",
              transition: "transform 0.1s",
              letterSpacing: "-0.01em",
            }}
          >
            <span style={{ fontSize: "17px" }}>✦</span>
            {isSubmitting ? "Analyzing..." : "Analyze Resume"}
          </button>

          <p
            style={{
              fontSize: "12.5px",
              color: "#9ca3af",
              textAlign: "center",
              marginTop: "12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "6px",
            }}
          >
            <span style={{ fontSize: "14px" }}>ⓘ</span>
            {file ? "Click Analyze Resume to continue" : "Please upload a resume to continue"}
          </p>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "1fr" : isTablet ? "repeat(2, 1fr)" : "repeat(3, 1fr)",
          gap: "16px",
          marginTop: "20px",
        }}
      >
        {([
          {
            icon: "⚡",
            bg: "#fff7ed",
            title: "Instant Analysis",
            desc: "Get results in seconds with AI-powered insights",
          },
          {
            icon: "🎯",
            bg: "#fef2f2",
            title: "Recruiter POV",
            desc: "See exactly how recruiters evaluate your resume",
          },
          {
            icon: "📈",
            bg: "#f0fdf4",
            title: "Actionable Fixes",
            desc: "Step-by-step improvements to boost your score",
          },
        ] as const).map(({ icon, bg, title, desc }) => (
          <div
            key={title}
            style={{
              background: "#ffffff",
              border: "1.5px solid #e5e7eb",
              borderRadius: "18px",
              padding: "28px 24px",
              boxShadow: "0 3px 0 #e5e7eb, 0 5px 16px rgba(0,0,0,0.05)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "12px",
                background: bg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "22px",
                marginBottom: "16px",
              }}
            >
              {icon}
            </div>
            <div
              style={{
                fontSize: "15px",
                fontWeight: 700,
                color: "#111827",
                marginBottom: "6px",
                letterSpacing: "-0.01em",
              }}
            >
              {title}
            </div>
            <div style={{ fontSize: "13px", color: "#6b7280", lineHeight: 1.55 }}>
              {desc}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
