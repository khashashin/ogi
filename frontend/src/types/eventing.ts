export interface TemporalGeoConventions {
  observed_at: string;
  valid_from: string;
  valid_to: string;
  lat: string;
  lon: string;
  location_label: string;
  geo_confidence: string;
}

export interface ProjectEvent {
  event_id: string;
  event_type: string;
  project_id: string;
  occurred_at: string;
  actor_user_id?: string | null;
  title: string;
  entity_id?: string | null;
  edge_id?: string | null;
  transform_run_id?: string | null;
  audit_log_id?: string | null;
  observed_at?: string | null;
  valid_from?: string | null;
  valid_to?: string | null;
  lat?: number | null;
  lon?: number | null;
  location_label?: string | null;
  geo_confidence?: number | null;
  payload?: Record<string, unknown>;
}

export interface ProjectEventsResponse {
  conventions: TemporalGeoConventions;
  items: ProjectEvent[];
}

export interface AuditLogEntry {
  id: string;
  project_id: string;
  actor_user_id?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface LocationAggregate {
  key: string;
  location_label?: string | null;
  lat?: number | null;
  lon?: number | null;
  geo_confidence?: number | null;
  entity_count: number;
  entity_ids: string[];
}
