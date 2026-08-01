import { ArrowRight, Check, Circle } from "lucide-react";

import Button from "../ui/Button";
import Card from "../ui/Card";

const buildSteps = (stats = {}) => [
  {
    id: "foundation",
    label: "Academic session and term",
    complete: Boolean(stats.active_academic_session && stats.active_academic_term),
  },
  {
    id: "structure",
    label: "Classes and subjects",
    complete:
      Number(stats.total_classes || 0) > 0
      && Number(stats.total_subjects || 0) > 0,
  },
  {
    id: "staff",
    label: "Teachers added",
    complete: Number(stats.total_teachers || 0) > 0,
  },
  {
    id: "students",
    label: "Students added",
    complete: Number(stats.total_students || 0) > 0,
  },
];

function AdminSetupProgressCard({ stats }) {
  const steps = buildSteps(stats);
  const completeCount = steps.filter((step) => step.complete).length;
  const percent = Math.round((completeCount / steps.length) * 100);
  const complete = completeCount === steps.length;

  if (complete) return null;

  return (
    <Card className="overflow-hidden border-primary/20 p-0">
      <div className="bg-primary-soft/55 px-4 py-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.15em] text-primary">
              School setup
            </p>
            <h2 className="mt-1 text-lg font-semibold text-text sm:text-xl">
              {completeCount} of {steps.length} foundation stages complete
            </h2>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              Continue from the first unfinished academic setup stage.
            </p>
          </div>
          <span className="self-start rounded-full bg-surface px-3 py-1.5 text-sm font-bold text-primary shadow-sm">
            {percent}%
          </span>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface/80">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>

      <div className="grid gap-2 px-4 py-4 sm:grid-cols-2 sm:px-5">
        {steps.map((step, index) => (
          <div
            key={step.id}
            className="flex min-h-11 items-center gap-3 rounded-xl border border-border/70 bg-surface px-3 py-2.5"
          >
            <span
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-full ${
                step.complete
                  ? "bg-success text-white"
                  : "border border-border bg-surface-muted text-text-faint"
              }`}
            >
              {step.complete ? <Check className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
            </span>
            <span className="min-w-0 text-sm font-semibold text-text-soft">
              {index + 1}. {step.label}
            </span>
          </div>
        ))}
      </div>

      <div className="border-t border-border px-4 py-4 sm:px-5">
        <Button
          type="button"
          className="w-full sm:w-auto"
          onClick={() => window.dispatchEvent(new CustomEvent("weave:open-role-guide"))}
        >
          Continue school setup
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  );
}

export default AdminSetupProgressCard;
