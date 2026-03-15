import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useProjectStore } from "../../stores/projectStore";
import { useGraphStore } from "../../stores/graphStore";
import { useInvestigatorStore } from "../../stores/investigatorStore";
import type { ScopeConfig } from "../../types/agent";
import { ApiKeySettings } from "../ApiKeySettings";
import { AgentSettingsDialog } from "./AgentSettingsDialog";
import { InvestigatorControls } from "./InvestigatorControls";
import { InvestigatorPrompt } from "./InvestigatorPrompt";
import { InvestigatorStepLog } from "./InvestigatorStepLog";

export function InvestigatorPanel() {
  const currentProject = useProjectStore((state) => state.currentProject);
  const selectedNodeIds = useGraphStore((state) => state.selectedNodeIds);
  const {
    activeRun,
    steps,
    isLoading,
    error,
    startRun,
    loadActiveRun,
    cancelRun,
    approveStep,
    rejectStep,
    reset,
  } = useInvestigatorStore();
  const [prompt, setPrompt] = useState("");
  const [scopeMode, setScopeMode] = useState<ScopeConfig["mode"]>("all");
  const [showSettings, setShowSettings] = useState(false);
  const [showApiKeys, setShowApiKeys] = useState(false);
  const [apiKeyService, setApiKeyService] = useState<string | null>(null);

  useEffect(() => {
    if (!currentProject) {
      reset();
      return;
    }
    void loadActiveRun(currentProject.id);
  }, [currentProject, loadActiveRun, reset]);

  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  const selectedEntityIds = useMemo(() => Array.from(selectedNodeIds), [selectedNodeIds]);

  if (!currentProject) {
    return <div className="flex h-full items-center justify-center p-4 text-xs text-text-muted">Select a project to use AI Investigator.</div>;
  }

  const handleStart = async () => {
    try {
      await startRun(currentProject.id, prompt, {
        mode: scopeMode,
        entity_ids: scopeMode === "selected" ? selectedEntityIds : [],
      });
      setPrompt("");
    } catch {
      // Store surfaces the error.
    }
  };

  return (
    <div className="flex h-full">
      <div className="w-[360px] border-r border-border">
        <InvestigatorControls
          run={activeRun}
          disabled={isLoading}
          onCancel={() => void cancelRun(currentProject.id)}
          onRefresh={() => void loadActiveRun(currentProject.id)}
          onOpenSettings={() => setShowSettings(true)}
        />
        <InvestigatorPrompt
          prompt={prompt}
          onPromptChange={setPrompt}
          scopeMode={scopeMode}
          onScopeModeChange={setScopeMode}
          selectedCount={selectedEntityIds.length}
          disabled={isLoading || Boolean(activeRun && ["pending", "running", "paused"].includes(activeRun.status))}
          onStart={() => void handleStart()}
        />
        <div className="p-3 text-[11px] text-text-muted">
          {activeRun ? (
            <>
              <div className="mb-1 font-semibold text-text">Current Prompt</div>
              <p className="whitespace-pre-wrap">{activeRun.prompt}</p>
              {activeRun.summary && (
                <>
                  <div className="mt-3 mb-1 font-semibold text-text">Final Summary</div>
                  <p className="whitespace-pre-wrap">{activeRun.summary}</p>
                </>
              )}
              {activeRun.error && (
                <>
                  <div className="mt-3 mb-1 font-semibold text-red-300">Run Error</div>
                  <p className="whitespace-pre-wrap text-red-200">{activeRun.error}</p>
                </>
              )}
            </>
          ) : (
            "Start a run to let the investigator plan transform calls, request approvals, and summarize findings."
          )}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <InvestigatorStepLog
          steps={steps}
          disabled={isLoading}
          onApprove={(stepId) => activeRun && void approveStep(currentProject.id, activeRun.id, stepId)}
          onReject={(stepId) => activeRun && void rejectStep(currentProject.id, activeRun.id, stepId)}
        />
      </div>
      <AgentSettingsDialog
        open={showSettings}
        projectId={currentProject.id}
        onClose={() => setShowSettings(false)}
        onOpenApiKeys={(serviceName) => {
          setApiKeyService(serviceName);
          setShowSettings(false);
          setShowApiKeys(true);
        }}
      />
      <ApiKeySettings
        open={showApiKeys}
        onClose={() => setShowApiKeys(false)}
        initialService={apiKeyService}
      />
    </div>
  );
}
