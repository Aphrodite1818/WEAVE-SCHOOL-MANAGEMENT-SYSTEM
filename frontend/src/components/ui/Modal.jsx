import { useEffect } from "react";
import { X } from "lucide-react";
import Button from "./Button";
import { cn } from "../../utils/cn";

function Modal({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  className = "",
  closeOnOverlay = true,
  showClose = true,
}) {
  useEffect(() => {
    if (!open) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open || !onClose) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape" && closeOnOverlay) onClose();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeOnOverlay, onClose, open]);

  if (!open) return null;

  const handleOverlayClick = () => {
    if (closeOnOverlay && onClose) onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/35 px-4 py-6 backdrop-blur-sm sm:items-center"
      onClick={handleOverlayClick}
    >
      <div
        className={cn(
          "max-h-[90vh] w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-premium animate-fadein",
          className
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {description && (
              <p className="mt-1 text-sm text-text-muted">{description}</p>
            )}
          </div>
          {showClose && onClose && (
            <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Close modal">
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div className="max-h-[60vh] overflow-y-auto px-5 py-5">{children}</div>
        {footer && <div className="border-t border-border px-5 py-4">{footer}</div>}
      </div>
    </div>
  );
}

export default Modal;
