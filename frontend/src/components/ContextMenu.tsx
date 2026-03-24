import { lazy, Suspense, useState, useEffect, useRef } from "react";
import {
  Trash2,
  Play,
  Copy,
  Focus,
  Loader2,
  Pencil,
  EyeOff,
  Lock,
  Unlock,
  Link2,
  Palette,
  ImageIcon,
} from "lucide-react";
import { toast } from "sonner";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";
import type { TransformInfo } from "../types/transform";
import { api } from "../api/client";
import { getSigmaRef } from "../stores/sigmaRef";
import { useIsViewer } from "../hooks/useIsViewer";
import { resolveEntityIconName } from "../lib/entityIconRegistry";
import { ENTITY_TYPE_META, EntityType } from "../types/entity";
const ChangeIconDialog = lazy(() =>
  import("./ChangeIconDialog").then((module) => ({ default: module.ChangeIconDialog })),
);
const ChangePersonImageDialog = lazy(() =>
  import("./ChangePersonImageDialog").then((module) => ({
    default: module.ChangePersonImageDialog,
  })),
);

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
  const [showChangeIcon, setShowChangeIcon] = useState(false);
  const [showChangeImage, setShowChangeImage] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const {
    entities,
    pinnedNodeIds,
    removeEntity,
    removeEdge,
    selectNode,
    hideNode,
    hideEdge,
    hideConnectedEdges,
    pinNode,
    unpinNode,
    connectionDraft,
    startConnectionDraft,
    cancelConnectionDraft,
  } = useGraphStore();
  const { currentProject } = useProjectStore();
  const isViewer = useIsViewer();

  const entity = menu.id && menu.type === "node" ? entities.get(menu.id) : null;
  const isPinned = Boolean(menu.id && pinnedNodeIds.has(menu.id));
  const isConnectionSource = Boolean(menu.id && connectionDraft.sourceId === menu.id);
  const isPersonNode = entity?.type === EntityType.Person;
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

  const handleTogglePin = () => {
    if (!currentProject || !menu.id || menu.type !== "node") return;
    if (isPinned) {
      unpinNode(currentProject.id, menu.id);
      toast.success("Node unpinned");
    } else {
      pinNode(currentProject.id, menu.id);
      toast.success("Node pinned");
    }
    close();
  };

  const handleStartConnection = () => {
    if (!menu.id || menu.type !== "node") return;
    if (isConnectionSource) {
      cancelConnectionDraft();
      toast.success("Connection mode cancelled");
    } else {
      startConnectionDraft(menu.id);
      selectNode(menu.id);
      toast.success("Connection mode started. Select a target node.");
    }
    close();
  };

  const handleOpenChangeIcon = () => {
    if (!menu.id || menu.type !== "node") return;
    setShowChangeIcon(true);
    close();
  };

  const handleOpenChangeImage = () => {
    if (!menu.id || menu.type !== "node" || !isPersonNode) return;
    setShowChangeImage(true);
    close();
  };

  const handleSaveIcon = async (iconName: string) => {
    if (!currentProject || !entity) return;
    try {
      const defaultIcon = ENTITY_TYPE_META[entity.type]?.icon ?? iconName;
      const normalizedIcon =
        resolveEntityIconName(iconName) === resolveEntityIconName(defaultIcon)
          ? defaultIcon
          : iconName;
      const updated = await api.entities.update(currentProject.id, entity.id, { icon: normalizedIcon });
      const { entities: entityMap } = useGraphStore.getState();
      entityMap.set(updated.id, updated);
      useGraphStore.setState({ entities: new Map(entityMap) });
      toast.success("Node icon updated");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Icon update failed: ${msg}`);
      throw e;
    }
  };

  const handleSavePersonImage = async (file: File) => {
    if (!currentProject || !entity || entity.type !== EntityType.Person) return;
    try {
      const result = await api.entities.uploadPersonImage(currentProject.id, entity.id, file);
      const updated = result.entity;
      const { entities: entityMap } = useGraphStore.getState();
      entityMap.set(updated.id, updated);
      useGraphStore.setState({ entities: new Map(entityMap) });
      toast.success("Person image updated");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Image update failed: ${msg}`);
      throw e;
    }
  };

  const handleRemovePersonImage = async () => {
    if (!currentProject || !entity || entity.type !== EntityType.Person) return;
    try {
      const updated = await api.entities.update(currentProject.id, entity.id, {
        properties: {
          ...entity.properties,
          visual_image_url: null,
          visual_image_backend: null,
          visual_image_path: null,
          visual_image_content_type: null,
        },
      });
      const { entities: entityMap } = useGraphStore.getState();
      entityMap.set(updated.id, updated);
      useGraphStore.setState({ entities: new Map(entityMap) });
      toast.success("Person image removed");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Image update failed: ${msg}`);
      throw e;
    }
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
    <>
      {menu.visible && (
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
            <button onClick={handleOpenChangeIcon} className={itemClass}>
              <Palette size={12} />
              Change Icon...
            </button>
          )}

          {!isViewer && isPersonNode && (
            <button onClick={handleOpenChangeImage} className={itemClass}>
              <ImageIcon size={12} />
              Change Image...
            </button>
          )}

          {!isViewer && (
            <>
              <button onClick={handleStartConnection} className={itemClass}>
                <Link2 size={12} />
                {isConnectionSource ? "Cancel Connection" : "Start Connection"}
              </button>

              <button onClick={handleTogglePin} className={itemClass}>
                {isPinned ? <Unlock size={12} /> : <Lock size={12} />}
                {isPinned ? "Unpin Node" : "Pin Node"}
              </button>

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
      )}

      <Suspense fallback={null}>
        <ChangeIconDialog
          open={showChangeIcon && Boolean(entity)}
          currentIcon={entity?.icon ?? "hash"}
          entityLabel={entity?.value ?? ""}
          onClose={() => setShowChangeIcon(false)}
          onSave={handleSaveIcon}
        />
      </Suspense>

      <Suspense fallback={null}>
        <ChangePersonImageDialog
          open={showChangeImage && isPersonNode}
          currentImageUrl={
            typeof entity?.properties?.visual_image_url === "string"
              ? entity.properties.visual_image_url
              : ""
          }
          projectId={currentProject?.id ?? null}
          entityId={entity?.id ?? null}
          entityLabel={entity?.value ?? ""}
          onClose={() => setShowChangeImage(false)}
          onSave={handleSavePersonImage}
          onRemove={handleRemovePersonImage}
        />
      </Suspense>
    </>
  );
}
