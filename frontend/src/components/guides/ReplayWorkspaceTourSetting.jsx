import { Compass } from "lucide-react";

import { requestWorkspaceTour, tourKeyForRole } from "../../features/guides/workspaceTourState";
import Button from "../ui/Button";

export default function ReplayWorkspaceTourSetting({ role }) {
  if (!tourKeyForRole(role)) return null;

  return (
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 gap-4">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
            <Compass className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-text">Workspace tour</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">
              Replay the introduction to the areas currently available in your workspace. Hidden or unreleased features are never included.
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          className="shrink-0"
          onClick={() => requestWorkspaceTour(role)}
        >
          Replay workspace tour
        </Button>
      </div>
    </section>
  );
}
