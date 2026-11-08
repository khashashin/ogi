import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, MapPin, RefreshCcw, X } from "lucide-react";
import maplibregl, { type Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { api } from "../api/client";
import { basemapLayerId, defaultBasemap, getBasemapOptions, type Basemap } from "../lib/basemaps";
import { getEnv } from "../lib/env";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import { useThemeStore } from "../stores/themeStore";
import type { MapCluster, MapPoint, MapRoute } from "../types/map";
import { useIsViewer } from "../hooks/useIsViewer";

const POINT_SOURCE_ID = "ogi-points";
const CLUSTER_SOURCE_ID = "ogi-clusters";
const ROUTE_SOURCE_ID = "ogi-routes";
const ADD_LOCATION_CURSOR =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='60' height='60' viewBox='0 0 60 60'%3E%3Cpath fill='%23ff0000' d='M29.603361,0 V29.603361 H0 v0.793233 h29.603361 v29.603362 h0.793233 V30.396594 H59.999956 V29.603361 H30.396594 V0 Z'/%3E%3C/svg%3E\") 30 30, crosshair";

const BASEMAP_OPTIONS = getBasemapOptions(getEnv("VITE_CARTO_API_KEY"));

function showBasemap(map: MapLibreMap, basemap: Basemap): void {
  BASEMAP_OPTIONS.forEach((option) => {
    const layerId = basemapLayerId(option.id);
    if (map.getLayer(layerId)) {
      map.setLayoutProperty(layerId, "visibility", option.id === basemap ? "visible" : "none");
    }
  });
}

interface PendingLocationDraft {
  lat: number;
  lon: number;
}

interface CursorCoordinates {
  lat: number;
  lon: number;
}

export function MapView() {
  const { currentProject } = useProjectStore();
  const { selectedNodeId, selectedEdgeId, selectNode, selectEdge, addEntity } = useGraphStore();
  const isViewer = useIsViewer();
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [clusters, setClusters] = useState<MapCluster[]>([]);
  const [routes, setRoutes] = useState<MapRoute[]>([]);
  const [zoom, setZoom] = useState(2);
  const [cluster, setCluster] = useState(true);
  // The basemap follows the theme until the user picks one.
  const resolvedTheme = useThemeStore((state) => state.resolvedTheme);
  const [chosenBasemap, setChosenBasemap] = useState<Basemap | null>(null);
  const basemap = chosenBasemap ?? defaultBasemap(BASEMAP_OPTIONS, resolvedTheme);
  const [showPoints, setShowPoints] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addLocationMode, setAddLocationMode] = useState(false);
  const [pendingLocation, setPendingLocation] = useState<PendingLocationDraft | null>(null);
  const [draftLabel, setDraftLabel] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [savingLocation, setSavingLocation] = useState(false);
  const [cursorCoordinates, setCursorCoordinates] = useState<CursorCoordinates | null>(null);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const basemapRef = useRef(basemap);
  const fitKeyRef = useRef<string>("");
  const addLocationModeRef = useRef(addLocationMode);
  const isViewerRef = useRef(isViewer);

  const projectId = currentProject?.id ?? null;

  const center = useMemo(() => {
    if (points.length === 0) return { lon: 8.5417, lat: 47.3769 };
    const lon = points.reduce((sum, p) => sum + p.lon, 0) / points.length;
    const lat = points.reduce((sum, p) => sum + p.lat, 0) / points.length;
    return { lon, lat };
  }, [points]);

  const syncCursor = () => {
    const map = mapRef.current;
    if (!map) return;
    map.getCanvas().style.cursor = !isViewerRef.current && addLocationModeRef.current ? ADD_LOCATION_CURSOR : "";
  };

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
    setAddLocationMode(false);
    setPendingLocation(null);
    setDraftLabel("");
    setDraftNotes("");
  }, [projectId]);

  useEffect(() => {
    addLocationModeRef.current = addLocationMode;
    syncCursor();
  }, [addLocationMode]);

  useEffect(() => {
    isViewerRef.current = isViewer;
    syncCursor();
  }, [isViewer]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: Object.fromEntries(BASEMAP_OPTIONS.map((option) => [basemapLayerId(option.id), option.source])),
        layers: BASEMAP_OPTIONS.map((option) => ({
          id: basemapLayerId(option.id),
          type: "raster" as const,
          source: basemapLayerId(option.id),
          layout: { visibility: option.id === basemapRef.current ? ("visible" as const) : ("none" as const) },
        })),
      },
      center: [8.5417, 47.3769],
      zoom: 2,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

    map.on("load", () => {
      // The theme may have changed while the style was loading.
      showBasemap(map, basemapRef.current);
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
        const coordinates = feature?.geometry && "coordinates" in feature.geometry ? feature.geometry.coordinates : null;
        if (Array.isArray(coordinates) && coordinates.length >= 2) {
          const nextZoom = Math.max(1, Math.min(20, Math.round(map.getZoom()) + 1));
          map.easeTo({
            center: [Number(coordinates[0]), Number(coordinates[1])],
            zoom: nextZoom,
            duration: 300,
          });
          setZoom(nextZoom);
          return;
        }

        const firstId = feature?.properties?.first_entity_id as string | undefined;
        if (firstId) selectNode(firstId);
      });

      map.on("click", (event) => {
        if (isViewerRef.current || !addLocationModeRef.current) return;
        const hitFeatures = map.queryRenderedFeatures(event.point, {
          layers: ["ogi-points-layer", "ogi-routes-layer", "ogi-clusters-layer"],
        });
        if (hitFeatures.length > 0) return;
        setPendingLocation({
          lat: Number(event.lngLat.lat.toFixed(6)),
          lon: Number(event.lngLat.lng.toFixed(6)),
        });
        setDraftLabel("");
        setDraftNotes("");
        setAddLocationMode(false);
      });

      map.on("mousemove", (event) => {
        setCursorCoordinates({
          lat: Number(event.lngLat.lat.toFixed(6)),
          lon: Number(event.lngLat.lng.toFixed(6)),
        });
      });

      map.on("mouseout", () => {
        setCursorCoordinates(null);
      });

      map.on("mouseenter", "ogi-points-layer", () => {
        if (!addLocationModeRef.current) {
          map.getCanvas().style.cursor = "pointer";
        }
      });
      map.on("mouseleave", "ogi-points-layer", () => {
        syncCursor();
      });
      map.on("mouseenter", "ogi-routes-layer", () => {
        if (!addLocationModeRef.current) {
          map.getCanvas().style.cursor = "pointer";
        }
      });
      map.on("mouseleave", "ogi-routes-layer", () => {
        syncCursor();
      });
      map.on("mouseenter", "ogi-clusters-layer", () => {
        if (!addLocationModeRef.current) {
          map.getCanvas().style.cursor = "pointer";
        }
      });
      map.on("mouseleave", "ogi-clusters-layer", () => {
        syncCursor();
      });
    });

    map.on("zoomend", () => {
      setZoom(Math.max(1, Math.min(20, Math.round(map.getZoom()))));
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
    basemapRef.current = basemap;
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const setVis = (layerId: string, visible: boolean) => {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
      }
    };

    showBasemap(map, basemap);
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

  const closeLocationDraft = () => {
    setPendingLocation(null);
    setDraftLabel("");
    setDraftNotes("");
  };

  const handleCreateLocation = async () => {
    if (!projectId || !pendingLocation) return;
    const fallbackLabel = `Pinned location (${pendingLocation.lat.toFixed(4)}, ${pendingLocation.lon.toFixed(4)})`;
    setSavingLocation(true);
    try {
      const created = await api.entities.create(projectId, {
        type: "Location",
        value: draftLabel.trim() || fallbackLabel,
        notes: draftNotes.trim(),
        properties: {
          lat: pendingLocation.lat,
          lon: pendingLocation.lon,
          location_label: draftLabel.trim() || fallbackLabel,
          geo_confidence: 1.0,
        },
      });
      addEntity(projectId, created);
      selectNode(created.id);
      closeLocationDraft();
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSavingLocation(false);
    }
  };

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
              onChange={(e) => setChosenBasemap(e.target.value as Basemap)}
              className="rounded border border-border bg-surface px-2 py-1 text-xs text-text"
            >
              {BASEMAP_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
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
              onChange={(e) => {
                const nextZoom = Number(e.target.value);
                setZoom(nextZoom);
                mapRef.current?.easeTo({ zoom: nextZoom, duration: 250 });
              }}
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
        <div className="relative h-full w-full">
          {!isViewer && (
            <div className="pointer-events-none absolute left-3 top-3 z-10">
              <button
                onClick={() => {
                  setAddLocationMode((current) => !current);
                  closeLocationDraft();
                }}
                className={`pointer-events-auto flex h-9 w-9 items-center justify-center rounded border shadow-sm transition-colors ${
                  addLocationMode
                    ? "border-green-400 bg-green-500/20 text-green-300"
                    : "border-border bg-surface text-green-400 hover:bg-surface-hover"
                }`}
                title={addLocationMode ? "Cancel add location mode" : "Add location from map"}
              >
                <MapPin size={16} />
              </button>
            </div>
          )}

          {pendingLocation && (
            <div className="absolute bottom-3 left-3 z-10 w-80 rounded-lg border border-border bg-surface p-3 shadow-lg">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MapPin size={14} className="text-green-400" />
                  <h3 className="text-sm font-semibold text-text">Create Location</h3>
                </div>
                <button onClick={closeLocationDraft} className="text-text-muted hover:text-text">
                  <X size={14} />
                </button>
              </div>
              <p className="mb-3 text-xs text-text-muted">
                Lat {pendingLocation.lat.toFixed(6)}, Lon {pendingLocation.lon.toFixed(6)}
              </p>
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs text-text-muted">Label</label>
                  <input
                    type="text"
                    value={draftLabel}
                    onChange={(event) => setDraftLabel(event.target.value)}
                    placeholder="Pinned location"
                    className="w-full rounded border border-border bg-bg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-text-muted">Notes</label>
                  <textarea
                    value={draftNotes}
                    onChange={(event) => setDraftNotes(event.target.value)}
                    rows={3}
                    placeholder="Optional notes"
                    className="w-full rounded border border-border bg-bg px-3 py-2 text-sm text-text focus:outline-none focus:border-accent"
                  />
                </div>
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={closeLocationDraft}
                    className="rounded border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-surface-hover hover:text-text"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateLocation}
                    disabled={savingLocation}
                    className="rounded bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent-hover disabled:opacity-60"
                  >
                    {savingLocation ? "Creating..." : "Create"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {cursorCoordinates && (
            <div className="pointer-events-none absolute bottom-3 left-3 z-[9] rounded border border-border bg-surface/90 px-2 py-1 text-[11px] text-text-muted shadow-sm">
              Lat {cursorCoordinates.lat.toFixed(6)}, Lon {cursorCoordinates.lon.toFixed(6)}
            </div>
          )}

          <div ref={mapContainerRef} className="h-full w-full" />
        </div>
      </div>
    </div>
  );
}
