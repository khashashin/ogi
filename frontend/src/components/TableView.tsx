import { useMemo, useState } from "react";
import { ArrowUpDown } from "lucide-react";
import { useGraphStore } from "../stores/graphStore";
import { matchesEntitySearch } from "../lib/entitySearch";
import { FilterPanel } from "./FilterPanel";

type SortKey = "type" | "value" | "source" | "weight" | "created_at";

export function TableView() {
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortAsc, setSortAsc] = useState(false);
  const { entities, hiddenNodeIds, searchQuery, selectedNodeId, selectNode } = useGraphStore();

  const rows = useMemo(() => {
    const list = Array.from(entities.values()).filter((entity) => {
      if (hiddenNodeIds.has(entity.id)) return false;
      return matchesEntitySearch(entity, searchQuery);
    });

    list.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") return sortAsc ? av - bv : bv - av;
      const sa = String(av).toLowerCase();
      const sb = String(bv).toLowerCase();
      return sortAsc ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
    return list;
  }, [entities, hiddenNodeIds, searchQuery, sortAsc, sortKey]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((v) => !v);
      return;
    }
    setSortKey(key);
    setSortAsc(true);
  };

  const thClass =
    "px-2 py-1 text-left text-[10px] uppercase tracking-wider text-text-muted border-b border-border";

  return (
    <div className="h-full flex flex-col bg-bg">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FilterPanel mode="inline" />
          <p className="text-xs text-text-muted">
            {rows.length} visible entities
            {searchQuery.trim() ? ` (query: ${searchQuery})` : ""}
          </p>
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-surface z-10">
            <tr>
              <th className={thClass}>
                <button onClick={() => toggleSort("type")} className="inline-flex items-center gap-1">
                  Type <ArrowUpDown size={10} />
                </button>
              </th>
              <th className={thClass}>
                <button onClick={() => toggleSort("value")} className="inline-flex items-center gap-1">
                  Value <ArrowUpDown size={10} />
                </button>
              </th>
              <th className={thClass}>
                <button onClick={() => toggleSort("source")} className="inline-flex items-center gap-1">
                  Source <ArrowUpDown size={10} />
                </button>
              </th>
              <th className={thClass}>
                <button onClick={() => toggleSort("weight")} className="inline-flex items-center gap-1">
                  Weight <ArrowUpDown size={10} />
                </button>
              </th>
              <th className={thClass}>
                <button onClick={() => toggleSort("created_at")} className="inline-flex items-center gap-1">
                  Created <ArrowUpDown size={10} />
                </button>
              </th>
              <th className={thClass}>Tags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((entity) => {
              const selected = selectedNodeId === entity.id;
              return (
                <tr
                  key={entity.id}
                  onClick={() => selectNode(entity.id)}
                  className={`cursor-pointer border-b border-border/60 ${
                    selected ? "bg-accent/10" : "hover:bg-surface-hover/40"
                  }`}
                >
                  <td className="px-2 py-1.5 text-xs text-text">{entity.type}</td>
                  <td className="px-2 py-1.5 text-xs text-text">{entity.value}</td>
                  <td className="px-2 py-1.5 text-xs text-text-muted">{entity.source}</td>
                  <td className="px-2 py-1.5 text-xs text-text-muted">{entity.weight}</td>
                  <td className="px-2 py-1.5 text-xs text-text-muted">
                    {new Date(entity.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-2 py-1.5 text-xs text-text-muted">{entity.tags.join(", ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
