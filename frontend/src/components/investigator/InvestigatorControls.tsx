import type { AgentRun } from "../../types/agent";

interface InvestigatorControlsProps {
  run: AgentRun | null;
  disabled?: boolean;
  onCancel: () => void;
  onRefresh: () => void;
  onOpenSettings: () => void;
}

function statusClass(status: AgentRun["status"]): string {
  switch (status) {
    case "running":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
    case "paused":
      return "border-amber-500/40 bg-amber-500/10 text-amber-300";
    case "failed":
    case "cancelled":
      return "border-red-500/40 bg-red-500/10 text-red-300";
    case "completed":
      return "border-sky-500/40 bg-sky-500/10 text-sky-300";
    default:
      return "border-border bg-surface-hover text-text-muted";
  }
}

export function InvestigatorControls({
  run,
  disabled = false,
  onCancel,
  onRefresh,
  onOpenSettings,
}: InvestigatorControlsProps) {
  return (
    <div className="flex items-center justify-between border-b border-border px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
        <span className="font-semibold text-text">AI Investigator</span>
        {run ? (
          <>
            <span className={`rounded border px-2 py-0.5 ${statusClass(run.status)}`}>{run.status}</span>
            <span>steps {run.usage?.steps_used ?? 0}</span>
            <span>transforms {run.usage?.transforms_run ?? 0}</span>
            <span>llm calls {run.usage?.llm_calls ?? 0}</span>
          </>
        ) : (
          <span>No active run</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenSettings}
          className="rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:bg-surface-hover hover:text-text"
        >
          Settings
        </button>
        <button
          onClick={onRefresh}
          className="rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:bg-surface-hover hover:text-text"
        >
          Refresh
        </button>
        <button
          onClick={onCancel}
          disabled={disabled || !run || ["completed", "failed", "cancelled"].includes(run.status)}
          className="rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:bg-surface-hover hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
