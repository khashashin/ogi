import { useState } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";

import { AnalysisPanel } from "./AnalysisPanel";
import { ContextMenu } from "./ContextMenu";
import { EntityInspector } from "./EntityInspector";
import { EntityPalette } from "./EntityPalette";
import { EventingPanel } from "./EventingPanel";
import { FilterPanel } from "./FilterPanel";
import { GraphCanvas } from "./GraphCanvas";
import { InvestigatorPanel } from "./investigator/InvestigatorPanel";
import { MapView } from "./MapView";
import { ProjectRealtimeBridge } from "./ProjectRealtimeBridge";
import { RightToolbar } from "./RightToolbar";
import { SearchBar } from "./SearchBar";
import { TableView } from "./TableView";
import { TimelinePanel } from "./TimelinePanel";
import { Toolbar } from "./Toolbar";
import { TransformPanel } from "./TransformPanel";
import { useGraphStore } from "../stores/graphStore";
import { useIsViewer } from "../hooks/useIsViewer";
import { tabButtonClass, type BottomTab } from "./workspace";

function CenterView() {
  const { centerView } = useGraphStore();

  return (
    <div className="relative h-full w-full">
      {centerView === "graph" && <GraphCanvas />}
      {centerView === "table" && <TableView />}
      {centerView === "map" && <MapView />}
      <SearchBar />
      {centerView === "graph" && <FilterPanel mode="overlay" />}
    </div>
  );
}

export function DesktopWorkspace() {
  const isViewer = useIsViewer();
  const {
    entities,
    edges,
    selectedNodeIds,
    nodeOverlay,
    setNodeOverlay,
    setAnalysisResults,
  } = useGraphStore();
  const [bottomTab, setBottomTab] = useState<BottomTab>(
    isViewer ? "events" : "transforms",
  );

  const hasAnalysisOverlay = nodeOverlay?.type.startsWith("analysis");

  const renderBottomPanel = () => (
    <>
      {bottomTab === "transforms" && !isViewer && <TransformPanel />}
      {bottomTab === "analysis" && !isViewer && <AnalysisPanel />}
      {bottomTab === "investigator" && !isViewer && <InvestigatorPanel />}
      {bottomTab === "events" && <EventingPanel />}
      {bottomTab === "timeline" && <TimelinePanel />}
    </>
  );

  return (
    <div className="flex h-screen w-screen flex-col bg-bg">
      <Toolbar />
      <ProjectRealtimeBridge />
      <Group orientation="horizontal" className="flex-1">
        {!isViewer && (
          <>
            <Panel defaultSize={10} minSize={2}>
              <div className="h-full overflow-hidden border-r border-border bg-surface">
                <EntityPalette />
              </div>
            </Panel>
            <Separator className="w-1 cursor-col-resize bg-border transition-colors hover:bg-accent" />
          </>
        )}

        <Panel defaultSize={80} minSize={30}>
          <Group orientation="vertical">
            <Panel defaultSize={65} minSize={30}>
              <CenterView />
            </Panel>

            <Separator className="h-1 cursor-row-resize bg-border transition-colors hover:bg-accent" />

            <Panel defaultSize={35} minSize={15}>
              <div className="flex h-full flex-col overflow-hidden border-t border-border bg-surface">
                <div className="flex items-center justify-between border-b border-border pr-2">
                  <div className="flex">
                    {!isViewer && (
                      <>
                        <button
                          onClick={() => setBottomTab("transforms")}
                          className={tabButtonClass(bottomTab, "transforms")}
                        >
                          Transforms
                        </button>
                        <button
                          onClick={() => setBottomTab("analysis")}
                          className={tabButtonClass(bottomTab, "analysis")}
                        >
                          Analysis
                        </button>
                        <button
                          onClick={() => setBottomTab("investigator")}
                          className={tabButtonClass(bottomTab, "investigator")}
                        >
                          AI Investigator
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => setBottomTab("events")}
                      className={tabButtonClass(bottomTab, "events")}
                    >
                      Events
                    </button>
                    <button
                      onClick={() => setBottomTab("timeline")}
                      className={tabButtonClass(bottomTab, "timeline")}
                    >
                      Timeline
                    </button>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-text-muted">
                      {entities.size} entities, {edges.size} edges
                    </span>
                    {selectedNodeIds.size > 0 && (
                      <span className="text-[10px] text-accent">
                        {selectedNodeIds.size} selected
                      </span>
                    )}
                    {hasAnalysisOverlay && !isViewer && (
                      <button
                        onClick={() => {
                          setNodeOverlay(null);
                          setAnalysisResults(null);
                        }}
                        className="rounded border border-border px-2 py-1 text-[10px] text-text-muted transition-colors hover:bg-surface-hover"
                      >
                        Reset View
                      </button>
                    )}
                  </div>
                </div>
                <div className="flex-1 overflow-hidden">{renderBottomPanel()}</div>
              </div>
            </Panel>
          </Group>
        </Panel>

        <Separator className="w-1 cursor-col-resize bg-border transition-colors hover:bg-accent" />

        <Panel defaultSize={10} minSize={12}>
          <div className="h-full overflow-hidden border-l border-border bg-surface">
            <EntityInspector />
          </div>
        </Panel>

        <Separator className="w-px bg-border" />

        <div className="w-10 shrink-0 border-l border-border">
          <RightToolbar />
        </div>
      </Group>

      <ContextMenu />
    </div>
  );
}
