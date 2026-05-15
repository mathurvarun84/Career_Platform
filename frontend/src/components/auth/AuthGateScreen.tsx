import { useCallback, useState } from "react";
import type { CSSProperties } from "react";

import { supabase } from "../../lib/supabase";
import { useAuthStore } from "../../store/authStore";

/** Local UI state only — no shared domain types required. */
type AuthGateTab = "signin" | "signup";

const INPUT_BASE_STYLE: CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  border: "1.5px solid #e5e7eb",
  borderRadius: "10px",
  fontSize: "13px",
  color: "#374151",
  background: "#fafafa",
  fontFamily: "inherit",
  outline: "none",
  boxSizing: "border-box",
};

function IconChartBar(): React.ReactElement {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#ffffff"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M3 3v18h18" />
      <path d="M7 16v-4" />
      <path d="M12 16v-9" />
      <path d="M17 16v-6" />
    </svg>
  );
}

function IconUser(): React.ReactElement {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#ffffff"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function IconTrendingUp(): React.ReactElement {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#ffffff"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  );
}

function IconLockMuted(): React.ReactElement {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#9ca3af"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function IconClockIndigo(): React.ReactElement {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#6366f1"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function IconUsersIndigo(): React.ReactElement {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#6366f1"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function IconFileSearchIndigo(): React.ReactElement {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#6366f1"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <circle cx="11.5" cy="14.5" r="2.5" />
      <path d="M13.25 16.25 15 18" />
    </svg>
  );
}

function GoogleMark(): React.ReactElement {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.55 0 9s.347 2.825.957 4.039l3.007-2.332z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z"
      />
    </svg>
  );
}

