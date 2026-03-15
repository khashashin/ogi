import { useState } from "react";
import {
  Bot,
  Boxes,
  ChevronUp,
  CircleX,
  ListTree,
  SlidersHorizontal,
} from "lucide-react";

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

type SheetTab = "panel" | "details" | "nodes" | "tools";

function MobileCenterView() {
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

export function MobileWorkspace() {
  const isViewer = useIsViewer();
  const { entities } = useGraphStore();
  const [bottomTab, setBottomTab] = useState<BottomTab>(
    isViewer ? "events" : "transforms",
  );
  const [activeSheet, setActiveSheet] = useState<SheetTab>("panel");
  const [sheetOpen, setSheetOpen] = useState(false);

  const openSheet = (tab: SheetTab) => {
    setActiveSheet(tab);
    setSheetOpen(true);
  };

  const renderBottomPanel = () => (
    <>
      {bottomTab === "transforms" && !isViewer && <TransformPanel />}
      {bottomTab === "analysis" && !isViewer && <AnalysisPanel />}
      {bottomTab === "investigator" && !isViewer && <InvestigatorPanel />}
      {bottomTab === "events" && <EventingPanel />}
      {bottomTab === "timeline" && <TimelinePanel />}
    </>
  );

  const renderSheetContent = () => {
    switch (activeSheet) {
      case "details":
        return <EntityInspector />;
      case "nodes":
        return <EntityPalette />;
      case "tools":
        return <RightToolbar orientation="horizontal" />;
      case "panel":
      default:
        return renderBottomPanel();
    }
  };

  const sheetTitle =
    activeSheet === "details"
      ? "Inspector"
      : activeSheet === "nodes"
        ? "Entity Palette"
        : activeSheet === "tools"
          ? "Project Tools"
          : bottomTab === "investigator"
            ? "AI Investigator"
            : bottomTab === "analysis"
              ? "Analysis"
              : bottomTab === "timeline"
                ? "Timeline"
                : bottomTab === "events"
                  ? "Events"
                  : "Transforms";

  return (
    <div className="flex h-screen w-screen flex-col bg-bg">
      <Toolbar />
      <ProjectRealtimeBridge />

      <div className="relative min-h-0 flex-1">
        <MobileCenterView />
      </div>

      <div className="border-t border-border bg-surface">
        <div className="flex items-center gap-1 overflow-x-auto px-2 py-2">
          {!isViewer && (
            <button
              onClick={() => openSheet("nodes")}
              className="shrink-0 rounded border border-border px-2 py-1 text-[11px] text-text-muted"
            >
              Nodes
            </button>
          )}
          <button
            onClick={() => openSheet("details")}
            className="shrink-0 rounded border border-border px-2 py-1 text-[11px] text-text-muted"
          >
            Details
          </button>
          <button
            onClick={() => openSheet("tools")}
            className="shrink-0 rounded border border-border px-2 py-1 text-[11px] text-text-muted"
          >
            Tools
          </button>
          {!isViewer && (
            <>
              <button
                onClick={() => {
                  setBottomTab("transforms");
                  openSheet("panel");
                }}
                className={tabButtonClass(bottomTab, "transforms")}
              >
                <Boxes size={12} className="mr-1 inline" />
                Transforms
              </button>
              <button
                onClick={() => {
                  setBottomTab("analysis");
                  openSheet("panel");
                }}
                className={tabButtonClass(bottomTab, "analysis")}
              >
                <SlidersHorizontal size={12} className="mr-1 inline" />
                Analysis
              </button>
              <button
                onClick={() => {
                  setBottomTab("investigator");
                  openSheet("panel");
                }}
                className={tabButtonClass(bottomTab, "investigator")}
              >
                <Bot size={12} className="mr-1 inline" />
                AI
              </button>
            </>
          )}
          <button
            onClick={() => {
              setBottomTab("events");
              openSheet("panel");
            }}
            className={tabButtonClass(bottomTab, "events")}
          >
            Events
          </button>
          <button
            onClick={() => {
              setBottomTab("timeline");
              openSheet("panel");
            }}
            className={tabButtonClass(bottomTab, "timeline")}
          >
            <ListTree size={12} className="mr-1 inline" />
            Timeline
          </button>
          <div className="ml-auto shrink-0 text-[10px] text-text-muted">
            {entities.size} entities
          </div>
        </div>
      </div>

      {sheetOpen && (
        <div className="absolute inset-0 z-50 bg-black/45">
          <button
            className="absolute inset-0"
            onClick={() => setSheetOpen(false)}
            aria-label="Close mobile panel"
          />
          <div className="absolute inset-x-0 bottom-0 flex max-h-[78vh] flex-col overflow-hidden rounded-t-2xl border-t border-border bg-surface shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-3 py-3">
              <div className="flex items-center gap-2">
                <ChevronUp size={16} className="text-text-muted" />
                <span className="text-sm font-medium text-text">{sheetTitle}</span>
              </div>
              <button
                onClick={() => setSheetOpen(false)}
                className="rounded p-1 text-text-muted hover:bg-surface-hover"
              >
                <CircleX size={16} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">{renderSheetContent()}</div>
          </div>
        </div>
      )}

      <ContextMenu />
    </div>
  );
}
