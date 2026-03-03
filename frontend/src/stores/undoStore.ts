import { create } from "zustand";
import type { Entity } from "../types/entity";
import type { Edge } from "../types/edge";

/** Discriminated union for all undoable actions. */
type UndoAction =
  | { type: "add_entity"; entity: Entity; nodeAttrs: Record<string, unknown> }
  | { type: "remove_entity"; entity: Entity; nodeAttrs: Record<string, unknown>; edges: Edge[]; edgeAttrs: Record<string, Record<string, unknown>> }
  | { type: "add_edge"; edge: Edge; edgeAttrs: Record<string, unknown> }
  | { type: "remove_edge"; edge: Edge; edgeAttrs: Record<string, unknown> }
  | { type: "batch"; actions: UndoAction[] };

const MAX_HISTORY = 50;

interface UndoState {
  undoStack: UndoAction[];
  redoStack: UndoAction[];
  push: (action: UndoAction) => void;
  undo: () => UndoAction | undefined;
  redo: () => UndoAction | undefined;
  canUndo: () => boolean;
  canRedo: () => boolean;
  clear: () => void;
}

export type { UndoAction };

export const useUndoStore = create<UndoState>((set, get) => ({
  undoStack: [],
  redoStack: [],

  push: (action) => {
    set((state) => ({
      undoStack: [...state.undoStack.slice(-(MAX_HISTORY - 1)), action],
      redoStack: [],
    }));
  },

  undo: () => {
    const { undoStack } = get();
    if (undoStack.length === 0) return undefined;
    const action = undoStack[undoStack.length - 1];
    set((state) => ({
      undoStack: state.undoStack.slice(0, -1),
      redoStack: [...state.redoStack, action],
    }));
    return action;
  },

  redo: () => {
    const { redoStack } = get();
    if (redoStack.length === 0) return undefined;
    const action = redoStack[redoStack.length - 1];
    set((state) => ({
      redoStack: state.redoStack.slice(0, -1),
      undoStack: [...state.undoStack, action],
    }));
    return action;
  },

  canUndo: () => get().undoStack.length > 0,
  canRedo: () => get().redoStack.length > 0,

  clear: () => set({ undoStack: [], redoStack: [] }),
}));
