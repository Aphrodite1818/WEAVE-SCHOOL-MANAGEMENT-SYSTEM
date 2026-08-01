import { Check } from "lucide-react";

import { cn } from "../../utils/cn";

function GuideProgressStepper({ steps = [], currentStepId }) {
  const currentIndex = Math.max(
    0,
    steps.findIndex((step) => step.id === currentStepId),
  );
  const completion = steps.length
    ? Math.round(
        (steps.filter((step) => step.complete).length / steps.length) * 100,
      )
    : 0;

  return (
    <div>
      <div className="md:hidden">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-faint">
              Step {currentIndex + 1} of {steps.length}
            </p>
            <p className="mt-1 text-sm font-semibold text-text">
              {steps[currentIndex]?.label || "Setup guide"}
            </p>
          </div>
          <span className="rounded-full bg-primary-soft px-2.5 py-1 text-xs font-bold text-primary">
            {completion}%
          </span>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${completion}%` }}
          />
        </div>
      </div>

      <div className="hidden md:grid md:grid-cols-4 md:gap-2">
        {steps.map((step, index) => {
          const active = step.id === currentStepId;
          const skipped = Boolean(step.skipped);
          const complete = Boolean(step.complete);
          return (
            <div
              key={step.id}
              className={cn(
                "relative min-w-0 rounded-xl border px-3 py-3 transition",
                active
                  ? "border-primary/45 bg-primary-soft"
                  : complete
                    ? "border-success/35 bg-success-soft"
                    : skipped
                      ? "border-border bg-surface-muted/45"
                      : "border-border bg-surface",
              )}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "grid h-7 w-7 shrink-0 place-items-center rounded-full border text-xs font-bold",
                    active
                      ? "border-primary bg-primary text-white"
                      : complete
                        ? "border-success bg-success text-white"
                        : "border-border bg-surface text-text-muted",
                  )}
                >
                  {complete ? <Check className="h-3.5 w-3.5" /> : index + 1}
                </span>
                <span className="min-w-0 truncate text-xs font-semibold text-text">
                  {step.shortLabel || step.label}
                </span>
              </div>
              {skipped && !complete ? (
                <p className="mt-2 text-[11px] font-medium text-text-faint">Skipped</p>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default GuideProgressStepper;
