export type AgentRunStatus =
  | "pending"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentStepType =
  | "think"
  | "tool_call"
  | "tool_result"
  | "approval_request"
  | "approval_response"
  | "error"
  | "summary";

export type AgentStepStatus =
  | "pending"
  | "running"
  | "waiting_approval"
  | "approved"
  | "rejected"
  | "completed"
  | "failed";

export interface ScopeConfig {
  mode: "all" | "selected";
  entity_ids: string[];
}

export interface BudgetConfig {
  max_steps?: number | null;
  max_transforms?: number | null;
  max_runtime_sec?: number | null;
}

export interface UsageInfo {
  steps_used: number;
  transforms_run: number;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface AgentRun {
  id: string;
  project_id: string;
  user_id: string;
  status: AgentRunStatus;
  scope: ScopeConfig;
  prompt: string;
  provider: string;
  model: string;
  config: Record<string, unknown>;
  budget: BudgetConfig;
  usage: UsageInfo;
  summary: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface AgentStep {
  id: string;
  run_id: string;
  step_number: number;
  type: AgentStepType;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: Record<string, unknown> | null;
  llm_output: string | null;
  token_usage: Record<string, number> | null;
  approval_payload: Record<string, unknown> | null;
  status: AgentStepStatus;
  worker_id: string | null;
  claimed_at: string | null;
  created_at: string;
  completed_at: string | null;
}

export type AgentEventMessageType =
  | "agent_run_started"
  | "agent_thinking"
  | "agent_tool_called"
  | "agent_tool_result"
  | "agent_approval_requested"
  | "agent_approval_resolved"
  | "agent_run_completed"
  | "agent_run_failed"
  | "agent_run_cancelled";

export interface AgentEventMessage {
  type: AgentEventMessageType;
  project_id: string;
  run_id: string;
  step_id: string | null;
  status: string | null;
  summary: string | null;
  timestamp: string;
}

export interface StartAgentRunRequest {
  prompt: string;
  scope: ScopeConfig;
  budget?: BudgetConfig;
}

export interface AgentSettings {
  provider: string;
  model: string;
  has_api_key: boolean;
}

export interface AgentModelOption {
  id: string;
  label: string;
  source: string;
}

export interface AgentModelCatalog {
  provider: string;
  default_model: string;
  recommended_models: AgentModelOption[];
  available_models: AgentModelOption[];
  has_api_key: boolean;
}

export interface AgentSettingsTestResult {
  provider: string;
  model: string;
  success: boolean;
  has_api_key: boolean;
  model_found: boolean;
  message: string;
  available_models: AgentModelOption[];
}
