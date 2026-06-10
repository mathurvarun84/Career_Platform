import { useCallback, useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { EvaluationDashboard } from "./EvaluationDashboard";
import TopBar from "./components/layout/TopBar";
import TabNav from "./components/layout/TabNav";
import ActionableFixes from "./components/ActionableFixes";
import GapCloser from "./components/GapCloser";
import ProgressTracking from "./components/ProgressTracking";
import MockInterview from "./components/MockInterview";
import RecruiterSimulation from "./components/RecruiterSimulation";
import AuthModal from "./components/auth/AuthModal";
import RequireAuth from "./components/auth/RequireAuth";
import ResumeUpload from "./components/ResumeUpload";
import AnalysisProgress from "./components/upload/AnalysisProgress";
import LandingPage from "./components/LandingPage";
import Footer from "./components/Footer";
import { useProgressStore } from "./hooks/useProgressStore";
import { supabase } from "./lib/supabase";
import { useAuthStore } from "./store/authStore";
import { useResumeStore } from "./store/useResumeStore";
import { T } from "./tokens";
import type { AnalysisResult } from "./types";
import { hydrateWithFallback } from "./utils/analysisFallback";
import PipelineInspectorPage from "./pages/PipelineInspectorPage";

const queryClient = new QueryClient();

const isDevPipelineInspector =
  import.meta.env.DEV && window.location.pathname === "/debug/pipeline";

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
  const [hasLeftLanding, setHasLeftLanding] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      console.log("AUTH EVENT:", _event, session?.user?.email);
      setSession(session);
      if (_event === "SIGNED_OUT") {
        setHasLeftLanding(false);
      }
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
      // Do NOT reset hasLeftLanding — user is on the upload page and should
      // stay there (transitioning to AnalysisProgress) not go back to landing.
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

  const handleNavigateToUpload = useCallback((): void => {
    setHasLeftLanding(true);
    setAnalysisResult(null);
    setIsFullAnalysisReady(false);
    setJobId(null);
    setActiveTab("overview");
  }, [setAnalysisResult, setIsFullAnalysisReady, setJobId, setActiveTab]);

  const showDashboard = Boolean(
    analysisResult !== null && isFullAnalysisReady
  );
  const showProgressStandalone =
    Boolean(user) && activeTab === "progress" && !showDashboard;
  const showAnalyzingPage =
    Boolean(streamInputs) &&
    (isLoading || isAnalyzing) &&
    !isFullAnalysisReady;
  const showLandingPage = !analysisResult && !showAnalyzingPage && !hasLeftLanding;

  if (showProgressStandalone) {
    return (
      <div className="page-shell min-h-screen" style={{ background: T.bgPage }}>
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
      <div className="page-shell min-h-screen" style={{ background: T.bgPage }}>
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
            id="panel-mock_interview"
            aria-labelledby="tab-mock_interview"
            className={activeTab === "mock_interview" ? "tab-enter" : undefined}
            style={{
              display: activeTab === "mock_interview" ? "block" : "none",
            }}
          >
            <div
              style={{
                maxWidth: "1200px",
                margin: "0 auto",
                padding: "40px 32px 48px",
              }}
            >
              <MockInterview />
            </div>
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
          background: "#f7f7fc",
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

  if (showLandingPage) {
    return (
      <div className="page-shell" style={{ minHeight: "100vh" }}>
        <LandingPage
          onNavigateToUpload={handleNavigateToUpload}
          onOpenAuthModal={() => setIsAuthModalOpen(true)}
        />
        <Footer />
        {isAuthModalOpen ? (
          <AuthModal onClose={() => setIsAuthModalOpen(false)} />
        ) : null}
      </div>
    );
  }

  return (
    <div className="page-shell" style={{ minHeight: "100vh", background: "#f7f7fc" }}>
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
  if (isDevPipelineInspector) {
    return <PipelineInspectorPage />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
