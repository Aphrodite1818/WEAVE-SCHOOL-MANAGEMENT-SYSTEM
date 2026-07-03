import { useEffect, useState } from "react";
import { MessageCircleMore } from "lucide-react";
import Button from "../ui/Button";
import AiChatPanel from "./AiChatPanel";

const isStandaloneDisplay = () => {
  if (typeof window === "undefined") return false;
  const standaloneMedia = window.matchMedia?.("(display-mode: standalone)")?.matches;
  const iosStandalone = window.navigator?.standalone === true;
  return Boolean(standaloneMedia || iosStandalone);
};

function AiChatLauncher() {
  const [open, setOpen] = useState(false);
  const [isInstalledApp, setIsInstalledApp] = useState(isStandaloneDisplay);

  useEffect(() => {
    const mediaQuery = window.matchMedia?.("(display-mode: standalone)");
    const updateDisplayMode = () => setIsInstalledApp(isStandaloneDisplay());

    updateDisplayMode();
    mediaQuery?.addEventListener?.("change", updateDisplayMode);

    return () => {
      mediaQuery?.removeEventListener?.("change", updateDisplayMode);
    };
  }, []);

  return (
    <>
      <div className={`ai-chat-launcher pointer-events-none fixed z-50 flex justify-end ${isInstalledApp ? "ai-chat-launcher--installed" : ""}`}>
        <Button
          type="button"
          onClick={() => setOpen(true)}
          className={`pointer-events-auto rounded-full shadow-premium ${isInstalledApp ? "h-12 w-12 px-0" : "px-3 py-2 text-xs sm:px-4 sm:text-sm"}`}
          aria-label="Open AI chat"
        >
          <MessageCircleMore className="h-4 w-4 shrink-0" />
          {!isInstalledApp && (
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
