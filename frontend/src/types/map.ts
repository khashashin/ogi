export interface MapPoint {
  entity_id: string;
  entity_type: string;
  label: string;
  lat: number;
  lon: number;
  geo_confidence?: number | null;
  location_label?: string | null;
  source: string;
}

export interface MapCluster {
  cluster_id: string;
  lat: number;
  lon: number;
  count: number;
  entity_ids: string[];
}

export interface MapPointsResponse {
  points: MapPoint[];
  clusters: MapCluster[];
  unresolved_labels: string[];
}

export interface MapRoute {
  edge_id: string;
  source_entity_id: string;
  target_entity_id: string;
  source_lat: number;
  source_lon: number;
  target_lat: number;
  target_lon: number;
  label: string;
  weight: number;
}

export interface MapRoutesResponse {
  routes: MapRoute[];
}
