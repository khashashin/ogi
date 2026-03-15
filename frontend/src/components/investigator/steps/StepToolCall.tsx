import type { AgentStep } from "../../../types/agent";

export function StepToolCall({ step }: { step: AgentStep }) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] font-semibold text-text">Tool Call</div>
      <div className="text-[11px] text-text-muted">
        <span className="text-text">{step.tool_name ?? "unknown"}</span>
      </div>
      {step.tool_input && (
        <pre className="overflow-x-auto rounded border border-border bg-bg p-2 text-[10px] text-text-muted">
{JSON.stringify(step.tool_input, null, 2)}
        </pre>
      )}
    </div>
  );
}
