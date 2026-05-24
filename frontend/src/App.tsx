import { useCallback, useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { EvaluationDashboard } from "./EvaluationDashboard";
import TopBar from "./components/layout/TopBar";
import TabNav from "./components/layout/TabNav";
import ActionableFixes from "./components/ActionableFixes";
import GapCloser from "./components/GapCloser";
import ProgressTracking from "./components/ProgressTracking";
import RecruiterSimulation from "./components/RecruiterSimulation";
import AuthModal from "./components/auth/AuthModal";
import RequireAuth from "./components/auth/RequireAuth";
import ResumeUpload from "./components/ResumeUpload";
import AnalysisProgress from "./components/upload/AnalysisProgress";
import { useProgressStore } from "./hooks/useProgressStore";
import { supabase } from "./lib/supabase";
import { useAuthStore } from "./store/authStore";
import { useResumeStore } from "./store/useResumeStore";
import type { AnalysisResult } from "./types";
import { hydrateWithFallback } from "./utils/analysisFallback";

const queryClient = new QueryClient();

function AppShell() {
  const setSession = useAuthStore((state) => state.setSession);
  const user = useAuthStore((state) => state.user);
  const analysisResult = useResumeStore((state) => state.analysisResult);
  const isFullAnalysisReady = useResumeStore(
    (state) => state.isFullAnalysisReady
  );
  const isLoading = useResumeStore((state) => state.isLoading);
  const isAnalyzing = useResumeStore((state) => state.isAnalyzing);
  const setActiveTab = useResumeStore((state) => state.setActiveTab);
  const setJobId = useResumeStore((state) => state.setJobId);
  const setAnalysisJdText = useResumeStore((state) => state.setAnalysisJdText);
  const setAnalysisResult = useResumeStore((state) => state.setAnalysisResult);
  const setFallbackInfo = useResumeStore((state) => state.setFallbackInfo);
  const setIsLoading = useResumeStore((state) => state.setIsLoading);
  const setIsAnalyzing = useResumeStore((state) => state.setIsAnalyzing);
  const setIsFullAnalysisReady = useResumeStore(
    (state) => state.setIsFullAnalysisReady
  );
  const bumpHistoryRefresh = useResumeStore((state) => state.bumpHistoryRefresh);
  const activeTab = useResumeStore((state) => state.activeTab);
  const {
    addCareerEntry,
    addSnapshot,
    career_record,
    snapshots,
    totalCoaching,
    totalPatches,
  } = useProgressStore();

  const [streamInputs, setStreamInputs] = useState<{
    file: File;
    jdText: string;
  } | null>(null);
  // Keep single AuthModal here so TopBar and RequireAuth share one instance.
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      console.log("AUTH EVENT:", _event, session?.user?.email);
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (user) {
      setIsAuthModalOpen(false);
    }
  }, [user]);

  const handleBeginAnalysis = useCallback(
    (file: File, jdText: string): void => {
      setStreamInputs({ file, jdText });
      setAnalysisJdText(jdText.trim() || null);
      setJobId(null);
      setAnalysisResult(null);
      setIsFullAnalysisReady(false);
      setIsLoading(true);
      setIsAnalyzing(true);
    },
    [
      setJobId,
      setAnalysisJdText,
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
      addSnapshot({
        timestamp: new Date().toISOString(),
        ats_score: hydrated.analysis.ats.score,
        jd_match: hydrated.analysis.gap?.jd_match_score_before ?? null,
        percentile: hydrated.analysis.percentile?.percentile ?? null,
        label: "Initial Analysis",
        patches_applied: 0,
        coaching_answers: 0,
        session_id: hydrated.analysis.job_id,
      });
      setStreamInputs(null);
      setIsLoading(false);
      setIsAnalyzing(false);
      bumpHistoryRefresh();
    },
    [
      setAnalysisResult,
      setIsFullAnalysisReady,
      setFallbackInfo,
      setJobId,
      setActiveTab,
      addSnapshot,
      setIsLoading,
      setIsAnalyzing,
      bumpHistoryRefresh,
    ]
  );

  const handleAnalysisCancelled = useCallback((): void => {
    setStreamInputs(null);
    setIsLoading(false);
    setIsAnalyzing(false);
  }, [setIsLoading, setIsAnalyzing]);

  const showDashboard = Boolean(
    analysisResult !== null && isFullAnalysisReady
  );
  const showProgressStandalone =
    Boolean(user) && activeTab === "progress" && !showDashboard;
  const showAnalyzingPage =
    Boolean(streamInputs) &&
    (isLoading || isAnalyzing) &&
    !isFullAnalysisReady;

  if (showProgressStandalone) {
    return (
      <div className="page-shell min-h-screen bg-white">
        <TopBar
          onOpenAuthModal={() => setIsAuthModalOpen(true)}
          onViewProgress={() => setActiveTab("progress")}
        />
        <ProgressTracking
          sessionId={analysisResult?.job_id ?? null}
          snapshots={snapshots}
          careerRecord={career_record}
          addCareerEntry={addCareerEntry}
        />
        {isAuthModalOpen ? (
          <AuthModal onClose={() => setIsAuthModalOpen(false)} />
        ) : null}
      </div>
    );
  }

  if (showDashboard) {
    return (
      <div className="page-shell min-h-screen bg-white">
        <TopBar
          onOpenAuthModal={() => setIsAuthModalOpen(true)}
          onViewProgress={() => setActiveTab("progress")}
        />
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
            id="panel-gap"
            aria-labelledby="tab-gap"
            className={activeTab === "gap" ? "tab-enter" : undefined}
            style={{ display: activeTab === "gap" ? "block" : "none" }}
          >
            <GapCloser onTabChange={(tab) => setActiveTab(tab)} />
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
            id="panel-fixes"
            aria-labelledby="tab-fixes"
            className={activeTab === "fixes" ? "tab-enter" : undefined}
            style={{ display: activeTab === "fixes" ? "block" : "none" }}
          >
            <ActionableFixes
              addSnapshot={addSnapshot}
              addCareerEntry={addCareerEntry}
              totalPatchesApplied={totalPatches}
              totalCoachingAnswers={totalCoaching}
            />
          </div>
          <div
            role="tabpanel"
            id="panel-progress"
            aria-labelledby="tab-progress"
            className={activeTab === "progress" ? "tab-enter" : undefined}
            style={{ display: activeTab === "progress" ? "block" : "none" }}
          >
            <ProgressTracking
              sessionId={analysisResult?.job_id ?? null}
              snapshots={snapshots}
              careerRecord={career_record}
              addCareerEntry={addCareerEntry}
            />
          </div>
        </div>
        {isAuthModalOpen ? (
          <AuthModal onClose={() => setIsAuthModalOpen(false)} />
        ) : null}
      </div>
    );
  }

  if (showAnalyzingPage && streamInputs) {
    return (
      <div
        className="page-shell"
        style={{
          minHeight: "100vh",
          background: "#ffffff",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <TopBar
          onOpenAuthModal={() => setIsAuthModalOpen(true)}
          onViewProgress={() => setActiveTab("progress")}
        />
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
            onLimitDismiss={handleAnalysisCancelled}
          />
        </div>
        {isAuthModalOpen ? (
          <AuthModal onClose={() => setIsAuthModalOpen(false)} />
        ) : null}
      </div>
    );
  }

  return (
    <div className="page-shell" style={{ minHeight: "100vh", background: "#ffffff" }}>
      <TopBar
        onOpenAuthModal={() => setIsAuthModalOpen(true)}
        onViewProgress={() => setActiveTab("progress")}
      />
      <RequireAuth onOpenAuthModal={() => setIsAuthModalOpen(true)}>
        <ResumeUpload onBeginAnalysis={handleBeginAnalysis} />
      </RequireAuth>
      {isAuthModalOpen ? (
        <AuthModal onClose={() => setIsAuthModalOpen(false)} />
      ) : null}
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
