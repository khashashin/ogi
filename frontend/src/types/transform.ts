import type { EntityType, Entity } from "./entity";
import type { Edge } from "./edge";

export interface TransformInfo {
  name: string;
  display_name: string;
  description: string;
  input_types: EntityType[];
  output_types: EntityType[];
  category: string;
}

export interface TransformResult {
  entities: Entity[];
  edges: Edge[];
  messages: string[];
  ui_messages: string[];
}

export type TransformStatus = "pending" | "running" | "completed" | "failed";

export interface TransformRun {
  id: string;
  project_id: string;
  transform_name: string;
  input_entity_id: string;
  status: TransformStatus;
  result: TransformResult | null;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface TransformConfig {
  settings: Record<string, string>;
}
