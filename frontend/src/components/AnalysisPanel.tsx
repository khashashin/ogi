import { useState } from "react";
import { BarChart3, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import { api } from "../api/client";

interface AlgorithmOption {
  value: string;
  label: string;
  description: string;
  type: "scores" | "communities";
}

const ALGORITHMS: AlgorithmOption[] = [
  { value: "degree_centrality", label: "Degree Centrality", description: "Nodes with most connections", type: "scores" },
  { value: "betweenness_centrality", label: "Betweenness Centrality", description: "Nodes bridging communities", type: "scores" },
  { value: "closeness_centrality", label: "Closeness Centrality", description: "Nodes closest to all others", type: "scores" },
  { value: "pagerank", label: "PageRank", description: "Most important nodes", type: "scores" },
  { value: "connected_components", label: "Connected Components", description: "Find isolated clusters", type: "communities" },
];

const COMMUNITY_COLORS = [
  "#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#f472b6",
  "#a78bfa", "#fb923c", "#34d399", "#60a5fa", "#94a3b8",
];

export function AnalysisPanel() {
  const [selected, setSelected] = useState(ALGORITHMS[0].value);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<{
    type: "scores" | "communities";
    scores?: Record<string, number>;
    communities?: string[][];
  } | null>(null);

  const { currentProject } = useProjectStore();
  const { entities, setNodeOverlay } = useGraphStore();

  const handleRun = async () => {
    if (!currentProject) return;
    setRunning(true);
    try {
      const result = await api.graph.analyze(currentProject.id, selected);
      const algo = ALGORITHMS.find((a) => a.value === selected);
      setResults({ type: algo?.type ?? "scores", ...result });

      if (result.scores) {
        const maxScore = Math.max(...Object.values(result.scores), 0.001);
        setNodeOverlay({ type: "analysis-scores", scores: result.scores, maxScore });
        toast.success(`${algo?.label}: analysis complete`);
      } else if (result.communities) {
        const nodeToColor: Record<string, string> = {};
        result.communities.forEach((community, i) => {
          const color = COMMUNITY_COLORS[i % COMMUNITY_COLORS.length];
          for (const nodeId of community) {
            nodeToColor[nodeId] = color;
          }
        });
        setNodeOverlay({ type: "analysis-communities", colors: nodeToColor });
        toast.success(`Found ${result.communities.length} connected components`);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Analysis failed: ${msg}`);
    } finally {
      setRunning(false);
    }
  };

  const handleReset = () => {
    setResults(null);
    setNodeOverlay(null);
  };

  // Sorted top entities for score results
  const topEntities = results?.scores
    ? Object.entries(results.scores)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 10)
        .map(([id, score]) => ({
          id,
          value: entities.get(id)?.value ?? id.slice(0, 8),
          type: entities.get(id)?.type ?? "unknown",
          score: score.toFixed(4),
        }))
    : [];

  return (
    <div className="flex h-full">
      {/* Algorithm selector */}
      <div className="w-56 border-r border-border overflow-y-auto">
        <div className="p-2 border-b border-border">
          <p className="text-xs font-semibold text-text-muted">Graph Analysis</p>
        </div>
        <div className="p-1">
          {ALGORITHMS.map((algo) => (
            <button
              key={algo.value}
              onClick={() => setSelected(algo.value)}
              className={`w-full text-left px-2 py-1.5 rounded text-xs ${
                selected === algo.value
                  ? "bg-surface-hover text-text"
                  : "text-text-muted hover:bg-surface-hover"
              }`}
            >
              <p className="font-medium">{algo.label}</p>
              <p className="text-[10px] text-text-muted">{algo.description}</p>
            </button>
          ))}
        </div>
        <div className="p-2 border-t border-border flex gap-1">
          <button
            onClick={handleRun}
            disabled={running}
            className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
          >
            {running ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <BarChart3 size={12} />
            )}
            Run
          </button>
          {results && (
            <button
              onClick={handleReset}
              className="px-2 py-1.5 text-xs text-text-muted border border-border rounded hover:bg-surface-hover"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-3">
        {!results ? (
          <div className="flex flex-col items-center justify-center h-full gap-1">
            <BarChart3 size={20} className="text-text-muted" />
            <p className="text-xs text-text-muted">Select an algorithm and click Run</p>
          </div>
        ) : results.type === "scores" && topEntities.length > 0 ? (
          <div>
            <h4 className="text-[10px] uppercase text-text-muted mb-2">
              Top Entities by Score
            </h4>
            <div className="space-y-1">
              {topEntities.map((item, i) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-text-muted w-4">{i + 1}.</span>
                    <span className="text-text">{item.value}</span>
                    <span className="text-[10px] text-text-muted">({item.type})</span>
                  </div>
                  <span className="text-accent font-mono text-[10px]">{item.score}</span>
                </div>
              ))}
            </div>
          </div>
        ) : results.type === "communities" && results.communities ? (
          <div>
            <h4 className="text-[10px] uppercase text-text-muted mb-2">
              Communities ({results.communities.length})
            </h4>
            <div className="space-y-2">
              {results.communities.map((community, i) => (
                <div key={i} className="p-2 border border-border rounded">
                  <div className="flex items-center gap-2 mb-1">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: COMMUNITY_COLORS[i % COMMUNITY_COLORS.length] }}
                    />
                    <span className="text-xs font-medium text-text">
                      Group {i + 1} ({community.length} entities)
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {community.slice(0, 8).map((id) => (
                      <span key={id} className="text-[10px] text-text-muted">
                        {entities.get(id)?.value ?? id.slice(0, 8)}
                      </span>
                    ))}
                    {community.length > 8 && (
                      <span className="text-[10px] text-text-muted">
                        +{community.length - 8} more
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
