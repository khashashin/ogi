import type { EntityType, Entity } from "./entity";
import type { Edge } from "./edge";

export interface TransformInfo {
  name: string;
  display_name: string;
  description: string;
  input_types: EntityType[];
  output_types: EntityType[];
  category: string;
  api_key_services: string[];
  settings: TransformSettingSchema[];
}

export interface TransformSettingSchema {
  name: string;
  display_name: string;
  description: string;
  required: boolean;
  default: string;
  field_type: "string" | "integer" | "number" | "boolean" | "select" | "secret";
  options: string[];
  min_value: number | null;
  max_value: number | null;
  pattern: string;
}

export interface TransformResult {
  entities: Entity[];
  edges: Edge[];
  messages: string[];
  ui_messages: string[];
}

export type TransformStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

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

export interface TransformSettingsResponse {
  transform_name: string;
  settings_schema: TransformSettingSchema[];
  defaults: Record<string, string>;
  global_settings: Record<string, string>;
  user_settings: Record<string, string>;
  resolved: Record<string, string>;
  can_manage_global: boolean;
}

// --- WebSocket message types ---

export type TransformJobMessageType =
  | "job_submitted"
  | "job_started"
  | "job_completed"
  | "job_failed"
  | "job_cancelled";

export interface TransformJobMessage {
  type: TransformJobMessageType;
  job_id: string;
  project_id: string;
  transform_name: string;
  input_entity_id: string;
  progress: number | null;
  message: string | null;
  result: TransformResult | null;
  error: string | null;
  timestamp: string;
}

export interface TransformWsCancelMessage {
  type: "cancel";
  job_id: string;
}

export interface TransformWsPingMessage {
  type: "ping";
}

export type TransformWsOutgoing = TransformWsCancelMessage | TransformWsPingMessage;
