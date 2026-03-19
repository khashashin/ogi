import { AlertTriangle } from "lucide-react";
import { useBetaNoticeStore } from "../stores/betaNoticeStore";

export function BetaNoticeDialog() {
  const { showNotice, dismiss } = useBetaNoticeStore();

  if (!showNotice) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-96 animate-fade-in">
        <div className="flex flex-col items-center gap-4 p-6">
          <AlertTriangle size={32} className="text-warning" />
          <h2 className="text-base font-semibold text-text">Beta Software</h2>
          <p className="text-sm text-text-muted text-center leading-relaxed">
            OpenGraph Intel is currently in <strong className="text-text">beta</strong>.
            Features may change, break, or be removed without notice. Your data,
            including projects and graphs, may be <strong className="text-text">completely
            wiped</strong> at any time without prior announcement.
          </p>
          <button
            onClick={dismiss}
            className="w-full mt-2 px-4 py-2 text-sm font-medium rounded bg-accent hover:bg-accent-hover text-white transition-colors"
          >
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
}
