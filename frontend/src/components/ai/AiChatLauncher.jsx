import { memo, useCallback, useEffect, useState } from "react";
import { MessageCircleMore } from "lucide-react";
import { authSession } from "../../services/api";
import Button from "../ui/Button";
import AiChatPanel from "./AiChatPanel";

const isMobileViewport = () => {
  if (typeof window === "undefined") return false;
  return window.matchMedia?.("(max-width: 767px)")?.matches ?? false;
};

const isMobileBottomNavVisible = () => {
  if (typeof document === "undefined" || !isMobileViewport()) return false;
  return document.documentElement.dataset.standalonePwa === "true";
};

function AiChatLauncher() {
  const user = authSession.getUser() || {};
  const actorType = String(user?.actor_type || "").toLowerCase();
  const isGlobalAccount =
    ["parent_account", "teacher_account"].includes(actorType) &&
    !user?.tenant_id;
  const [open, setOpen] = useState(false);
  const [hasBottomNav, setHasBottomNav] = useState(isMobileViewport);
  const openPanel = useCallback(() => setOpen(true), []);
  const closePanel = useCallback(() => setOpen(false), []);

  useEffect(() => {
    const updateDisplayMode = () => {
      setHasBottomNav(isMobileBottomNavVisible());
    };

    updateDisplayMode();
    const timer = window.setTimeout(updateDisplayMode, 0);
    window.addEventListener("resize", updateDisplayMode);
    window.addEventListener("orientationchange", updateDisplayMode);

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", updateDisplayMode);
      window.removeEventListener("orientationchange", updateDisplayMode);
    };
  }, []);

  if (isGlobalAccount) return null;

  return (
    <>
      <div className={`ai-chat-launcher pointer-events-none fixed z-50 flex justify-end ${hasBottomNav ? "ai-chat-launcher--with-bottom-nav" : ""}`}>
        <Button
          type="button"
          onClick={openPanel}
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
      <AiChatPanel open={open} onClose={closePanel} />
    </>
  );
}

export default memo(AiChatLauncher);
