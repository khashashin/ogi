import { useState, useEffect } from "react";
import { X, Plus, Trash2, Key } from "lucide-react";
import { api } from "../api/client";

interface ApiKeySettingsProps {
  open: boolean;
  onClose: () => void;
}

const KNOWN_SERVICES = [
  "openai",
  "virustotal",
  "shodan",
  "censys",
  "passivetotal",
  "securitytrails",
  "abuseipdb",
] as const;

export function ApiKeySettings({ open, onClose }: ApiKeySettingsProps) {
  const [services, setServices] = useState<string[]>([]);
  const [newService, setNewService] = useState("");
  const [newKey, setNewKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) loadKeys();
  }, [open]);

  const loadKeys = async () => {
    setLoading(true);
    try {
      const data = await api.apiKeys.list();
      setServices(data.map((d) => d.service_name));
    } catch {
      setServices([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newService.trim() || !newKey.trim()) return;
    setError(null);
    try {
      await api.apiKeys.save(newService.trim().toLowerCase(), newKey.trim());
      setNewService("");
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
              onChange={(e) => setNewService(e.target.value)}
              className="px-2 py-1.5 text-sm bg-bg border border-border rounded text-text w-36"
            >
              <option value="">Service...</option>
              {KNOWN_SERVICES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
              <option value="__custom">Custom...</option>
            </select>
            {newService === "__custom" && (
              <input
                type="text"
                placeholder="Service name"
                value=""
                onChange={(e) => setNewService(e.target.value)}
                className="px-2 py-1.5 text-sm bg-bg border border-border rounded text-text w-28"
              />
            )}
            <input
              type="password"
              placeholder="API key"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className="flex-1 px-2 py-1.5 text-sm bg-bg border border-border rounded text-text"
            />
            <button
              type="submit"
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-accent text-white rounded hover:bg-accent-hover"
            >
              <Plus size={14} />
            </button>
          </form>

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
