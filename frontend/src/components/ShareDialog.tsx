import { useState, useEffect } from "react";
import { X, UserPlus, Trash2 } from "lucide-react";
import { api } from "../api/client";

interface ProjectMember {
  project_id: string;
  user_id: string;
  role: string;
  display_name: string;
  email: string;
}

interface ShareDialogProps {
  open: boolean;
  onClose: () => void;
  projectId: string;
}

const ROLES = ["owner", "editor", "viewer"] as const;

export function ShareDialog({ open, onClose, projectId }: ShareDialogProps) {
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<string>("editor");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      loadMembers();
    }
  }, [open, projectId]);

  const loadMembers = async () => {
    try {
      const data = await api.members.list(projectId);
      setMembers(data);
    } catch {
      // Members may not be supported (SQLite mode)
      setMembers([]);
    }
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError(null);
    setLoading(true);
    try {
      await api.members.add(projectId, { email: email.trim(), role });
      setEmail("");
      await loadMembers();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await api.members.update(projectId, userId, { role: newRole });
      await loadMembers();
    } catch (err) {
      setError(String(err));
    }
  };

  const handleRemove = async (userId: string) => {
    if (!window.confirm("Are you sure you want to remove this member from the project?")) return;
    try {
      await api.members.remove(projectId, userId);
      await loadMembers();
    } catch (err) {
      setError(String(err));
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md bg-surface border border-border rounded-lg shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Share Project</h2>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        <div className="p-4">
          {/* Invite form */}
          <form onSubmit={handleInvite} className="flex gap-2 mb-4">
            <input
              type="email"
              placeholder="User email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 px-3 py-1.5 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="px-2 py-1.5 text-sm bg-bg border border-border rounded text-text"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <button
              type="submit"
              disabled={loading}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
            >
              <UserPlus size={14} />
            </button>
          </form>

          {error && <p className="text-xs text-danger mb-3">{error}</p>}

          {/* Member list */}
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {members.length === 0 && (
              <p className="text-xs text-text-muted">No members yet</p>
            )}
            {members.map((m) => (
              <div key={m.user_id} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded bg-bg">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text truncate">
                    {m.display_name || m.email}
                  </p>
                  {m.display_name && (
                    <p className="text-xs text-text-muted truncate">{m.email}</p>
                  )}
                </div>
                <select
                  value={m.role}
                  onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                  className="px-2 py-1 text-xs bg-surface border border-border rounded text-text"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
                <button
                  onClick={() => handleRemove(m.user_id)}
                  className="p-1 text-text-muted hover:text-danger"
                  title="Remove member"
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
