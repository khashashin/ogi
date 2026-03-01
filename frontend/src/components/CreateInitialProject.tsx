import { useState } from "react";
import { useProjectStore } from "../stores/projectStore";
import { Loader2 } from "lucide-react";

export function CreateInitialProject() {
  const { createProject } = useProjectStore();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setError(null);
    setBusy(true);
    try {
      await createProject(name.trim(), description.trim(), isPublic);
    } catch (err) {
      setError(String(err));
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-center h-screen w-screen bg-bg">
      <div className="w-full max-w-md p-6 bg-surface border border-border rounded-lg shadow-lg">
        <h1 className="text-xl font-semibold text-text mb-2">Welcome to OpenGraph Intel!</h1>
        <p className="text-sm text-text-muted mb-6">
          To get started, please create your first project. Everything in OGI belongs to a project.
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-text">Project Name</label>
            <input
              type="text"
              placeholder="e.g. My Investigation"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-text">Description (Optional)</label>
            <textarea
              placeholder="Brief description of this project..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent resize-none"
            />
          </div>
          
          <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              className="accent-accent"
            />
            Make this project public (visible to everyone)
          </label>

          {error && <p className="text-xs text-danger">{error}</p>}

          <button
            type="submit"
            disabled={busy || !name.trim()}
            className="flex items-center justify-center gap-2 px-4 py-2 mt-2 text-sm bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
          >
            {busy ? <Loader2 size={16} className="animate-spin" /> : "Create Project"}
          </button>
        </form>
      </div>
    </div>
  );
}
