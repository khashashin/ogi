import { useEffect } from "react";
import { Routes, Route, useParams } from "react-router";
import { Loader2 } from "lucide-react";
import { Toaster } from "sonner";
import { Layout } from "./components/Layout";
import { AuthPage } from "./components/AuthPage";
import { ResetPasswordPage } from "./components/ResetPasswordPage";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LandingPage } from "./components/LandingPage";
import { MyProjectsPage } from "./components/MyProjectsPage";
import { DiscoverPage } from "./components/DiscoverPage";
import { TransformsCatalogPage } from "./components/TransformsCatalogPage";
import { TermsPage } from "./components/TermsPage";
import { PrivacyPage } from "./components/PrivacyPage";
import { CookieConsentBanner } from "./components/CookieConsentBanner";
import { BetaNoticeDialog } from "./components/BetaNoticeDialog";
import { useProjectStore } from "./stores/projectStore";
import { useGraphStore } from "./stores/graphStore";
import { useAuthStore } from "./stores/authStore";
import { useRealtimeSync } from "./hooks/useRealtimeSync";
import { useAnalytics } from "./hooks/useAnalytics";

function WorkspaceView() {
  const { projectId } = useParams<{ projectId: string }>();
  const { currentProject, loadProjectById, loading, error } = useProjectStore();
  const { loadGraph, loading: graphLoading } = useGraphStore();

  useRealtimeSync(currentProject?.id ?? null);

  useEffect(() => {
    if (projectId && currentProject?.id !== projectId) {
      loadProjectById(projectId);
    }
  }, [projectId, currentProject?.id, loadProjectById]);

  useEffect(() => {
    if (currentProject) {
      loadGraph(currentProject.id);
    }
  }, [currentProject, loadGraph]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-screen w-screen bg-bg gap-3">
        <Loader2 size={24} className="animate-spin text-accent" />
        <p className="text-sm text-text-muted">Loading project...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-screen w-screen bg-bg gap-3">
        <p className="text-sm text-danger">Failed to load project</p>
        <p className="text-xs text-text-muted max-w-md text-center">{error}</p>
      </div>
    );
  }

  return (
    <>
      <Layout />
      {graphLoading && (
        <div className="fixed bottom-4 left-4 z-50 flex items-center gap-2 bg-surface border border-border rounded px-3 py-2 shadow-lg animate-fade-in">
          <Loader2 size={14} className="animate-spin text-accent" />
          <span className="text-xs text-text-muted">Loading graph...</span>
        </div>
      )}
    </>
  );
}

function App() {
  useAnalytics();
  const initialize = useAuthStore((state) => state.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<AuthPage mode="signin" />} />
        <Route path="/signup" element={<AuthPage mode="signup" />} />
        <Route path="/forgot-password" element={<AuthPage mode="forgot" />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/discover" element={<DiscoverPage />} />
        <Route path="/transforms" element={<TransformsCatalogPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/projects" element={<MyProjectsPage />} />
          <Route path="/projects/:projectId" element={<WorkspaceView />} />
        </Route>
      </Routes>
      <BetaNoticeDialog />
      <CookieConsentBanner />
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#1a1d27",
            border: "1px solid #2e3348",
            color: "#e1e4ed",
          },
        }}
      />
    </>
  );
}

export default App;
