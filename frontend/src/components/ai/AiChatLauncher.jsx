import { useEffect, useState } from "react";
import { MessageCircleMore } from "lucide-react";
import Button from "../ui/Button";
import AiChatPanel from "./AiChatPanel";

const isStandaloneDisplay = () => {
  if (typeof window === "undefined") return false;

  const standaloneMedia = window.matchMedia?.("(display-mode: standalone)")?.matches;
  const fullscreenMedia = window.matchMedia?.("(display-mode: fullscreen)")?.matches;
  const iosStandalone = window.navigator?.standalone === true;

  return Boolean(standaloneMedia || fullscreenMedia || iosStandalone);
};

const isMobileBottomNavVisible = () => {
  if (typeof document === "undefined") return false;
  return Boolean(document.querySelector('[data-mobile-bottom-nav="true"]'));
};

function AiChatLauncher() {
  const [open, setOpen] = useState(false);
  const [hasBottomNav, setHasBottomNav] = useState(() => isStandaloneDisplay() || isMobileBottomNavVisible());

  useEffect(() => {
    const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
    const fullscreenQuery = window.matchMedia?.("(display-mode: fullscreen)");
    const updateDisplayMode = () => {
      setHasBottomNav(isStandaloneDisplay() || isMobileBottomNavVisible());
    };

    updateDisplayMode();
    const timer = window.setTimeout(updateDisplayMode, 0);
    standaloneQuery?.addEventListener?.("change", updateDisplayMode);
    fullscreenQuery?.addEventListener?.("change", updateDisplayMode);
    window.addEventListener("resize", updateDisplayMode);
    window.addEventListener("orientationchange", updateDisplayMode);

    return () => {
      window.clearTimeout(timer);
      standaloneQuery?.removeEventListener?.("change", updateDisplayMode);
      fullscreenQuery?.removeEventListener?.("change", updateDisplayMode);
      window.removeEventListener("resize", updateDisplayMode);
      window.removeEventListener("orientationchange", updateDisplayMode);
    };
  }, []);

  return (
    <>
      <div className={`ai-chat-launcher pointer-events-none fixed z-50 flex justify-end ${hasBottomNav ? "ai-chat-launcher--with-bottom-nav" : ""}`}>
        <Button
          type="button"
          onClick={() => setOpen(true)}
          className={`pointer-events-auto rounded-full shadow-premium ${hasBottomNav ? "h-12 w-12 px-0" : "px-3 py-2 text-xs sm:px-4 sm:text-sm"}`}
          aria-label="Open AI chat"
        >
          <MessageCircleMore className="h-4 w-4 shrink-0" />
          {!hasBottomNav && (
            <>
              <span className="hidden xs:inline sm:inline">AI Chat</span>
              <span className="xs:hidden sm:hidden">AI</span>
            </>
          )}
        </Button>
      </div>
      <AiChatPanel open={open} onClose={() => setOpen(false)} />
    </>
  );
}

export default AiChatLauncher;
