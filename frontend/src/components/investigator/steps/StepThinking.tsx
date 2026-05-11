import type { AgentStep } from "../../../types/agent";

export function StepThinking({ step }: { step: AgentStep }) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] font-semibold text-text">Reasoning</div>
      <p className="whitespace-pre-wrap text-[11px] text-text-muted">
        {step.llm_output || "No reasoning recorded."}
      </p>
    </div>
  );
}
