import { useResumeStore } from "../../store/useResumeStore";
import type { TabId } from "../../types/index";
import { useWindowSize } from "../../hooks/useWindowSize";

const tabs: Array<{ id: TabId; icon: string; label: string }> = [
  { id: "overview", icon: "⊞", label: "Overview" },
  { id: "fixes", icon: "✦", label: "Actionable Fixes" },
  { id: "recruiter", icon: "👤", label: "Recruiter View" },
  { id: "gap", icon: "◎", label: "Gap Closer" },
];

const disabledBeforeAnalysis = new Set<TabId>(["fixes", "gap"]);

export default function TabNav() {
  const activeTab = useResumeStore((state) => state.activeTab);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const analysisResult = useResumeStore((state) => state.analysisResult);
  const fallbackInfo = useResumeStore((state) => state.fallbackInfo);
  const { isMobile } = useWindowSize();
  const unavailableByTab: Partial<Record<TabId, boolean>> = {
    fixes: (fallbackInfo.fixes?.length ?? 0) > 0,
    recruiter:
      (fallbackInfo.recruiter?.length ?? 0) > 0 || analysisResult?.sim === null,
    gap: (fallbackInfo.gap?.length ?? 0) > 0 || analysisResult?.gap === null,
  };

  const handleTabClick = (tabId: TabId): void => {
    if (!analysisResult && disabledBeforeAnalysis.has(tabId)) {
      return;
    }

    setActiveTab(tabId);
  };

  return (
    <nav
      className={isMobile ? "tab-nav-scroll" : undefined}
      role="tablist"
      style={{
        display: "flex",
        alignItems: "center",
        background: "#ffffff",
        borderBottom: "1.5px solid #e5e7eb",
        padding: isMobile ? "0 16px" : "0 32px",
        gap: "0",
        overflowX: isMobile ? "auto" : "visible",
        whiteSpace: isMobile ? "nowrap" : "normal",
        msOverflowStyle: "none",
        scrollbarWidth: "none",
        WebkitOverflowScrolling: "touch",
      }}
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        const isDisabled = !analysisResult && disabledBeforeAnalysis.has(tab.id);

        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-controls={`panel-${tab.id}`}
            aria-selected={isActive}
            aria-label={tab.label}
            onClick={() => handleTabClick(tab.id)}
            onMouseEnter={(event) => {
              if (!isActive && !isDisabled) {
                event.currentTarget.style.color = "#374151";
                event.currentTarget.style.background = "#f9fafb";
              }
            }}
            onMouseLeave={(event) => {
              if (!isActive && !isDisabled) {
                event.currentTarget.style.color = "#6b7280";
                event.currentTarget.style.background = "transparent";
              }
            }}
            style={{
              padding: "14px 20px",
              fontSize: "13px",
              fontWeight: isActive ? 700 : 500,
              color: isDisabled ? "#d1d5db" : isActive ? "#6366f1" : "#6b7280",
              background: "transparent",
              border: "none",
              borderBottom: isActive
                ? "2px solid #6366f1"
                : "2px solid transparent",
              cursor: isDisabled ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              whiteSpace: "nowrap",
              transition: "color 0.15s",
              marginBottom: "-1.5px",
            }}
          >
            <span style={{ lineHeight: 1 }}>{tab.icon}</span>
            <span>{tab.label}</span>
            {unavailableByTab[tab.id] ? (
              <span
                style={{
                  marginLeft: "4px",
                  background: "#fefce8",
                  border: "1px solid #fde68a",
                  color: "#d97706",
                  borderRadius: "999px",
                  padding: "1px 7px",
                  fontSize: "10px",
                  fontWeight: 700,
                }}
              >
                !
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}
