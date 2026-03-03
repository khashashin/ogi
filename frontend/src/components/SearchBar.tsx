import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Search, X, ChevronUp, ChevronDown } from "lucide-react";
import { useGraphStore } from "../stores/graphStore";
import { getSigmaRef } from "../stores/sigmaRef";
import { matchesEntitySearch } from "../lib/entitySearch";

export function SearchBar() {
  const [visible, setVisible] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const { graph, entities, searchQuery, setSearchQuery, selectNode, setNodeOverlay } = useGraphStore();

  const handleClose = useCallback(() => {
    setVisible(false);
    setSearchQuery("");
    setCurrentIndex(0);
    setNodeOverlay(null);
  }, [setSearchQuery, setNodeOverlay]);

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
    if (!searchQuery.trim()) return [];
    const ids: string[] = [];
    entities.forEach((entity, id) => {
      if (matchesEntitySearch(entity, searchQuery)) ids.push(id);
    });
    return ids;
  }, [searchQuery, entities]);

  // Push search overlay to the centralized store (GraphCanvas owns the nodeReducer)
  useEffect(() => {
    if (!visible || !searchQuery.trim() || matchingIds.length === 0) {
      // Clear search overlay when not searching
      if (visible && searchQuery.trim() && matchingIds.length === 0) {
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
  }, [visible, matchingIds, currentIndex, searchQuery, setNodeOverlay]);

  const navigateTo = (index: number) => {
    const id = matchingIds[index];
    if (!id) return;
    setCurrentIndex(index);
    selectNode(id);
    const sigma = getSigmaRef();
    if (sigma) {
      const displayData = sigma.getNodeDisplayData(id);
      const target = displayData
        ? { x: displayData.x, y: displayData.y }
        : graph.hasNode(id)
          ? (() => {
              const attrs = graph.getNodeAttributes(id);
              return { x: Number(attrs.x) || 0, y: Number(attrs.y) || 0 };
            })()
          : null;

      if (target) {
        const camera = sigma.getCamera();
        const current = camera.getState();
        camera.animate(
          {
            x: target.x,
            y: target.y,
            ratio: Math.min(current.ratio, 0.8),
          },
          { duration: 300 }
        );
      }
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
        placeholder="Search... type:Domain tag:important source:whois"
        value={searchQuery}
        onChange={(e) => {
          setSearchQuery(e.target.value);
          setCurrentIndex(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) handleNext();
          if (e.key === "Enter" && e.shiftKey) handlePrev();
          if (e.key === "Escape") handleClose();
        }}
        className="w-64 px-1 py-0.5 text-xs bg-transparent text-text focus:outline-none"
      />
      {searchQuery && (
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
