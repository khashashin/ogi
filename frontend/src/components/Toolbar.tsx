import { useState, useEffect } from "react";
import { Link } from "react-router";
import { LayoutGrid, Wand2, ZoomIn, ZoomOut, Focus, Download, Undo2, Redo2, Keyboard, User, Lock, Unlock, Users, ChevronRight, Table, Network, Map as MapIcon, EyeOff, Eye } from "lucide-react";
import { ExportImportDialog } from "./ExportImportDialog";
import { KeyboardShortcutsDialog } from "./KeyboardShortcutsDialog";
import { ProfileDialog } from "./ProfileDialog";
import { ApiKeySettings } from "./ApiKeySettings";
import { TransformHub } from "./marketplace/TransformHub";
import { ShareDialog } from "./ShareDialog";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import { useUndoStore } from "../stores/undoStore";
import { useAuthStore } from "../stores/authStore";
import { getSigmaRef } from "../stores/sigmaRef";
import { useIsViewer } from "../hooks/useIsViewer";
import { applyGraphLayout, GRAPH_LAYOUT_OPTIONS, type GraphLayoutPreset } from "../lib/graphLayouts";

export function Toolbar() {
  const { currentProject, updateProject } = useProjectStore();
  const {
    graph,
    entities,
    edges,
    centerView,
    setCenterView,
    persistPositions,
    performUndo,
    performRedo,
    selectedNodeId,
    selectedEdgeId,
    manualHiddenNodeIds,
    manualHiddenEdgeIds,
    hideSelected,
    unhideAll,
    unhideNode,
    unhideEdge,
  } = useGraphStore();
  const canUndo = useUndoStore((s) => s.undoStack.length > 0);
  const canRedo = useUndoStore((s) => s.redoStack.length > 0);
  const [showExportImport, setShowExportImport] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showApiKeys, setShowApiKeys] = useState(false);
  const [showPlugins, setShowPlugins] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [showHiddenItems, setShowHiddenItems] = useState(false);
  const [selectedLayout, setSelectedLayout] = useState<GraphLayoutPreset>("force");
  const { user, authEnabled } = useAuthStore();
  const isViewer = useIsViewer();

  const handleTogglePrivacy = async () => {
    if (!currentProject) return;
    try {
      await updateProject(currentProject.id, { is_public: !currentProject.is_public });
    } catch (err) {
      console.error(err);
    }
  };

  const applySelectedLayout = () => {
    if (graph.order < 2) return;
    applyGraphLayout(selectedLayout, graph, entities);
    if (currentProject) persistPositions(currentProject.id);
    getSigmaRef()?.refresh();
    getSigmaRef()?.getCamera().animatedReset({ duration: 300 });
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
  const hiddenEntities = [...manualHiddenNodeIds]
    .map((id) => entities.get(id))
    .filter((entity): entity is NonNullable<typeof entity> => Boolean(entity));
  const hiddenEdges = [...manualHiddenEdgeIds]
    .map((id) => edges.get(id))
    .filter((edge): edge is NonNullable<typeof edge> => Boolean(edge));
  const hasSelection = Boolean(selectedNodeId || selectedEdgeId);

  return (
    <div className="flex items-center h-10 px-3 bg-surface border-b border-border gap-2">
      {/* Dashboard link + breadcrumb */}
      <Link
        to="/"
        className="text-sm font-semibold text-text hover:text-accent transition-colors"
      >
        OpenGraph Intel
      </Link>
      <span className="px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider bg-warning/15 text-warning border border-warning/30 rounded">
        beta
      </span>
      {currentProject && (
        <>
          <ChevronRight size={12} className="text-text-muted" />
          <span className="text-sm text-text truncate max-w-48">
            {currentProject.name}
          </span>
        </>
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
        disabled={!canUndo || isViewer}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded disabled:opacity-30 disabled:cursor-default"
        title="Undo (Ctrl+Z)"
      >
        <Undo2 size={14} />
      </button>
      <button
        onClick={() => currentProject && performRedo(currentProject.id)}
        disabled={!canRedo || isViewer}
        className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded disabled:opacity-30 disabled:cursor-default"
        title="Redo (Ctrl+Y)"
      >
        <Redo2 size={14} />
      </button>

      {centerView === "graph" && (
        <>
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
          <div className="flex items-center gap-1 rounded border border-border bg-bg px-1 py-0.5">
            <LayoutGrid size={12} className="text-text-muted" />
            <select
              value={selectedLayout}
              onChange={(e) => setSelectedLayout(e.target.value as GraphLayoutPreset)}
              className="bg-transparent text-[11px] text-text focus:outline-none"
              title="Choose layout preset"
            >
              {GRAPH_LAYOUT_OPTIONS.map((option) => (
                <option key={option.id} value={option.id} className="bg-surface text-text">
                  {option.label}
                </option>
              ))}
            </select>
            <button
              onClick={applySelectedLayout}
              className="p-1 text-text-muted hover:text-text hover:bg-surface-hover rounded"
              title={GRAPH_LAYOUT_OPTIONS.find((option) => option.id === selectedLayout)?.description ?? "Apply layout"}
            >
              <Wand2 size={12} />
            </button>
          </div>

          <div className="w-px h-4 bg-border" />

          {!isViewer && (
            <>
              <button
                onClick={() => currentProject && hideSelected(currentProject.id)}
                disabled={!currentProject || !hasSelection}
                className="p-1.5 text-text-muted hover:text-text hover:bg-surface-hover rounded disabled:opacity-30 disabled:cursor-default"
                title="Hide selected item"
              >
                <EyeOff size={14} />
              </button>

              <div className="relative">
                <button
                  onClick={() => setShowHiddenItems((open) => !open)}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-text hover:bg-surface-hover rounded"
                  title="Show hidden items"
                >
                  <Eye size={12} />
                  Hidden {manualHiddenNodeIds.size + manualHiddenEdgeIds.size > 0 ? `(${manualHiddenNodeIds.size + manualHiddenEdgeIds.size})` : ""}
                </button>
                {showHiddenItems && (
                  <div className="absolute right-0 top-8 z-50 w-80 rounded border border-border bg-surface shadow-lg p-2">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-text">Hidden Items</span>
                      <button
                        onClick={() => currentProject && unhideAll(currentProject.id)}
                        disabled={!currentProject || (manualHiddenNodeIds.size === 0 && manualHiddenEdgeIds.size === 0)}
                        className="text-[11px] text-accent disabled:opacity-40"
                      >
                        Unhide all
                      </button>
                    </div>
                    {hiddenEntities.length === 0 && hiddenEdges.length === 0 ? (
                      <div className="text-[11px] text-text-muted">No hidden items.</div>
                    ) : (
                      <div className="max-h-72 overflow-auto space-y-2">
                        {hiddenEntities.length > 0 && (
                          <div>
                            <div className="mb-1 text-[10px] uppercase tracking-wide text-text-muted">Entities</div>
                            <div className="space-y-1">
                              {hiddenEntities.map((entity) => (
                                <div key={entity.id} className="flex items-center justify-between gap-2 rounded bg-bg px-2 py-1">
                                  <div className="min-w-0">
                                    <div className="truncate text-xs text-text">{entity.value}</div>
                                    <div className="text-[10px] text-text-muted">{entity.type}</div>
                                  </div>
                                  <button
                                    onClick={() => currentProject && unhideNode(currentProject.id, entity.id)}
                                    className="text-[11px] text-accent"
                                  >
                                    Show
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {hiddenEdges.length > 0 && (
                          <div>
                            <div className="mb-1 text-[10px] uppercase tracking-wide text-text-muted">Edges</div>
                            <div className="space-y-1">
                              {hiddenEdges.map((edge) => (
                                <div key={edge.id} className="flex items-center justify-between gap-2 rounded bg-bg px-2 py-1">
                                  <div className="min-w-0">
                                    <div className="truncate text-xs text-text">{edge.label || "Edge"}</div>
                                    <div className="text-[10px] text-text-muted">{edge.source_id.slice(0, 6)} {"->"} {edge.target_id.slice(0, 6)}</div>
                                  </div>
                                  <button
                                    onClick={() => currentProject && unhideEdge(currentProject.id, edge.id)}
                                    className="text-[11px] text-accent"
                                  >
                                    Show
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="w-px h-4 bg-border" />
            </>
          )}
        </>
      )}

      <button
        onClick={() => setCenterView("graph")}
        className={`p-1.5 rounded ${centerView === "graph" ? "text-accent bg-surface-hover" : "text-text-muted hover:text-text hover:bg-surface-hover"}`}
        title="Graph view"
      >
        <Network size={14} />
      </button>
      <button
        onClick={() => setCenterView("table")}
        className={`p-1.5 rounded ${centerView === "table" ? "text-accent bg-surface-hover" : "text-text-muted hover:text-text hover:bg-surface-hover"}`}
        title="Table view"
      >
        <Table size={14} />
      </button>
      <button
        onClick={() => setCenterView("map")}
        className={`p-1.5 rounded ${centerView === "map" ? "text-accent bg-surface-hover" : "text-text-muted hover:text-text hover:bg-surface-hover"}`}
        title="Map view"
      >
        <MapIcon size={14} />
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

      <div className="w-px h-4 bg-border" />

      {/* Privacy Toggle & Share */}
      {currentProject && (!currentProject.owner_id || currentProject.owner_id === user?.id) && !isViewer && (
        <>
          <button
            onClick={() => setShowShare(true)}
            className="p-1.5 rounded hover:bg-surface-hover text-text-muted hover:text-text"
            title="Share Project"
          >
            <Users size={14} />
          </button>
          
          <button
            onClick={handleTogglePrivacy}
            className={`p-1.5 rounded hover:bg-surface-hover ${currentProject.is_public ? 'text-green-400' : 'text-text-muted hover:text-text'}`}
            title={currentProject.is_public ? "Public Project (Click to make Private)" : "Private Project (Click to make Public)"}
          >
            {currentProject.is_public ? <Unlock size={14} /> : <Lock size={14} />}
          </button>
          <div className="w-px h-4 bg-border" />
        </>
      )}

      {/* User profile */}
      <button
        onClick={() => setShowProfile(true)}
        className="flex items-center justify-center w-6 h-6 rounded-full bg-accent text-white text-[10px] font-semibold hover:opacity-80"
        title={authEnabled && user?.email ? user.email : "Profile & Settings"}
      >
        {authEnabled && user ? (
          ((user.user_metadata?.display_name as string) ?? user.email ?? "")
            .slice(0, 2)
            .toUpperCase() || <User size={12} />
        ) : (
          <User size={12} />
        )}
      </button>

      <ExportImportDialog
        open={showExportImport}
        onClose={() => setShowExportImport(false)}
      />
      <KeyboardShortcutsDialog
        open={showShortcuts}
        onClose={() => setShowShortcuts(false)}
      />
      <ProfileDialog
        open={showProfile}
        onClose={() => setShowProfile(false)}
        onOpenApiKeys={() => setShowApiKeys(true)}
        onOpenPlugins={() => setShowPlugins(true)}
      />
      <ApiKeySettings
        open={showApiKeys}
        onClose={() => setShowApiKeys(false)}
      />
      <TransformHub
        open={showPlugins}
        onClose={() => setShowPlugins(false)}
      />
      {currentProject && (
        <ShareDialog
          open={showShare}
          onClose={() => setShowShare(false)}
          projectId={currentProject.id}
        />
      )}
    </div>
  );
}
