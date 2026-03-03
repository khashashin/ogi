import { Panel, Group, Separator } from "react-resizable-panels";
import { GraphCanvas } from "./GraphCanvas";
import { EntityPalette } from "./EntityPalette";
import { EntityInspector } from "./EntityInspector";
import { TransformPanel } from "./TransformPanel";
import { Toolbar } from "./Toolbar";
import { ContextMenu } from "./ContextMenu";
import { SearchBar } from "./SearchBar";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";

export function Layout() {
  useKeyboardShortcuts();

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
              <div className="h-full bg-surface border-t border-border overflow-hidden">
                <TransformPanel />
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
