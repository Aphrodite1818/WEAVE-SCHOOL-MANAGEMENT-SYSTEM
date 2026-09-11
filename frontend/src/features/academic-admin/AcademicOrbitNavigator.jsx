import { GraduationCap, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";

import { academicLevelService } from "../../services/academicsService";
import { cn } from "../../utils/cn";
import { filterDepartmentWorkflow } from "./academicDepartmentCapability";
import {
  academicWorkflowConfig,
  academicWorkflowOrder,
} from "./academicWorkflowConfig";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);

const ORBIT_POSITION_STORAGE_KEY = "weave:admin:academic-orbit-position:v1";
const EDGE_GAP = 12;
const BUTTON_SIZE = 56;
const MENU_GAP = 12;
const DRAG_THRESHOLD = 5;
const VALID_EDGES = new Set(["left", "right", "top", "bottom"]);
const DEFAULT_POSITION_PREFERENCE = { edge: "right", ratio: 1 };

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const getViewport = () => ({
  width: typeof window === "undefined" ? 1280 : window.innerWidth,
  height: typeof window === "undefined" ? 720 : window.innerHeight,
});

const readPositionPreference = () => {
  if (typeof window === "undefined") return DEFAULT_POSITION_PREFERENCE;

  try {
    const raw = window.localStorage.getItem(ORBIT_POSITION_STORAGE_KEY);
    if (!raw) return DEFAULT_POSITION_PREFERENCE;
    const parsed = JSON.parse(raw);
    if (!VALID_EDGES.has(parsed?.edge) || !Number.isFinite(parsed?.ratio)) {
      return DEFAULT_POSITION_PREFERENCE;
    }
    return {
      edge: parsed.edge,
      ratio: clamp(parsed.ratio, 0, 1),
    };
  } catch {
    return DEFAULT_POSITION_PREFERENCE;
  }
};

const positionFromPreference = (preference, viewport) => {
  const horizontalTravel = Math.max(
    0,
    viewport.width - BUTTON_SIZE - EDGE_GAP * 2,
  );
  const verticalTravel = Math.max(
    0,
    viewport.height - BUTTON_SIZE - EDGE_GAP * 2,
  );
  const ratio = clamp(preference?.ratio ?? 1, 0, 1);

  if (preference?.edge === "left" || preference?.edge === "right") {
    return {
      x:
        preference.edge === "left"
          ? EDGE_GAP
          : Math.max(EDGE_GAP, viewport.width - BUTTON_SIZE - EDGE_GAP),
      y: EDGE_GAP + verticalTravel * ratio,
    };
  }

  return {
    x: EDGE_GAP + horizontalTravel * ratio,
    y:
      preference?.edge === "top"
        ? EDGE_GAP
        : Math.max(EDGE_GAP, viewport.height - BUTTON_SIZE - EDGE_GAP),
  };
};

const snapToNearestEdge = (position, viewport) => {
  const maxX = Math.max(EDGE_GAP, viewport.width - BUTTON_SIZE - EDGE_GAP);
  const maxY = Math.max(EDGE_GAP, viewport.height - BUTTON_SIZE - EDGE_GAP);
  const x = clamp(position.x, EDGE_GAP, maxX);
  const y = clamp(position.y, EDGE_GAP, maxY);
  const distances = [
    { edge: "left", distance: x - EDGE_GAP },
    { edge: "right", distance: maxX - x },
    { edge: "top", distance: y - EDGE_GAP },
    { edge: "bottom", distance: maxY - y },
  ];
  const edge = distances.reduce((nearest, candidate) =>
    candidate.distance < nearest.distance ? candidate : nearest,
  ).edge;

  if (edge === "left" || edge === "right") {
    const travel = Math.max(1, maxY - EDGE_GAP);
    return {
      edge,
      ratio: clamp((y - EDGE_GAP) / travel, 0, 1),
    };
  }

  const travel = Math.max(1, maxX - EDGE_GAP);
  return {
    edge,
    ratio: clamp((x - EDGE_GAP) / travel, 0, 1),
  };
};

