import { Check, Minus } from "lucide-react";

import { cn } from "../../utils/cn";

function GuideProgressStepper({
  steps = [],
  currentStepId,
  onStepSelect,
}) {
  const currentIndex = Math.max(
    0,
    steps.findIndex((step) => step.id === currentStepId),
  );
  const resolvedCount = steps.filter(
    (step) => step.complete || step.skipped,
  ).length;
  const completion = steps.length
    ? Math.round((resolvedCount / steps.length) * 100)
    : 0;
  const lineProgress = steps.length > 1
    ? Math.min(100, (resolvedCount / (steps.length - 1)) * 100)
    : completion;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 md:hidden">
        <div className="min-w-0">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-primary">
            Step {currentIndex + 1} of {steps.length}
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-text">
            {steps[currentIndex]?.label || "Getting started"}
          </p>
        </div>
        <span className="shrink-0 text-sm font-bold text-primary">
          {completion}%
        </span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted md:hidden">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300"
          style={{ width: `${completion}%` }}
        />
      </div>

      <div className="overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <ol
          className="relative grid min-w-[42rem] gap-0 px-1 md:min-w-0"
          style={{
            gridTemplateColumns: `repeat(${Math.max(steps.length, 1)}, minmax(0, 1fr))`,
          }}
        >
          <div
            aria-hidden="true"
            className="absolute left-[8%] right-[8%] top-[1.05rem] h-px bg-border"
          />
          <div
            aria-hidden="true"
            className="absolute left-[8%] top-[1.05rem] h-px bg-primary transition-[width] duration-300"
            style={{ width: `${Math.min(84, lineProgress * 0.84)}%` }}
          />

          {steps.map((step, index) => {
            const active = step.id === currentStepId;
            const complete = Boolean(step.complete);
            const skipped = Boolean(step.skipped && !complete);
            const clickable = typeof onStepSelect === "function";
            const Wrapper = clickable ? "button" : "div";

            return (
              <li key={step.id} className="relative min-w-0 px-2 text-center">
                <Wrapper
                  {...(clickable
                    ? {
                        type: "button",
                        onClick: () => onStepSelect(step),
                      }
                    : {})}
                  className={cn(
                    "group relative z-10 mx-auto flex w-full min-w-0 flex-col items-center",
                    clickable && "cursor-pointer",
                  )}
                >
                  <span
                    className={cn(
                      "guide-progress-node grid h-[2.1rem] w-[2.1rem] place-items-center rounded-full border-2 bg-surface text-xs font-bold shadow-[0_0_0_5px_rgb(var(--color-surface))] transition",
                      active && "guide-progress-node-active border-primary bg-primary text-white",
                      complete && !active && "guide-progress-node-complete border-success bg-success text-white",
                      skipped && !active && "border-border bg-surface-muted text-text-faint",
                      !active && !complete && !skipped && "border-border text-text-muted",
                      clickable && "group-hover:border-primary/60",
                    )}
                  >
                    {complete ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : skipped ? (
                      <Minus className="h-3.5 w-3.5" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <span
                    className={cn(
                      "mt-3 block max-w-[9rem] truncate text-xs font-semibold",
                      active ? "guide-progress-label-active text-primary" : "text-text-soft",
                    )}
                  >
                    {step.shortLabel || step.label}
                  </span>
                  <span className="mt-1 text-[10px] font-medium text-text-faint">
                    {complete ? "Complete" : skipped ? "Skipped" : active ? "In progress" : "Upcoming"}
                  </span>
                </Wrapper>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

export default GuideProgressStepper;
