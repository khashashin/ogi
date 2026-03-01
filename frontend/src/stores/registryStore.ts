import { create } from "zustand";
import { api } from "../api/client";
import type {
  RegistryTransform,
  RegistryIndex,
  UpdateAvailable,
  PluginInfoV2,
} from "../types/registry";

interface RegistryState {
  // Data
  index: RegistryIndex | null;
  installedPlugins: PluginInfoV2[];
  searchResults: RegistryTransform[];
  updates: UpdateAvailable[];

  // UI state
  loading: boolean;
  installing: string | null;
  removing: string | null;
  error: string | null;
  searchQuery: string;
  selectedCategory: string | null;
  selectedTier: string | null;
  activeTab: "installed" | "browse" | "updates";

  // Actions
  fetchIndex: () => Promise<void>;
  fetchInstalledPlugins: () => Promise<void>;
  searchTransforms: (query: string, category?: string, tier?: string) => Promise<void>;
  installTransform: (slug: string) => Promise<void>;
  removeTransform: (slug: string) => Promise<void>;
  updateTransform: (slug: string) => Promise<void>;
  checkUpdates: () => Promise<void>;
  setSearchQuery: (query: string) => void;
  setSelectedCategory: (category: string | null) => void;
  setSelectedTier: (tier: string | null) => void;
  setActiveTab: (tab: "installed" | "browse" | "updates") => void;
  clearError: () => void;
}

export const useRegistryStore = create<RegistryState>((set, get) => ({
  index: null,
  installedPlugins: [],
  searchResults: [],
  updates: [],
  loading: false,
  installing: null,
  removing: null,
  error: null,
  searchQuery: "",
  selectedCategory: null,
  selectedTier: null,
  activeTab: "browse",

  fetchIndex: async () => {
    set({ loading: true, error: null });
    try {
      const index = await api.registry.index();
      set({ index, loading: false });
    } catch (err) {
      set({ error: (err as Error).message, loading: false });
    }
  },

  fetchInstalledPlugins: async () => {
    try {
      const plugins = await api.plugins.list() as PluginInfoV2[];
      set({ installedPlugins: plugins });
    } catch {
      set({ installedPlugins: [] });
    }
  },

  searchTransforms: async (query: string, category?: string, tier?: string) => {
    set({ loading: true, error: null, searchQuery: query });
    try {
      const results = await api.registry.search(query, category, tier);
      set({ searchResults: results, loading: false });
    } catch (err) {
      set({ error: (err as Error).message, loading: false });
    }
  },

  installTransform: async (slug: string) => {
    set({ installing: slug, error: null });
    try {
      await api.registry.install(slug);
      // Refresh installed list and search results
      await get().fetchInstalledPlugins();
      const { searchQuery, selectedCategory, selectedTier } = get();
      await get().searchTransforms(searchQuery, selectedCategory ?? undefined, selectedTier ?? undefined);
      set({ installing: null });
    } catch (err) {
      set({ error: (err as Error).message, installing: null });
    }
  },

  removeTransform: async (slug: string) => {
    set({ removing: slug, error: null });
    try {
      await api.registry.remove(slug);
      await get().fetchInstalledPlugins();
      set({ removing: null });
    } catch (err) {
      set({ error: (err as Error).message, removing: null });
    }
  },

  updateTransform: async (slug: string) => {
    set({ installing: slug, error: null });
    try {
      await api.registry.update(slug);
      await get().fetchInstalledPlugins();
      await get().checkUpdates();
      set({ installing: null });
    } catch (err) {
      set({ error: (err as Error).message, installing: null });
    }
  },

  checkUpdates: async () => {
    try {
      const updates = await api.registry.checkUpdates();
      set({ updates });
    } catch {
      set({ updates: [] });
    }
  },

  setSearchQuery: (query: string) => set({ searchQuery: query }),
  setSelectedCategory: (category: string | null) => set({ selectedCategory: category }),
  setSelectedTier: (tier: string | null) => set({ selectedTier: tier }),
  setActiveTab: (tab: "installed" | "browse" | "updates") => set({ activeTab: tab }),
  clearError: () => set({ error: null }),
}));
