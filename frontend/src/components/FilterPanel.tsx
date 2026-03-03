import { useMemo, useState } from "react";
import { Funnel, RotateCcw } from "lucide-react";
import { useGraphStore } from "../stores/graphStore";
import { useProjectStore } from "../stores/projectStore";

interface FilterPanelProps {
  mode?: "overlay" | "inline";
}

export function FilterPanel({ mode = "overlay" }: FilterPanelProps) {
  const [open, setOpen] = useState(false);
  const { currentProject } = useProjectStore();
  const { entities, filterState, setFilterState, resetFilters } = useGraphStore();

  const allTypes = useMemo(
    () => Array.from(new Set(Array.from(entities.values()).map((entity) => entity.type))).sort(),
    [entities]
  );
  const allSources = useMemo(
    () => Array.from(new Set(Array.from(entities.values()).map((entity) => entity.source))).sort(),
    [entities]
  );
  const allTags = useMemo(
    () =>
      Array.from(
        new Set(Array.from(entities.values()).flatMap((entity) => entity.tags))
      ).sort(),
    [entities]
  );

  const toggleIn = (
    key: "types" | "tags" | "sources",
    value: string,
  ) => {
    if (!currentProject) return;
    const values = filterState[key];
    const next = values.includes(value)
      ? values.filter((item) => item !== value)
      : [...values, value];
    setFilterState(currentProject.id, { [key]: next });
  };

  const containerClass =
    mode === "overlay" ? "absolute top-2 left-2 z-40" : "relative inline-block z-20";

  return (
    <div className={containerClass}>
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1 px-2 py-1 text-xs bg-surface border border-border rounded shadow text-text hover:bg-surface-hover"
      >
        <Funnel size={12} />
        Filters
      </button>

      {open && (
        <div
          className={`mt-1 w-[300px] max-h-[70vh] overflow-y-auto bg-surface border border-border rounded shadow-lg p-3 space-y-3 ${
            mode === "inline" ? "absolute left-0 top-full" : ""
          }`}
        >
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-text">Filter Graph</h3>
            {currentProject && (
              <button
                onClick={() => resetFilters(currentProject.id)}
                className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text"
              >
                <RotateCcw size={10} />
                Reset
              </button>
            )}
          </div>

          <label className="flex items-center gap-2 text-xs text-text">
            <input
              type="checkbox"
              checked={filterState.hideFiltered}
              disabled={!currentProject}
              onChange={(e) =>
                currentProject &&
                setFilterState(currentProject.id, { hideFiltered: e.target.checked })
              }
            />
            Hide filtered nodes
          </label>

          <div className="space-y-1">
            <p className="text-[10px] uppercase text-text-muted">Types</p>
            <div className="grid grid-cols-2 gap-1">
              {allTypes.map((type) => (
                <label key={type} className="flex items-center gap-1 text-xs text-text">
                  <input
                    type="checkbox"
                    checked={filterState.types.includes(type)}
                    disabled={!currentProject}
                    onChange={() => toggleIn("types", type)}
                  />
                  <span className="truncate">{type}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <p className="text-[10px] uppercase text-text-muted">Tags</p>
            <div className="grid grid-cols-2 gap-1">
              {allTags.length === 0 && (
                <p className="text-[10px] text-text-muted">No tags in this project</p>
              )}
              {allTags.map((tag) => (
                <label key={tag} className="flex items-center gap-1 text-xs text-text">
                  <input
                    type="checkbox"
                    checked={filterState.tags.includes(tag)}
                    disabled={!currentProject}
                    onChange={() => toggleIn("tags", tag)}
                  />
                  <span className="truncate">{tag}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <p className="text-[10px] uppercase text-text-muted">Sources</p>
            <div className="grid grid-cols-2 gap-1">
              {allSources.map((source) => (
                <label key={source} className="flex items-center gap-1 text-xs text-text">
                  <input
                    type="checkbox"
                    checked={filterState.sources.includes(source)}
                    disabled={!currentProject}
                    onChange={() => toggleIn("sources", source)}
                  />
                  <span className="truncate">{source}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-1">
            <p className="text-[10px] uppercase text-text-muted">Created date range</p>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="date"
                value={filterState.dateFrom}
                disabled={!currentProject}
                onChange={(e) =>
                  currentProject && setFilterState(currentProject.id, { dateFrom: e.target.value })
                }
                className="px-2 py-1 text-xs bg-bg border border-border rounded text-text"
              />
              <input
                type="date"
                value={filterState.dateTo}
                disabled={!currentProject}
                onChange={(e) =>
                  currentProject && setFilterState(currentProject.id, { dateTo: e.target.value })
                }
                className="px-2 py-1 text-xs bg-bg border border-border rounded text-text"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
