import { useEffect, useState } from "react";
import { ImageIcon, Save, Trash2, Upload, X } from "lucide-react";
import { ProtectedMediaImage } from "./ProtectedMediaImage";

interface ChangePersonImageDialogProps {
  open: boolean;
  currentImageUrl: string;
  projectId: string | null;
  entityId: string | null;
  entityLabel: string;
  onClose: () => void;
  onSave: (file: File) => Promise<void> | void;
  onRemove: () => Promise<void> | void;
}

export function ChangePersonImageDialog({
  open,
  currentImageUrl,
  projectId,
  entityId,
  entityLabel,
  onClose,
  onSave,
  onRemove,
}: ChangePersonImageDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState(currentImageUrl);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSelectedFile(null);
    setPreviewUrl(currentImageUrl);
    setSaving(false);
  }, [open, currentImageUrl]);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(currentImageUrl);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [selectedFile, currentImageUrl]);

  if (!open) return null;

  const handleSave = async () => {
    if (!selectedFile) return;
    setSaving(true);
    try {
      await onSave(selectedFile);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    setSaving(true);
    try {
      await onRemove();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-2xl rounded-xl border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-text">Change Person Image</h2>
            <p className="max-w-[26rem] truncate text-xs text-text-muted">{entityLabel}</p>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text">
            <X size={16} />
          </button>
        </div>

        <div className="grid gap-4 px-4 py-4 md:grid-cols-[220px_1fr]">
          <div className="rounded-xl border border-border bg-bg px-4 py-5">
            <div className="mb-3 text-xs uppercase tracking-[0.18em] text-text-muted">
              Preview
            </div>
            <div className="flex aspect-square items-center justify-center overflow-hidden rounded-full border border-border bg-surface">
              {previewUrl ? (
                selectedFile ? (
                  <img
                    src={previewUrl}
                    alt=""
                    className="h-full w-full object-cover"
                    onError={(event) => {
                      event.currentTarget.style.display = "none";
                    }}
                  />
                ) : (
                  <ProtectedMediaImage
                    projectId={projectId}
                    entityId={entityId}
                    src={previewUrl}
                    className="h-full w-full object-cover"
                  />
                )
              ) : (
                <ImageIcon size={36} className="text-text-muted" />
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-bg p-4">
            <div className="mb-2 block text-xs uppercase tracking-[0.18em] text-text-muted">
              Upload Image
            </div>
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-surface px-4 py-6 text-sm text-text hover:bg-surface-hover">
              <Upload size={16} />
              <span>{selectedFile ? selectedFile.name : "Choose image file"}</span>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFile(file);
                }}
              />
            </label>
            <p className="mt-2 text-xs text-text-muted">
              OGI stores Person images in Supabase Storage when available, otherwise it falls back to local uploaded media.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-border px-4 py-3">
          <button
            type="button"
            onClick={handleRemove}
            disabled={saving || !currentImageUrl}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-text-muted hover:text-text disabled:opacity-50"
          >
            <Trash2 size={14} />
            Remove Image
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border px-3 py-2 text-sm text-text-muted hover:text-text"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !selectedFile}
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm text-white hover:bg-accent-hover disabled:opacity-60"
            >
              <Save size={14} />
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
