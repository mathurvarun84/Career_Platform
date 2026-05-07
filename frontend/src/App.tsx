import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { EvaluationDashboard } from "./EvaluationDashboard";
import TopBar from "./components/layout/TopBar";
import TabNav from "./components/layout/TabNav";
import ActionableFixes from "./components/ActionableFixes";
import GapCloser from "./components/GapCloser";
import RecruiterSimulation from "./components/RecruiterSimulation";
import AnalysisProgress from "./components/upload/AnalysisProgress";
import UploadZone from "./components/upload/UploadZone";
import { useResumeStore } from "./store/useResumeStore";

const queryClient = new QueryClient();

function AppShell() {
  const analysisResult = useResumeStore((state) => state.analysisResult);
  const activeTab = useResumeStore((state) => state.activeTab);
  const isAnalyzing = useResumeStore((state) => state.isAnalyzing);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);

  if (!analysisResult) {
    return (
      <div style={{ minHeight: '100vh', background: '#ffffff' }}>
        <TopBar />
        <UploadZone />
        {isAnalyzing && <AnalysisProgress />}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <TopBar />
      <TabNav />
      <div className="tab-content">
        <div
          role="tabpanel"
          id="panel-overview"
          aria-labelledby="tab-overview"
          className={activeTab === "overview" ? "tab-enter" : undefined}
          style={{ display: activeTab === "overview" ? "block" : "none" }}
        >
          <EvaluationDashboard onTabChange={(tab: string) => setActiveTab(tab as import("./types").TabId)} />
        </div>
        <div
          role="tabpanel"
          id="panel-fixes"
          aria-labelledby="tab-fixes"
          className={activeTab === "fixes" ? "tab-enter" : undefined}
          style={{ display: activeTab === "fixes" ? "block" : "none" }}
        >
          <ActionableFixes />
        </div>
        <div
          role="tabpanel"
          id="panel-recruiter"
          aria-labelledby="tab-recruiter"
          className={activeTab === "recruiter" ? "tab-enter" : undefined}
          style={{ display: activeTab === "recruiter" ? "block" : "none" }}
        >
          <RecruiterSimulation />
        </div>
        <div
          role="tabpanel"
          id="panel-gap"
          aria-labelledby="tab-gap"
          className={activeTab === "gap" ? "tab-enter" : undefined}
          style={{ display: activeTab === "gap" ? "block" : "none" }}
        >
          <GapCloser />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
