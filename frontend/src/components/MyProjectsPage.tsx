import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router";
import { Loader2, Plus, Trash2, Lock, Unlock, User, FolderOpen, LogOut } from "lucide-react";
import { api } from "../api/client";
import type { MyProjectItem } from "../api/client";
import { useAuthStore } from "../stores/authStore";
import { useProjectStore } from "../stores/projectStore";
import { ProfileDialog } from "./ProfileDialog";
import { ApiKeySettings } from "./ApiKeySettings";
import { PluginManager } from "./PluginManager";

export function MyProjectsPage() {
  const navigate = useNavigate();
  const { user, authEnabled } = useAuthStore();
  const { deleteProject } = useProjectStore();
  const [projects, setProjects] = useState<MyProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPublic, setNewPublic] = useState(false);
  const [creating, setCreating] = useState(false);

  const [showProfile, setShowProfile] = useState(false);
  const [showApiKeys, setShowApiKeys] = useState(false);
  const [showPlugins, setShowPlugins] = useState(false);

  const fetchMyProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.projects.my();
      setProjects(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMyProjects();
  }, []);

  const owned = projects.filter((p) => p.source === "owned");
  const shared = projects.filter((p) => p.source === "member");
  const bookmarked = projects.filter((p) => p.source === "bookmarked");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const project = await api.projects.create({
        name: newName.trim(),
        description: newDesc.trim(),
        is_public: newPublic,
      });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(String(err));
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this project? This action cannot be undone.")) return;
    try {
      await deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(String(err));
    }
  };

  const handleUnbookmark = async (id: string) => {
    try {
      await api.projects.unbookmark(id);
      setProjects((prev) => prev.filter((p) => !(p.id === id && p.source === "bookmarked")));
    } catch (err) {
      setError(String(err));
    }
  };

  const handleLeave = async (id: string) => {
    if (!user) return;
    if (!window.confirm("Are you sure you want to leave this project?")) return;
    try {
      await api.members.remove(id, user.id);
      setProjects((prev) => prev.filter((p) => !(p.id === id && p.source === "member")));
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      {/* Top bar */}
      <header className="flex items-center h-12 px-4 bg-surface border-b border-border">
        <span className="text-sm font-semibold text-text mr-6">OGI</span>
        <nav className="flex items-center gap-4">
          <span className="text-sm text-accent font-medium">My Projects</span>
          <Link to="/discover" className="text-sm text-text-muted hover:text-text">
            Discover
          </Link>
        </nav>
        <div className="flex-1" />
        {authEnabled && user ? (
          <button
            onClick={() => setShowProfile(true)}
            className="flex items-center justify-center w-7 h-7 rounded-full bg-accent text-white text-[10px] font-semibold hover:opacity-80"
            title={user.email ?? "Profile & Settings"}
          >
            {((user.user_metadata?.display_name as string) ?? user.email ?? "")
              .slice(0, 2)
              .toUpperCase() || <User size={12} />}
          </button>
        ) : (
          <Link to="/login" className="text-sm text-accent hover:underline">
            Sign In
          </Link>
        )}
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-xl font-semibold text-text">My Projects</h1>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-accent text-white rounded hover:bg-accent-hover"
          >
            <Plus size={14} />
            New Project
          </button>
        </div>

        {/* Create project form */}
        {showCreate && (
          <form
            onSubmit={handleCreate}
            className="mb-8 p-4 bg-surface border border-border rounded-lg"
          >
            <div className="flex flex-col gap-3">
              <input
                type="text"
                placeholder="Project name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                autoFocus
                className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
              />
              <textarea
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                rows={2}
                className="px-3 py-2 text-sm bg-bg border border-border rounded text-text focus:outline-none focus:border-accent resize-none"
              />
              <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
                <input
                  type="checkbox"
                  checked={newPublic}
                  onChange={(e) => setNewPublic(e.target.checked)}
                  className="accent-accent"
                />
                Make public
              </label>
              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-accent text-white rounded hover:bg-accent-hover disabled:opacity-50"
                >
                  {creating && <Loader2 size={14} className="animate-spin" />}
                  Create
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-3 py-1.5 text-sm text-text-muted hover:text-text"
                >
                  Cancel
                </button>
              </div>
            </div>
          </form>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center py-16 gap-3">
            <p className="text-sm text-danger">{error}</p>
            <button
              onClick={fetchMyProjects}
              className="px-3 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            <ProjectSection
              title="Owned"
              projects={owned}
              onOpen={(id) => navigate(`/projects/${id}`)}
              onDelete={handleDelete}
              showDelete
            />
            <ProjectSection
              title="Shared with me"
              projects={shared}
              onOpen={(id) => navigate(`/projects/${id}`)}
              onDelete={handleLeave}
              showDelete
            />
            <ProjectSection
              title="Bookmarked"
              projects={bookmarked}
              onOpen={(id) => navigate(`/projects/${id}`)}
              onDelete={handleUnbookmark}
              showDelete
            />
          </>
        )}
      </div>

      <ProfileDialog
        open={showProfile}
        onClose={() => setShowProfile(false)}
        onOpenApiKeys={() => setShowApiKeys(true)}
        onOpenPlugins={() => setShowPlugins(true)}
      />
      <ApiKeySettings
        open={showApiKeys}
        onClose={() => setShowApiKeys(false)}
      />
      <PluginManager
        open={showPlugins}
        onClose={() => setShowPlugins(false)}
      />
    </div>
  );
}

interface ProjectSectionProps {
  title: string;
  projects: MyProjectItem[];
  onOpen: (id: string) => void;
  onDelete?: (id: string) => void;
  showDelete?: boolean;
}

function ProjectSection({ title, projects, onOpen, onDelete, showDelete }: ProjectSectionProps) {
  if (projects.length === 0) {
    return (
      <div className="mb-8">
        <h2 className="text-sm font-medium text-text-muted mb-3">{title}</h2>
        <p className="text-xs text-text-muted py-4 text-center border border-dashed border-border rounded">
          No projects
        </p>
      </div>
    );
  }

  return (
    <div className="mb-8">
      <h2 className="text-sm font-medium text-text-muted mb-3">{title}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {projects.map((p) => (
          <div
            key={p.id}
            className="group flex flex-col p-4 bg-surface border border-border rounded-lg hover:border-accent/50 cursor-pointer transition-colors"
            onClick={() => onOpen(p.id)}
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <FolderOpen size={14} className="text-text-muted" />
                <span className="text-sm font-medium text-text truncate">{p.name}</span>
              </div>
              <div className="flex items-center gap-1">
                {title !== "Bookmarked" && (
                  p.is_public ? (
                    <Unlock size={12} className="text-green-400" />
                  ) : (
                    <Lock size={12} className="text-text-muted" />
                  )
                )}
                {showDelete && onDelete && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(p.id);
                    }}
                    className="p-1 text-text-muted hover:text-danger opacity-0 group-hover:opacity-100 transition-opacity"
                    title={title === "Bookmarked" ? "Remove bookmark" : title === "Shared with me" ? "Leave project" : "Delete project"}
                  >
                    {title === "Shared with me" ? <LogOut size={12} /> : <Trash2 size={12} />}
                  </button>
                )}
              </div>
            </div>
            {p.description && (
              <p className="text-xs text-text-muted mb-2 line-clamp-2">{p.description}</p>
            )}
            <div className="flex items-center gap-2 mt-auto">
              <span className="text-[10px] px-1.5 py-0.5 bg-bg rounded text-text-muted">
                {p.role}
              </span>
              <span className="text-[10px] text-text-muted ml-auto">
                {new Date(p.updated_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
