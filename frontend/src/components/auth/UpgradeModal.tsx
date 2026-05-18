import { useEffect, useState } from "react";

interface UpgradeModalProps {
  uploadsThisMonth: number;
  limit: number;
  onClose: () => void;
}

export default function UpgradeModal({ uploadsThisMonth, limit, onClose }: UpgradeModalProps) {
  const [isCloseHovered, setIsCloseHovered] = useState(false);
  const [isCtaHovered, setIsCtaHovered] = useState(false);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

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
            transition: "color 0.15s",
          }}
          onMouseEnter={() => setIsCloseHovered(true)}
          onMouseLeave={() => setIsCloseHovered(false)}
          aria-label="Close modal"
        >
          ✕
        </button>

        <div style={{ marginBottom: "24px" }}>
          <div style={{ fontSize: "20px", fontWeight: 700, color: "#111827", marginBottom: "12px" }}>
            Monthly limit reached
          </div>
          <div style={{ fontSize: "14px", color: "#6b7280", lineHeight: 1.6 }}>
            You've used all {limit} free analyses this month. Upgrade to continue using Career Platform.
          </div>
        </div>

        <div
          style={{
            background: "#f9fafb",
            borderRadius: "12px",
            padding: "16px",
            marginBottom: "24px",
          }}
        >
          <div style={{ fontSize: "12px", fontWeight: 600, color: "#6b7280", marginBottom: "8px" }}>
            USAGE THIS MONTH
          </div>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "#6c47ff", marginBottom: "4px" }}>
            {uploadsThisMonth} / {limit}
          </div>
          <div style={{ fontSize: "12px", color: "#9ca3af" }}>
            Your counter resets on the 1st of next month
          </div>
        </div>

        <div style={{ marginBottom: "20px" }}>
          <div style={{ fontSize: "12px", fontWeight: 600, color: "#6b7280", marginBottom: "8px" }}>
            PRO FEATURES
          </div>
          <ul
            style={{
              fontSize: "14px",
              color: "#374151",
              margin: 0,
              paddingLeft: "20px",
              lineHeight: 1.7,
            }}
          >
            <li>Unlimited analyses</li>
            <li>Advanced recruiter simulation</li>
            <li>Priority support</li>
            <li>Export in multiple formats</li>
          </ul>
        </div>

        <button
          type="button"
          onClick={onClose}
          style={{
            width: "100%",
            padding: "12px 16px",
            background: isCtaHovered ? "#5a3ad6" : "#6c47ff",
            color: "#ffffff",
            border: "none",
            borderRadius: "10px",
            fontSize: "14px",
            fontWeight: 700,
            cursor: "pointer",
            transition: "background 0.15s",
            boxShadow: "0 3px 0 #4338ca",
          }}
          onMouseEnter={() => setIsCtaHovered(true)}
          onMouseLeave={() => setIsCtaHovered(false)}
        >
          Upgrade Now
        </button>

        <div style={{ textAlign: "center", marginTop: "16px" }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "#6b7280",
              fontSize: "14px",
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}
