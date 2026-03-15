import { useState } from "react";
import { Download, Globe, GlobeLock, Keyboard, Users } from "lucide-react";

import { ExportImportDialog } from "./ExportImportDialog";
import { KeyboardShortcutsDialog } from "./KeyboardShortcutsDialog";
import { ShareDialog } from "./ShareDialog";
import { useProjectStore } from "../stores/projectStore";
import { useAuthStore } from "../stores/authStore";
import { useIsViewer } from "../hooks/useIsViewer";

type RightToolbarProps = {
  orientation?: "vertical" | "horizontal";
};

export function RightToolbar({ orientation = "vertical" }: RightToolbarProps) {
  const { currentProject, updateProject } = useProjectStore();
  const { user } = useAuthStore();
  const isViewer = useIsViewer();
  const [showExportImport, setShowExportImport] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showShare, setShowShare] = useState(false);

  const canManagePrivacy =
    Boolean(currentProject) &&
    (!currentProject?.owner_id || currentProject.owner_id === user?.id) &&
    !isViewer;

  const handleTogglePrivacy = async () => {
    if (!currentProject) return;
    try {
      await updateProject(currentProject.id, { is_public: !currentProject.is_public });
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <>
      <div
        className={
          orientation === "horizontal"
            ? "flex w-full items-center justify-start gap-1 bg-surface px-2 py-2"
            : "flex h-full w-10 flex-col items-center gap-1 bg-surface px-1 py-2"
        }
      >
        <button
          onClick={() => setShowExportImport(true)}
          className="p-2 text-text-muted hover:text-text hover:bg-surface-hover rounded"
          title="Export / Import"
        >
          <Download size={14} />
        </button>

        <button
          onClick={() => setShowShortcuts(true)}
          className="p-2 text-text-muted hover:text-text hover:bg-surface-hover rounded"
          title="Keyboard shortcuts"
        >
          <Keyboard size={14} />
        </button>

        {canManagePrivacy && (
          <>
            <button
              onClick={() => setShowShare(true)}
              className="p-2 text-text-muted hover:text-text hover:bg-surface-hover rounded"
              title="Share Project"
            >
              <Users size={14} />
            </button>

            <button
              onClick={handleTogglePrivacy}
              className={`p-2 rounded hover:bg-surface-hover ${
                currentProject?.is_public ? "text-green-400" : "text-text-muted hover:text-text"
              }`}
              title={
                currentProject?.is_public
                  ? "Public Project (Click to make Private)"
                  : "Private Project (Click to make Public)"
              }
            >
              {currentProject?.is_public ? <Globe size={14} /> : <GlobeLock size={14} />}
            </button>
          </>
        )}
      </div>

      <ExportImportDialog
        open={showExportImport}
        onClose={() => setShowExportImport(false)}
      />
      <KeyboardShortcutsDialog
        open={showShortcuts}
        onClose={() => setShowShortcuts(false)}
      />
      {currentProject && (
        <ShareDialog
          open={showShare}
          onClose={() => setShowShare(false)}
          projectId={currentProject.id}
        />
      )}
    </>
  );
}
