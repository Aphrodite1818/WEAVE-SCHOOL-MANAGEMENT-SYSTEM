import { ArrowRight, ClipboardList } from "lucide-react";

import Button from "../ui/Button";

function GettingStartedBanner({ guide, onContinue }) {
  if (!guide?.config || !guide.currentStep) return null;

  return (
    <section className="overflow-hidden rounded-2xl border border-primary/20 bg-surface shadow-sm">
      <div className="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
            <ClipboardList className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-primary">
                {guide.config.eyebrow}
              </p>
              <span className="text-xs font-semibold text-text-faint">
                {guide.completionPercent}% complete
              </span>
            </div>
            <h2 className="mt-1 text-base font-semibold text-text">
              {guide.currentStep.label}
            </h2>
            <p className="mt-1 line-clamp-2 max-w-2xl text-sm leading-6 text-text-muted">
              {guide.currentStep.description}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3 sm:min-w-52">
          <div className="hidden min-w-24 flex-1 sm:block">
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-300"
                style={{ width: `${guide.completionPercent}%` }}
              />
            </div>
          </div>
          <Button type="button" size="small" onClick={onContinue} className="w-full sm:w-auto">
            Continue
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </section>
  );
}

export default GettingStartedBanner;
