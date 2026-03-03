import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Search, X, ChevronUp, ChevronDown } from "lucide-react";
import { useGraphStore } from "../stores/graphStore";
import { getSigmaRef } from "../stores/sigmaRef";

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [visible, setVisible] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const { graph, entities, selectNode, setNodeOverlay } = useGraphStore();

  const handleClose = useCallback(() => {
    setVisible(false);
    setQuery("");
    setCurrentIndex(0);
    setNodeOverlay(null);
  }, [setNodeOverlay]);

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
  }, [visible, handleClose]);

  // Compute matches
  const matchingIds = useMemo(() => {
    if (!query.trim()) return [];
    const lowerQuery = query.toLowerCase();
    const ids: string[] = [];
    entities.forEach((entity, id) => {
      const matches =
        entity.value.toLowerCase().includes(lowerQuery) ||
        entity.type.toLowerCase().includes(lowerQuery) ||
        entity.notes.toLowerCase().includes(lowerQuery) ||
        entity.tags.some((t) => t.toLowerCase().includes(lowerQuery)) ||
        Object.values(entity.properties).some((v) =>
          String(v).toLowerCase().includes(lowerQuery)
        );
      if (matches) ids.push(id);
    });
    return ids;
  }, [query, entities]);

  // Push search overlay to the centralized store (GraphCanvas owns the nodeReducer)
  useEffect(() => {
    if (!visible || !query.trim() || matchingIds.length === 0) {
      // Clear search overlay when not searching
      if (visible && query.trim() && matchingIds.length === 0) {
        // Active search with no results — still show the overlay to dim everything
        setNodeOverlay({ type: "search", matchIds: new Set(), focusId: null });
      }
      return;
    }

    setNodeOverlay({
      type: "search",
      matchIds: new Set(matchingIds),
      focusId: matchingIds[currentIndex] ?? null,
    });
  }, [visible, matchingIds, currentIndex, query, setNodeOverlay]);

  const navigateTo = (index: number) => {
    const id = matchingIds[index];
    if (!id) return;
    setCurrentIndex(index);
    selectNode(id);
    const sigma = getSigmaRef();
    if (sigma && graph.hasNode(id)) {
      const attrs = graph.getNodeAttributes(id);
      sigma.getCamera().animate(
        { x: attrs.x, y: attrs.y, ratio: 0.5 },
        { duration: 300 }
      );
    }
  };

  const handleNext = () => {
    if (matchingIds.length === 0) return;
    navigateTo((currentIndex + 1) % matchingIds.length);
  };

  const handlePrev = () => {
    if (matchingIds.length === 0) return;
    navigateTo((currentIndex - 1 + matchingIds.length) % matchingIds.length);
  };

  if (!visible) return null;

  return (
    <div className="absolute top-2 left-1/2 -translate-x-1/2 z-40 flex items-center gap-1 bg-surface border border-border rounded shadow-lg px-2 py-1 animate-fade-in">
      <Search size={14} className="text-text-muted shrink-0" />
      <input
        ref={inputRef}
        type="text"
        placeholder="Search entities..."
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setCurrentIndex(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) handleNext();
          if (e.key === "Enter" && e.shiftKey) handlePrev();
          if (e.key === "Escape") handleClose();
        }}
        className="w-64 px-1 py-0.5 text-xs bg-transparent text-text focus:outline-none"
      />
      {query && (
        <span className="text-[10px] text-text-muted whitespace-nowrap tabular-nums">
          {matchingIds.length === 0
            ? "No matches"
            : `${currentIndex + 1} / ${matchingIds.length}`}
        </span>
      )}
      {matchingIds.length > 1 && (
        <>
          <button
            onClick={handlePrev}
            className="p-0.5 text-text-muted hover:text-text"
            title="Previous (Shift+Enter)"
          >
            <ChevronUp size={12} />
          </button>
          <button
            onClick={handleNext}
            className="p-0.5 text-text-muted hover:text-text"
            title="Next (Enter)"
          >
            <ChevronDown size={12} />
          </button>
        </>
      )}
      <button
        onClick={handleClose}
        className="p-0.5 text-text-muted hover:text-text"
        title="Close (Esc)"
      >
        <X size={12} />
      </button>
    </div>
  );
}
