import { Link } from "react-router";
import { useCookieConsentStore } from "../stores/cookieConsentStore";

export function CookieConsentBanner() {
  const { showBanner, acceptAll, rejectAll } = useCookieConsentStore();

  if (!showBanner) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-surface border-t border-border animate-fade-in">
      <div className="max-w-4xl mx-auto px-4 py-4 flex flex-col sm:flex-row items-center gap-4">
        <p className="text-sm text-text-secondary flex-1 text-center sm:text-left">
          We use cookies to analyze site usage and improve your experience.
          See our{" "}
          <Link to="/privacy" className="text-accent underline hover:text-accent/80">
            Privacy Policy
          </Link>{" "}
          for details.
        </p>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={rejectAll}
            className="px-4 py-2 text-sm font-medium rounded border border-border text-text bg-surface hover:bg-bg transition-colors cursor-pointer"
          >
            Reject
          </button>
          <button
            onClick={acceptAll}
            className="px-4 py-2 text-sm font-medium rounded border border-border text-text bg-surface hover:bg-bg transition-colors cursor-pointer"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
