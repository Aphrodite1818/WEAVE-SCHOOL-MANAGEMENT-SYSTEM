import { useEffect } from "react";
import { X } from "lucide-react";
import Button from "./Button";
import { cn } from "../../utils/cn";

const MODAL_LOCKS_KEY = "__weaveModalScrollLocks";
const MODAL_LOCK_COUNT_KEY = "__weaveModalLockCount";

const getModalScrollTarget = () =>
  document.querySelector('[data-guide-page="true"]') ||
  document.getElementById("dashboard-scroll-viewport") ||
  document.body;

const acquireModalScrollLock = () => {
  const target = getModalScrollTarget();
  if (!target) return () => {};

  const locks = window[MODAL_LOCKS_KEY] || new Map();
  window[MODAL_LOCKS_KEY] = locks;

  const existing = locks.get(target);
  const lock = existing || {
    count: 0,
    overflow: target.style.overflow,
    overscrollBehavior: target.style.overscrollBehavior,
  };

  lock.count += 1;
  locks.set(target, lock);
  target.style.overflow = "hidden";
  target.style.overscrollBehavior = "none";

  window[MODAL_LOCK_COUNT_KEY] =
    Number(window[MODAL_LOCK_COUNT_KEY] || 0) + 1;
  document.documentElement.dataset.modalOpen = "true";

  let released = false;
  return () => {
    if (released) return;
    released = true;

    const current = locks.get(target);
    if (current) {
      current.count -= 1;
      if (current.count <= 0) {
        target.style.overflow = current.overflow;
        target.style.overscrollBehavior = current.overscrollBehavior;
        locks.delete(target);
      } else {
        locks.set(target, current);
      }
    }

    window[MODAL_LOCK_COUNT_KEY] = Math.max(
      0,
      Number(window[MODAL_LOCK_COUNT_KEY] || 0) - 1,
    );
    if (window[MODAL_LOCK_COUNT_KEY] === 0) {
      delete document.documentElement.dataset.modalOpen;
    }
  };
};

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
  placement = "responsive",
}) {
  useEffect(() => {
    if (!open) return undefined;
    return acquireModalScrollLock();
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
      data-modal-overlay="true"
      className={cn(
        "fixed inset-0 z-50 flex justify-center bg-slate-950/35 px-4 py-6 backdrop-blur-sm",
        placement === "center" ? "items-center" : "items-end sm:items-center",
      )}
      onClick={handleOverlayClick}
    >
      <div
        className={cn(
          "max-h-[calc(100dvh-2rem)] w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-premium animate-fadein",
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
        <div
          data-modal-scroll-container="true"
          className="max-h-[min(60dvh,calc(100dvh-11rem))] overflow-y-auto overscroll-contain px-5 py-5 [-webkit-overflow-scrolling:touch]"
        >
          {children}
        </div>
        {footer && <div className="border-t border-border px-5 py-4">{footer}</div>}
      </div>
    </div>
  );
}

export default Modal;
