import { useState } from "react";
import { MessageCircleMore } from "lucide-react";
import Button from "../ui/Button";
import AiChatPanel from "./AiChatPanel";

function AiChatLauncher() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="fixed bottom-[calc(5.85rem+env(safe-area-inset-bottom))] right-4 z-40 md:bottom-6 md:right-6">
        <Button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-full px-4 shadow-premium"
        >
          <MessageCircleMore className="h-4 w-4" />
          AI Chat
        </Button>
      </div>
      <AiChatPanel open={open} onClose={() => setOpen(false)} />
    </>
  );
}

export default AiChatLauncher;
