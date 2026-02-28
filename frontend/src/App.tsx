import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { Toaster } from "sonner";
import { Layout } from "./components/Layout";
import { useProjectStore } from "./stores/projectStore";
import { useGraphStore } from "./stores/graphStore";

function App() {
  const { fetchProjects, currentProject, loading, error } = useProjectStore();
  const { loadGraph, loading: graphLoading } = useGraphStore();

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    if (currentProject) {
      loadGraph(currentProject.id);
    }
  }, [currentProject, loadGraph]);

  return (
    <>
      {loading ? (
        <div className="flex flex-col items-center justify-center h-screen w-screen bg-bg gap-3">
          <Loader2 size={24} className="animate-spin text-accent" />
          <p className="text-sm text-text-muted">Loading projects...</p>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center h-screen w-screen bg-bg gap-3">
          <p className="text-sm text-danger">Failed to connect to backend</p>
          <p className="text-xs text-text-muted max-w-md text-center">{error}</p>
          <button
            onClick={() => fetchProjects()}
            className="px-3 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover"
          >
            Retry
          </button>
        </div>
      ) : (
        <Layout />
      )}
      {graphLoading && !loading && (
        <div className="fixed bottom-4 left-4 z-50 flex items-center gap-2 bg-surface border border-border rounded px-3 py-2 shadow-lg animate-fade-in">
          <Loader2 size={14} className="animate-spin text-accent" />
          <span className="text-xs text-text-muted">Loading graph...</span>
        </div>
      )}
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
