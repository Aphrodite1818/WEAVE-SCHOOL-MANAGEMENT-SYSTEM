import { useState } from "react";
import { MessageCircleMore } from "lucide-react";
import Button from "../ui/Button";
import AiChatPanel from "./AiChatPanel";

function AiChatLauncher() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="ai-chat-launcher pointer-events-none fixed z-40 flex justify-end">
        <Button
          type="button"
          onClick={() => setOpen(true)}
          className="pointer-events-auto rounded-full px-3 py-2 text-xs shadow-premium sm:px-4 sm:text-sm"
        >
          <MessageCircleMore className="h-4 w-4 shrink-0" />
          <span className="hidden xs:inline sm:inline">AI Chat</span>
          <span className="xs:hidden sm:hidden">AI</span>
        </Button>
      </div>
      <AiChatPanel open={open} onClose={() => setOpen(false)} />
    </>
  );
}

export default AiChatLauncher;
