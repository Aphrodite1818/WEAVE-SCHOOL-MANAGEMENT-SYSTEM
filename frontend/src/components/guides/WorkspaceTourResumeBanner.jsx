import { ArrowRight, Compass } from "lucide-react";

import { resumeIndexFromState } from "../../features/guides/workspaceTourState";
import Button from "../ui/Button";

export default function WorkspaceTourResumeBanner({ role, state, onResume }) {
  if (state?.status !== "in_progress") return null;

  const resumeIndex = resumeIndexFromState(state);
  const locationCopy = resumeIndex >= 0 ? `You stopped at step ${resumeIndex + 1}.` : "Your workspace tour is not complete yet.";

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-primary/25 bg-primary-subtle/70 px-5 py-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
          <Compass className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-text">Workspace tour</h2>
            <span className="rounded-full border border-warning/30 bg-warning-soft px-2 py-0.5 text-[11px] font-semibold text-amber-800">
              Incomplete
            </span>
          </div>
          <p className="mt-1 text-sm leading-6 text-text-muted">
            {locationCopy} Resume whenever you are ready. It will not force itself open again after a temporary skip.
          </p>
          {role === "admin" ? (
            <p className="mt-1 text-xs text-text-muted">
              This is separate from your school-year setup progress.
            </p>
          ) : null}
        </div>
      </div>
      <Button type="button" size="small" onClick={onResume}>
        Resume tour
        <ArrowRight className="h-4 w-4" />
      </Button>
    </section>
  );
}
