import { useMemo } from "react";
import type { ScopeConfig } from "../../types/agent";

interface InvestigatorPromptProps {
  prompt: string;
  onPromptChange: (value: string) => void;
  scopeMode: ScopeConfig["mode"];
  onScopeModeChange: (value: ScopeConfig["mode"]) => void;
  selectedCount: number;
  disabled?: boolean;
  onStart: () => void;
}

export function InvestigatorPrompt({
  prompt,
  onPromptChange,
  scopeMode,
  onScopeModeChange,
  selectedCount,
  disabled = false,
  onStart,
}: InvestigatorPromptProps) {
  const selectedDisabled = selectedCount === 0;
  const helperText = useMemo(() => {
    if (scopeMode === "selected") {
      return selectedDisabled
        ? "Select one or more entities on the graph to use selected scope."
        : `${selectedCount} selected entities will be visible to the investigator.`;
    }
    return "The investigator can reason over the entire project graph.";
  }, [scopeMode, selectedCount, selectedDisabled]);

  return (
    <div className="border-b border-border p-3">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold text-text">Prompt</p>
          <p className="text-[11px] text-text-muted">Describe the investigation goal and desired outcome.</p>
        </div>
        <button
          onClick={onStart}
          disabled={disabled || !prompt.trim() || (scopeMode === "selected" && selectedDisabled)}
          className="rounded border border-accent/50 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Start Run
        </button>
      </div>
      <textarea
        value={prompt}
        onChange={(event) => onPromptChange(event.target.value)}
        disabled={disabled}
        rows={4}
        placeholder="Example: Investigate the selected infrastructure for ownership, external exposure, and high-confidence pivots."
        className="w-full rounded border border-border bg-bg px-3 py-2 text-xs text-text outline-none transition-colors placeholder:text-text-muted focus:border-accent"
      />
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[11px] text-text-muted">
          <input
            type="radio"
            name="investigator-scope"
            checked={scopeMode === "all"}
            onChange={() => onScopeModeChange("all")}
            disabled={disabled}
          />
          Whole project
        </label>
        <label className="flex items-center gap-2 text-[11px] text-text-muted">
          <input
            type="radio"
            name="investigator-scope"
            checked={scopeMode === "selected"}
            onChange={() => onScopeModeChange("selected")}
            disabled={disabled || selectedDisabled}
          />
          Selected entities
        </label>
        <span className="text-[11px] text-text-muted">{helperText}</span>
      </div>
    </div>
  );
}
