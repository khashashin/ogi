import { useState } from "react";
import { Panel, Group, Separator } from "react-resizable-panels";
import { GraphCanvas } from "./GraphCanvas";
import { EntityPalette } from "./EntityPalette";
import { EntityInspector } from "./EntityInspector";
import { TransformPanel } from "./TransformPanel";
import { AnalysisPanel } from "./AnalysisPanel";
import { Toolbar } from "./Toolbar";
import { ContextMenu } from "./ContextMenu";
import { SearchBar } from "./SearchBar";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";

type BottomTab = "transforms" | "analysis";

export function Layout() {
  useKeyboardShortcuts();
  const [bottomTab, setBottomTab] = useState<BottomTab>("transforms");

  return (
    <div className="flex flex-col h-screen w-screen bg-bg">
      <Toolbar />
      <Group orientation="horizontal" className="flex-1">
        {/* Left sidebar: Entity Palette */}
        <Panel defaultSize={15} minSize={8} maxSize={25}>
          <div className="h-full bg-surface border-r border-border overflow-hidden">
            <EntityPalette />
          </div>
        </Panel>

        <Separator className="w-1 bg-border hover:bg-accent transition-colors cursor-col-resize" />

        {/* Center: Graph + Bottom panel */}
        <Panel defaultSize={65} minSize={30}>
          <Group orientation="vertical">
            <Panel defaultSize={70} minSize={30}>
              <div className="relative w-full h-full">
                <GraphCanvas />
                <SearchBar />
              </div>
            </Panel>

            <Separator className="h-1 bg-border hover:bg-accent transition-colors cursor-row-resize" />

            <Panel defaultSize={30} minSize={15}>
              <div className="h-full bg-surface border-t border-border overflow-hidden flex flex-col">
                {/* Bottom panel tabs */}
                <div className="flex border-b border-border">
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
                </div>
                <div className="flex-1 overflow-hidden">
                  {bottomTab === "transforms" ? <TransformPanel /> : <AnalysisPanel />}
                </div>
              </div>
            </Panel>
          </Group>
        </Panel>

        <Separator className="w-1 bg-border hover:bg-accent transition-colors cursor-col-resize" />

        {/* Right sidebar: Entity Inspector */}
        <Panel defaultSize={20} minSize={12} maxSize={30}>
          <div className="h-full bg-surface border-l border-border overflow-hidden">
            <EntityInspector />
          </div>
        </Panel>
      </Group>

      <ContextMenu />
    </div>
  );
}
