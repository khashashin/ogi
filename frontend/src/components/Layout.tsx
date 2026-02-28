import { Panel, Group, Separator } from "react-resizable-panels";
import { GraphCanvas } from "./GraphCanvas";
import { EntityPalette } from "./EntityPalette";
import { EntityInspector } from "./EntityInspector";
import { TransformPanel } from "./TransformPanel";
import { Toolbar } from "./Toolbar";

export function Layout() {
  return (
    <div className="flex flex-col h-screen w-screen bg-bg">
      <Toolbar />
      <Group orientation="horizontal" className="flex-1">
        {/* Left sidebar: Entity Palette */}
        <Panel defaultSize={120} minSize={10} maxSize={120}>
          <div className="h-full bg-surface border-r border-border overflow-hidden">
            <EntityPalette />
          </div>
        </Panel>

        <Separator className="w-1 bg-border hover:bg-accent transition-colors cursor-col-resize" />

        {/* Center: Graph + Bottom panel */}
        <Panel defaultSize={60} minSize={30}>
          <Group orientation="vertical">
            <Panel defaultSize={70} minSize={30}>
              <GraphCanvas />
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
        <Panel defaultSize={320} minSize={15} maxSize={320}>
          <div className="h-full bg-surface border-l border-border overflow-hidden">
            <EntityInspector />
          </div>
        </Panel>
      </Group>
    </div>
  );
}
