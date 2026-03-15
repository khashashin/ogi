import { useEffect, useState } from "react";

const MOBILE_QUERY = "(max-width: 1023px)";

export function useIsMobile() {
  const getMatches = () =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(MOBILE_QUERY).matches;

  const [isMobile, setIsMobile] = useState(getMatches);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const media = window.matchMedia(MOBILE_QUERY);
    const onChange = () => setIsMobile(media.matches);

    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return isMobile;
}
