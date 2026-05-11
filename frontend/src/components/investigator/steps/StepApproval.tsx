import type { AgentStep } from "../../../types/agent";

interface StepApprovalProps {
  step: AgentStep;
  disabled?: boolean;
  onApprove: () => void;
  onReject: () => void;
}

export function StepApproval({ step, disabled = false, onApprove, onReject }: StepApprovalProps) {
  return (
    <div className="space-y-2">
      <div className="text-[11px] font-semibold text-text">Approval Required</div>
      <p className="text-[11px] text-text-muted">
        Tool <span className="text-text">{step.tool_name ?? "unknown"}</span> is waiting for approval.
      </p>
      {step.approval_payload && (
        <pre className="overflow-x-auto rounded border border-border bg-bg p-2 text-[10px] text-text-muted">
{JSON.stringify(step.approval_payload, null, 2)}
        </pre>
      )}
      <div className="flex items-center gap-2">
        <button
          onClick={onApprove}
          disabled={disabled}
          className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-300 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          onClick={onReject}
          disabled={disabled}
          className="rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-[11px] text-red-300 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}
