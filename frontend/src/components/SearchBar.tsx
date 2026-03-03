import { useState, useEffect, useRef } from "react";
import { Search, X } from "lucide-react";
import { useGraphStore } from "../stores/graphStore";
import { getSigmaRef } from "../stores/sigmaRef";

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { graph, entities, selectNode } = useGraphStore();

  // Ctrl+F to toggle search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        setVisible(true);
        setTimeout(() => inputRef.current?.focus(), 50);
      }
      if (e.key === "Escape" && visible) {
        handleClose();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [visible]);

  // Apply search highlight via Sigma node reducer
  useEffect(() => {
    const sigma = getSigmaRef();
    if (!sigma || !query.trim()) {
      // Clear any search highlighting
      sigma?.setSetting("nodeReducer", (_, data) => data);
      sigma?.refresh();
      return;
    }

    const lowerQuery = query.toLowerCase();
    const matchingIds = new Set<string>();

    entities.forEach((entity, id) => {
      const matches =
        entity.value.toLowerCase().includes(lowerQuery) ||
        entity.type.toLowerCase().includes(lowerQuery) ||
        entity.notes.toLowerCase().includes(lowerQuery) ||
        entity.tags.some((t) => t.toLowerCase().includes(lowerQuery)) ||
        Object.values(entity.properties).some((v) =>
          String(v).toLowerCase().includes(lowerQuery)
        );
      if (matches) matchingIds.add(id);
    });

    sigma.setSetting("nodeReducer", (node, data) => {
      if (matchingIds.size === 0) return data;
      if (matchingIds.has(node)) {
        return { ...data, highlighted: true, zIndex: 1 };
      }
      return { ...data, color: `${data.color}22`, label: "" };
    });

    sigma.refresh();
  }, [query, entities, graph]);

  const handleClose = () => {
    setVisible(false);
    setQuery("");
    // Clear highlighting
    const sigma = getSigmaRef();
    if (sigma) {
      sigma.setSetting("nodeReducer", (_, data) => data);
      sigma.refresh();
    }
  };

  const handleSelectFirst = () => {
    if (!query.trim()) return;
    const lowerQuery = query.toLowerCase();
    for (const [id, entity] of entities) {
      if (entity.value.toLowerCase().includes(lowerQuery)) {
        selectNode(id);
        // Center camera on the node
        const sigma = getSigmaRef();
        if (sigma && graph.hasNode(id)) {
          const attrs = graph.getNodeAttributes(id);
          sigma.getCamera().animate(
            { x: attrs.x, y: attrs.y, ratio: 0.5 },
            { duration: 300 }
          );
        }
        break;
      }
    }
  };

  if (!visible) return null;

  return (
    <div className="absolute top-2 left-1/2 -translate-x-1/2 z-40 flex items-center gap-1 bg-surface border border-border rounded shadow-lg px-2 py-1">
      <Search size={14} className="text-text-muted shrink-0" />
      <input
        ref={inputRef}
        type="text"
        placeholder="Search entities... (type:Domain, tag:important)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSelectFirst();
          if (e.key === "Escape") handleClose();
        }}
        className="w-64 px-1 py-0.5 text-xs bg-transparent text-text focus:outline-none"
      />
      {query && (
        <button
          onClick={handleClose}
          className="p-0.5 text-text-muted hover:text-text"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}
