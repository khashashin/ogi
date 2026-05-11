import { useEffect, useMemo, useState } from "react";
import { ExternalLink, KeyRound, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../api/client";
import type { AgentModelCatalog, AgentModelOption } from "../../types/agent";

interface AgentSettingsDialogProps {
  open: boolean;
  projectId: string;
  onClose: () => void;
  onOpenApiKeys: (serviceName: string) => void;
}

const PROVIDERS = [
  {
    id: "openai",
    label: "OpenAI",
    serviceName: "openai",
    defaultModel: "gpt-4.1-mini",
    createUrl: "https://platform.openai.com/api-keys",
    usageUrl: "https://platform.openai.com/settings/organization/limits",
    usageLabel: "Billing & Limits",
  },
  {
    id: "gemini",
    label: "Gemini",
    serviceName: "gemini",
    defaultModel: "gemini-2.5-flash",
    createUrl: "https://aistudio.google.com/app/apikey",
    usageUrl: "https://aistudio.google.com/spend",
    usageLabel: "Gemini API Spend",
  },
  {
    id: "anthropic",
    label: "Claude",
    serviceName: "anthropic",
    defaultModel: "claude-3-5-sonnet-latest",
    createUrl: "https://console.anthropic.com/settings/keys",
    usageUrl: "https://console.anthropic.com/settings/limits",
    usageLabel: "Limits",
  },
] as const;

export function AgentSettingsDialog({
  open,
  projectId,
  onClose,
  onOpenApiKeys,
}: AgentSettingsDialogProps) {
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [services, setServices] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<AgentModelCatalog | null>(null);
  const [selectedPreset, setSelectedPreset] = useState("");
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testOk, setTestOk] = useState<boolean | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    Promise.all([api.agent.getSettings(projectId), api.apiKeys.list()])
      .then(async ([data, apiKeys]) => {
        setServices(apiKeys.map((item) => item.service_name));
        setProvider(data.provider || "openai");
        const nextModel =
          data.model ||
          PROVIDERS.find((item) => item.id === data.provider)?.defaultModel ||
          "";
        setModel(nextModel);
        const nextCatalog = await api.agent.listModels(
          projectId,
          data.provider || "openai",
        );
        setCatalog(nextCatalog);
        const presetMatch = nextCatalog.available_models.find(
          (item) => item.id === nextModel,
        );
        setSelectedPreset(presetMatch?.id || "");
        setTestMessage(null);
        setTestOk(null);
      })
      .catch((error) =>
        toast.error(error instanceof Error ? error.message : String(error)),
      )
      .finally(() => setLoading(false));
  }, [open, projectId]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api.agent
      .listModels(projectId, provider)
      .then((data) => {
        if (cancelled) return;
        setCatalog(data);
        setSelectedPreset((current) => {
          if (
            current &&
            data.available_models.some((item) => item.id === current)
          ) {
            return current;
          }
          return data.available_models.some((item) => item.id === model.trim())
            ? model.trim()
            : "";
        });
      })
      .catch((error) => {
        if (cancelled) return;
        toast.error(error instanceof Error ? error.message : String(error));
      });
    return () => {
      cancelled = true;
    };
  }, [open, projectId, provider]);

  const providerMeta = useMemo(
    () => PROVIDERS.find((item) => item.id === provider) ?? PROVIDERS[0],
    [provider],
  );

  const availableModels = useMemo<AgentModelOption[]>(
    () => catalog?.available_models ?? [],
    [catalog],
  );

  useEffect(() => {
    setSelectedPreset(
      availableModels.some((item) => item.id === model.trim())
        ? model.trim()
        : "",
    );
  }, [availableModels, model]);

  const save = async () => {
    setSaving(true);
    try {
      await api.agent.saveSettings(projectId, {
        provider,
        model: model.trim(),
      });
      toast.success("AI Investigator settings saved");
      onClose();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  const testSettings = async () => {
    setTesting(true);
    setTestMessage(null);
    setTestOk(null);
    try {
      const result = await api.agent.testSettings(projectId, {
        provider,
        model: model.trim(),
      });
      setTestMessage(result.message);
      setTestOk(result.success);
      if (result.available_models.length > 0) {
        setCatalog((current) => ({
          provider: result.provider,
          default_model: current?.default_model || providerMeta.defaultModel,
          recommended_models: current?.recommended_models || [],
          available_models: result.available_models,
          has_api_key: result.has_api_key,
        }));
      }
      if (result.success) {
        toast.success("AI Investigator settings validated");
      } else {
        toast.error(result.message);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setTestMessage(message);
      setTestOk(false);
      toast.error(message);
    } finally {
      setTesting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-xl rounded-lg border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-accent" />
            <h2 className="text-sm font-semibold text-text">
              AI Investigator Settings
            </h2>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-4 p-4">
          <p className="text-xs text-text-muted">
            Choose the LLM provider and model used for agent runs. API keys stay
            in encrypted backend storage.
          </p>

          <div className="rounded border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] text-amber-100">
            Strongly recommended: set provider billing and usage caps before
            enabling AI-driven investigations. Agent loops, repeated transforms,
            or large graph explorations can consume tokens faster than expected.
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {PROVIDERS.map((item) => {
              const active = provider === item.id;
              const configured = services.includes(item.serviceName);
              return (
                <button
                  key={item.id}
                  onClick={() => {
                    setProvider(item.id);
                    setModel((current) => current.trim() || item.defaultModel);
                    setTestMessage(null);
                    setTestOk(null);
                  }}
                  className={`rounded border p-3 text-left transition-colors ${
                    active
                      ? "border-accent bg-accent/10"
                      : "border-border bg-bg hover:bg-surface-hover"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs font-semibold text-text">
                      {item.label}
                    </span>
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] ${
                        configured
                          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                          : "border-border bg-surface-hover text-text-muted"
                      }`}
                    >
                      {configured ? "configured" : "missing key"}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted">
                    {item.defaultModel}
                  </p>
                </button>
              );
            })}
          </div>

          <div className="space-y-2">
            <label className="text-xs font-medium text-text">Model</label>
            <select
              value={selectedPreset}
              onChange={(event) => {
                const nextValue = event.target.value;
                setSelectedPreset(nextValue);
                if (nextValue) {
                  setModel(nextValue);
                }
                setTestMessage(null);
                setTestOk(null);
              }}
              className="w-full rounded border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-accent"
            >
              <option value="">Custom model...</option>
              {availableModels.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}{" "}
                  {item.source === "recommended" ? "• suggested" : ""}
                </option>
              ))}
            </select>
            <input
              value={model}
              onChange={(event) => {
                const nextValue = event.target.value;
                setModel(nextValue);
                setSelectedPreset(
                  availableModels.some((item) => item.id === nextValue.trim())
                    ? nextValue.trim()
                    : "",
                );
                setTestMessage(null);
                setTestOk(null);
              }}
              placeholder={catalog?.default_model || providerMeta.defaultModel}
              className="w-full rounded border border-border bg-bg px-3 py-2 text-sm text-text outline-none focus:border-accent"
            />
            <div className="text-[11px] text-text-muted">
              Use the dropdown for discovered models or type any provider model
              ID manually.
            </div>
          </div>

          <div className="rounded border border-border bg-bg p-3">
            <div className="mb-2 flex items-center justify-between">
              <div>
                <div className="text-xs font-semibold text-text">
                  {providerMeta.label} API Key
                </div>
                <div className="text-[11px] text-text-muted">
                  Create a key with the provider, then store it in OGI.
                </div>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={providerMeta.createUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-text-muted hover:bg-surface-hover hover:text-text"
                >
                  Create Key
                  <ExternalLink size={12} />
                </a>
                <a
                  href={providerMeta.usageUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-100 hover:bg-amber-500/15"
                >
                  {providerMeta.usageLabel}
                  <ExternalLink size={12} />
                </a>
                <button
                  onClick={() => onOpenApiKeys(providerMeta.serviceName)}
                  className="inline-flex items-center gap-1 rounded border border-accent/40 bg-accent/10 px-2 py-1 text-[11px] text-accent hover:bg-accent/15"
                >
                  <KeyRound size={12} />
                  Store Key
                </button>
              </div>
            </div>
            <div className="text-[11px] text-text-muted">
              Current status:{" "}
              {loading
                ? "checking..."
                : services.includes(providerMeta.serviceName)
                  ? "API key available"
                  : "API key not found"}
            </div>
            {testMessage ? (
              <div
                className={`mt-2 rounded border px-2 py-1.5 text-[11px] ${
                  testOk
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    : "border-amber-500/40 bg-amber-500/10 text-amber-200"
                }`}
              >
                {testMessage}
              </div>
            ) : null}
          </div>

          <div className="rounded border border-border bg-bg p-3">
            <div className="mb-2 text-xs font-semibold text-text">
              Validation
            </div>
            <div className="text-[11px] text-text-muted">
              Test checks the stored API key server-side and verifies the
              selected model against the provider.
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-3">
          <button
            onClick={testSettings}
            disabled={testing || !model.trim()}
            className="rounded border border-accent/40 bg-accent/10 px-3 py-1.5 text-sm text-accent hover:bg-accent/15 disabled:opacity-50"
          >
            {testing ? "Testing..." : "Test"}
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="rounded border border-border px-3 py-1.5 text-sm text-text-muted hover:bg-surface-hover hover:text-text"
            >
              Cancel
            </button>
            <button
              onClick={save}
              disabled={saving || !model.trim()}
              className="rounded bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent-hover disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
