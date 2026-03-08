import { useState } from "react";
import { Panel, Group, Separator } from "react-resizable-panels";
import { GraphCanvas } from "./GraphCanvas";
import { EntityPalette } from "./EntityPalette";
import { EntityInspector } from "./EntityInspector";
import { TransformPanel } from "./TransformPanel";
import { AnalysisPanel } from "./AnalysisPanel";
import { Toolbar } from "./Toolbar";
import { RightToolbar } from "./RightToolbar";
import { ContextMenu } from "./ContextMenu";
import { SearchBar } from "./SearchBar";
import { FilterPanel } from "./FilterPanel";
import { TableView } from "./TableView";
import { EventingPanel } from "./EventingPanel";
import { TimelinePanel } from "./TimelinePanel";
import { MapView } from "./MapView";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useIsViewer } from "../hooks/useIsViewer";
import { useGraphStore } from "../stores/graphStore";

type BottomTab = "transforms" | "analysis" | "events" | "timeline";

export function Layout() {
  useKeyboardShortcuts();
  const isViewer = useIsViewer();
  const { centerView, nodeOverlay, setNodeOverlay, setAnalysisResults } = useGraphStore();
  const [bottomTab, setBottomTab] = useState<BottomTab>(isViewer ? "events" : "transforms");

  const hasAnalysisOverlay = nodeOverlay?.type.startsWith("analysis");

  return (
    <div className="flex flex-col h-screen w-screen bg-bg">
      <Toolbar />
      <RightToolbar />
      <Group orientation="horizontal" className="flex-1">
        {/* Left sidebar: Entity Palette */}
        {!isViewer && (
          <>
            <Panel defaultSize={10} minSize={2}>
              <div className="h-full bg-surface border-r border-border overflow-hidden">
                <EntityPalette />
              </div>
            </Panel>

            <Separator className="w-1 bg-border hover:bg-accent transition-colors cursor-col-resize" />
          </>
        )}

        {/* Center: Graph + Bottom panel */}
        <Panel defaultSize={80} minSize={30}>
          <Group orientation="vertical">
            <Panel defaultSize={70} minSize={30}>
              <div className="relative w-full h-full">
                {centerView === "graph" && <GraphCanvas />}
                {centerView === "table" && <TableView />}
                {centerView === "map" && <MapView />}
                <SearchBar />
                {centerView === "graph" && <FilterPanel mode="overlay" />}
              </div>
            </Panel>

            <>
              <Separator className="h-1 bg-border hover:bg-accent transition-colors cursor-row-resize" />

              <Panel defaultSize={30} minSize={15}>
                <div className="h-full bg-surface border-t border-border overflow-hidden flex flex-col">
                  {/* Bottom panel tabs */}
                  <div className="flex items-center justify-between border-b border-border pr-2">
                    <div className="flex">
                      {!isViewer && (
                        <>
                        <button
                          onClick={() => setBottomTab("transforms")}
                          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                            bottomTab === "transforms"
                              ? "text-text border-b-2 border-accent"
                              : "text-text-muted hover:text-text"
                          }`}
                        >
                          Transforms
                        </button>
                        <button
                          onClick={() => setBottomTab("analysis")}
                          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                            bottomTab === "analysis"
                              ? "text-text border-b-2 border-accent"
                              : "text-text-muted hover:text-text"
                          }`}
                        >
                          Analysis
                        </button>
                        </>
                      )}
                        <button
                          onClick={() => setBottomTab("events")}
                          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                            bottomTab === "events"
                              ? "text-text border-b-2 border-accent"
                              : "text-text-muted hover:text-text"
                          }`}
                        >
                          Events
                        </button>
                        <button
                          onClick={() => setBottomTab("timeline")}
                          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                            bottomTab === "timeline"
                              ? "text-text border-b-2 border-accent"
                              : "text-text-muted hover:text-text"
                          }`}
                        >
                          Timeline
                        </button>
                    </div>
                    {hasAnalysisOverlay && !isViewer && (
                        <button
                          onClick={() => {
                            setNodeOverlay(null);
                            setAnalysisResults(null);
                          }}
                          className="px-2 py-1 text-[10px] text-text-muted border border-border rounded hover:bg-surface-hover transition-colors"
                        >
                          Reset View
                        </button>
                    )}
                  </div>
                  <div className="flex-1 overflow-hidden">
                    {bottomTab === "transforms" && !isViewer && <TransformPanel />}
                    {bottomTab === "analysis" && !isViewer && <AnalysisPanel />}
                    {bottomTab === "events" && <EventingPanel />}
                    {bottomTab === "timeline" && <TimelinePanel />}
                  </div>
                </div>
              </Panel>
            </>
          </Group>
        </Panel>

        <Separator className="w-1 bg-border hover:bg-accent transition-colors cursor-col-resize" />

        {/* Right sidebar: Entity Inspector */}
        <Panel defaultSize={10} minSize={12}>
          <div className="h-full bg-surface border-l border-border overflow-hidden">
            <EntityInspector />
          </div>
        </Panel>
      </Group>

      <ContextMenu />
    </div>
  );
}
