import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "../../utils/cn";

function Dropdown({
  trigger,
  children,
  align = "right",
  className = "",
  open: openProp,
  onOpenChange,
}) {
  const isControlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = isControlled ? openProp : internalOpen;
  const ref = useRef(null);

  const setOpen = useCallback(
    (nextOrUpdater) => {
      if (!isControlled) {
        setInternalOpen((current) => {
          const next =
            typeof nextOrUpdater === "function"
              ? nextOrUpdater(current)
              : nextOrUpdater;
          onOpenChange?.(next);
          return next;
        });
        return;
      }

      const next =
        typeof nextOrUpdater === "function"
          ? nextOrUpdater(openProp)
          : nextOrUpdater;
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange, openProp]
  );

  useEffect(() => {
    if (!open) return undefined;

    const handlePointerDown = (event) => {
      if (!ref.current?.contains(event.target)) setOpen(false);
    };

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, [open, setOpen]);

  return (
    <div ref={ref} className="relative">
      <div onClick={() => setOpen((current) => !current)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            "absolute z-40 mt-2 min-w-56 rounded-2xl border border-border bg-surface p-2 shadow-premium animate-fadein",
            align === "right" ? "right-0" : "left-0",
            className
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export default Dropdown;