export default function AcademicOrbitNavigator({
  currentWorkflow = "",
  workflows,
}) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [viewport, setViewport] = useState(getViewport);
  const [positionPreference, setPositionPreference] = useState(
    readPositionPreference,
  );
  const [dragPosition, setDragPosition] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [menuStyle, setMenuStyle] = useState(null);
  const menuRef = useRef(null);
  const dragRef = useRef(null);
  const [fallbackWorkflows, setFallbackWorkflows] = useState(() =>
    filterDepartmentWorkflow(academicWorkflowOrder, []),
  );
  const visibleWorkflows = Array.isArray(workflows)
    ? workflows
    : fallbackWorkflows;
  const settledPosition = positionFromPreference(positionPreference, viewport);
  const buttonPosition = dragPosition || settledPosition;

  useEffect(() => {
    if (Array.isArray(workflows)) return undefined;

    let mounted = true;
    academicLevelService
      .getCategories()
      .then((response) => {
        if (mounted) {
          setFallbackWorkflows(
            filterDepartmentWorkflow(academicWorkflowOrder, asItems(response)),
          );
        }
      })
      .catch(() => {
        if (mounted) {
          setFallbackWorkflows(
            filterDepartmentWorkflow(academicWorkflowOrder, []),
          );
        }
      });

    return () => {
      mounted = false;
    };
  }, [workflows]);

  useEffect(() => {
    const handleResize = () => {
      setViewport(getViewport());
      setDragPosition(null);
      setIsDragging(false);
      dragRef.current = null;
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        ORBIT_POSITION_STORAGE_KEY,
        JSON.stringify(positionPreference),
      );
    } catch {
      // Position memory is an enhancement; navigation must still work if storage is unavailable.
    }
  }, [positionPreference]);

  useLayoutEffect(() => {
    if (!open || !menuRef.current) {
      setMenuStyle(null);
      return;
    }

    const menuRect = menuRef.current.getBoundingClientRect();
    const maxLeft = Math.max(EDGE_GAP, viewport.width - menuRect.width - EDGE_GAP);
    const maxTop = Math.max(EDGE_GAP, viewport.height - menuRect.height - EDGE_GAP);
    const buttonCenterX = settledPosition.x + BUTTON_SIZE / 2;
    const buttonCenterY = settledPosition.y + BUTTON_SIZE / 2;
    let left;
    let top;

    if (positionPreference.edge === "right") {
      left = settledPosition.x - MENU_GAP - menuRect.width;
      top = buttonCenterY - menuRect.height / 2;
    } else if (positionPreference.edge === "left") {
      left = settledPosition.x + BUTTON_SIZE + MENU_GAP;
      top = buttonCenterY - menuRect.height / 2;
    } else if (positionPreference.edge === "top") {
      left = buttonCenterX - menuRect.width / 2;
      top = settledPosition.y + BUTTON_SIZE + MENU_GAP;
    } else {
      left = buttonCenterX - menuRect.width / 2;
      top = settledPosition.y - MENU_GAP - menuRect.height;
    }

    setMenuStyle({
      left: `${clamp(left, EDGE_GAP, maxLeft)}px`,
      top: `${clamp(top, EDGE_GAP, maxTop)}px`,
    });
  }, [
    open,
    positionPreference.edge,
    settledPosition.x,
    settledPosition.y,
    viewport.height,
    viewport.width,
  ]);

  const selectWorkflow = (workflow) => {
    setOpen(false);
    navigate(`/admin/academic/${workflow}`);
  };

  const handlePointerDown = useCallback(
    (event) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;

      event.preventDefault();
      event.currentTarget.setPointerCapture?.(event.pointerId);
      dragRef.current = {
        pointerId: event.pointerId,
        startClientX: event.clientX,
        startClientY: event.clientY,
        startX: settledPosition.x,
        startY: settledPosition.y,
        currentX: settledPosition.x,
        currentY: settledPosition.y,
        moved: false,
      };
    },
    [settledPosition.x, settledPosition.y],
  );

  const handlePointerMove = useCallback(
    (event) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== event.pointerId) return;

      const deltaX = event.clientX - drag.startClientX;
      const deltaY = event.clientY - drag.startClientY;
      const moved =
        drag.moved || Math.hypot(deltaX, deltaY) >= DRAG_THRESHOLD;
      if (!moved) return;

      event.preventDefault();
      if (!drag.moved) {
        setOpen(false);
        setIsDragging(true);
      }

      const maxX = Math.max(
        EDGE_GAP,
        viewport.width - BUTTON_SIZE - EDGE_GAP,
      );
      const maxY = Math.max(
        EDGE_GAP,
        viewport.height - BUTTON_SIZE - EDGE_GAP,
      );
      const nextPosition = {
        x: clamp(drag.startX + deltaX, EDGE_GAP, maxX),
        y: clamp(drag.startY + deltaY, EDGE_GAP, maxY),
      };

      dragRef.current = {
        ...drag,
        moved: true,
        currentX: nextPosition.x,
        currentY: nextPosition.y,
      };
      setDragPosition(nextPosition);
    },
    [viewport.height, viewport.width],
  );

  const finishPointerInteraction = useCallback(
    (event, cancelled = false) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== event.pointerId) return;

      event.currentTarget.releasePointerCapture?.(event.pointerId);
      dragRef.current = null;

      if (cancelled) {
        setDragPosition(null);
        setIsDragging(false);
        return;
      }

      if (!drag.moved) {
        setDragPosition(null);
        setIsDragging(false);
        setOpen((value) => !value);
        return;
      }

      const preference = snapToNearestEdge(
        { x: drag.currentX, y: drag.currentY },
        viewport,
      );
      setPositionPreference(preference);
      setDragPosition(null);
      setIsDragging(false);
    },
    [viewport],
  );

  const handlePointerUp = useCallback(
    (event) => finishPointerInteraction(event, false),
    [finishPointerInteraction],
  );

  const handlePointerCancel = useCallback(
    (event) => finishPointerInteraction(event, true),
    [finishPointerInteraction],
  );

  const handleButtonKeyDown = (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    setOpen((value) => !value);
  };

  return (
    <>
      {open ? (
        <button
          type="button"
          aria-label="Close academic navigation"
          className="fixed inset-0 z-40 cursor-default bg-slate-950/[0.04] backdrop-blur-[1px]"
          onClick={() => setOpen(false)}
        />
      ) : null}

      {open ? (
        <div
          ref={menuRef}
          data-academic-workflow-menu="true"
          className="fixed z-50 flex max-h-[65dvh] w-[min(23rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl"
          style={{
            ...(menuStyle || {}),
            visibility: menuStyle ? "visible" : "hidden",
          }}
        >
          <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/70 px-3.5 py-3">
            <div className="min-w-0">
              <p className="text-sm font-bold text-text">Academic navigation</p>
              <p className="mt-0.5 text-[11px] leading-4 text-text-muted">
                Jump to any academic workspace.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-border/70 text-text-muted transition hover:bg-surface-muted hover:text-text"
              aria-label="Close academic navigation"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-3 gap-2 overflow-y-auto overscroll-contain p-3">
            {visibleWorkflows.map((workflow) => {
              const config = academicWorkflowConfig[workflow];
              const Icon = config.icon;
              const active = workflow === currentWorkflow;
              return (
                <button
                  key={workflow}
                  type="button"
                  title={config.title}
                  aria-label={`Open ${config.title}`}
                  aria-current={active ? "page" : undefined}
                  onClick={() => selectWorkflow(workflow)}
                  className={cn(
                    "flex min-h-[4.75rem] min-w-0 flex-col items-center justify-center gap-1.5 rounded-xl border px-2 py-2.5 text-center transition",
                    active
                      ? "border-primary/35 bg-primary-soft text-primary"
                      : "border-border/70 bg-surface text-text-soft hover:border-primary/25 hover:bg-surface-muted hover:text-text",
                  )}
                >
                  <span
                    className={cn(
                      "grid h-8 w-8 shrink-0 place-items-center rounded-lg",
                      active ? "bg-primary/10" : "bg-surface-muted",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="w-full break-words text-[11px] font-semibold leading-4">
                    {config.shortTitle || config.title}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <div
        data-academic-workflow-navigator="true"
        className="fixed z-50"
        style={{
          left: `${buttonPosition.x}px`,
          top: `${buttonPosition.y}px`,
        }}
      >
        <button
          type="button"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerCancel}
          onKeyDown={handleButtonKeyDown}
          aria-expanded={open}
          aria-label={open ? "Close academic navigation" : "Open academic navigation"}
          title="Drag to reposition. Click to open academic navigation."
          className={cn(
            "grid h-14 w-14 touch-none select-none place-items-center rounded-full border-[5px] border-primary-soft bg-primary text-white shadow-xl transition-[transform,box-shadow]",
            isDragging
              ? "cursor-grabbing scale-105 shadow-2xl"
              : "cursor-grab hover:scale-105",
            open && "shadow-lg",
          )}
        >
          {open ? <X className="h-5 w-5" /> : <GraduationCap className="h-5 w-5" />}
        </button>
      </div>
    </>
  );
}
