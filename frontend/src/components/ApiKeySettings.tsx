import { useState, useEffect, useMemo } from "react";
import { X, Plus, Trash2, Key } from "lucide-react";
import { api } from "../api/client";

interface ApiKeySettingsProps {
  open: boolean;
  onClose: () => void;
  initialService?: string | null;
}

const KNOWN_SERVICES = [
  "openai",
  "gemini",
  "anthropic",
  "peeringdb",
  "openweather",
  "virustotal",
  "ipinfo",
  "urlscan",
  "shodan",
  "opencve",
  "maltiverse",
  "censys",
  "passivetotal",
  "securitytrails",
  "abuseipdb",
  "abusech",
] as const;

const CUSTOM_SERVICE_VALUE = "__custom";

function normalizeServiceName(serviceName: string): string {
  return serviceName.trim().toLowerCase();
}

export function ApiKeySettings({ open, onClose, initialService = null }: ApiKeySettingsProps) {
  const [services, setServices] = useState<string[]>([]);
  const [newService, setNewService] = useState("");
  const [customService, setCustomService] = useState("");
  const [newKey, setNewKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const configuredServices = useMemo(
    () => new Set(services.map(normalizeServiceName).filter(Boolean)),
    [services],
  );
  const selectedServiceName =
    newService === CUSTOM_SERVICE_VALUE ? customService : newService;
  const normalizedNewService = normalizeServiceName(selectedServiceName);
  const duplicateService = Boolean(
    normalizedNewService && configuredServices.has(normalizedNewService),
  );
  const canAddKey = Boolean(
    normalizedNewService && newKey.trim() && !duplicateService,
  );

  useEffect(() => {
    if (open) loadKeys();
  }, [open]);

  useEffect(() => {
    if (!open || !initialService) return;
    const normalized = normalizeServiceName(initialService);
    if (!normalized) return;
    if ((KNOWN_SERVICES as readonly string[]).includes(normalized)) {
      setNewService(normalized);
      setCustomService("");
    } else {
      setNewService(CUSTOM_SERVICE_VALUE);
      setCustomService(normalized);
    }
  }, [initialService, open]);

  const loadKeys = async () => {
    setLoading(true);
    try {
      const data = await api.apiKeys.list();
      setServices([
        ...new Set(data.map((d) => normalizeServiceName(d.service_name)).filter(Boolean)),
      ]);
    } catch {
      setServices([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!normalizedNewService || !newKey.trim()) return;
    if (duplicateService) {
      setError(`${normalizedNewService} already has an API key.`);
      return;
    }
    setError(null);
    try {
      await api.apiKeys.save(normalizedNewService, newKey.trim());
      setNewService("");
      setCustomService("");
      setNewKey("");
      await loadKeys();
    } catch (err) {
      setError(String(err));
    }
  };

  const handleDelete = async (service: string) => {
    if (!window.confirm("Are you sure you want to remove this API key?")) return;
    try {
      await api.apiKeys.delete(service);
      await loadKeys();
    } catch (err) {
      setError(String(err));
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md bg-surface border border-border rounded-lg shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Key size={16} className="text-accent" />
            <h2 className="text-sm font-semibold text-text">API Keys</h2>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        <div className="p-4">
          <p className="text-xs text-text-muted mb-3">
            Configure API keys for transforms that require external service access.
          </p>

          {/* Add form */}
          <form onSubmit={handleAdd} className="flex gap-2 mb-4">
            <select
              value={newService}
              onChange={(e) => {
                setNewService(e.target.value);
                if (e.target.value !== CUSTOM_SERVICE_VALUE) {
                  setCustomService("");
                }
                setError(null);
              }}
              className="px-2 py-1.5 text-sm bg-bg border border-border rounded text-text w-36"
            >
              <option value="">Service...</option>
              {KNOWN_SERVICES.map((s) => {
                const configured = configuredServices.has(s);
                return (
                  <option key={s} value={s} disabled={configured}>
                    {s}
                    {configured ? " (configured)" : ""}
                  </option>
                );
              })}
              <option value={CUSTOM_SERVICE_VALUE}>Custom...</option>
            </select>
            {newService === CUSTOM_SERVICE_VALUE && (
              <input
                type="text"
                placeholder="Service name"
                value={customService}
                onChange={(e) => {
                  setCustomService(e.target.value);
                  setError(null);
                }}
                className="px-2 py-1.5 text-sm bg-bg border border-border rounded text-text w-28"
              />
            )}
            <input
              type="password"
              placeholder="API key"
              value={newKey}
              onChange={(e) => {
                setNewKey(e.target.value);
                setError(null);
              }}
              className="flex-1 px-2 py-1.5 text-sm bg-bg border border-border rounded text-text"
            />
            <button
              type="submit"
              disabled={!canAddKey}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-accent text-white rounded hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
              title={duplicateService ? "API key already configured" : "Add API key"}
            >
              <Plus size={14} />
            </button>
          </form>

          {duplicateService && (
            <p className="text-xs text-text-muted mb-3">
              {normalizedNewService} already has an API key. Remove it before adding another.
            </p>
          )}

          {error && <p className="text-xs text-danger mb-3">{error}</p>}

          {/* Stored keys */}
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {loading && <p className="text-xs text-text-muted">Loading...</p>}
            {!loading && services.length === 0 && (
              <p className="text-xs text-text-muted">No API keys configured</p>
            )}
            {services.map((service) => (
              <div
                key={service}
                className="flex items-center justify-between px-3 py-2 rounded bg-bg"
              >
                <div className="flex items-center gap-2">
                  <Key size={12} className="text-text-muted" />
                  <span className="text-sm text-text">{service}</span>
                </div>
                <button
                  onClick={() => handleDelete(service)}
                  className="p-1 text-text-muted hover:text-danger"
                  title="Remove key"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
