import { useEffect, useMemo, useState } from "react";
import { Loader2, RefreshCcw } from "lucide-react";

import { api } from "../api/client";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import type { MapCluster, MapPoint, MapRoute } from "../types/map";

const PAD = 16;
const WIDTH = 1000;
const HEIGHT = 620;

type XY = { x: number; y: number };

function project(lat: number, lon: number, bounds: { minLat: number; maxLat: number; minLon: number; maxLon: number }): XY {
  const lonSpan = Math.max(0.0001, bounds.maxLon - bounds.minLon);
  const latSpan = Math.max(0.0001, bounds.maxLat - bounds.minLat);
  const x = PAD + ((lon - bounds.minLon) / lonSpan) * (WIDTH - PAD * 2);
  const y = PAD + (1 - (lat - bounds.minLat) / latSpan) * (HEIGHT - PAD * 2);
  return { x, y };
}

export function MapView() {
  const { currentProject } = useProjectStore();
  const { selectedNodeId, selectedEdgeId, selectNode, selectEdge } = useGraphStore();
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [clusters, setClusters] = useState<MapCluster[]>([]);
  const [routes, setRoutes] = useState<MapRoute[]>([]);
  const [zoom, setZoom] = useState(4);
  const [cluster, setCluster] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const projectId = currentProject?.id ?? null;

  const refresh = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [pointsResp, routesResp] = await Promise.all([
        api.map.points(projectId, zoom, cluster),
        api.map.routes(projectId),
      ]);
      setPoints(pointsResp.points ?? []);
      setClusters(pointsResp.clusters ?? []);
      setRoutes(routesResp.routes ?? []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, zoom, cluster]);

  const bounds = useMemo(() => {
    const coords = points.map((p) => ({ lat: p.lat, lon: p.lon }));
    if (coords.length === 0) {
      return { minLat: -85, maxLat: 85, minLon: -180, maxLon: 180 };
    }
    return {
      minLat: Math.min(...coords.map((c) => c.lat)),
      maxLat: Math.max(...coords.map((c) => c.lat)),
      minLon: Math.min(...coords.map((c) => c.lon)),
      maxLon: Math.max(...coords.map((c) => c.lon)),
    };
  }, [points]);

  if (!projectId) {
    return <div className="h-full p-3 text-xs text-text-muted">Select a project to view map.</div>;
  }

  return (
    <div className="h-full flex flex-col bg-bg">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-3 text-xs text-text-muted">
          <span>Points: <span className="text-text">{points.length}</span></span>
          <span>Routes: <span className="text-text">{routes.length}</span></span>
          <span>Clusters: <span className="text-text">{clusters.length}</span></span>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-xs text-text-muted">
            Zoom
            <input
              type="range"
              min={1}
              max={20}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
            />
            <span className="w-5 text-right text-text">{zoom}</span>
          </label>
          <label className="flex items-center gap-1 text-xs text-text-muted">
            <input type="checkbox" checked={cluster} onChange={(e) => setCluster(e.target.checked)} />
            Cluster
          </label>
          <button
            onClick={refresh}
            disabled={loading}
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:text-text hover:bg-surface-hover disabled:opacity-60"
          >
            <RefreshCcw size={12} className={loading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-3 mt-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-[11px] text-red-300">
          {error}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-hidden p-2">
        {loading ? (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            <Loader2 size={14} className="mr-2 animate-spin" />
            Loading map data...
          </div>
        ) : (
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-full w-full rounded border border-border bg-surface">
            <defs>
              <pattern id="map-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect x="0" y="0" width={WIDTH} height={HEIGHT} fill="url(#map-grid)" />

            {routes.map((route) => {
              const s = project(route.source_lat, route.source_lon, bounds);
              const t = project(route.target_lat, route.target_lon, bounds);
              const active = selectedEdgeId === route.edge_id;
              return (
                <line
                  key={route.edge_id}
                  x1={s.x}
                  y1={s.y}
                  x2={t.x}
                  y2={t.y}
                  stroke={active ? "#60a5fa" : "rgba(148,163,184,0.5)"}
                  strokeWidth={active ? 3 : 1.5}
                  onClick={() => selectEdge(route.edge_id)}
                  style={{ cursor: "pointer" }}
                />
              );
            })}

            {points.map((point) => {
              const p = project(point.lat, point.lon, bounds);
              const active = selectedNodeId === point.entity_id;
              return (
                <g key={point.entity_id} transform={`translate(${p.x},${p.y})`} onClick={() => selectNode(point.entity_id)} style={{ cursor: "pointer" }}>
                  <circle r={active ? 7 : 5} fill={active ? "#60a5fa" : "#22d3ee"} stroke="#0f172a" strokeWidth="1.5" />
                  {active && (
                    <text x={10} y={4} fill="#e2e8f0" fontSize="11">
                      {point.label}
                    </text>
                  )}
                </g>
              );
            })}

            {cluster && clusters.map((clusterItem) => {
              const p = project(clusterItem.lat, clusterItem.lon, bounds);
              return (
                <g
                  key={clusterItem.cluster_id}
                  transform={`translate(${p.x},${p.y})`}
                  onClick={() => selectNode(clusterItem.entity_ids[0] ?? null)}
                  style={{ cursor: "pointer" }}
                >
                  <circle r={10} fill="rgba(251,191,36,0.85)" stroke="#111827" strokeWidth="1.5" />
                  <text x={0} y={4} textAnchor="middle" fill="#111827" fontSize="10" fontWeight={700}>
                    {clusterItem.count}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}
