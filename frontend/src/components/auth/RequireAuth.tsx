import { useAuthStore } from "../../store/authStore";

import AuthGateScreen from "./AuthGateScreen";

interface RequireAuthProps {
  children: React.ReactNode;
  onOpenAuthModal: () => void;
}

/**
 * Wraps protected UI: shows a hydration spinner, then either the full auth gate
 * (see `AuthGateScreen.tsx`) or `children`. Split-screen layout lives in
 * `AuthGateScreen`; this file only gates routing by auth state.
 */
export default function RequireAuth({
  children,
  onOpenAuthModal: _onOpenAuthModal,
}: RequireAuthProps) {
  const loading = useAuthStore((state) => state.loading);
  const user = useAuthStore((state) => state.user);

  if (loading) {
    return (
      <div
        style={{
          minHeight: "calc(100vh - 70px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "50%",
            border: "3px solid #e5e7eb",
            borderTopColor: "#6366f1",
            animation: "spin 0.7s linear infinite",
          }}
        />
      </div>
    );
  }

  if (!user) {
    return <AuthGateScreen />;
  }

  return <>{children}</>;
}
