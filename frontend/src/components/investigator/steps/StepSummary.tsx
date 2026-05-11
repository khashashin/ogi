import type { AgentStep } from "../../../types/agent";

export function StepSummary({ step }: { step: AgentStep }) {
  const summary = step.llm_output || (typeof step.tool_output?.summary === "string" ? step.tool_output.summary : "");
  return (
    <div className="space-y-1">
      <div className="text-[11px] font-semibold text-text">Summary</div>
      <p className="whitespace-pre-wrap text-[11px] text-text-muted">
        {summary || "No summary available."}
      </p>
    </div>
  );
}
