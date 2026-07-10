import { useEffect, useState } from "react";
import { RefreshCw, ShieldAlert, Wrench } from "lucide-react";

import Button from "../../components/ui/Button";
import { clearStoredMaintenanceState, getStoredMaintenanceState, PLATFORM_MAINTENANCE_EVENT } from "../../services/api";

const DEFAULT_MESSAGE = "LearnlyAI is temporarily in maintenance mode. Please try again later.";

function MaintenanceModePage() {
  const [state, setState] = useState(() => getStoredMaintenanceState());

  useEffect(() => {
    const handleMaintenanceUpdate = (event) => {
      setState(event.detail || getStoredMaintenanceState());
    };

    window.addEventListener(PLATFORM_MAINTENANCE_EVENT, handleMaintenanceUpdate);
    return () => window.removeEventListener(PLATFORM_MAINTENANCE_EVENT, handleMaintenanceUpdate);
  }, []);

  const message = state?.message || DEFAULT_MESSAGE;
  const reason = state?.reason;

  const handleRetry = () => {
    clearStoredMaintenanceState();
    window.location.assign("/login");
  };

  return (
    <main className="min-h-screen bg-app px-4 py-8 text-text sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-4xl items-center justify-center">
        <section className="relative w-full overflow-hidden rounded-[2rem] border border-border bg-surface p-6 shadow-premium sm:p-8 lg:p-10">
          <div className="pointer-events-none absolute inset-0 opacity-70" aria-hidden="true">
            <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/20 blur-3xl" />
            <div className="absolute -bottom-24 left-8 h-72 w-72 rounded-full bg-warning/20 blur-3xl" />
          </div>

          <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-warning">
                <ShieldAlert className="h-3.5 w-3.5" />
                Platform maintenance
              </div>

              <h1 className="mt-5 max-w-2xl text-3xl font-semibold tracking-tight text-text sm:text-5xl">
                LearnlyAI is temporarily under maintenance.
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-6 text-text-muted sm:text-base">
                {message}
              </p>

              {reason ? (
                <div className="mt-5 rounded-2xl border border-border/70 bg-surface-muted/40 px-4 py-3 text-sm text-text-soft">
                  <span className="font-semibold text-text">Reason:</span> {reason}
                </div>
              ) : null}

              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <Button onClick={handleRetry}>
                  <RefreshCw className="h-4 w-4" />
                  Retry login
                </Button>
                <Button variant="outline" onClick={() => window.location.reload()}>
                  Check again
                </Button>
              </div>
            </div>

            <div className="rounded-[1.75rem] border border-border bg-surface-muted/30 p-5">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-warning/10 text-warning">
                <Wrench className="h-7 w-7" />
              </div>
              <p className="mt-5 text-sm font-semibold uppercase tracking-wide text-text-muted">What this means</p>
              <p className="mt-2 text-sm leading-6 text-text-soft">
                Your school data is safe. Platform access is temporarily paused while the owner handles maintenance or damage control.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

export default MaintenanceModePage;
