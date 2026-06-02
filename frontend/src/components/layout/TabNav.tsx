import { useResumeStore } from "../../store/useResumeStore";
import { T } from "../../tokens";
import type { TabId } from "../../types/index";
import { countActionableFixes } from "../../utils/fixesPipeline";
import { hasJobDescription } from "../../utils/hasJobDescription";

const tabs: Array<{ id: TabId; icon: string; label: string }> = [
  { id: "overview", icon: "📊", label: "Overview" },
  { id: "gap", icon: "◎", label: "Gap Analysis" },
  { id: "recruiter", icon: "👤", label: "Recruiter View" },
  { id: "fixes", icon: "✦", label: "Fixes" },
  { id: "mock_interview", icon: "🎯", label: "Mock Interview" },
  { id: "progress", icon: "↗", label: "Progress" },
];

const disabledBeforeAnalysis = new Set<TabId>(["fixes", "gap"]);
const alwaysEnabledTabs = new Set<TabId>(["progress"]);
const roleFitLockedTabs = new Set<TabId>(["fixes", "gap", "progress"]);

export default function TabNav() {
  const activeTab = useResumeStore((state) => state.activeTab);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const analysisResult = useResumeStore((state) => state.analysisResult);
  const fallbackInfo = useResumeStore((state) => state.fallbackInfo);

  const hasJd = hasJobDescription(analysisResult?.gap);
  const roleFitLocked = analysisResult?.role_fit?.fitness === "underqualified";
  const fixCount = countActionableFixes(analysisResult);

  const unavailableByTab: Partial<Record<TabId, boolean>> = {
    fixes: (fallbackInfo.fixes?.length ?? 0) > 0,
    recruiter:
      (fallbackInfo.recruiter?.length ?? 0) > 0 || analysisResult?.sim === null,
    gap: (fallbackInfo.gap?.length ?? 0) > 0 || analysisResult?.gap === null,
  };

  const handleTabClick = (tabId: TabId): void => {
    if (tabId === "gap" && analysisResult && !hasJd) {
      return;
    }

    if (roleFitLocked && roleFitLockedTabs.has(tabId)) {
      return;
    }

    if (
      !analysisResult &&
      disabledBeforeAnalysis.has(tabId) &&
      !alwaysEnabledTabs.has(tabId)
    ) {
      return;
    }

    setActiveTab(tabId);
  };

  return (
    <nav
      role="tablist"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px 40px",
      }}
    >
      <div
        style={{
          display: "flex",
          border: `1.5px solid ${T.border}`,
          borderRadius: 12,
          overflow: "hidden",
          background: T.bgCard,
        }}
      >
        {tabs.map((tab, index) => {
        const isActive = activeTab === tab.id;
        const isGapLocked = tab.id === "gap" && Boolean(analysisResult) && !hasJd;
        const isRoleFitLocked = roleFitLocked && roleFitLockedTabs.has(tab.id);
        const isDisabled =
          isGapLocked ||
          isRoleFitLocked ||
          (!analysisResult &&
            disabledBeforeAnalysis.has(tab.id) &&
            !alwaysEnabledTabs.has(tab.id));

        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-controls={`panel-${tab.id}`}
            aria-selected={isActive}
            aria-label={tab.label}
            aria-disabled={isDisabled}
            onClick={() => handleTabClick(tab.id)}
            onMouseEnter={(event) => {
              if (!isActive && !isDisabled) {
                event.currentTarget.style.background = T.bgHover;
              }
            }}
            onMouseLeave={(event) => {
              if (!isActive && !isDisabled) {
                event.currentTarget.style.background = T.bgCard;
              }
            }}
            style={{
              padding: "8px 18px",
              fontSize: 13,
              fontWeight: isActive ? 700 : 500,
              color: isDisabled ? T.textDisabled : isActive ? "#ffffff" : T.textSecondary,
              background: isActive ? T.primary : T.bgCard,
              border: "none",
              borderLeft: index > 0 ? `1px solid ${isActive ? T.primary : T.border}` : "none",
              cursor: isDisabled ? "not-allowed" : "pointer",
              fontFamily: "inherit",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              whiteSpace: "nowrap",
              transition: "all 0.15s",
            }}
          >
            <span style={{ lineHeight: 1 }}>{tab.icon}</span>
            <span>{tab.label}</span>
            {tab.id === "fixes" && fixCount > 0 ? (
              <span
                style={{
                  marginLeft: "2px",
                  background: "#dcfce7",
                  color: "#15803d",
                  borderRadius: "999px",
                  padding: "1px 7px",
                  fontSize: "10px",
                  fontWeight: 700,
                }}
              >
                {fixCount}
              </span>
            ) : null}
            {isGapLocked || isRoleFitLocked ? (
              <span
                style={{
                  marginLeft: "2px",
                  background: "#f3f4f6",
                  color: "#9ca3af",
                  borderRadius: "999px",
                  padding: "1px 7px",
                  fontSize: "10px",
                  fontWeight: 700,
                }}
              >
                🔒
              </span>
            ) : null}
            {unavailableByTab[tab.id] && !isGapLocked ? (
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
      </div>
    </nav>
  );
}
