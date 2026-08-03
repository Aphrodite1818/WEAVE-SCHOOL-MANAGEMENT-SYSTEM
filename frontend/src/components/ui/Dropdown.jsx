import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "../../utils/cn";

function Dropdown({
  trigger,
  children,
  align = "right",
  className = "",
  open: openProp,
  onOpenChange,
  strategy = "fixed",
}) {
  const isControlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const [fixedPosition, setFixedPosition] = useState(null);
  const open = isControlled ? openProp : internalOpen;
  const ref = useRef(null);
  const menuRef = useRef(null);
  const isFixed = strategy === "fixed";

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

  const updateFixedPosition = useCallback(() => {
    if (!isFixed || !ref.current) return;

    const rect = ref.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const menuHeight = menuRef.current?.offsetHeight || 0;
    const gap = 8;
    const edgePadding = 8;
    const spaceBelow = viewportHeight - rect.bottom - edgePadding;
    const spaceAbove = rect.top - edgePadding;
    const shouldOpenUp = menuHeight > 0 && spaceBelow < menuHeight && spaceAbove > spaceBelow;
    const maxHeight = Math.max(
      160,
      Math.floor((shouldOpenUp ? spaceAbove : spaceBelow) - gap)
    );

    setFixedPosition({
      ...(shouldOpenUp
        ? { bottom: Math.max(edgePadding, viewportHeight - rect.top + gap) }
        : { top: rect.bottom + gap }),
      maxHeight,
      ...(align === "right"
        ? { right: Math.max(edgePadding, viewportWidth - rect.right) }
        : { left: Math.max(edgePadding, rect.left) }),
    });
  }, [align, isFixed]);

  useEffect(() => {
    if (!open || !isFixed) return undefined;

    updateFixedPosition();
    window.addEventListener("resize", updateFixedPosition);
    window.addEventListener("scroll", updateFixedPosition, true);

    return () => {
      window.removeEventListener("resize", updateFixedPosition);
      window.removeEventListener("scroll", updateFixedPosition, true);
    };
  }, [isFixed, open, updateFixedPosition]);

  useEffect(() => {
    if (!open) return undefined;

    const handlePointerDown = (event) => {
      if (!ref.current?.contains(event.target)) setOpen(false);
    };

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, [open, setOpen]);

  return (
    <div ref={ref} className="relative min-w-0">
      <div onClick={() => setOpen((current) => !current)}>{trigger}</div>
      {open && (
        <div
          ref={menuRef}
          style={isFixed ? fixedPosition || undefined : undefined}
          className={cn(
            "min-w-56 max-w-[calc(100vw-1rem)] overflow-y-auto rounded-2xl border border-border bg-surface p-2 shadow-premium animate-fadein [overflow-wrap:anywhere]",
            isFixed
              ? "fixed z-[80]"
              : cn("absolute z-40 mt-2", align === "right" ? "right-0" : "left-0"),
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
