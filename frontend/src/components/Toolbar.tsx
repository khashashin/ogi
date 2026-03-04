import { useState, useEffect } from "react";
import { Plus, FolderOpen, LayoutGrid, Maximize2, ZoomIn, ZoomOut, Focus, Download, Undo2, Redo2, Keyboard } from "lucide-react";
import { ExportImportDialog } from "./ExportImportDialog";
import { KeyboardShortcutsDialog } from "./KeyboardShortcutsDialog";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { circular } from "graphology-layout";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import { useUndoStore } from "../stores/undoStore";
import { getSigmaRef } from "../stores/sigmaRef";

export function Toolbar() {
  const { currentProject, projects, selectProject, createProject } = useProjectStore();
  const { graph, loadGraph, entities, edges, persistPositions, performUndo, performRedo } = useGraphStore();
  const canUndo = useUndoStore((s) => s.undoStack.length > 0);
  const canRedo = useUndoStore((s) => s.redoStack.length > 0);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [showProjectList, setShowProjectList] = useState(false);
  const [showExportImport, setShowExportImport] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return;
    await createProject(newProjectName.trim());
    setNewProjectName("");
    setShowNewProject(false);
  };

  const handleSelectProject = async (project: typeof projects[0]) => {
    selectProject(project);
    await loadGraph(project.id);
    setShowProjectList(false);
  };

  const runForceLayout = () => {
    if (graph.order < 2) return;
    forceAtlas2.assign(graph, {
      iterations: 200,
      settings: {
        gravity: 1,
        scalingRatio: 2,
        barnesHutOptimize: graph.order > 50,
      },
    });
    if (currentProject) persistPositions(currentProject.id);
  };

  const runCircularLayout = () => {
    if (graph.order < 2) return;
    circular.assign(graph);
    if (currentProject) persistPositions(currentProject.id);
  };

  // Listen for keyboard shortcut toggle
  useEffect(() => {
    const handler = () => setShowShortcuts((v) => !v);
    window.addEventListener("ogi-toggle-shortcuts", handler);
    return () => window.removeEventListener("ogi-toggle-shortcuts", handler);
  }, []);

  const handleZoomIn = () => getSigmaRef()?.getCamera().animatedZoom({ duration: 200 });
  const handleZoomOut = () => getSigmaRef()?.getCamera().animatedUnzoom({ duration: 200 });
  const handleFit = () => getSigmaRef()?.getCamera().animatedReset({ duration: 300 });

  return (
    <div className="flex items-center h-10 px-3 bg-surface border-b border-border gap-2">
      {/* Project selector */}
      <div className="relative">
        <button
          onClick={() => setShowProjectList(!showProjectList)}
          className="flex items-center gap-1.5 px-2 py-1 text-sm text-text hover:bg-surface-hover rounded"
        >
          <FolderOpen size={14} />
          <span>{currentProject?.name ?? "No Project"}</span>
        </button>
        {showProjectList && (
          <div className="absolute top-full left-0 mt-1 w-56 bg-surface border border-border rounded shadow-lg z-50">
            {projects.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSelectProject(p)}
                className="w-full text-left px-3 py-2 text-sm text-text hover:bg-surface-hover"
              >
                {p.name}
              </button>
            ))}
            {projects.length === 0 && (
              <p className="px-3 py-2 text-xs text-text-muted">No projects yet</p>
            )}
          </div>
        )}
      </div>

      {/* New project */}
      {showNewProject ? (
        <div className="flex items-center gap-1">
          <input
            type="text"
            placeholder="Project name"
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreateProject()}
            autoFocus
            className="px-2 py-1 text-xs bg-bg border border-border rounded text-text w-40 focus:outline-none focus:border-accent"
          />
          <button
            onClick={handleCreateProject}
            className="px-2 py-1 text-xs bg-accent text-white rounded hover:bg-accent-hover"
          >
            Create
          </button>
          <button
            onClick={() => setShowNewProject(false)}
            className="px-2 py-1 text-xs text-text-muted hover:text-text"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setShowNewProject(true)}
          className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-text hover:bg-surface-hover rounded"
        >
          <Plus size={12} />
          New
        </button>
      )}

      <div className="flex-1" />

      {/* Graph stats */}
      <span className="text-[10px] text-text-muted">
        {entities.size} entities, {edges.size} edges
      </span>

      <div className="w-px h-4 bg-border" />

      {/* Undo / Redo */}
      <button
        onClick={() => currentProject && performUndo(currentProject.id)}
        disabled={!canUndo}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded disabled:opacity-30 disabled:cursor-default"
        title="Undo (Ctrl+Z)"
      >
        <Undo2 size={14} />
      </button>
      <button
        onClick={() => currentProject && performRedo(currentProject.id)}
        disabled={!canRedo}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded disabled:opacity-30 disabled:cursor-default"
        title="Redo (Ctrl+Y)"
      >
        <Redo2 size={14} />
      </button>

      <div className="w-px h-4 bg-border" />

      {/* Zoom controls */}
      <button
        onClick={handleZoomIn}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded"
        title="Zoom in (+)"
      >
        <ZoomIn size={14} />
      </button>
      <button
        onClick={handleZoomOut}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded"
        title="Zoom out (-)"
      >
        <ZoomOut size={14} />
      </button>
      <button
        onClick={handleFit}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded"
        title="Fit to screen (0)"
      >
        <Focus size={14} />
      </button>

      <div className="w-px h-4 bg-border" />

      {/* Layout controls */}
      <button
        onClick={runForceLayout}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded"
        title="Force-directed layout"
      >
        <LayoutGrid size={14} />
      </button>
      <button
        onClick={runCircularLayout}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded"
        title="Circular layout"
      >
        <Maximize2 size={14} />
      </button>

      <div className="w-px h-4 bg-border" />

      <button
        onClick={() => setShowExportImport(true)}
        className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-text hover:bg-surface-hover rounded"
        title="Export / Import"
      >
        <Download size={12} />
        Export
      </button>

      <button
        onClick={() => setShowShortcuts(true)}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded"
        title="Keyboard shortcuts"
      >
        <Keyboard size={14} />
      </button>

      <ExportImportDialog
        open={showExportImport}
        onClose={() => setShowExportImport(false)}
      />
      <KeyboardShortcutsDialog
        open={showShortcuts}
        onClose={() => setShowShortcuts(false)}
      />
    </div>
  );
}
