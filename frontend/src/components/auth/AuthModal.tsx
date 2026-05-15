import { useEffect, useMemo, useState } from "react";

import { useAuthStore } from "../../store/authStore";

interface AuthModalProps {
  onClose: () => void;
}

type AuthTab = "sign_in" | "sign_up";

const INPUT_BASE_STYLE: React.CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  border: "1.5px solid #e5e7eb",
  borderRadius: "10px",
  fontSize: "14px",
  color: "#374151",
  background: "#fafafa",
  outline: "none",
  fontFamily: "inherit",
  transition: "border-color 0.15s",
  boxSizing: "border-box",
};

export default function AuthModal({ onClose }: AuthModalProps) {
  const signInWithGoogle = useAuthStore((state) => state.signInWithGoogle);
  const signInWithEmail = useAuthStore((state) => state.signInWithEmail);
  const signUpWithEmail = useAuthStore((state) => state.signUpWithEmail);

  const [activeTab, setActiveTab] = useState<AuthTab>("sign_in");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [checkEmailSent, setCheckEmailSent] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [isGoogleHovered, setIsGoogleHovered] = useState(false);
  const [isCloseHovered, setIsCloseHovered] = useState(false);
  const [isCtaPressed, setIsCtaPressed] = useState(false);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const ctaLabel = useMemo(() => {
    if (isSubmitting) {
      return "Please wait…";
    }
    return activeTab === "sign_in" ? "Sign In" : "Create Account";
  }, [activeTab, isSubmitting]);

  const getInputStyle = (fieldName: string): React.CSSProperties => {
    if (focusedField !== fieldName) {
      return INPUT_BASE_STYLE;
    }
    return {
      ...INPUT_BASE_STYLE,
      borderColor: "#6c47ff",
      background: "#ffffff",
    };
  };

  const switchTab = (tab: AuthTab): void => {
    setActiveTab(tab);
    setErrorMessage("");
    setEmail("");
    setPassword("");
    setCheckEmailSent(false);
  };

  const handleGoogleSignIn = (): void => {
    void signInWithGoogle();
  };

  const handleEmailAction = async (): Promise<void> => {
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      if (activeTab === "sign_in") {
        await signInWithEmail(email, password);
        onClose();
        return;
      }

      await signUpWithEmail(email, password, fullName);
      setCheckEmailSent(true);
    } catch (error) {
      if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Authentication failed");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        zIndex: 100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        style={{
          position: "relative",
          background: "#ffffff",
          borderRadius: "16px",
          padding: "32px",
          width: "100%",
          maxWidth: "420px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
          boxSizing: "border-box",
        }}
      >
        <button
          type="button"
          onClick={onClose}
          style={{
            position: "absolute",
            top: "16px",
            right: "16px",
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: "20px",
            color: isCloseHovered ? "#374151" : "#9ca3af",
            lineHeight: 1,
            padding: 0,
          }}
          onMouseEnter={() => setIsCloseHovered(true)}
          onMouseLeave={() => setIsCloseHovered(false)}
          aria-label="Close"
        >
          ✕
        </button>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <div
            style={{
              width: "36px",
              height: "36px",
              background: "linear-gradient(135deg, #6c47ff, #5a3de0)",
              borderRadius: "10px",
              color: "#ffffff",
              fontSize: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            ✦
          </div>
          <div>
            <div
              style={{
                fontSize: "20px",
                fontWeight: 800,
                color: "#111827",
              }}
            >
              Resume Intelligence
            </div>
            <div
              style={{
                fontSize: "13px",
                color: "#6b7280",
                marginTop: "4px",
              }}
            >
              Sign in to save your analysis history
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleGoogleSignIn}
          style={{
            width: "100%",
            padding: "12px",
            border: "1.5px solid #e5e7eb",
            borderRadius: "10px",
            background: isGoogleHovered ? "#f9fafb" : "#ffffff",
            color: "#374151",
            fontSize: "14px",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "10px",
            cursor: "pointer",
            marginTop: "24px",
            boxSizing: "border-box",
          }}
          onMouseEnter={() => setIsGoogleHovered(true)}
          onMouseLeave={() => setIsGoogleHovered(false)}
        >
          <svg width="18" height="18" viewBox="0 0 18 18">
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
          Continue with Google
        </button>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            margin: "20px 0",
          }}
        >
          <hr
            style={{
              flex: 1,
              border: "none",
              borderTop: "1px solid #e5e7eb",
            }}
          />
          <div
            style={{
              fontSize: "13px",
              color: "#9ca3af",
            }}
          >
            or
          </div>
          <hr
            style={{
              flex: 1,
              border: "none",
              borderTop: "1px solid #e5e7eb",
            }}
          />
        </div>

        <div
          style={{
            display: "flex",
            background: "#f3f4f6",
            borderRadius: "10px",
            padding: "4px",
          }}
        >
          <button
            type="button"
            onClick={() => switchTab("sign_in")}
            style={{
              flex: 1,
              padding: "8px",
              fontSize: "13px",
              fontWeight: 600,
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              textAlign: "center",
              background: activeTab === "sign_in" ? "#ffffff" : "transparent",
              color: activeTab === "sign_in" ? "#111827" : "#6b7280",
              boxShadow:
                activeTab === "sign_in" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => switchTab("sign_up")}
            style={{
              flex: 1,
              padding: "8px",
              fontSize: "13px",
              fontWeight: 600,
              borderRadius: "8px",
              border: "none",
              cursor: "pointer",
              textAlign: "center",
              background: activeTab === "sign_up" ? "#ffffff" : "transparent",
              color: activeTab === "sign_up" ? "#111827" : "#6b7280",
              boxShadow:
                activeTab === "sign_up" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
            }}
          >
            Sign Up
          </button>
        </div>

        {checkEmailSent ? (
          <div
            style={{
              textAlign: "center",
              marginTop: "24px",
            }}
          >
            <div
              style={{
                fontSize: "34px",
                lineHeight: 1,
              }}
            >
              ✉
            </div>
            <div
              style={{
                fontSize: "20px",
                fontWeight: 700,
                color: "#111827",
                marginTop: "14px",
              }}
            >
              Check your inbox
            </div>
            <div
              style={{
                fontSize: "14px",
                color: "#6b7280",
                marginTop: "8px",
              }}
            >
              We sent a confirmation link to {email}
            </div>
          </div>
        ) : (
          <div style={{ marginTop: "16px" }}>
            {activeTab === "sign_up" && (
              <div style={{ marginBottom: "16px" }}>
                <label
                  htmlFor="auth-full-name"
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    color: "#6c47ff",
                    letterSpacing: "0.5px",
                    textTransform: "uppercase",
                    display: "block",
                    marginBottom: "5px",
                  }}
                >
                  Full Name
                </label>
                <input
                  id="auth-full-name"
                  type="text"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  style={getInputStyle("fullName")}
                  onFocus={() => setFocusedField("fullName")}
                  onBlur={() => setFocusedField((current) => (current === "fullName" ? null : current))}
                />
              </div>
            )}

            <div style={{ marginBottom: "16px" }}>
              <label
                htmlFor="auth-email"
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "#6c47ff",
                  letterSpacing: "0.5px",
                  textTransform: "uppercase",
                  display: "block",
                  marginBottom: "5px",
                }}
              >
                Email
              </label>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                style={getInputStyle("email")}
                onFocus={() => setFocusedField("email")}
                onBlur={() => setFocusedField((current) => (current === "email" ? null : current))}
              />
            </div>

            <div style={{ marginBottom: "16px" }}>
              <label
                htmlFor="auth-password"
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "#6c47ff",
                  letterSpacing: "0.5px",
                  textTransform: "uppercase",
                  display: "block",
                  marginBottom: "5px",
                }}
              >
                Password
              </label>
              <input
                id="auth-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                style={getInputStyle("password")}
                onFocus={() => setFocusedField("password")}
                onBlur={() => setFocusedField((current) => (current === "password" ? null : current))}
              />
            </div>

            {errorMessage ? (
              <div
                style={{
                  background: "#fef2f2",
                  border: "1.5px solid #fecaca",
                  borderRadius: "8px",
                  padding: "10px 14px",
                  fontSize: "13px",
                  color: "#ef4444",
                  marginBottom: "16px",
                }}
              >
                {errorMessage}
              </div>
            ) : null}

            <button
              type="button"
              onClick={() => void handleEmailAction()}
              disabled={isSubmitting}
              style={{
                width: "100%",
                padding: "12px",
                background: isSubmitting ? "#f3f4f6" : "#6c47ff",
                color: isSubmitting ? "#9ca3af" : "#ffffff",
                border: isSubmitting
                  ? "1.5px solid #e5e7eb"
                  : "1.5px solid #5a3de0",
                boxShadow: isSubmitting
                  ? "2px 3px 0px #e5e7eb"
                  : isCtaPressed
                    ? "0px 1px 0px #5a3de0"
                    : "2px 3px 0px #5a3de0",
                borderRadius: "10px",
                fontSize: "14px",
                fontWeight: 700,
                cursor: isSubmitting ? "not-allowed" : "pointer",
                transform: !isSubmitting && isCtaPressed ? "translateY(2px)" : "translateY(0px)",
                transition: "transform 0.05s, box-shadow 0.05s",
              }}
              onMouseDown={() => {
                if (!isSubmitting) {
                  setIsCtaPressed(true);
                }
              }}
              onMouseUp={() => setIsCtaPressed(false)}
              onMouseLeave={() => setIsCtaPressed(false)}
            >
              {ctaLabel}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
