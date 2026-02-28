import { useEffect } from "react";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import { getSigmaRef } from "../stores/sigmaRef";

export function useKeyboardShortcuts() {
  const { selectedNodeId, selectedEdgeId, removeEntity, removeEdge, selectNode } =
    useGraphStore();
  const { currentProject } = useProjectStore();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't intercept when typing in inputs
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }

      const sigma = getSigmaRef();

      // Delete / Backspace — delete selected
      if (e.key === "Delete" || e.key === "Backspace") {
        if (currentProject && selectedNodeId) {
          e.preventDefault();
          removeEntity(currentProject.id, selectedNodeId);
        } else if (currentProject && selectedEdgeId) {
          e.preventDefault();
          removeEdge(currentProject.id, selectedEdgeId);
        }
      }

      // Escape — deselect
      if (e.key === "Escape") {
        selectNode(null);
      }

      // + / = — zoom in
      if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        sigma?.getCamera().animatedZoom({ duration: 200 });
      }

      // - — zoom out
      if (e.key === "-") {
        e.preventDefault();
        sigma?.getCamera().animatedUnzoom({ duration: 200 });
      }

      // 0 — fit to screen
      if (e.key === "0" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        sigma?.getCamera().animatedReset({ duration: 300 });
      }
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [selectedNodeId, selectedEdgeId, currentProject, removeEntity, removeEdge, selectNode]);
}
