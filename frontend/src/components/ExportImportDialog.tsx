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
  const [cloudImportUrl, setCloudImportUrl] = useState("");
  const [cloudExportBusy, setCloudExportBusy] = useState<null | "json" | "csv" | "graphml">(null);
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

  const handleCloudExport = async (format: "json" | "csv" | "graphml") => {
    setCloudExportBusy(format);
    try {
      const { url } = await api.export.cloud(currentProject.id, format);
      if (!url) {
        toast.error("Cloud export failed: missing signed URL");
        return;
      }

      await navigator.clipboard.writeText(url);
      toast.success(`Cloud export ready (${format.toUpperCase()}). Signed URL copied.`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Cloud export failed: ${msg}`);
    } finally {
      setCloudExportBusy(null);
    }
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

  const handleImportFromCloudUrl = async () => {
    const raw = cloudImportUrl.trim();
    if (!raw) {
      toast.error("Provide a cloud export URL first");
      return;
    }
    setImporting(true);
    try {
      let url: URL;
      try {
        url = new URL(raw);
      } catch {
        toast.error("Invalid URL");
        return;
      }

      const res = await fetch(url.toString());
      if (!res.ok) {
        throw new Error(`Cloud URL fetch failed: ${res.status}`);
      }

      const blob = await res.blob();
      const pathname = url.pathname.toLowerCase();
      let filename = pathname.split("/").pop() || "cloud-import";
      if (!filename.includes(".")) {
        const ct = (blob.type || "").toLowerCase();
        if (ct.includes("json")) filename += ".json";
        else if (ct.includes("zip")) filename += ".csv";
        else if (ct.includes("xml")) filename += ".graphml";
      }

      const file = new File([blob], filename, { type: blob.type || "application/octet-stream" });
      await handleImport(file);
      setCloudImportUrl("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Cloud import failed: ${msg}`);
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
  const cloudBtnClass =
    "w-full flex items-center gap-2 px-3 py-2 rounded text-xs text-text hover:bg-surface-hover border border-border bg-surface/40";

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
              <button
                onClick={() => handleCloudExport("json")}
                className={cloudBtnClass}
                disabled={cloudExportBusy !== null}
              >
                <Upload size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">Save JSON to Cloud</p>
                  <p className="text-[10px] text-text-muted">
                    {cloudExportBusy === "json" ? "Preparing signed URL..." : "Upload to Supabase Storage and copy signed URL"}
                  </p>
                </div>
              </button>
              <button onClick={() => handleExport("csv")} className={btnClass}>
                <Download size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">CSV (ZIP)</p>
                  <p className="text-[10px] text-text-muted">Entities + edges as CSV files</p>
                </div>
              </button>
              <button
                onClick={() => handleCloudExport("csv")}
                className={cloudBtnClass}
                disabled={cloudExportBusy !== null}
              >
                <Upload size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">Save CSV to Cloud</p>
                  <p className="text-[10px] text-text-muted">
                    {cloudExportBusy === "csv" ? "Preparing signed URL..." : "Upload to Supabase Storage and copy signed URL"}
                  </p>
                </div>
              </button>
              <button onClick={() => handleExport("graphml")} className={btnClass}>
                <Download size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">GraphML</p>
                  <p className="text-[10px] text-text-muted">Compatible with Gephi, yEd</p>
                </div>
              </button>
              <button
                onClick={() => handleCloudExport("graphml")}
                className={cloudBtnClass}
                disabled={cloudExportBusy !== null}
              >
                <Upload size={14} className="text-accent" />
                <div className="text-left">
                  <p className="font-medium">Save GraphML to Cloud</p>
                  <p className="text-[10px] text-text-muted">
                    {cloudExportBusy === "graphml" ? "Preparing signed URL..." : "Upload to Supabase Storage and copy signed URL"}
                  </p>
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
              <div className="pt-2 border-t border-border/70">
                <p className="text-[10px] text-text-muted mb-2">Import from Cloud Signed URL</p>
                <div className="flex gap-2">
                  <input
                    type="url"
                    placeholder="https://...signed-download-url"
                    value={cloudImportUrl}
                    onChange={(e) => setCloudImportUrl(e.target.value)}
                    className="flex-1 px-2 py-1.5 text-xs bg-bg border border-border rounded text-text focus:outline-none focus:border-accent"
                  />
                  <button
                    onClick={handleImportFromCloudUrl}
                    disabled={importing}
                    className="px-3 py-1.5 text-xs bg-surface border border-border rounded text-text hover:bg-surface-hover disabled:opacity-50"
                  >
                    Load URL
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
