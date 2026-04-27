import { useEffect, useMemo, useState } from "react";
import { Loader2, MapPin, Clock3, RefreshCcw, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

import { api } from "../api/client";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import type { TransformRun } from "../types/transform";
import type { AuditLogEntry, LocationAggregate, ProjectEvent } from "../types/eventing";

function formatDate(value: string | undefined | null): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function eventBadgeClass(eventType: string): string {
  if (eventType.startsWith("transform_")) return "bg-sky-500/15 text-sky-300 border-sky-500/40";
  if (eventType === "entity_created") return "bg-emerald-500/15 text-emerald-300 border-emerald-500/40";
  if (eventType === "edge_created") return "bg-violet-500/15 text-violet-300 border-violet-500/40";
  if (eventType === "audit_log") return "bg-amber-500/15 text-amber-300 border-amber-500/40";
  return "bg-surface-hover text-text-muted border-border";
}

export function EventingPanel() {
  const { currentProject } = useProjectStore();
  const { selectNode, selectEdge, setCenterView } = useGraphStore();
  const [events, setEvents] = useState<ProjectEvent[]>([]);
  const [locations, setLocations] = useState<LocationAggregate[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [transformRunByEventId, setTransformRunByEventId] = useState<Record<string, TransformRun | null>>({});
  const [loading, setLoading] = useState(false);
  const [loadingDetailsEventId, setLoadingDetailsEventId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const projectId = currentProject?.id ?? null;

  const refresh = async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [eventsResp, locationsResp, auditResp] = await Promise.all([
        api.eventing.events(projectId),
        api.eventing.locations(projectId),
        api.eventing.auditLogs(projectId),
      ]);
      setEvents(eventsResp.items ?? []);
      setLocations(locationsResp ?? []);
      setAuditLogs(auditResp ?? []);
      setExpandedEventId(null);
      setTransformRunByEventId({});
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const timelineCount = events.length;
  const locationCount = locations.length;
  const locationEntityTotal = useMemo(
    () => locations.reduce((sum, row) => sum + (row.entity_count ?? 0), 0),
    [locations]
  );

  const openEventDetails = async (event: ProjectEvent) => {
    const nextId = expandedEventId === event.event_id ? null : event.event_id;
    setExpandedEventId(nextId);
    if (!nextId || !event.transform_run_id || !projectId || transformRunByEventId[event.event_id] !== undefined) {
      return;
    }
    try {
      setLoadingDetailsEventId(event.event_id);
      const run = await api.transforms.getRun(event.transform_run_id);
      setTransformRunByEventId((prev) => ({ ...prev, [event.event_id]: run }));
    } catch {
      setTransformRunByEventId((prev) => ({ ...prev, [event.event_id]: null }));
    } finally {
      setLoadingDetailsEventId(null);
    }
  };

  const jumpToEntity = (entityId: string | null | undefined) => {
    if (!entityId) return;
    setCenterView("graph");
    selectNode(entityId);
  };

  const jumpToEdge = (edgeId: string | null | undefined) => {
    if (!edgeId) return;
    setCenterView("graph");
    selectEdge(edgeId);
  };

  if (!projectId) {
    return <div className="h-full p-3 text-xs text-text-muted">Select a project to view events.</div>;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-4 text-xs">
          <span className="text-text-muted">
            Timeline <span className="text-text">{timelineCount}</span>
          </span>
          <span className="text-text-muted">
            Locations <span className="text-text">{locationCount}</span>
          </span>
          <span className="text-text-muted">
            Entities in locations <span className="text-text">{locationEntityTotal}</span>
          </span>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:text-text hover:bg-surface-hover disabled:opacity-60"
          title="Refresh events and locations"
        >
          <RefreshCcw size={12} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mx-3 mt-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-[11px] text-red-300">
          {error}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 p-3 lg:grid-cols-2">
        <section className="min-h-0 rounded border border-border bg-bg/50">
          <div className="flex items-center gap-2 border-b border-border px-2 py-1.5 text-xs font-semibold text-text">
            <Clock3 size={13} />
            Event Timeline
          </div>
          <div className="h-[calc(100%-30px)] overflow-y-auto p-2">
            {loading ? (
              <div className="flex h-full items-center justify-center text-xs text-text-muted">
                <Loader2 size={14} className="mr-2 animate-spin" />
                Loading events...
              </div>
            ) : events.length === 0 ? (
              <div className="text-xs text-text-muted">No events yet.</div>
            ) : (
              <div className="space-y-2">
                {events.map((event) => {
                  const isExpanded = expandedEventId === event.event_id;
                  const audit = event.audit_log_id ? auditLogs.find((row) => row.id === event.audit_log_id) : null;
                  const run = transformRunByEventId[event.event_id];
                  return (
                    <div
                      key={event.event_id}
                      className={`w-full rounded border p-2 text-left transition-colors ${
                        isExpanded ? "border-accent bg-accent/10" : "border-border bg-surface/40 hover:bg-surface-hover"
                      }`}
                    >
                      <div className="mb-1 flex w-full items-start justify-between gap-2 text-left">
                        <p className="text-xs text-text">{event.title}</p>
                        <div className="flex items-center gap-2">
                          <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${eventBadgeClass(event.event_type)}`}>
                            {event.event_type}
                          </span>
                          <button
                            onClick={() => openEventDetails(event)}
                            className="rounded border border-border p-0.5 text-text-muted hover:bg-surface-hover hover:text-text"
                            title={isExpanded ? "Collapse details" : "Expand details"}
                          >
                            {isExpanded ? (
                              <ChevronUp size={12} />
                            ) : (
                              <ChevronDown size={12} />
                            )}
                          </button>
                        </div>
                      </div>
                      <div className="space-y-0.5 text-[11px] text-text-muted">
                        <div>Occurred: {formatDate(event.occurred_at)}</div>
                        {event.observed_at && <div>Observed: {formatDate(event.observed_at)}</div>}
                        {(event.valid_from || event.valid_to) && (
                          <div>
                            Valid: {formatDate(event.valid_from)} - {formatDate(event.valid_to)}
                          </div>
                        )}
                        {(event.location_label || (event.lat != null && event.lon != null)) && (
                          <div>
                            Location: {event.location_label ?? "Unlabeled"} {event.lat != null && event.lon != null ? `(${event.lat.toFixed(4)}, ${event.lon.toFixed(4)})` : ""}
                          </div>
                        )}
                      </div>

                      {isExpanded && (
                        <div className="mt-2 rounded border border-border bg-bg/70 p-2 text-[11px]">
                          <div className="mb-2 flex flex-wrap gap-2">
                            {event.entity_id && (
                              <button
                                onClick={() => jumpToEntity(event.entity_id)}
                                className="rounded border border-border px-2 py-1 text-text-muted hover:bg-surface-hover hover:text-text"
                              >
                                Open Entity
                              </button>
                            )}
                            {event.edge_id && (
                              <button
                                onClick={() => jumpToEdge(event.edge_id)}
                                className="rounded border border-border px-2 py-1 text-text-muted hover:bg-surface-hover hover:text-text"
                              >
                                Open Edge
                              </button>
                            )}
                          </div>

                          {event.transform_run_id && (
                            <div className="mb-2 rounded border border-border bg-surface/40 p-2">
                              <div className="mb-1 text-[11px] font-semibold text-text">Transform Run</div>
                              {loadingDetailsEventId === event.event_id ? (
                                <div className="flex items-center gap-2 text-text-muted">
                                  <Loader2 size={12} className="animate-spin" />
                                  Loading run details...
                                </div>
                              ) : run ? (
                                <div className="space-y-0.5 text-text-muted">
                                  <div>Name: {run.transform_name}</div>
                                  <div>Status: {run.status}</div>
                                  <div>Started: {formatDate(run.started_at)}</div>
                                  <div>Completed: {formatDate(run.completed_at)}</div>
                                  {run.error && <div>Error: {run.error}</div>}
                                </div>
                              ) : (
                                <div className="text-text-muted">No run details available.</div>
                              )}
                            </div>
                          )}

                          {event.audit_log_id && (
                            <div className="mb-2 rounded border border-border bg-surface/40 p-2">
                              <div className="mb-1 text-[11px] font-semibold text-text">Audit Log</div>
                              {audit ? (
                                <div className="space-y-0.5 text-text-muted">
                                  <div>Action: {audit.action}</div>
                                  <div>Resource: {audit.resource_type}</div>
                                  <div>When: {formatDate(audit.created_at)}</div>
                                  <pre className="mt-1 overflow-x-auto rounded border border-border bg-bg p-2 text-[10px] text-text-muted">
{JSON.stringify(audit.details ?? {}, null, 2)}
                                  </pre>
                                </div>
                              ) : (
                                <div className="text-text-muted">Audit log not found.</div>
                              )}
                            </div>
                          )}

                          <div className="rounded border border-border bg-surface/40 p-2">
                            <div className="mb-1 text-[11px] font-semibold text-text">Event Payload</div>
                            <pre className="overflow-x-auto text-[10px] text-text-muted">
{JSON.stringify(event.payload ?? {}, null, 2)}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        <section className="min-h-0 rounded border border-border bg-bg/50">
          <div className="flex items-center gap-2 border-b border-border px-2 py-1.5 text-xs font-semibold text-text">
            <MapPin size={13} />
            Normalized Locations
          </div>
          <div className="h-[calc(100%-30px)] overflow-y-auto p-2">
            {loading ? (
              <div className="flex h-full items-center justify-center text-xs text-text-muted">
                <Loader2 size={14} className="mr-2 animate-spin" />
                Loading locations...
              </div>
            ) : locations.length === 0 ? (
              <div className="text-xs text-text-muted">No geospatial data found yet.</div>
            ) : (
              <div className="space-y-2">
                {locations.map((row) => {
                  const hasCoords = row.lat != null && row.lon != null;
                  const mapUrl = hasCoords
                    ? `https://www.openstreetmap.org/?mlat=${row.lat}&mlon=${row.lon}#map=8/${row.lat}/${row.lon}`
                    : null;
                  const firstEntityId = row.entity_ids?.[0] ?? null;
                  return (
                    <div key={row.key} className="rounded border border-border bg-surface/40 p-2 text-[11px]">
                      <div className="mb-1 flex items-start justify-between gap-2">
                        <p className="text-xs text-text">{row.location_label ?? "Unlabeled location"}</p>
                        <span className="rounded border border-border px-1.5 py-0.5 text-[10px] text-text-muted">
                          {row.entity_count} entities
                        </span>
                      </div>
                      <div className="space-y-0.5 text-text-muted">
                        <div>
                          Coordinates: {hasCoords ? `${row.lat?.toFixed(4)}, ${row.lon?.toFixed(4)}` : "n/a"}
                        </div>
                        <div>Confidence: {row.geo_confidence != null ? row.geo_confidence.toFixed(2) : "n/a"}</div>
                        {mapUrl && (
                          <a
                            href={mapUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-accent hover:underline"
                          >
                            Open in map <ExternalLink size={11} />
                          </a>
                        )}
                        {firstEntityId && (
                          <button
                            onClick={() => jumpToEntity(firstEntityId)}
                            className="ml-3 inline-flex items-center gap-1 text-accent hover:underline"
                          >
                            Jump to entity
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
