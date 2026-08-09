import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import Button from "./Button";
import { cn } from "../../utils/cn";

const MODAL_LOCKS_KEY = "__weaveModalScrollLocks";
const MODAL_LOCK_COUNT_KEY = "__weaveModalLockCount";
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

const getModalScrollTarget = () =>
  document.querySelector('[data-guide-page="true"]') ||
  document.getElementById("dashboard-scroll-viewport") ||
  document.body;

const readVisualViewportRect = () => {
  if (typeof window === "undefined" || !window.visualViewport) return null;

  const height = Math.max(0, Math.round(window.visualViewport.height || 0));
  if (!height) return null;

  return {
    top: Math.max(0, Math.round(window.visualViewport.offsetTop || 0)),
    height,
  };
};

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
  const panelRef = useRef(null);
  const previouslyFocusedRef = useRef(null);
  const [visualViewportRect, setVisualViewportRect] = useState(
    readVisualViewportRect,
  );

  useEffect(() => {
    if (!open) return undefined;
    return acquireModalScrollLock();
  }, [open]);

  useLayoutEffect(() => {
    if (!open || typeof window === "undefined") return undefined;

    const visualViewport = window.visualViewport;
    let frameId = 0;

    const syncVisualViewport = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(() => {
        const next = readVisualViewportRect();
        setVisualViewportRect((current) => {
          if (
            current?.top === next?.top
            && current?.height === next?.height
          ) {
            return current;
          }
          return next;
        });
      });
    };

    syncVisualViewport();
    visualViewport?.addEventListener("resize", syncVisualViewport);
    visualViewport?.addEventListener("scroll", syncVisualViewport);
    window.addEventListener("resize", syncVisualViewport);

    return () => {
      window.cancelAnimationFrame(frameId);
      visualViewport?.removeEventListener("resize", syncVisualViewport);
      visualViewport?.removeEventListener("scroll", syncVisualViewport);
      window.removeEventListener("resize", syncVisualViewport);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;

    previouslyFocusedRef.current = document.activeElement;
    const panel = panelRef.current;
    const focusTarget = panel?.querySelector(FOCUSABLE_SELECTOR) || panel;
    focusTarget?.focus({ preventScroll: true });

    return () => {
      const previous = previouslyFocusedRef.current;
      if (previous instanceof HTMLElement && document.contains(previous)) {
        previous.focus({ preventScroll: true });
      }
      previouslyFocusedRef.current = null;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape" && closeOnOverlay && onClose) {
        onClose();
        return;
      }

      if (event.key !== "Tab") return;

      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll(FOCUSABLE_SELECTOR)).filter(
        (element) => element instanceof HTMLElement && !element.hidden,
      );

      if (!focusable.length) {
        event.preventDefault();
        panel.focus({ preventScroll: true });
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || !panel.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeOnOverlay, onClose, open]);

  if (!open) return null;

  const handleOverlayClick = () => {
    if (closeOnOverlay && onClose) onClose();
  };

  const visualViewportStyle = visualViewportRect
    ? {
        top: `${visualViewportRect.top}px`,
        height: `${visualViewportRect.height}px`,
      }
    : undefined;

  return (
    <div
      data-modal-overlay="true"
      data-modal-placement={placement}
      data-modal-visual-viewport="true"
      className="fixed inset-x-0 top-0 z-[100] flex h-[100dvh] min-h-0 items-center justify-center overflow-hidden bg-slate-950/35 px-3 py-3 backdrop-blur-sm sm:px-4 sm:py-6"
      style={visualViewportStyle}
      onClick={handleOverlayClick}
    >
      <div
        ref={panelRef}
        data-modal-panel="true"
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        className={cn(
          "flex min-h-0 max-h-full w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-premium animate-fadein",
          className,
        )}
        onClick={(event) => event.stopPropagation()}
      >
        <div
          data-modal-header="true"
          className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-4"
        >
          <div className="min-w-0">
            <h2 className="text-lg font-semibold">{title}</h2>
            {description && (
              <p className="mt-1 text-sm text-text-muted">{description}</p>
            )}
          </div>
          {showClose && onClose && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onClose}
              aria-label="Close modal"
              className="shrink-0"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div
          data-modal-scroll-container="true"
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-5 [-webkit-overflow-scrolling:touch]"
        >
          {children}
        </div>
        {footer ? (
          <div
            data-modal-footer="true"
            className="shrink-0 border-t border-border bg-surface px-5 py-4"
          >
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default Modal;
