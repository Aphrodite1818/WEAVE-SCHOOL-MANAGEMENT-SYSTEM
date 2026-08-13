import { ArrowLeft, Copy, LoaderCircle, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { useToast } from "../../hooks/useToast";
import { cbtService } from "../../services/cbtService";

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString();
}

export default function CBTPairingCodePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { showError, showSuccess } = useToast();
  const [copying, setCopying] = useState(false);
  const [pairedServer, setPairedServer] = useState(null);
  const [pollError, setPollError] = useState("");

  const pairingCode = location.state?.pairingCode || null;
  const existingServerIds = useMemo(
    () => new Set((location.state?.existingServerIds || []).map((value) => String(value))),
    [location.state?.existingServerIds],
  );
  const hasPairedSuccessfully = Boolean(pairedServer);

  const handleCopy = async () => {
    if (!pairingCode?.pairing_code) return;
    setCopying(true);
    try {
      await navigator.clipboard.writeText(pairingCode.pairing_code);
      showSuccess("Pairing code copied.");
    } catch {
      showError("Could not copy pairing code.");
    } finally {
      setCopying(false);
    }
  };

  useEffect(() => {
    if (!pairingCode?.pairing_code || hasPairedSuccessfully) return undefined;

    let cancelled = false;

    const pollForPairedServer = async () => {
      try {
        const response = await cbtService.listServers();
        if (cancelled) return;

        const items = Array.isArray(response?.items) ? response.items : [];
        const newestServer = items.find((server) => !existingServerIds.has(String(server.id)));

        if (newestServer) {
          setPairedServer(newestServer);
          setPollError("");
        }
      } catch {
        if (!cancelled) {
          setPollError("We could not confirm pairing yet. We'll keep trying automatically.");
        }
      }
    };

    pollForPairedServer();
    const intervalId = window.setInterval(pollForPairedServer, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [existingServerIds, hasPairedSuccessfully, pairingCode?.pairing_code]);

  useEffect(() => {
    if (!pairedServer) return undefined;

    const redirectId = window.setTimeout(() => {
      navigate("/admin/cbt", {
        replace: true,
      });
    }, 1450);

    return () => window.clearTimeout(redirectId);
  }, [navigate, pairedServer]);

  return (
    <DashboardLayout role="admin" title="Server Pairing Code">
      <div className="flex min-h-[calc(100dvh-12rem)] flex-col">
        <div className="mb-4">
          <Button type="button" variant="ghost" onClick={() => navigate("/admin/cbt")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-1 items-center justify-center">
          {hasPairedSuccessfully ? (
            <div className="flex flex-col items-center text-center">
              <div className="pairing-success-orbit" aria-hidden="true">
                <svg className="pairing-success-orbit__ring" viewBox="0 0 128 128">
                  <circle className="pairing-success-orbit__circle" cx="64" cy="64" r="54" pathLength="1" />
                </svg>
                <svg className="pairing-success-orbit__check" viewBox="0 0 128 128">
                  <path d="M38 66 L57 84 L92 45" pathLength="1" />
                </svg>
              </div>
              <p className="mt-6 text-base font-semibold uppercase tracking-[0.22em] text-success">
                Paired
              </p>
            </div>
          ) : (
            <Card className="w-full max-w-3xl border-border/70 bg-surface px-6 py-10 text-center shadow-sm sm:px-10 sm:py-14">
              <div className="mx-auto flex max-w-2xl flex-col items-center">
                {pairingCode?.pairing_code ? (
                <>
                  <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-primary">
                    <ShieldCheck className="h-7 w-7" />
                  </div>
                  <p className="text-sm font-semibold uppercase tracking-[0.22em] text-primary">
                    Server Pairing Code
                  </p>
                  <code className="mt-6 block break-all text-center text-4xl font-black tracking-[0.28em] text-text sm:text-6xl">
                    {pairingCode.pairing_code}
                  </code>
                  <p className="mt-6 max-w-xl text-sm leading-6 text-text-muted">
                    Enter this code on the local CBT server. It can be used once and expires {formatDateTime(pairingCode.expires_at)}.
                  </p>
                  <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-primary/15 bg-surface/80 px-4 py-2 text-xs font-semibold text-text-muted">
                    <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                    Waiting for backend confirmation of server pairing
                  </div>
                  {pollError ? (
                    <p className="mt-4 max-w-xl text-sm leading-6 text-amber-700">
                      {pollError}
                    </p>
                  ) : null}
                  <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                    <Button type="button" onClick={handleCopy} disabled={copying}>
                      <Copy className="h-4 w-4" />
                      Copy code
                    </Button>
                    <Button type="button" variant="outline" onClick={() => navigate("/admin/cbt")}>
                      Back to servers
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <p className="mt-6 max-w-xl text-sm leading-6 text-text-muted">
                    No active pairing code is available on this page yet. Generate a fresh pairing code from the CBT servers page to open it here.
                  </p>
                  <div className="mt-8">
                    <Button type="button" onClick={() => navigate("/admin/cbt")}>
                      Back to servers
                    </Button>
                  </div>
                </>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
