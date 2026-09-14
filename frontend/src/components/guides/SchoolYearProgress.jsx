import { Check } from "lucide-react";
import { ROLE_GUIDES } from "../../features/guides/roleGuideConfig";
import { schoolYearProgress, SCHOOL_YEAR_STAGES } from "../../features/guides/schoolYearProgress";
import "./schoolYearSetup.css";

export default function SchoolYearProgress({ completion, current, onSelect, disabled }) {
  const progress = schoolYearProgress(completion);
  return <nav aria-label="School year setup" className="mb-10">
    <p className="mb-5 text-sm text-text-muted">{disabled ? "Checking your saved setup…" : `${progress.completedStages} of 3 stages complete`}</p>
    <ol className="grid grid-cols-3 gap-3 sm:gap-6">
      {SCHOOL_YEAR_STAGES.map((stage, index) => {
        const stepId = stage.steps.find((id) => completion?.[id] !== true) || stage.steps[0];
        const step = ROLE_GUIDES.admin.steps.find((item) => item.id === stepId);
        const active = stage.steps.includes(current);
        const complete = !disabled && stage.steps.every((id) => completion?.[id] === true);
        return <li key={stage.id} className={`border-t-2 pt-4 ${complete || active ? "border-primary" : "border-border"}`}>
          <button type="button" onClick={() => onSelect(step)} disabled={disabled || !progress.canOpen(step.id)} aria-current={active ? "step" : undefined}
            className="flex min-h-11 items-center gap-2 rounded-lg text-left text-sm font-medium text-text disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary sm:gap-3">
            <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full ${complete || active ? "bg-primary text-primary-foreground" : "bg-surface-muted text-text-muted"}`}>
              {complete ? <Check className="h-4 w-4" /> : index + 1}
            </span>{stage.label}<span className="sr-only">{complete ? ", complete" : ""}</span>
          </button>
        </li>;
      })}
    </ol>
  </nav>;
}
