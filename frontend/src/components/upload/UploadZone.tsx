/* eslint-disable @typescript-eslint/no-unused-vars */
// @ts-nocheck
import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";

import { fetchUsageLimit } from "../../api/analyze";
import UpgradeModal from "../auth/UpgradeModal";
import { TOP_COMPANIES, TOP_ROLES_BY_GROUP } from "../../constants/jdFetchData";
import type { FetchJDResult } from "../../types";
import { useWindowSize } from "../../hooks/useWindowSize";
import { supabase } from "../../lib/supabase";
import { useResumeStore } from "../../store/useResumeStore";
import { T } from "../../tokens";
import { FeaturePulseCard } from "../feedback/FeaturePulseCard";

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

// Preserved for JD fetch tab (future)
function _extractDomain(url: string | null): string | null {
  if (!url) {
    return null;
  }

  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

interface UploadZoneProps {
  onBeginAnalysis: (file: File, jdText: string) => void;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function UploadZone({ onBeginAnalysis }: UploadZoneProps) {
  const pendingAnalyseRole = useResumeStore((s) => s.pendingAnalyseRole);
  const setPendingAnalyseRole = useResumeStore((s) => s.setPendingAnalyseRole);

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
  const [upgradeModalOpen, setUpgradeModalOpen] = useState(false);
  const [upgradeData, setUpgradeData] = useState<{
    uploadsThisMonth: number;
    limit: number;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { isMobile, isTablet } = useWindowSize();

  useEffect(() => {
    if (!pendingAnalyseRole) {
      return;
    }
    setRole("other");
    setCustomRole(pendingAnalyseRole);
    setJdTab("fetch");
    setJdText(
      `Job Description — ${pendingAnalyseRole}\n\nPaste or fetch the full JD for this role to run a targeted analysis.`
    );
    setPendingAnalyseRole(null);
  }, [pendingAnalyseRole, setPendingAnalyseRole]);

  const jdFetchUrl = `${import.meta.env.VITE_API_URL ?? ""}/api/fetch-jd`;
  const _loadingSteps = [
    "Analyzing your resume...",
    "Running recruiter simulation...",
    "Calculating market position...",
  ];

  const setAnalysisResult = useResumeStore((state) => state.setAnalysisResult);
  const setFallbackInfo = useResumeStore((state) => state.setFallbackInfo);
  const setIsAnalyzing = useResumeStore((state) => state.setIsAnalyzing);
  const setIsLoading = useResumeStore((state) => state.setIsLoading);
  const setIsFullAnalysisReady = useResumeStore(
    (state) => state.setIsFullAnalysisReady
  );
  const setAnalysisError = useResumeStore((state) => state.setAnalysisError);
  const setCurrentProgress = useResumeStore((state) => state.setCurrentProgress);
  const feedbackState = useResumeStore((state) => state.feedbackState);
  const showFeedbackMoment = useResumeStore((state) => state.showFeedbackMoment);
  const clearActiveMoment = useResumeStore((state) => state.clearActiveMoment);

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

    const { data: sessionData, error: sessionError } =
      await supabase.auth.getSession();
    if (sessionError || !sessionData.session?.access_token) {
      setSubmitError("Sign in to run analysis.");
      return;
    }

    setIsSubmitting(true);
    try {
      const usage = await fetchUsageLimit(sessionData.session.access_token);
      if (!usage.allowed) {
        setUpgradeData({
          uploadsThisMonth: usage.uploads_this_month,
          limit: usage.limit,
        });
        setUpgradeModalOpen(true);
        return;
      }

      setSubmitProgress(0);
      setLoadingStepIndex(0);
      setIsFullAnalysisReady(false);
      setAnalysisResult(null);
      setIsLoading(true);
      setIsAnalyzing(true);
      onBeginAnalysis(file, jdText.trim() || "");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Could not verify your usage limit.";
      setSubmitError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const effectiveCompany = company === "other" ? customCompany : company;
  const effectiveRole = role === "other" ? customRole : role;
  const canFetch =
    effectiveCompany.trim().length > 0 && effectiveRole.trim().length > 0;
  const hasSelectedCompany = effectiveCompany.trim().length > 0;
  const hasSelectedRole = effectiveRole.trim().length > 0;
  const canAnalyze = file !== null;

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
        setJdLoadedFromFetch(true);
        showFeedbackMoment("feature_pulse_jd_fetch");
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
    <>
      <div style={{ minHeight: "100vh", background: T.bgPage }}>
        {/* Progress bar */}
        {isSubmitting && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              height: "3px",
              zIndex: 100,
              width: `${submitProgress}%`,
              background: T.gradientBrand,
              transition: "width 0.2s ease",
            }}
          />
        )}

        {/* Hero Section */}
        <section
          style={{
            background: T.gradientHeroUpload,
            padding: isMobile ? "40px 20px 32px" : "56px 40px 48px",
            textAlign: "center",
          }}
        >
          <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 14px",
                borderRadius: 20,
                background: T.bgCard,
                border: `1.5px solid ${T.primaryMid}`,
                fontSize: 12,
                fontWeight: 700,
                color: T.primary,
                boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                marginBottom: 20,
              }}
            >
              ✦ AI Resume Analysis
            </div>

            <div
              style={{
                fontFamily: "'DM Serif Display', serif",
                fontSize: 44,
                lineHeight: 1.1,
                letterSpacing: "-0.02em",
                color: T.textPrimary,
                marginBottom: 14,
              }}
            >
              Let's analyse your resume
            </div>

            <div
              style={{
                fontSize: 16,
                color: T.textSecondary,
                maxWidth: 520,
                margin: "0 auto",
                lineHeight: 1.65,
              }}
            >
              Paste your resume and the job description below. Our AI will score, analyse, and rewrite it in under 60 seconds.
            </div>
          </div>
        </section>

        {/* Upload Card */}
        <div style={{ maxWidth: "1200px", margin: "0 auto", padding: isMobile ? "0 20px 60px" : "0 40px 80px" }}>
          <div
            style={{
              maxWidth: 900,
              margin: "0 auto 40px",
              background: T.bgCard,
              border: `1.5px solid ${T.border}`,
              borderRadius: T.radiusXl,
              boxShadow: T.shadowXl,
              overflow: "hidden",
            }}
          >
            {/* Two-column grid — single column on tablet */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: isTablet ? "1fr" : "1fr 1fr",
                borderBottom: `1.5px solid ${T.border}`,
              }}
            >
              {/* Left: Resume Upload */}
              <div
                style={{
                  padding: isMobile ? 24 : 36,
                  borderRight: isTablet ? "none" : `1.5px solid ${T.border}`,
                  borderBottom: isTablet ? `1.5px solid ${T.border}` : "none",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    marginBottom: 20,
                  }}
                >
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: T.radiusXs,
                      background: T.primaryLight,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 18,
                      flexShrink: 0,
                      color: T.primary,
                    }}
                  >
                    📄
                  </div>
                  <div>
                    <div
                      style={{
                        fontSize: 16,
                        fontWeight: 700,
                        color: T.textPrimary,
                        marginBottom: 2,
                      }}
                    >
                      Upload Resume
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: T.textMuted,
                      }}
                    >
                      PDF, DOCX, or TXT · Max 5MB
                    </div>
                  </div>
                </div>

                {/* Drop Zone */}
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  style={{
                    border: `2px dashed ${
                      isDragging || file
                        ? T.primary
                        : T.borderStrong
                    }`,
                    borderRadius: T.radiusLg,
                    padding: "40px 24px",
                    background: isDragging ? T.primaryLight : file ? T.emeraldLight : T.bgInput,
                    textAlign: "center",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    minHeight: 200,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 12,
                  }}
                >
                  {file ? (
                    <>
                      <div
                        style={{
                          width: 52,
                          height: 52,
                          borderRadius: "50%",
                          background: T.emeraldLight,
                          border: `2px solid ${T.emeraldBorder}`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 22,
                          color: T.emerald,
                        }}
                      >
                        ✓
                      </div>
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 700,
                          color: T.textPrimary,
                          marginTop: 10,
                        }}
                      >
                        {file.name}
                      </div>
                      <div
                        style={{
                          fontSize: 12,
                          color: T.textMuted,
                        }}
                      >
                        {(file.size / 1024).toFixed(0)} KB
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setFile(null);
                        }}
                        style={{
                          fontSize: 12,
                          color: T.rose,
                          cursor: "pointer",
                          background: "none",
                          border: "none",
                          fontFamily: "inherit",
                          textDecoration: "underline",
                          marginTop: 4,
                        }}
                      >
                        Remove
                      </button>
                    </>
                  ) : (
                    <>
                      <div
                        style={{
                          width: 56,
                          height: 56,
                          borderRadius: "50%",
                          background: T.bgSubtle,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 24,
                          color: T.textMuted,
                        }}
                      >
                        ☁
                      </div>
                      <div
                        style={{
                          fontSize: 15,
                          fontWeight: 600,
                          color: T.textPrimary,
                        }}
                      >
                        Drop your resume here
                      </div>
                      <div
                        style={{
                          fontSize: 13,
                          color: T.textMuted,
                        }}
                      >
                        or click to browse files
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          fileInputRef.current?.click();
                        }}
                        style={{
                          padding: "8px 20px",
                          borderRadius: T.radiusXs,
                          background: T.primary,
                          color: "#ffffff",
                          fontSize: 13,
                          fontWeight: 700,
                          border: "none",
                          cursor: "pointer",
                          fontFamily: "inherit",
                          boxShadow: `0 3px 0 ${T.primaryFloor}, 0 6px 16px rgba(91,95,199,0.25)`,
                          marginTop: 4,
                        }}
                      >
                        Browse Files
                      </button>
                    </>
                  )}
                </div>

                {/* Security Pill */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    padding: "11px 14px",
                    borderRadius: T.radiusXs,
                    background: T.primaryLight,
                    border: `1px solid ${T.primaryMid}`,
                    marginTop: 16,
                    fontSize: 12,
                    color: T.primary,
                    lineHeight: 1.5,
                  }}
                >
                  <div style={{ flexShrink: 0, marginTop: 1 }}>🔒</div>
                  <span>Your resume is processed securely and never stored on our servers.</span>
                </div>

                {/* Hidden file input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  style={{ display: "none" }}
                  onChange={handleFileChange}
                />
              </div>

              {/* Right: Job Description */}
              <div style={{ padding: isMobile ? 24 : 36 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    marginBottom: 20,
                  }}
                >
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: T.radiusXs,
                      background: T.violetLight,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 18,
                      flexShrink: 0,
                      color: T.violet,
                    }}
                  >
                    🎯
                  </div>
                  <div>
                    <div
                      style={{
                        fontSize: 16,
                        fontWeight: 700,
                        color: T.textPrimary,
                        marginBottom: 2,
                      }}
                    >
                      Job Description
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: T.textMuted,
                      }}
                    >
                      Paste or fetch the job posting
                    </div>
                  </div>
                </div>

                {/* JD Tab Toggle */}
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    marginBottom: 16,
                    borderBottom: `1px solid ${T.border}`,
                  }}
                >
                  {["paste", "fetch"].map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setJdTab(tab as "paste" | "fetch")}
                      style={{
                        padding: "8px 12px",
                        background: "none",
                        border: "none",
                        fontSize: 13,
                        fontWeight: 600,
                        color: jdTab === tab ? T.primary : T.textMuted,
                        cursor: "pointer",
                        borderBottom: jdTab === tab ? `2px solid ${T.primary}` : "none",
                        fontFamily: "inherit",
                        transition: "color 0.2s",
                      }}
                    >
                      {tab === "paste" ? "Paste JD" : "Fetch JD"}
                    </button>
                  ))}
                </div>

                {/* Paste Tab */}
                {jdTab === "paste" && (
                  <>
                    {/* Textarea */}
                    <textarea
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  placeholder="Paste the job description here...

Include the full posting for the most accurate analysis — job title, requirements, responsibilities, and any 'nice to have' skills."
                  style={{
                    width: "100%",
                    height: 240,
                    padding: "16px 18px",
                    borderRadius: T.radiusMd,
                    border: `1.5px solid ${T.border}`,
                    fontSize: 14,
                    fontFamily: "inherit",
                    color: T.textPrimary,
                    lineHeight: 1.65,
                    background: T.bgInput,
                    resize: "none",
                    outline: "none",
                    transition: "border-color 0.15s, box-shadow 0.15s",
                    boxSizing: "border-box",
                  }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = T.primary;
                    e.currentTarget.style.boxShadow = "0 0 0 3px rgba(91,95,199,0.12)";
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = T.border;
                    e.currentTarget.style.boxShadow = "none";
                  }}
                />

                {/* Character counter */}
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: 8,
                    padding: "0 2px",
                  }}
                >
                  <span style={{ fontSize: 12, color: T.textMuted }}>
                    Minimum 50 characters for accurate analysis
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: jdText.length >= 50 ? T.emerald : T.textMuted,
                    }}
                  >
                    {jdText.length} chars
                  </span>
                </div>

                {/* Hint Pill */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    padding: "11px 14px",
                    borderRadius: T.radiusXs,
                    background: T.violetLight,
                    border: `1px solid ${T.violetBorder}`,
                    marginTop: 12,
                    fontSize: 12,
                    color: T.violet,
                    lineHeight: 1.5,
                  }}
                >
                  <div style={{ flexShrink: 0, marginTop: 1 }}>✦</div>
                  <span>
                    Tip: Include the full posting including 'nice to have' skills — our AI extracts every signal, not just the requirements list.
                  </span>
                </div>
                  </>
                )}

                {/* Fetch Tab */}
                {jdTab === "fetch" && (
                  <>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: 12,
                        marginBottom: 16,
                      }}
                    >
                      <div>
                        <label
                          style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color: T.textMuted,
                            display: "block",
                            marginBottom: 6,
                          }}
                        >
                          Company
                        </label>
                        {company !== "other" && !hasSelectedCompany ? (
                          <select
                            value={company}
                            onChange={(e) => setCompany(e.target.value)}
                            style={{
                              width: "100%",
                              padding: "8px 10px",
                              borderRadius: T.radiusMd,
                              border: `1px solid ${T.border}`,
                              fontSize: 13,
                              fontFamily: "inherit",
                              background: T.bgInput,
                              color: T.textPrimary,
                              cursor: "pointer",
                            }}
                          >
                            <option value="">Select company...</option>
                            {TOP_COMPANIES.map((comp) => (
                              <option key={comp} value={comp}>
                                {comp}
                              </option>
                            ))}
                            <option value="other">Other...</option>
                          </select>
                        ) : (
                          <input
                            type="text"
                            value={company === "other" ? customCompany : company}
                            onChange={(e) =>
                              company === "other"
                                ? setCustomCompany(e.target.value)
                                : setCompany(e.target.value)
                            }
                            placeholder="Enter company name"
                            style={{
                              width: "100%",
                              padding: "8px 10px",
                              borderRadius: T.radiusMd,
                              border: `1px solid ${T.border}`,
                              fontSize: 13,
                              fontFamily: "inherit",
                              background: T.bgInput,
                              color: T.textPrimary,
                            }}
                          />
                        )}
                      </div>

                      <div>
                        <label
                          style={{
                            fontSize: 12,
                            fontWeight: 600,
                            color: T.textMuted,
                            display: "block",
                            marginBottom: 6,
                          }}
                        >
                          Role
                        </label>
                        {role !== "other" && !hasSelectedRole ? (
                          <select
                            value={role}
                            onChange={(e) => setRole(e.target.value)}
                            style={{
                              width: "100%",
                              padding: "8px 10px",
                              borderRadius: T.radiusMd,
                              border: `1px solid ${T.border}`,
                              fontSize: 13,
                              fontFamily: "inherit",
                              background: T.bgInput,
                              color: T.textPrimary,
                              cursor: "pointer",
                            }}
                          >
                            <option value="">Select role...</option>
                            {TOP_ROLES_BY_GROUP.map((r) => (
                              <option key={r} value={r}>
                                {r}
                              </option>
                            ))}
                            <option value="other">Other...</option>
                          </select>
                        ) : (
                          <input
                            type="text"
                            value={role === "other" ? customRole : role}
                            onChange={(e) =>
                              role === "other"
                                ? setCustomRole(e.target.value)
                                : setRole(e.target.value)
                            }
                            placeholder="Enter role"
                            style={{
                              width: "100%",
                              padding: "8px 10px",
                              borderRadius: T.radiusMd,
                              border: `1px solid ${T.border}`,
                              fontSize: 13,
                              fontFamily: "inherit",
                              background: T.bgInput,
                              color: T.textPrimary,
                            }}
                          />
                        )}
                      </div>
                    </div>

                    <button
                      onClick={() => handleFetchJD()}
                      disabled={!canFetch || fetchStatus === "loading"}
                      style={{
                        width: "100%",
                        padding: "8px 12px",
                        borderRadius: T.radiusMd,
                        fontSize: 13,
                        fontWeight: 600,
                        background:
                          canFetch && fetchStatus !== "loading"
                            ? T.primary
                            : T.bgSubtle,
                        color:
                          canFetch && fetchStatus !== "loading"
                            ? "#ffffff"
                            : T.textDisabled,
                        border: "none",
                        cursor:
                          canFetch && fetchStatus !== "loading"
                            ? "pointer"
                            : "not-allowed",
                        fontFamily: "inherit",
                        marginBottom: 12,
                      }}
                    >
                      {fetchStatus === "loading"
                        ? "Fetching JD..."
                        : "Fetch JD"}
                    </button>

                    {fetchStatus === "found" && fetchResult?.jd_text && (
                      <div
                        style={{
                          padding: "10px 12px",
                          borderRadius: T.radiusMd,
                          background: T.emeraldLight,
                          border: `1px solid ${T.emeraldBorder}`,
                          fontSize: 12,
                          color: T.emerald,
                          marginBottom: 12,
                        }}
                      >
                        ✓ JD fetched successfully{" "}
                        {fetchResult.fetched_at &&
                          `(${formatFetchTime(fetchResult.fetched_at)})`}
                      </div>
                    )}

                    {fetchStatus === "error" && (
                      <div
                        style={{
                          padding: "10px 12px",
                          borderRadius: T.radiusMd,
                          background: "#fee2e2",
                          border: "1px solid #fca5a5",
                          fontSize: 12,
                          color: "#dc2626",
                          marginBottom: 12,
                        }}
                      >
                        ✗ {fetchResult?.error_message || "Failed to fetch JD"}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* CTA Strip */}
            <div
              style={{
                borderTop: `1.5px solid ${T.border}`,
                background: `linear-gradient(135deg, ${T.bgCard}, ${T.bgInput})`,
                padding: "28px 36px",
              }}
            >
              <button
                onClick={() => {
                  void handleSubmit();
                }}
                disabled={!canAnalyze || isSubmitting}
                style={{
                  width: "100%",
                  padding: "16px 32px",
                  borderRadius: T.radiusMd,
                  fontSize: 16,
                  fontWeight: 700,
                  background: canAnalyze && !isSubmitting ? T.primary : T.bgSubtle,
                  color: canAnalyze && !isSubmitting ? "#ffffff" : T.textDisabled,
                  border: "none",
                  cursor: canAnalyze && !isSubmitting ? "pointer" : "not-allowed",
                  fontFamily: "inherit",
                  boxShadow: canAnalyze && !isSubmitting
                    ? `0 4px 0 ${T.primaryFloor}, 0 8px 24px rgba(91,95,199,0.28)`
                    : "0 3px 0 #d1d5db",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                  transition: "all 0.15s",
                }}
                onMouseEnter={(e) => {
                  if (canAnalyze && !isSubmitting) {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow = `0 6px 0 ${T.primaryFloor}, 0 12px 32px rgba(91,95,199,0.35)`;
                  }
                }}
                onMouseLeave={(e) => {
                  if (canAnalyze && !isSubmitting) {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = `0 4px 0 ${T.primaryFloor}, 0 8px 24px rgba(91,95,199,0.28)`;
                  }
                }}
                onMouseDown={(e) => {
                  if (canAnalyze && !isSubmitting) {
                    e.currentTarget.style.transform = "translateY(3px)";
                    e.currentTarget.style.boxShadow = `0 1px 0 ${T.primaryFloor}`;
                  }
                }}
                onMouseUp={(e) => {
                  if (canAnalyze && !isSubmitting) {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow = `0 4px 0 ${T.primaryFloor}, 0 8px 24px rgba(91,95,199,0.28)`;
                  }
                }}
              >
                {isSubmitting ? "Checking…" : "Analyse My Resume →"}
              </button>

              {submitError && (
                <div
                  style={{
                    fontSize: 13,
                    color: "#dc2626",
                    marginTop: 10,
                    textAlign: "center",
                  }}
                >
                  {submitError}
                </div>
              )}

              {!canAnalyze && !submitError && (
                <div
                  style={{
                    fontSize: 13,
                    color: T.textMuted,
                    marginTop: 10,
                    textAlign: "center",
                  }}
                >
                  Upload your resume to continue
                </div>
              )}

              <button
                onClick={() => {
                  setFile(new File(["demo"], "demo.pdf"));
                  setJdText(
                    "Senior Software Engineer - Backend\n\nWe are looking for a Senior Software Engineer with 5+ years of experience in backend development. Required: Python, Node.js, PostgreSQL, AWS, Docker. Nice to have: Kubernetes, Kafka, system design experience."
                  );
                }}
                style={{
                  background: "none",
                  border: "none",
                  fontSize: 13,
                  fontWeight: 700,
                  color: T.primary,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  textDecoration: "underline",
                  textDecorationColor: "rgba(91,95,199,0.3)",
                  marginTop: 12,
                  width: "100%",
                  textAlign: "center",
                }}
              >
                Try Demo Mode →
              </button>
            </div>
          </div>

          {/* Preview Feature Cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 16,
              maxWidth: 900,
              margin: "0 auto",
            }}
          >
            {[
              {
                icon: "🎯",
                title: "ATS Score Analysis",
                body: "12-dimension scoring against your exact job description — not a generic template.",
              },
              {
                icon: "✦",
                title: "AI Bullet Rewrites",
                body: "Three rewrite styles per bullet: balanced, aggressive, and top-1% — all grounded in your experience.",
              },
              {
                icon: "👁",
                title: "Recruiter Simulation",
                body: "See your resume through the eyes of 4 recruiter personas, including a FAANG hiring manager.",
              },
            ].map((card, idx) => (
              <div
                key={idx}
                style={{
                  background: T.bgCard,
                  border: `1.5px solid ${T.border}`,
                  borderRadius: T.radiusLg,
                  padding: 24,
                  textAlign: "center",
                  boxShadow: "0 2px 6px rgba(0,0,0,0.04)",
                }}
              >
                <div style={{ fontSize: 32, marginBottom: 12 }}>{card.icon}</div>
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: T.textPrimary,
                    marginBottom: 8,
                  }}
                >
                  {card.title}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: T.textMuted,
                    lineHeight: 1.55,
                  }}
                >
                  {card.body}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {upgradeModalOpen && upgradeData ? (
        <UpgradeModal
          uploadsThisMonth={upgradeData.uploadsThisMonth}
          limit={upgradeData.limit}
          onClose={() => setUpgradeModalOpen(false)}
        />
      ) : null}

      {feedbackState?.active_moment === "feature_pulse_jd_fetch" ? (
        <FeaturePulseCard
          featureName="jd_fetch"
          featureLabel="JD Auto-Fetch"
          question="Did we fetch the right job description?"
          onDismiss={clearActiveMoment}
        />
      ) : null}
    </>
  );
}
