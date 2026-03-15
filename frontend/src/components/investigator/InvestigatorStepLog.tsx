import type { AgentStep } from "../../types/agent";
import { StepApproval } from "./steps/StepApproval";
import { StepError } from "./steps/StepError";
import { StepSummary } from "./steps/StepSummary";
import { StepThinking } from "./steps/StepThinking";
import { StepToolCall } from "./steps/StepToolCall";

interface InvestigatorStepLogProps {
  steps: AgentStep[];
  disabled?: boolean;
  onApprove: (stepId: string) => void;
  onReject: (stepId: string) => void;
}

function stepTitle(step: AgentStep): string {
  switch (step.type) {
    case "think":
      return "Think";
    case "tool_call":
      return "Tool Call";
    case "tool_result":
      return "Tool Result";
    case "approval_request":
      return "Approval";
    case "summary":
      return "Summary";
    case "error":
      return "Error";
    default:
      return step.type;
  }
}

function renderBody(
  step: AgentStep,
  disabled: boolean,
  onApprove: (stepId: string) => void,
  onReject: (stepId: string) => void
) {
  if (step.status === "waiting_approval") {
    return (
      <StepApproval
        step={step}
        disabled={disabled}
        onApprove={() => onApprove(step.id)}
        onReject={() => onReject(step.id)}
      />
    );
  }
  if (step.type === "think") return <StepThinking step={step} />;
  if (step.type === "tool_call" || step.type === "tool_result" || step.type === "approval_request") {
    return <StepToolCall step={step} />;
  }
  if (step.type === "summary") return <StepSummary step={step} />;
  if (step.type === "error" || step.status === "failed") return <StepError step={step} />;
  return (
    <pre className="overflow-x-auto rounded border border-border bg-bg p-2 text-[10px] text-text-muted">
{JSON.stringify(step, null, 2)}
    </pre>
  );
}

export function InvestigatorStepLog({
  steps,
  disabled = false,
  onApprove,
  onReject,
}: InvestigatorStepLogProps) {
  if (steps.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-xs text-text-muted">
        No run history yet.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="space-y-3">
        {steps.map((step) => (
          <div key={step.id} className="rounded border border-border bg-bg/60 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded border border-border px-2 py-0.5 text-[10px] text-text-muted">
                  step {step.step_number}
                </span>
                <span className="text-xs font-semibold text-text">{stepTitle(step)}</span>
              </div>
              <span className="text-[10px] uppercase tracking-wide text-text-muted">{step.status}</span>
            </div>
            {renderBody(step, disabled, onApprove, onReject)}
          </div>
        ))}
      </div>
    </div>
  );
}
