import { useEffect, useRef, useState } from "react";

import { downloadResumeReport, getDownloadVerification } from "../../api/client";
import { useWindowSize } from "../../hooks/useWindowSize";
import { useResumeStore } from "../../store/useResumeStore";
import { useAuthStore } from "../../store/authStore";
import type { DownloadVerification, TopBarProps } from "../../types";

export default function TopBar({ onOpenAuthModal, onViewProgress }: TopBarProps) {
  const analysisResult = useResumeStore((state) => state.analysisResult);
  const jobId = useResumeStore((state) => state.jobId);
  const selectedStyle = useResumeStore((state) => state.selectedStyle);
  const isLoading = useResumeStore((state) => state.isLoading);
  const baselineAts = useResumeStore((state) => state.baselineAts);
  const resetAnalysis = useResumeStore((state) => state.resetAnalysis);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const user = useAuthStore((state) => state.user);
  const loading = useAuthStore((state) => state.loading);
  const signOut = useAuthStore((state) => state.signOut);
  const { isMobile } = useWindowSize();
  const [isPressed, setIsPressed] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isSignInPressed, setIsSignInPressed] = useState(false);
  const [isChipHovered, setIsChipHovered] = useState(false);
  const [isDownloadHovered, setIsDownloadHovered] = useState(false);
  const [isSignOutHovered, setIsSignOutHovered] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);
  const [verificationResult, setVerificationResult] = useState<DownloadVerification | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const displayName = user?.user_metadata.full_name ?? user?.email ?? "";
  const avatarName =
    user?.user_metadata.full_name ?? user?.email?.split("@")[0] ?? "User";
  const avatarUrl = user?.user_metadata.avatar_url
    ? user.user_metadata.avatar_url
    : `https://ui-avatars.com/api/?name=${encodeURIComponent(avatarName).replace(/%20/g, "+")}&background=6366f1&color=fff&size=40`;
  const firstName =
    user?.user_metadata.full_name?.split(" ").filter(Boolean)[0] ??
    user?.email?.split("@")[0] ??
    "User";
  const downloadJobId = jobId ?? analysisResult?.job_id;
  const canDownload = Boolean(downloadJobId) && !isLoading && !isDownloading;

  // Calculate score delta (simplified: count applied patches)
  const originalAts = baselineAts ?? analysisResult?.ats?.score ?? 0;
  const currentAts = analysisResult?.ats?.score ?? 0;
  const scoreImprovement = Math.max(0, currentAts - originalAts);

  const downloadLabel = scoreImprovement > 0
    ? `Download (+${scoreImprovement} pts)`
    : "Download Report";

  useEffect(() => {
    if (!isMenuOpen) {
      return;
    }

    const handleMouseDown = (event: MouseEvent): void => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMenuOpen]);

  useEffect(() => {
    if (!isMenuOpen || !downloadJobId) {
      return;
    }

    let cancelled = false;
    getDownloadVerification(downloadJobId)
      .then((result) => {
        if (!cancelled) {
          setVerificationResult(result);
        }
      })
      .catch((error) => {
        console.error("Download verification failed:", error);
        if (!cancelled) {
          setVerificationResult(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [downloadJobId, isMenuOpen]);

  const handleSignOut = async (): Promise<void> => {
    setIsSigningOut(true);
    try {
      await signOut();
      setIsMenuOpen(false);
    } catch (error) {
      console.error("Failed to sign out", error);
    } finally {
      setIsSigningOut(false);
    }
  };

  const handleDownload = async (): Promise<void> => {
    if (!downloadJobId) {
      return;
    }

    setIsDownloading(true);
    try {
      await downloadResumeReport(downloadJobId, selectedStyle);
      setIsMenuOpen(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Download failed.";
      window.alert(message);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: isMobile ? "14px 16px" : "14px 32px",
        background: "#ffffff",
        borderBottom: "1.5px solid #e5e7eb",
        position: "sticky",
        top: 0,
        zIndex: 50,
        backdropFilter: "blur(12px)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: isMobile ? "8px" : "12px",
          minWidth: 0,
          flex: 1,
        }}
      >
        <div
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "12px",
            background: "linear-gradient(135deg, #6366f1, #7c3aed)",
            boxShadow: "0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            color: "#ffffff",
            fontSize: "19px",
            fontWeight: 700,
            lineHeight: 1,
          }}
        >
          {"\u2726"}
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              fontSize: "16px",
              fontWeight: 700,
              color: "#111827",
              lineHeight: 1.2,
              letterSpacing: "-0.01em",
              whiteSpace: isMobile ? "nowrap" : undefined,
            }}
          >
            {isMobile ? "Career Intelligence" : "AI Career Intelligence Platform"}
          </div>
          {!isMobile ? (
            <div
              style={{
                fontSize: "11px",
                fontWeight: 400,
                color: "#6b7280",
                marginTop: "2px",
              }}
            >
              Powered by Advanced AI
            </div>
          ) : null}
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: isMobile ? "8px" : "16px",
          marginLeft: "auto",
          minWidth: 0,
          flexShrink: 0,
        }}
      >
        <button
          onClick={resetAnalysis}
          disabled={!analysisResult || isLoading}
          aria-label="Analyze another resume"
          onMouseDown={() => setIsPressed(true)}
          onMouseUp={() => setIsPressed(false)}
          onMouseLeave={() => setIsPressed(false)}
          style={{
            background: (!analysisResult || isLoading) ? "#f3f4f6" : "#7c3aed",
            color: (!analysisResult || isLoading) ? "#9ca3af" : "#ffffff",
            borderRadius: "10px",
            padding: isMobile ? "10px 12px" : "10px 20px",
            fontSize: "13px",
            fontWeight: 700,
            border: "none",
            cursor: (!analysisResult || isLoading) ? "not-allowed" : "pointer",
            transform: (!analysisResult || isLoading) || isPressed ? "translateY(3px)" : "translateY(0px)",
            transition: "transform 0.1s, box-shadow 0.1s",
            boxShadow: (!analysisResult || isLoading)
              ? "0 3px 0 #d1d5db"
              : isPressed
                ? "0 1px 0 #5b21b6"
                : "0 3px 0 #5b21b6, 0 5px 12px rgba(124, 58, 237, 0.25)",
          }}
        >
          {isMobile ? "\u21bb" : "Analyze Another Resume"}
        </button>

        {loading ? (
          <div
            aria-hidden="true"
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "50%",
              background: "#f3f4f6",
              flexShrink: 0,
            }}
          />
        ) : user ? (
          <div
            ref={menuRef}
            style={{
              position: "relative",
              flexShrink: 0,
            }}
          >
            <button
              type="button"
              onClick={() => setIsMenuOpen((current) => !current)}
              onMouseEnter={() => setIsChipHovered(true)}
              onMouseLeave={() => setIsChipHovered(false)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "5px 10px 5px 5px",
                border: `1.5px solid ${isChipHovered || isMenuOpen ? "#d1d5db" : "#e5e7eb"}`,
                borderRadius: "999px",
                background: isChipHovered || isMenuOpen ? "#f9fafb" : "#ffffff",
                cursor: "pointer",
                transition: "all 0.15s",
                minWidth: 0,
              }}
            >
              <img
                src={avatarUrl}
                alt={displayName ? `${displayName} avatar` : "User avatar"}
                style={{
                  width: "28px",
                  height: "28px",
                  borderRadius: "50%",
                  border: "1.5px solid #e5e7eb",
                  objectFit: "cover",
                  flexShrink: 0,
                }}
              />
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 500,
                  color: "#111827",
                  maxWidth: isMobile ? "88px" : "120px",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {firstName}
              </div>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <path
                  d="M3 4.5L6 7.5L9 4.5"
                  stroke="#6b7280"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>

            {isMenuOpen ? (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  right: 0,
                  background: "#ffffff",
                  border: "1.5px solid #e5e7eb",
                  borderRadius: "12px",
                  boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
                  minWidth: "180px",
                  zIndex: 200,
                  padding: "6px",
                }}
              >
                <div
                  style={{
                    padding: "10px 12px 8px",
                    borderBottom: "1px solid #f3f4f6",
                  }}
                >
                  <div
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color: "#111827",
                    }}
                  >
                    {displayName}
                  </div>
                  <div
                    style={{
                      fontSize: "12px",
                      color: "#6b7280",
                      marginTop: "2px",
                    }}
                  >
                    {user.email}
                  </div>
                </div>

                {onViewProgress ? (
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("progress");
                      onViewProgress();
                      setIsMenuOpen(false);
                    }}
                    onMouseEnter={() => setIsDownloadHovered(true)}
                    onMouseLeave={() => setIsDownloadHovered(false)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "9px 12px",
                      borderRadius: "8px",
                      fontSize: "13px",
                      color: "#374151",
                      cursor: "pointer",
                      background: isDownloadHovered ? "#f9fafb" : "#ffffff",
                      border: "none",
                      width: "100%",
                      marginTop: "2px",
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path
                        d="M2 12L6 8L9 11L14 5M14 5H10M14 5V9"
                        stroke="#6b7280"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Progress history
                  </button>
                ) : null}

                <div style={{ position: "relative" }}>
                  {verificationResult && !verificationResult.clean ? (
                    <div
                      style={{
                        background: "#fffbeb",
                        border: "1.5px solid #fbbf24",
                        borderRadius: "10px",
                        padding: "10px 14px",
                        fontSize: "13px",
                        color: "#92400e",
                        marginBottom: "12px",
                      }}
                    >
                      ⚠ {verificationResult.total_verified} of {verificationResult.total_applied} changes confirmed in document. Download may be missing some edits.
                    </div>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void handleDownload()}
                    disabled={!canDownload}
                    onMouseEnter={() => {
                      setIsDownloadHovered(true);
                      setIsTooltipVisible(true);
                    }}
                    onMouseLeave={() => {
                      setIsDownloadHovered(false);
                      setIsTooltipVisible(false);
                    }}
                    title={`ATS Score: ${originalAts}${scoreImprovement > 0 ? ` → ${currentAts}` : ""}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "9px 12px",
                      borderRadius: "8px",
                      fontSize: "13px",
                      color: canDownload ? "#374151" : "#9ca3af",
                      cursor: canDownload ? "pointer" : "not-allowed",
                      background: canDownload && isDownloadHovered ? "#f9fafb" : "#ffffff",
                      border: "none",
                      width: "100%",
                      marginTop: "2px",
                      position: "relative",
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path
                        d="M8 2.5V9.5M8 9.5L5.5 7M8 9.5L10.5 7M3 11.5V12C3 12.5523 3.44772 13 4 13H12C12.5523 13 13 12.5523 13 12V11.5"
                        stroke={canDownload ? "#6b7280" : "#9ca3af"}
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    {isDownloading ? "Downloading..." : downloadLabel}
                  </button>
                  {isTooltipVisible && canDownload && (
                    <div
                      style={{
                        position: "absolute",
                        bottom: "calc(100% + 8px)",
                        left: 0,
                        background: "#111827",
                        color: "#ffffff",
                        borderRadius: "6px",
                        padding: "6px 10px",
                        fontSize: "11px",
                        whiteSpace: "nowrap",
                        zIndex: 300,
                        pointerEvents: "none",
                      }}
                    >
                      {`Download your resume • ATS: ${originalAts}${scoreImprovement > 0 ? ` → ${currentAts}` : ""}`}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => void handleSignOut()}
                  disabled={isSigningOut}
                  onMouseEnter={() => setIsSignOutHovered(true)}
                  onMouseLeave={() => setIsSignOutHovered(false)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "9px 12px",
                    borderRadius: "8px",
                    fontSize: "13px",
                    color: isSigningOut ? "#fca5a5" : "#ef4444",
                    cursor: isSigningOut ? "not-allowed" : "pointer",
                    background: !isSigningOut && isSignOutHovered ? "#f9fafb" : "#ffffff",
                    border: "none",
                    borderTop: "1px solid #f3f4f6",
                    width: "100%",
                    marginTop: "2px",
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path
                      d="M6 3.5H4.5C3.94772 3.5 3.5 3.94772 3.5 4.5V11.5C3.5 12.0523 3.94772 12.5 4.5 12.5H6M9 11L12 8L9 5M12 8H6"
                      stroke={isSigningOut ? "#fca5a5" : "#ef4444"}
                      strokeWidth="1.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  {isSigningOut ? "Signing out\u2026" : "Sign out"}
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          <button
            type="button"
            onClick={onOpenAuthModal}
            onMouseDown={() => setIsSignInPressed(true)}
            onMouseUp={() => setIsSignInPressed(false)}
            onMouseLeave={() => setIsSignInPressed(false)}
            style={{
              background: "#6366f1",
              color: "#ffffff",
              borderRadius: "10px",
              padding: "8px 18px",
              fontSize: "13px",
              fontWeight: 700,
              boxShadow: isSignInPressed
                ? "0 1px 0 #4338ca"
                : "0 3px 0 #4338ca, 0 5px 12px rgba(99,102,241,0.25)",
              border: "none",
              cursor: "pointer",
              transform: isSignInPressed ? "translateY(2px)" : "translateY(0px)",
              transition: "transform 0.1s, box-shadow 0.1s",
              flexShrink: 0,
            }}
          >
            Sign In
          </button>
        )}
      </div>
    </header>
  );
}
