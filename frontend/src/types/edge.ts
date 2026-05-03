import type { PropertyValue } from "./entity";

export interface Edge {
  id: string;
  source_id: string;
  target_id: string;
  label: string;
  weight: number;
  properties: Record<string, PropertyValue>;
  bidirectional: boolean;
  source_transform: string;
  project_id: string | null;
  created_at: string;
}

export interface EdgeCreate {
  source_id: string;
  target_id: string;
  label?: string;
  weight?: number;
  properties?: Record<string, PropertyValue>;
  bidirectional?: boolean;
  source_transform?: string;
}

export interface EdgeUpdate {
  label?: string;
  weight?: number;
  properties?: Record<string, PropertyValue>;
}