export default function AuthGateScreen() {
  const signInWithGoogle = useAuthStore((s) => s.signInWithGoogle);
  const signInWithEmail = useAuthStore((s) => s.signInWithEmail);
  const signUpWithEmail = useAuthStore((s) => s.signUpWithEmail);

  const [tab, setTab] = useState<AuthGateTab>("signin");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [googleHovered, setGoogleHovered] = useState(false);
  const [ctaPressed, setCtaPressed] = useState(false);
  const [awaitingEmailConfirmation, setAwaitingEmailConfirmation] =
    useState(false);
  const [confirmationEmail, setConfirmationEmail] = useState("");
  const [passwordResetSent, setPasswordResetSent] = useState(false);

  const getInputStyle = useCallback(
    (field: string): CSSProperties => ({
      ...INPUT_BASE_STYLE,
      borderColor: focusedField === field ? "#6366f1" : "#e5e7eb",
      background: focusedField === field ? "#ffffff" : "#fafafa",
    }),
    [focusedField]
  );

  const switchTab = (next: AuthGateTab): void => {
    setTab(next);
    setError(null);
    setPasswordResetSent(false);
  };

  const handleForgotPassword = async (): Promise<void> => {
    setError(null);
    const trimmed = email.trim();
    if (!trimmed) {
      setError("Enter your email above, then tap Forgot password again.");
      return;
    }
    try {
      await supabase.auth.resetPasswordForEmail(trimmed, {
        redirectTo: window.location.origin,
      });
      setError(null);
      setPasswordResetSent(true);
    } catch {
      setError("Could not send reset email. Please try again.");
    }
  };

  const handleGoogle = (): void => {
    void signInWithGoogle();
  };

  const handlePrimaryClick = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    setPasswordResetSent(false);
    try {
      if (tab === "signin") {
        await signInWithEmail(email.trim(), password);
      } else {
        const { session } = await signUpWithEmail(
          email.trim(),
          password,
          fullName.trim()
        );
        if (session === null) {
          setAwaitingEmailConfirmation(true);
          setConfirmationEmail(email.trim());
        }
      }
    } catch {
      setError(
        tab === "signin"
          ? "Invalid email or password. Please try again."
          : "Could not create account. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const ctaLabel =
    tab === "signin" ? "Sign in to my account" : "Create my account";
  const ctaLoadingLabel =
    tab === "signin" ? "Signing in…" : "Creating account…";

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        minHeight: "calc(100vh - 70px)",
        width: "100%",
        overflow: "hidden",
      }}
    >
      {/* Left — value panel */}
      <div
        style={{
          background: "#6366f1",
          padding: "48px 40px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          minWidth: 0,
          overflow: "hidden",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            columnGap: "10px",
          }}
        >
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "17px",
              color: "#ffffff",
              flexShrink: 0,
            }}
          >
            ✦
          </div>
          <div
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: "rgba(255,255,255,0.9)",
            }}
          >
            AI Career Intelligence Platform
          </div>
        </div>

        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            minHeight: 0,
            paddingTop: "24px",
            paddingBottom: "24px",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              columnGap: "6px",
              background: "rgba(255,255,255,0.15)",
              borderRadius: "999px",
              padding: "4px 12px",
              fontSize: "11px",
              fontWeight: 600,
              color: "rgba(255,255,255,0.9)",
              marginBottom: "20px",
              width: "fit-content",
            }}
          >
            Built for serious job seekers
          </div>
          <div
            style={{
              fontSize: "26px",
              fontWeight: 700,
              color: "#ffffff",
              lineHeight: 1.25,
              marginBottom: "12px",
            }}
          >
            Land your next role
            <br />
            with AI precision
          </div>
          <div
            style={{
              fontSize: "13px",
              color: "rgba(255,255,255,0.72)",
              lineHeight: 1.6,
              marginBottom: "32px",
            }}
          >
            Get a full breakdown of how your resume performs — against ATS
            filters, real recruiters, and the exact job you want.
          </div>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              rowGap: "14px",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                columnGap: "12px",
              }}
            >
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: "rgba(255,255,255,0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <IconChartBar />
              </div>
              <div>
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "#ffffff",
                  }}
                >
                  ATS score + gap analysis
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "rgba(255,255,255,0.65)",
                    lineHeight: 1.45,
                    marginTop: "2px",
                  }}
                >
                  Know exactly which keywords you&apos;re missing before you
                  apply
                </div>
              </div>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                columnGap: "12px",
              }}
            >
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: "rgba(255,255,255,0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <IconUser />
              </div>
              <div>
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "#ffffff",
                  }}
                >
                  Recruiter view simulation
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "rgba(255,255,255,0.65)",
                    lineHeight: 1.45,
                    marginTop: "2px",
                  }}
                >
                  See your resume through the eyes of 4 recruiter personas
                </div>
              </div>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                columnGap: "12px",
              }}
            >
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: "rgba(255,255,255,0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <IconTrendingUp />
              </div>
              <div>
                <div
                  style={{
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "#ffffff",
                  }}
                >
                  Track progress over time
                </div>
                <div
                  style={{
                    fontSize: "12px",
                    color: "rgba(255,255,255,0.65)",
                    lineHeight: 1.45,
                    marginTop: "2px",
                  }}
                >
                  Compare scores across versions as you improve your resume
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          style={{
            borderTop: "1px solid rgba(255,255,255,0.15)",
            paddingTop: "20px",
          }}
        >
          {/* TODO: replace with real user testimonial */}
          <div
            style={{
              fontSize: "12.5px",
              color: "rgba(255,255,255,0.8)",
              lineHeight: 1.55,
              fontStyle: "italic",
              marginBottom: "10px",
            }}
          >
            &quot;Went from 0 callbacks to 3 interviews in a week. The JD
            matching alone is worth it.&quot;
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              columnGap: "8px",
            }}
          >
            <div
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: "rgba(255,255,255,0.25)",
                fontSize: "11px",
                fontWeight: 600,
                color: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              PK
            </div>
            <div>
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "rgba(255,255,255,0.9)",
                }}
              >
                Priya K.
              </div>
              <div
                style={{
                  fontSize: "11px",
                  color: "rgba(255,255,255,0.6)",
                }}
              >
                Product Manager · hired at Razorpay
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right — auth form */}
      <div
        style={{
          background: "#ffffff",
          padding: "48px 40px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          minWidth: 0,
          overflow: "auto",
          boxSizing: "border-box",
        }}
      >
        {awaitingEmailConfirmation ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              flex: "1 1 auto",
              minHeight: "200px",
            }}
          >
            <div
              style={{
                fontSize: "48px",
                lineHeight: 1,
                color: "#6366f1",
                marginBottom: "16px",
              }}
            >
              ✉
            </div>
            <div
              style={{
                fontSize: "18px",
                fontWeight: 700,
                color: "#111827",
                marginBottom: "10px",
              }}
            >
              Check your email
            </div>
            <div
              style={{
                fontSize: "13px",
                color: "#6b7280",
                lineHeight: 1.6,
                maxWidth: "360px",
              }}
            >
              We sent a confirmation link to {confirmationEmail}. Click it to
              activate your account.
            </div>
          </div>
        ) : (
          <>
        <div
          style={{
            fontSize: "22px",
            fontWeight: 700,
            color: "#111827",
            marginBottom: "6px",
          }}
        >
          Welcome back
        </div>
        <div
          style={{
            fontSize: "13px",
            color: "#6b7280",
            marginBottom: "28px",
            lineHeight: 1.5,
          }}
        >
          Sign in to run your analysis and track your progress.
        </div>

        {passwordResetSent ? (
          <div
            style={{
              fontSize: "13px",
              color: "#6b7280",
              lineHeight: 1.5,
              marginBottom: "16px",
              background: "#f9fafb",
              border: "1.5px solid #e5e7eb",
              borderRadius: "10px",
              padding: "12px 14px",
            }}
          >
            If an account exists for this email, we sent a password reset link
            to {email.trim()}.
          </div>
        ) : null}

        <button
          type="button"
          onClick={handleGoogle}
          onMouseEnter={() => setGoogleHovered(true)}
          onMouseLeave={() => setGoogleHovered(false)}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            columnGap: "10px",
            width: "100%",
            padding: "11px 16px",
            border: "1.5px solid",
            borderColor: googleHovered ? "#d1d5db" : "#e5e7eb",
            borderRadius: "10px",
            background: googleHovered ? "#f9fafb" : "#ffffff",
            fontSize: "13px",
            fontWeight: 600,
            color: "#374151",
            marginBottom: "16px",
            cursor: "pointer",
            boxSizing: "border-box",
          }}
        >
          <GoogleMark />
          Continue with Google
        </button>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            columnGap: "12px",
            marginBottom: "16px",
          }}
        >
          <div style={{ flex: 1, height: "1px", background: "#e5e7eb" }} />
          <div style={{ fontSize: "12px", color: "#9ca3af", flexShrink: 0 }}>
            or continue with email
          </div>
          <div style={{ flex: 1, height: "1px", background: "#e5e7eb" }} />
        </div>

        <div
          style={{
            display: "flex",
            border: "1.5px solid #e5e7eb",
            borderRadius: "10px",
            overflow: "hidden",
            marginBottom: "20px",
          }}
        >
          <button
            type="button"
            onClick={() => switchTab("signin")}
            style={{
              flex: 1,
              padding: "9px",
              fontSize: "13px",
              fontWeight: 600,
              border: "none",
              cursor: "pointer",
              background: tab === "signin" ? "#6366f1" : "#ffffff",
              color: tab === "signin" ? "#ffffff" : "#6b7280",
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            onClick={() => switchTab("signup")}
            style={{
              flex: 1,
              padding: "9px",
              fontSize: "13px",
              fontWeight: 600,
              border: "none",
              cursor: "pointer",
              background: tab === "signup" ? "#6366f1" : "#ffffff",
              color: tab === "signup" ? "#ffffff" : "#6b7280",
            }}
          >
            Create account
          </button>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            rowGap: "12px",
            marginBottom: "16px",
          }}
        >
          {tab === "signup" ? (
            <div>
              <label
                htmlFor="gate-full-name"
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: "5px",
                  display: "block",
                }}
              >
                Full name
              </label>
              <input
                id="gate-full-name"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                style={getInputStyle("fullName")}
                onFocus={() => setFocusedField("fullName")}
                onBlur={() =>
                  setFocusedField((c) => (c === "fullName" ? null : c))
                }
              />
            </div>
          ) : null}

          <div>
            <label
              htmlFor="gate-email"
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "#374151",
                marginBottom: "5px",
                display: "block",
              }}
            >
              Email address
            </label>
            <input
              id="gate-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={getInputStyle("email")}
              onFocus={() => setFocusedField("email")}
              onBlur={() => setFocusedField((c) => (c === "email" ? null : c))}
            />
          </div>

          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "5px",
              }}
            >
              <label
                htmlFor="gate-password"
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "#374151",
                  display: "block",
                }}
              >
                Password
              </label>
              {tab === "signin" ? (
                <button
                  type="button"
                  onClick={() => void handleForgotPassword()}
                  style={{
                    fontSize: "12px",
                    color: "#6366f1",
                    cursor: "pointer",
                    background: "none",
                    border: "none",
                    padding: 0,
                    fontWeight: 600,
                  }}
                >
                  Forgot password?
                </button>
              ) : null}
            </div>
            <input
              id="gate-password"
              type="password"
              autoComplete={
                tab === "signin" ? "current-password" : "new-password"
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={getInputStyle("password")}
              onFocus={() => setFocusedField("password")}
              onBlur={() =>
                setFocusedField((c) => (c === "password" ? null : c))
              }
            />
          </div>
        </div>

        {error ? (
          <div
            style={{
              fontSize: "13px",
              color: "#ef4444",
              marginBottom: "8px",
            }}
          >
            ⚠ {error}
          </div>
        ) : null}

        <button
          type="button"
          disabled={loading}
          onClick={() => void handlePrimaryClick()}
          onMouseDown={() => {
            if (!loading) {
              setCtaPressed(true);
            }
          }}
          onMouseUp={() => setCtaPressed(false)}
          onMouseLeave={() => setCtaPressed(false)}
          style={{
            width: "100%",
            padding: "12px",
            background: loading ? "#a5b4fc" : "#6366f1",
            color: "#ffffff",
            border: "none",
            borderRadius: "10px",
            fontSize: "14px",
            fontWeight: 700,
            cursor: loading ? "not-allowed" : "pointer",
            marginBottom: "16px",
            boxShadow: loading
              ? "0 3px 0 #d1d5db"
              : ctaPressed
                ? "0 1px 0 #4338ca"
                : "0 3px 0 #4338ca",
            transform: !loading && ctaPressed ? "translateY(2px)" : "none",
            boxSizing: "border-box",
          }}
        >
          {loading ? ctaLoadingLabel : ctaLabel}
        </button>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            columnGap: "7px",
            marginBottom: "0",
          }}
        >
          <IconLockMuted />
          <div
            style={{
              fontSize: "11.5px",
              color: "#9ca3af",
              lineHeight: 1.4,
            }}
          >
            Your resume data is private, encrypted, and never shared with third
            parties.
          </div>
        </div>

        <div
          style={{
            marginTop: "28px",
            borderTop: "1px solid #f3f4f6",
            paddingTop: "20px",
            display: "flex",
            columnGap: "0",
          }}
        >
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
              rowGap: "6px",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "#eef2ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <IconClockIndigo />
            </div>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "#111827",
              }}
            >
              60 sec
            </div>
            <div style={{ fontSize: "11px", color: "#9ca3af", lineHeight: 1.35 }}>
              Full analysis
              <br />
              turnaround
            </div>
          </div>
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
              rowGap: "6px",
              borderLeft: "1px solid #f3f4f6",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "#eef2ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <IconUsersIndigo />
            </div>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "#111827",
              }}
            >
              4 personas
            </div>
            <div style={{ fontSize: "11px", color: "#9ca3af", lineHeight: 1.35 }}>
              Recruiter types
              <br />
              simulated
            </div>
          </div>
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              textAlign: "center",
              rowGap: "6px",
              borderLeft: "1px solid #f3f4f6",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "#eef2ff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <IconFileSearchIndigo />
            </div>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 700,
                color: "#111827",
              }}
            >
              Line by line
            </div>
            <div style={{ fontSize: "11px", color: "#9ca3af", lineHeight: 1.35 }}>
              JD keyword
              <br />
              matching
            </div>
          </div>
        </div>
          </>
        )}
      </div>
    </div>
  );
}
