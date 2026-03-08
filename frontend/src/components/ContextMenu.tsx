import { useState, useEffect, useRef } from "react";
import { Trash2, Play, Copy, Focus, Loader2, Pencil, EyeOff } from "lucide-react";
import { toast } from "sonner";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import type { TransformInfo } from "../types/transform";
import { api } from "../api/client";
import { getSigmaRef } from "../stores/sigmaRef";
import { useIsViewer } from "../hooks/useIsViewer";

interface MenuState {
  visible: boolean;
  x: number;
  y: number;
  type: "node" | "edge" | "stage";
  id: string | null;
}

export function ContextMenu() {
  const [menu, setMenu] = useState<MenuState>({
    visible: false,
    x: 0,
    y: 0,
    type: "stage",
    id: null,
  });
  const [transforms, setTransforms] = useState<TransformInfo[]>([]);
  const [showTransforms, setShowTransforms] = useState(false);
  const [runningTransform, setRunningTransform] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const { entities, removeEntity, removeEdge, selectNode, hideNode, hideEdge, hideConnectedEdges } = useGraphStore();
  const { currentProject } = useProjectStore();
  const isViewer = useIsViewer();

  const entity = menu.id && menu.type === "node" ? entities.get(menu.id) : null;
  const menuVisible = menu.visible;
  const menuX = menu.x;
  const menuY = menu.y;

  // Listen for context menu events from GraphCanvas
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setMenu({
        visible: true,
        x: detail.x,
        y: detail.y,
        type: detail.type,
        id: detail.id,
      });
      setShowTransforms(false);
      setRunningTransform(null);

      // Fetch transforms if right-clicked a node
      if (detail.type === "node" && detail.id) {
        api.transforms
          .forEntity(detail.id)
          .then(setTransforms)
          .catch(() => setTransforms([]));
      }
    };

    window.addEventListener("ogi-context-menu", handler);
    return () => window.removeEventListener("ogi-context-menu", handler);
  }, []);

  // Close on click outside or Escape
  useEffect(() => {
    if (!menu.visible) return;

    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenu((m) => ({ ...m, visible: false }));
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenu((m) => ({ ...m, visible: false }));
      }
    };

    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [menu.visible]);

  // Adjust menu position to stay within viewport
  useEffect(() => {
    if (!menuVisible || !menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    let x = menuX;
    let y = menuY;
    if (rect.right > window.innerWidth) {
      x = window.innerWidth - rect.width - 8;
    }
    if (rect.bottom > window.innerHeight) {
      y = window.innerHeight - rect.height - 8;
    }
    if (x < 0) x = 8;
    if (y < 0) y = 8;
    if (x !== menuX || y !== menuY) {
      setMenu((m) => ({ ...m, x, y }));
    }
  }, [menuVisible, menuX, menuY]);

  if (!menu.visible) return null;

  const close = () => setMenu((m) => ({ ...m, visible: false }));

  const handleDelete = async () => {
    if (!currentProject || !menu.id) return;
    if (menu.type === "node") {
      if (!window.confirm("Are you sure you want to delete this entity?")) return;
      await removeEntity(currentProject.id, menu.id);
      toast.success("Entity deleted");
    } else if (menu.type === "edge") {
      if (!window.confirm("Are you sure you want to delete this edge?")) return;
      await removeEdge(currentProject.id, menu.id);
      toast.success("Edge deleted");
    }
    close();
  };

  const handleCopyValue = () => {
    if (entity) {
      navigator.clipboard.writeText(entity.value);
      toast.success("Copied to clipboard");
    }
    close();
  };

  const handleSelectNode = () => {
    if (menu.id && menu.type === "node") {
      selectNode(menu.id);
    }
    close();
  };

  const handleFitToScreen = () => {
    getSigmaRef()?.getCamera().animatedReset();
    close();
  };

  const handleExpandNeighbors = async () => {
    if (!currentProject || !menu.id || menu.type !== "node") return;
    try {
      const before = useGraphStore.getState().entities.size;
      const { entities: neighborEntities, edges: neighborEdges } = await api.graph.neighbors(
        currentProject.id,
        menu.id
      );
      const { addEntity, addEdge } = useGraphStore.getState();
      for (const item of neighborEntities) addEntity(currentProject.id, item);
      for (const item of neighborEdges) addEdge(currentProject.id, item);
      const after = useGraphStore.getState().entities.size;
      toast.success(`Expanded neighbors: +${Math.max(0, after - before)} entities`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Failed to expand neighbors: ${msg}`);
    } finally {
      close();
    }
  };

  const handleEditProperties = () => {
    if (!menu.id || menu.type !== "node") return;
    selectNode(menu.id);
    window.dispatchEvent(new CustomEvent("ogi-edit-properties", { detail: { entityId: menu.id } }));
    close();
  };

  const handleHideNode = () => {
    if (!currentProject || !menu.id || menu.type !== "node") return;
    hideNode(currentProject.id, menu.id);
    toast.success("Entity hidden");
    close();
  };

  const handleHideConnectedEdges = () => {
    if (!currentProject || !menu.id || menu.type !== "node") return;
    hideConnectedEdges(currentProject.id, menu.id);
    toast.success("Connected edges hidden");
    close();
  };

  const handleHideEdge = () => {
    if (!currentProject || !menu.id || menu.type !== "edge") return;
    hideEdge(currentProject.id, menu.id);
    toast.success("Edge hidden");
    close();
  };

  const handleRunTransform = async (name: string) => {
    if (!currentProject || !menu.id) return;
    setRunningTransform(name);
    try {
      const run = await api.transforms.run(name, menu.id, currentProject.id);
      if (run.result) {
        const { addEntity, addEdge } = useGraphStore.getState();
        for (const newEntity of run.result.entities) {
          addEntity(currentProject.id, newEntity);
        }
        for (const newEdge of run.result.edges) {
          addEdge(currentProject.id, newEdge);
        }
        toast.success(`${name}: found ${run.result.entities.length} entities`);
      }
      if (run.error) {
        toast.error(`${name}: ${run.error}`);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Transform failed: ${msg}`);
    } finally {
      setRunningTransform(null);
      close();
    }
  };

  const itemClass =
    "w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text hover:bg-surface-hover text-left";

  return (
    <div
      ref={menuRef}
      className="fixed z-50 bg-surface border border-border rounded shadow-lg py-1 min-w-[180px] animate-fade-in"
      style={{ left: menu.x, top: menu.y }}
    >
      {menu.type === "node" && entity && (
        <>
          <div className="px-3 py-1 text-[10px] text-text-muted border-b border-border mb-1 truncate max-w-[240px]">
            {entity.value}
          </div>

          <button onClick={handleSelectNode} className={itemClass}>
            <Focus size={12} />
            Select
          </button>

          <button onClick={handleExpandNeighbors} className={itemClass}>
            <Focus size={12} />
            Expand Neighbors
          </button>

          {!isViewer && (
            <button onClick={handleEditProperties} className={itemClass}>
              <Pencil size={12} />
              Edit Properties...
            </button>
          )}

          {!isViewer && (
            <>
              <button onClick={handleHideNode} className={itemClass}>
                <EyeOff size={12} />
                Hide Selected Node
              </button>

              <button onClick={handleHideConnectedEdges} className={itemClass}>
                <EyeOff size={12} />
                Hide Connected Edges
              </button>
            </>
          )}

          <button onClick={handleCopyValue} className={itemClass}>
            <Copy size={12} />
            Copy Value
          </button>

          {!isViewer && transforms.length > 0 && (
            <>
              <div className="border-t border-border my-1" />
              {showTransforms ? (
                transforms.map((t) => (
                  <button
                    key={t.name}
                    onClick={() => handleRunTransform(t.name)}
                    disabled={runningTransform !== null}
                    className={`${itemClass} disabled:opacity-50`}
                  >
                    {runningTransform === t.name ? (
                      <Loader2 size={12} className="animate-spin text-accent" />
                    ) : (
                      <Play size={12} className="text-accent shrink-0" />
                    )}
                    {t.display_name}
                  </button>
                ))
              ) : (
                <button
                  onClick={() => setShowTransforms(true)}
                  className={itemClass}
                >
                  <Play size={12} className="text-accent shrink-0" />
                  Run Transform...
                </button>
              )}
            </>
          )}

          {!isViewer && (
            <>
              <div className="border-t border-border my-1" />
              <button onClick={handleDelete} className={`${itemClass} text-danger hover:text-danger`}>
                <Trash2 size={12} />
                Delete Entity
              </button>
            </>
          )}
        </>
      )}

      {menu.type === "edge" && !isViewer && (
        <>
          <button onClick={handleHideEdge} className={itemClass}>
            <EyeOff size={12} />
            Hide Edge
          </button>

          <div className="border-t border-border my-1" />

          <button onClick={handleDelete} className={`${itemClass} text-danger hover:text-danger`}>
            <Trash2 size={12} />
            Delete Edge
          </button>
        </>
      )}

      {menu.type === "stage" && (
        <>
          <button onClick={handleFitToScreen} className={itemClass}>
            <Focus size={12} />
            Fit to Screen
          </button>
        </>
      )}
    </div>
  );
}
