import { useEffect, useState } from "react";
import { Ban, RefreshCw, ShieldAlert } from "lucide-react";

import Button from "../../components/ui/Button";
import {
  clearStoredSecurityBlockState,
  getStoredSecurityBlockState,
  SECURITY_BLOCK_EVENT,
} from "../../services/api";

const DEFAULT_MESSAGE = "Access from this network has been temporarily blocked for security reasons.";

function NetworkBlockedPage() {
  const [state, setState] = useState(() => getStoredSecurityBlockState());

  useEffect(() => {
    const handleSecurityBlockUpdate = (event) => {
      setState(event.detail || getStoredSecurityBlockState());
    };

    window.addEventListener(SECURITY_BLOCK_EVENT, handleSecurityBlockUpdate);
    return () => window.removeEventListener(SECURITY_BLOCK_EVENT, handleSecurityBlockUpdate);
  }, []);

  const message = state?.message || DEFAULT_MESSAGE;
  const reason = state?.reason;
  const ipLabel = state?.ipLabel;
  const expiresAt = state?.expiresAt;

  const handleRetry = () => {
    clearStoredSecurityBlockState();
    window.location.assign("/login");
  };

  return (
    <main className="min-h-screen bg-app px-4 py-8 text-text sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-4xl items-center justify-center">
        <section className="relative w-full overflow-hidden rounded-[2rem] border border-border bg-surface p-6 shadow-premium sm:p-8 lg:p-10">
          <div className="pointer-events-none absolute inset-0 opacity-70" aria-hidden="true">
            <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-error/20 blur-3xl" />
            <div className="absolute -bottom-24 left-8 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
          </div>

          <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-error/30 bg-error-soft px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-error">
                <ShieldAlert className="h-3.5 w-3.5" />
                Network blocked
              </div>

              <h1 className="mt-5 max-w-2xl text-3xl font-semibold tracking-tight text-text sm:text-5xl">
                Access from this network is temporarily blocked.
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-6 text-text-muted sm:text-base">
                {message}
              </p>

              <div className="mt-5 grid gap-3 rounded-2xl border border-border/70 bg-surface-muted/40 px-4 py-3 text-sm text-text-soft">
                {reason ? (
                  <p><span className="font-semibold text-text">Reason:</span> {reason}</p>
                ) : null}
                {ipLabel ? (
                  <p><span className="font-semibold text-text">Network:</span> {ipLabel}</p>
                ) : null}
                {expiresAt ? (
                  <p><span className="font-semibold text-text">Expires:</span> {expiresAt}</p>
                ) : null}
              </div>

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
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-error-soft text-error">
                <Ban className="h-7 w-7" />
              </div>
              <p className="mt-5 text-sm font-semibold uppercase tracking-wide text-text-muted">What this means</p>
              <p className="mt-2 text-sm leading-6 text-text-soft">
                This network was manually contained by the platform owner. Try again later or use a trusted network if you believe this is a mistake.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

export default NetworkBlockedPage;
