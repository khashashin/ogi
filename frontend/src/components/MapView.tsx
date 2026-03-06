import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, RefreshCcw } from "lucide-react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { api } from "../api/client";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import type { MapCluster, MapPoint, MapRoute } from "../types/map";

const POINT_SOURCE_ID = "ogi-points";
const CLUSTER_SOURCE_ID = "ogi-clusters";
const ROUTE_SOURCE_ID = "ogi-routes";
const BASE_LAYER_OSM = "basemap-osm";
const BASE_LAYER_HOT = "basemap-hot";
const BASE_LAYER_CARTO = "basemap-carto";
const BASE_LAYER_SAT = "basemap-sat";

type Basemap = "osm" | "hot" | "carto" | "sat";

export function MapView() {
  const { currentProject } = useProjectStore();
  const { selectedNodeId, selectedEdgeId, selectNode, selectEdge } = useGraphStore();
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [clusters, setClusters] = useState<MapCluster[]>([]);
  const [routes, setRoutes] = useState<MapRoute[]>([]);
  const [zoom, setZoom] = useState(4);
  const [cluster, setCluster] = useState(true);
  const [basemap, setBasemap] = useState<Basemap>("osm");
  const [showPoints, setShowPoints] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const fitKeyRef = useRef<string>("");

  const projectId = currentProject?.id ?? null;

  const center = useMemo(() => {
    if (points.length === 0) return { lon: 8.5417, lat: 47.3769 };
    const lon = points.reduce((sum, p) => sum + p.lon, 0) / points.length;
    const lat = points.reduce((sum, p) => sum + p.lat, 0) / points.length;
    return { lon, lat };
  }, [points]);

  const refresh = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [pointsResp, routesResp] = await Promise.all([
        api.map.points(projectId, zoom, true),
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
  }, [projectId, zoom]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          "base-osm": {
            type: "raster",
            tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap Contributors",
          },
          "base-hot": {
            type: "raster",
            tiles: ["https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap Contributors, Humanitarian OpenStreetMap Team",
          },
          "base-carto": {
            type: "raster",
            tiles: ["https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap Contributors, &copy; CARTO",
          },
          "base-sat": {
            type: "raster",
            tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
            tileSize: 256,
            attribution: "Tiles &copy; Esri",
          },
        },
        layers: [
          { id: BASE_LAYER_OSM, type: "raster", source: "base-osm" },
          { id: BASE_LAYER_HOT, type: "raster", source: "base-hot", layout: { visibility: "none" } },
          { id: BASE_LAYER_CARTO, type: "raster", source: "base-carto", layout: { visibility: "none" } },
          { id: BASE_LAYER_SAT, type: "raster", source: "base-sat", layout: { visibility: "none" } },
        ],
      },
      center: [8.5417, 47.3769],
      zoom: 2,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

    map.on("load", () => {
      map.addSource(ROUTE_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "ogi-routes-layer",
        type: "line",
        source: ROUTE_SOURCE_ID,
        paint: {
          "line-color": ["case", ["boolean", ["get", "selected"], false], "#60a5fa", "#64748b"],
          "line-width": ["case", ["boolean", ["get", "selected"], false], 4, 2],
          "line-opacity": 0.85,
        },
      });

      map.addSource(POINT_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "ogi-points-layer",
        type: "circle",
        source: POINT_SOURCE_ID,
        paint: {
          "circle-color": ["case", ["boolean", ["get", "selected"], false], "#60a5fa", "#22d3ee"],
          "circle-radius": ["case", ["boolean", ["get", "selected"], false], 8, 6],
          "circle-stroke-color": "#0f172a",
          "circle-stroke-width": 1.5,
        },
      });

      map.addSource(CLUSTER_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: "ogi-clusters-layer",
        type: "circle",
        source: CLUSTER_SOURCE_ID,
        paint: {
          "circle-color": "#fbbf24",
          "circle-radius": ["interpolate", ["linear"], ["get", "count"], 2, 10, 20, 20],
          "circle-opacity": 0.9,
          "circle-stroke-color": "#111827",
          "circle-stroke-width": 1.5,
        },
      });
      map.addLayer({
        id: "ogi-clusters-count",
        type: "symbol",
        source: CLUSTER_SOURCE_ID,
        layout: {
          "text-field": ["get", "count"],
          "text-size": 11,
        },
        paint: { "text-color": "#111827" },
      });

      map.on("click", "ogi-points-layer", (event) => {
        const feature = event.features?.[0];
        const id = feature?.properties?.entity_id as string | undefined;
        if (id) selectNode(id);
      });

      map.on("click", "ogi-routes-layer", (event) => {
        const feature = event.features?.[0];
        const id = feature?.properties?.edge_id as string | undefined;
        if (id) selectEdge(id);
      });

      map.on("click", "ogi-clusters-layer", (event) => {
        const feature = event.features?.[0];
        const firstId = feature?.properties?.first_entity_id as string | undefined;
        if (firstId) selectNode(firstId);
      });

      map.on("mouseenter", "ogi-points-layer", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "ogi-points-layer", () => {
        map.getCanvas().style.cursor = "";
      });
      map.on("mouseenter", "ogi-routes-layer", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "ogi-routes-layer", () => {
        map.getCanvas().style.cursor = "";
      });
      map.on("mouseenter", "ogi-clusters-layer", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "ogi-clusters-layer", () => {
        map.getCanvas().style.cursor = "";
      });
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [selectEdge, selectNode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const pointFeatures = points.map((point) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [point.lon, point.lat] },
      properties: {
        entity_id: point.entity_id,
        label: point.label,
        selected: selectedNodeId === point.entity_id,
      },
    }));

    const clusterFeatures = clusters.map((item) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [item.lon, item.lat] },
      properties: {
        cluster_id: item.cluster_id,
        count: item.count,
        first_entity_id: item.entity_ids[0] ?? null,
      },
    }));

    const routeFeatures = routes.map((route) => ({
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [route.source_lon, route.source_lat],
          [route.target_lon, route.target_lat],
        ],
      },
      properties: {
        edge_id: route.edge_id,
        selected: selectedEdgeId === route.edge_id,
      },
    }));

    const pointSource = map.getSource(POINT_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    const clusterSource = map.getSource(CLUSTER_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    const routeSource = map.getSource(ROUTE_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;

    pointSource?.setData({ type: "FeatureCollection", features: pointFeatures } as GeoJSON.FeatureCollection);
    clusterSource?.setData({ type: "FeatureCollection", features: cluster ? clusterFeatures : [] } as GeoJSON.FeatureCollection);
    routeSource?.setData({ type: "FeatureCollection", features: routeFeatures } as GeoJSON.FeatureCollection);
  }, [points, clusters, routes, selectedNodeId, selectedEdgeId, cluster]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const setVis = (layerId: string, visible: boolean) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      }
    };

    setVis(BASE_LAYER_OSM, basemap === "osm");
    setVis(BASE_LAYER_HOT, basemap === "hot");
    setVis(BASE_LAYER_CARTO, basemap === "carto");
    setVis(BASE_LAYER_SAT, basemap === "sat");
    setVis("ogi-points-layer", showPoints);
    setVis("ogi-routes-layer", showRoutes);
    setVis("ogi-clusters-layer", cluster);
    setVis("ogi-clusters-count", cluster);
  }, [basemap, showPoints, showRoutes, cluster]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const key = JSON.stringify(points.map((p) => [p.entity_id, p.lat, p.lon]));
    if (key === fitKeyRef.current) return;
    fitKeyRef.current = key;

    if (points.length > 0) {
      const bounds = new maplibregl.LngLatBounds();
      for (const p of points) bounds.extend([p.lon, p.lat]);
      map.fitBounds(bounds, { padding: 50, duration: 400, maxZoom: 8 });
    } else {
      map.flyTo({ center: [center.lon, center.lat], zoom: 2, duration: 300 });
    }
  }, [points, center]);

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
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1 text-xs text-text-muted">
            Basemap
            <select
              value={basemap}
              onChange={(e) => setBasemap(e.target.value as Basemap)}
              className="rounded border border-border bg-surface px-2 py-1 text-xs text-text"
            >
              <option value="osm">OSM Standard</option>
              <option value="hot">OSM Humanitarian</option>
              <option value="carto">CARTO Light</option>
              <option value="sat">Satellite (Esri)</option>
            </select>
          </label>
          <div className="flex items-center gap-2 rounded border border-border px-2 py-1">
            <label className="flex items-center gap-1 text-xs text-text-muted">
              <input type="checkbox" checked={cluster} onChange={(e) => setCluster(e.target.checked)} />
              Clusters
            </label>
            <span className="text-[10px] text-text-muted">Detail</span>
            <input
              type="range"
              min={1}
              max={20}
              value={zoom}
              onChange={(e) => setZoom(Number(e.target.value))}
              disabled={!cluster}
              title="Cluster detail level"
            />
            <span className="w-5 text-right text-xs text-text">{zoom}</span>
          </div>
          <label className="flex items-center gap-1 text-xs text-text-muted">
            <input type="checkbox" checked={showPoints} onChange={(e) => setShowPoints(e.target.checked)} />
            Points
          </label>
          <label className="flex items-center gap-1 text-xs text-text-muted">
            <input type="checkbox" checked={showRoutes} onChange={(e) => setShowRoutes(e.target.checked)} />
            Routes
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

      <div className="min-h-0 flex-1 overflow-hidden">
        {loading && (
          <div className="absolute z-10 m-3 flex items-center rounded border border-border bg-surface px-2 py-1 text-xs text-text-muted">
            <Loader2 size={13} className="mr-2 animate-spin" />
            Loading map data...
          </div>
        )}
        <div ref={mapContainerRef} className="h-full w-full" />
      </div>
    </div>
  );
}
