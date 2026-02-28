import { useEffect } from "react";
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

  return <Layout />;
}

export default App;
