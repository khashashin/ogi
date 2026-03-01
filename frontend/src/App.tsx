import { useEffect } from "react";
import { Toaster } from "sonner";
import { Layout } from "./components/Layout";
import { useProjectStore } from "./stores/projectStore";
import { useGraphStore } from "./stores/graphStore";

function App() {
  const { fetchProjects, currentProject } = useProjectStore();
  const { loadGraph } = useGraphStore();

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
      <Layout />
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#1e1e2e",
            border: "1px solid #313244",
            color: "#cdd6f4",
          },
        }}
      />
    </>
  );
}

export default App;
