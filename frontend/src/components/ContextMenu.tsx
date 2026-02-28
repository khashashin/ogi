import { useState, useEffect, useRef } from "react";
import { Trash2, Play, Copy, Focus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import type { TransformInfo } from "../types/transform";
import { api } from "../api/client";
import { getSigmaRef } from "../stores/sigmaRef";

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

  const { entities, removeEntity, removeEdge, selectNode } = useGraphStore();
  const { currentProject } = useProjectStore();

  const entity = menu.id && menu.type === "node" ? entities.get(menu.id) : null;

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
    if (!menu.visible || !menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    let { x, y } = menu;
    if (rect.right > window.innerWidth) {
      x = window.innerWidth - rect.width - 8;
    }
    if (rect.bottom > window.innerHeight) {
      y = window.innerHeight - rect.height - 8;
    }
    if (x < 0) x = 8;
    if (y < 0) y = 8;
    if (x !== menu.x || y !== menu.y) {
      setMenu((m) => ({ ...m, x, y }));
    }
  }, [menu.visible]);

  if (!menu.visible) return null;

  const close = () => setMenu((m) => ({ ...m, visible: false }));

  const handleDelete = async () => {
    if (!currentProject || !menu.id) return;
    if (menu.type === "node") {
      await removeEntity(currentProject.id, menu.id);
      toast.success("Entity deleted");
    } else if (menu.type === "edge") {
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

          <button onClick={handleCopyValue} className={itemClass}>
            <Copy size={12} />
            Copy Value
          </button>

          {transforms.length > 0 && (
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
                      <Play size={12} className="text-accent" />
                    )}
                    {t.display_name}
                  </button>
                ))
              ) : (
                <button
                  onClick={() => setShowTransforms(true)}
                  className={itemClass}
                >
                  <Play size={12} className="text-accent" />
                  Run Transform...
                </button>
              )}
            </>
          )}

          <div className="border-t border-border my-1" />
          <button onClick={handleDelete} className={`${itemClass} text-danger hover:text-danger`}>
            <Trash2 size={12} />
            Delete Entity
          </button>
        </>
      )}

      {menu.type === "edge" && (
        <>
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
