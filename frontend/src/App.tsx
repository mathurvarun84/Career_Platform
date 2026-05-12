import { useCallback, useState } from "react";
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
import type { AnalysisResult } from "./types";
import { hydrateWithFallback } from "./utils/analysisFallback";

const queryClient = new QueryClient();

function AppShell() {
  const analysisResult = useResumeStore((state) => state.analysisResult);
  const isFullAnalysisReady = useResumeStore(
    (state) => state.isFullAnalysisReady
  );
  const activeTab = useResumeStore((state) => state.activeTab);
  const isLoading = useResumeStore((state) => state.isLoading);
  const isAnalyzing = useResumeStore((state) => state.isAnalyzing);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const setJobId = useResumeStore((state) => state.setJobId);
  const setAnalysisResult = useResumeStore((state) => state.setAnalysisResult);
  const setFallbackInfo = useResumeStore((state) => state.setFallbackInfo);
  const setIsLoading = useResumeStore((state) => state.setIsLoading);
  const setIsAnalyzing = useResumeStore((state) => state.setIsAnalyzing);
  const setIsFullAnalysisReady = useResumeStore(
    (state) => state.setIsFullAnalysisReady
  );

  const [streamInputs, setStreamInputs] = useState<{
    file: File;
    jdText: string;
  } | null>(null);

  const handleBeginAnalysis = useCallback(
    (file: File, jdText: string): void => {
      setStreamInputs({ file, jdText });
      setJobId(null);
      setAnalysisResult(null);
      setIsFullAnalysisReady(false);
      setIsLoading(true);
      setIsAnalyzing(true);
    },
    [
      setJobId,
      setAnalysisResult,
      setIsFullAnalysisReady,
      setIsLoading,
      setIsAnalyzing,
    ]
  );

  const handleAnalysisComplete = useCallback(
    (result: AnalysisResult): void => {
      const hydrated = hydrateWithFallback(result);
      setAnalysisResult(hydrated.analysis);
      setIsFullAnalysisReady(true);
      setFallbackInfo(hydrated.debugByTab);
      setJobId(hydrated.analysis.job_id);
      setActiveTab("overview");
      setStreamInputs(null);
      setIsLoading(false);
      setIsAnalyzing(false);
    },
    [
      setAnalysisResult,
      setIsFullAnalysisReady,
      setFallbackInfo,
      setJobId,
      setActiveTab,
      setIsLoading,
      setIsAnalyzing,
    ]
  );

  const showDashboard = Boolean(
    analysisResult !== null && isFullAnalysisReady
  );
  const showAnalyzingPage =
    Boolean(streamInputs) &&
    (isLoading || isAnalyzing) &&
    !isFullAnalysisReady;

  if (showDashboard) {
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
            <EvaluationDashboard
              onTabChange={(tab: string) =>
                setActiveTab(tab as import("./types").TabId)
              }
            />
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

  if (showAnalyzingPage && streamInputs) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "#ffffff",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <TopBar />
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
          }}
        >
          <AnalysisProgress
            resumeFile={streamInputs.file}
            jdText={streamInputs.jdText}
            onComplete={handleAnalysisComplete}
          />
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#ffffff" }}>
      <TopBar />
      <UploadZone onBeginAnalysis={handleBeginAnalysis} />
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
