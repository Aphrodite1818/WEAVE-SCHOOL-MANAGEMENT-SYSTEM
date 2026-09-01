import { GraduationCap, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { cn } from "../../utils/cn";
import {
  academicWorkflowConfig,
  academicWorkflowOrder,
} from "./academicWorkflowConfig";

const INNER_RING_COUNT = 7;

const orbitPosition = (index, total, radius, startAngle = -90) => {
  const angle = startAngle + (360 / total) * index;
  const radians = (angle * Math.PI) / 180;
  return {
    left: `calc(50% + ${Math.cos(radians) * radius}px)`,
    top: `calc(50% + ${Math.sin(radians) * radius}px)`,
  };
};

function OrbitItem({ workflow, currentWorkflow, position, onSelect }) {
  const config = academicWorkflowConfig[workflow];
  const Icon = config.icon;
  const active = workflow === currentWorkflow;

  return (
    <button
      type="button"
      title={config.title}
      aria-label={`Open ${config.title}`}
      onClick={() => onSelect(workflow)}
      className={cn(
        "group absolute z-10 grid h-11 w-11 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border bg-surface shadow-sm transition hover:-translate-y-[55%] hover:border-primary/40 hover:text-primary hover:shadow-md",
        active
          ? "border-primary bg-primary text-white"
          : "border-border/80 text-text-soft",
      )}
      style={position}
    >
      <Icon className="h-4 w-4" />
      <span className="pointer-events-none absolute bottom-full mb-2 hidden max-w-36 whitespace-nowrap rounded-lg border border-border bg-surface px-2 py-1 text-[11px] font-semibold text-text shadow-lg group-hover:block">
        {config.title}
      </span>
    </button>
  );
}

export default function AcademicOrbitNavigator({ currentWorkflow = "" }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const inner = academicWorkflowOrder.slice(0, INNER_RING_COUNT);
  const outer = academicWorkflowOrder.slice(INNER_RING_COUNT);

  const selectWorkflow = (workflow) => {
    setOpen(false);
    navigate(`/admin/academic/${workflow}`);
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

      <div className="fixed bottom-20 right-4 z-50 sm:bottom-6 sm:right-6">
        {open ? (
          <>
            <div className="mb-3 grid w-[min(22rem,calc(100vw-1.5rem))] grid-cols-3 gap-2 rounded-2xl border border-border bg-surface p-3 shadow-2xl sm:hidden">
              {academicWorkflowOrder.map((workflow) => {
                const config = academicWorkflowConfig[workflow];
                const Icon = config.icon;
                const active = workflow === currentWorkflow;
                return (
                  <button
                    key={workflow}
                    type="button"
                    onClick={() => selectWorkflow(workflow)}
                    className={cn(
                      "flex min-h-20 flex-col items-center justify-center gap-2 rounded-xl border px-2 py-2 text-center text-[11px] font-semibold transition",
                      active
                        ? "border-primary bg-primary-soft text-primary"
                        : "border-border/70 text-text-soft hover:bg-surface-muted",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{config.title}</span>
                  </button>
                );
              })}
            </div>

            <div className="relative hidden h-[22rem] w-[22rem] rounded-full border border-border/60 bg-surface/95 shadow-2xl backdrop-blur sm:block">
              <div className="absolute inset-[4.9rem] rounded-full border border-dashed border-primary/20" />
              <div className="absolute inset-[1.1rem] rounded-full border border-dashed border-border/70" />

              {inner.map((workflow, index) => (
                <OrbitItem
                  key={workflow}
                  workflow={workflow}
                  currentWorkflow={currentWorkflow}
                  position={orbitPosition(index, inner.length, 82)}
                  onSelect={selectWorkflow}
                />
              ))}
              {outer.map((workflow, index) => (
                <OrbitItem
                  key={workflow}
                  workflow={workflow}
                  currentWorkflow={currentWorkflow}
                  position={orbitPosition(index, outer.length, 145, -64)}
                  onSelect={selectWorkflow}
                />
              ))}

              <button
                type="button"
                onClick={() => setOpen(false)}
                className="absolute left-1/2 top-1/2 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-[6px] border-primary-soft bg-primary text-white shadow-lg"
                aria-label="Close academic navigation"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </>
        ) : null}

        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-label={open ? "Close academic navigation" : "Open academic navigation"}
          className={cn(
            "ml-auto grid h-14 w-14 place-items-center rounded-full border-[5px] border-primary-soft bg-primary text-white shadow-xl transition hover:scale-105",
            open && "sm:hidden",
          )}
        >
          <GraduationCap className="h-5 w-5" />
        </button>
      </div>
    </>
  );
}
