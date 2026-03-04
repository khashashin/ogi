import { X } from "lucide-react";

interface KeyboardShortcutsDialogProps {
  open: boolean;
  onClose: () => void;
}

const SHORTCUTS = [
  { category: "General", items: [
    { keys: ["Ctrl", "Z"], description: "Undo last action" },
    { keys: ["Ctrl", "Y"], description: "Redo last action" },
    { keys: ["Ctrl", "F"], description: "Search entities" },
    { keys: ["Esc"], description: "Deselect / close panels" },
  ]},
  { category: "Graph", items: [
    { keys: ["Del"], description: "Delete selected entity or edge" },
    { keys: ["+"], description: "Zoom in" },
    { keys: ["-"], description: "Zoom out" },
    { keys: ["0"], description: "Fit graph to screen" },
  ]},
  { category: "Search", items: [
    { keys: ["Enter"], description: "Next match" },
    { keys: ["Shift", "Enter"], description: "Previous match" },
  ]},
];

export function KeyboardShortcutsDialog({ open, onClose }: KeyboardShortcutsDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-lg shadow-xl w-96 max-h-[80vh] overflow-y-auto animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Keyboard Shortcuts</h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-text">
            <X size={14} />
          </button>
        </div>
        <div className="p-4 space-y-4">
          {SHORTCUTS.map((section) => (
            <div key={section.category}>
              <h3 className="text-[10px] uppercase tracking-wider text-text-muted mb-2">
                {section.category}
              </h3>
              <div className="space-y-1.5">
                {section.items.map((item) => (
                  <div key={item.description} className="flex items-center justify-between text-xs">
                    <span className="text-text-muted">{item.description}</span>
                    <div className="flex items-center gap-0.5">
                      {item.keys.map((key, i) => (
                        <span key={i}>
                          {i > 0 && <span className="text-text-muted mx-0.5">+</span>}
                          <kbd className="px-1.5 py-0.5 bg-bg border border-border rounded text-[10px] font-mono text-text">
                            {key}
                          </kbd>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
