import { DesktopWorkspace } from "./DesktopWorkspace";
import { MobileWorkspace } from "./MobileWorkspace";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useIsMobile } from "../hooks/useIsMobile";

export function Layout() {
  useKeyboardShortcuts();
  const isMobile = useIsMobile();

  return isMobile ? <MobileWorkspace /> : <DesktopWorkspace />;
}
