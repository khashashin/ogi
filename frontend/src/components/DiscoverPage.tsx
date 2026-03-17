import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router";
import { Loader2, Search, Heart, User, FolderOpen } from "lucide-react";
import { api } from "../api/client";
import type { DiscoverProject } from "../api/client";
import { useAuthStore } from "../stores/authStore";

export function DiscoverPage() {
  const { user, authEnabled } = useAuthStore();
  const [projects, setProjects] = useState<DiscoverProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const fetchProjects = useCallback(async (query: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.discover.list(query || undefined);
      setProjects(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects("");
  }, [fetchProjects]);

  const handleSearchChange = (value: string) => {
    setSearch(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchProjects(value), 300);
  };

  const toggleBookmark = async (project: DiscoverProject) => {
    if (!authEnabled || !user) return;
    try {
      if (project.is_bookmarked) {
        await api.projects.unbookmark(project.id);
      } else {
        await api.projects.bookmark(project.id);
      }
      setProjects((prev) =>
        prev.map((p) =>
          p.id === project.id ? { ...p, is_bookmarked: !p.is_bookmarked } : p
        )
      );
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      {/* Top bar */}
      <header className="flex items-center h-12 px-4 bg-surface border-b border-border">
        <span className="text-sm font-semibold text-text mr-6">OGI</span>
        <nav className="flex items-center gap-4">
          <Link to="/" className="text-sm text-text-muted hover:text-text">
            My Projects
          </Link>
          <span className="text-sm text-accent font-medium">Discover</span>
        </nav>
        <div className="flex-1" />
        {authEnabled && user ? (
          <div
            className="flex items-center justify-center w-7 h-7 rounded-full bg-accent text-white text-[10px] font-semibold"
            title={user.email ?? "Profile"}
          >
            {((user.user_metadata?.display_name as string) ?? user.email ?? "")
              .slice(0, 2)
              .toUpperCase() || <User size={12} />}
          </div>
        ) : (
          <Link to="/login" className="text-sm text-accent hover:underline">
            Sign In
          </Link>
        )}
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <h1 className="text-xl font-semibold text-text mb-6">Discover Public Projects</h1>

        {/* Search */}
        <div className="relative mb-6">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm bg-surface border border-border rounded text-text focus:outline-none focus:border-accent"
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-accent" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center py-16 gap-3">
            <p className="text-sm text-danger">{error}</p>
            <button
              onClick={() => fetchProjects(search)}
              className="px-3 py-1.5 text-xs bg-accent text-white rounded hover:bg-accent-hover"
            >
              Retry
            </button>
          </div>
        ) : projects.length === 0 ? (
          <p className="text-sm text-text-muted text-center py-16">
            {search ? "No projects match your search." : "No public projects yet."}
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {projects.map((p) => (
              <div
                key={p.id}
                className="flex flex-col p-4 bg-surface border border-border rounded-lg hover:border-accent/50 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FolderOpen size={14} className="text-text-muted shrink-0" />
                    <span className="text-sm font-medium text-text truncate">{p.name}</span>
                  </div>
                  {authEnabled && user && (
                    <button
                      onClick={() => toggleBookmark(p)}
                      className={`p-1 shrink-0 ${p.is_bookmarked ? "text-red-400" : "text-text-muted hover:text-red-400"}`}
                      title={p.is_bookmarked ? "Remove bookmark" : "Bookmark"}
                    >
                      <Heart size={14} fill={p.is_bookmarked ? "currentColor" : "none"} />
                    </button>
                  )}
                </div>
                {p.description && (
                  <p className="text-xs text-text-muted mb-2 line-clamp-2">{p.description}</p>
                )}
                <div className="flex items-center justify-between mt-auto">
                  <span className="text-[10px] text-text-muted">
                    by {p.owner_name || "Anonymous"}
                  </span>
                  <Link
                    to={`/projects/${p.id}`}
                    className="text-xs text-accent hover:underline"
                  >
                    Open
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
