import { useState, useRef } from "react";
import { Download, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { useProjectStore } from "../stores/projectStore";
import { useGraphStore } from "../stores/graphStore";
import { api } from "../api/client";
import { useIsViewer } from "../hooks/useIsViewer";

interface ExportImportDialogProps {
  open: boolean;
  onClose: () => void;
}

export function ExportImportDialog({ open, onClose }: ExportImportDialogProps) {
  const [tab, setTab] = useState<"export" | "import">("export");
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { currentProject } = useProjectStore();
  const { loadGraph } = useGraphStore();
  const isViewer = useIsViewer();

  if (!open || !currentProject) return null;

  const handleExport = (format: "json" | "csv" | "graphml") => {
    const url =
      format === "json"
        ? api.export.json(currentProject.id)
        : format === "csv"
          ? api.export.csv(currentProject.id)
          : api.export.graphml(currentProject.id);

    // Trigger download
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    a.click();
    toast.success(`Exporting as ${format.toUpperCase()}...`);
  };

  const handleImport = async (file: File) => {
    setImporting(true);
    try {
      const ext = file.name.split(".").pop()?.toLowerCase();
      let summary;
      if (ext === "json" || file.name.endsWith(".ogi.json")) {
        summary = await api.import.json(currentProject.id, file);
      } else if (ext === "csv") {
        summary = await api.import.csv(currentProject.id, file);
      } else if (ext === "graphml") {
        summary = await api.import.graphml(currentProject.id, file);
      } else if (ext === "mtgx") {
        summary = await api.import.maltego(currentProject.id, file);
      } else {
        toast.error("Unsupported file format. Use .json, .csv, .graphml, or .mtgx");
        setImporting(false);
        return;
      }

      toast.success(
        `Imported: ${summary.entities_added} added, ${summary.entities_merged} merged, ${summary.edges_added} edges`
      );
      // Reload graph to show imported data
      await loadGraph(currentProject.id);
      onClose();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Import failed: ${msg}`);
    } finally {
      setImporting(false);
    }
  };

  const tabClass = (t: string) =>
    `px-3 py-1.5 text-xs rounded-t ${
      tab === t
        ? "bg-surface text-text border-t border-x border-border"
        : "text-text-muted hover:text-text"
    }`;

  const btnClass =
    "w-full flex items-center gap-2 px-3 py-2 rounded text-xs text-text hover:bg-surface-hover border border-border";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-bg border border-border rounded-lg shadow-xl w-[400px]">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold text-text">Export / Import</h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-hover text-text-muted"
          >
            <X size={14} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-4 pt-3">
          <button onClick={() => setTab("export")} className={tabClass("export")}>
            <Download size={12} className="inline mr-1" />
            Export
          </button>
          {!isViewer && (
            <button onClick={() => setTab("import")} className={tabClass("import")}>
              <Upload size={12} className="inline mr-1" />
              Import
            </button>
          )}
        </div>

        {/* Content */}
        <div className="p-4">
          {tab === "export" || isViewer ? (
            <div className="space-y-2">
              <p className="text-[10px] text-text-muted mb-3">
                Export all entities and edges from "{currentProject.name}"
              </p>
              <button onClick={() => handleExport("json")} className={btnClass}>
                <Download size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">OpenGraph Intel JSON</p>
                  <p className="text-[10px] text-text-muted">Full project data, re-importable</p>
                </div>
              </button>
              <button onClick={() => handleExport("csv")} className={btnClass}>
                <Download size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">CSV (ZIP)</p>
                  <p className="text-[10px] text-text-muted">Entities + edges as CSV files</p>
                </div>
              </button>
              <button onClick={() => handleExport("graphml")} className={btnClass}>
                <Download size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">GraphML</p>
                  <p className="text-[10px] text-text-muted">Compatible with Gephi, yEd</p>
                </div>
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-[10px] text-text-muted">
                Import entities and edges into "{currentProject.name}".
                Duplicates are automatically merged.
              </p>
              <div
                onClick={() => fileInputRef.current?.click()}
                className="flex flex-col items-center justify-center gap-2 p-6 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-accent transition-colors"
              >
                <Upload size={24} className="text-text-muted" />
                <p className="text-xs text-text-muted">
                  {importing ? "Importing..." : "Click to select a file (.json, .csv, .graphml, .mtgx)"}
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,.csv,.graphml,.mtgx"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleImport(file);
                  e.target.value = "";
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
