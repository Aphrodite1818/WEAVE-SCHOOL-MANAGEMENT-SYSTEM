import { ArrowLeft, Copy, LoaderCircle, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { useToast } from "../../hooks/useToast";
import { cbtService } from "../../services/cbtService";
import { realtimeClient } from "../../services/realtimeClient";
import { matchesCbtPairingEvent } from "../../services/realtimeEventMatchers";

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
  const [confirmationError, setConfirmationError] = useState("");

  const pairingCode = location.state?.pairingCode || null;
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

    const reconcilePairing = async () => {
      try {
        const status = await cbtService.getPairingStatus(
          pairingCode.pairing_code,
        );
        if (cancelled) return;

        if (status?.status === "paired" && status.server_id) {
          const server = await cbtService.getServer(status.server_id);
          if (cancelled) return;
          setPairedServer(server);
          setConfirmationError("");
        } else if (["expired", "invalidated"].includes(status?.status)) {
          setConfirmationError(
            "This pairing code is no longer active. Generate a fresh code to continue.",
          );
        }
      } catch {
        if (!cancelled) {
          setConfirmationError(
            "We could not confirm pairing. Use Refresh or wait for a realtime update.",
          );
        }
      }
    };

    reconcilePairing();
    const unsubscribeEvent = realtimeClient.subscribe(
      "cbt.pairing.completed",
      (message) => {
        if (matchesCbtPairingEvent(pairingCode.pairing_request_id, message)) {
          reconcilePairing();
        }
      },
    );
    const unsubscribeConnection = realtimeClient.subscribeConnection(
      (state) => {
        if (state.status === "reconnected") reconcilePairing();
      },
    );

    return () => {
      cancelled = true;
      unsubscribeEvent();
      unsubscribeConnection();
    };
  }, [
    hasPairedSuccessfully,
    pairingCode?.pairing_code,
    pairingCode?.pairing_request_id,
  ]);

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
          <Button
            type="button"
            variant="ghost"
            onClick={() => navigate("/admin/cbt")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-1 items-center justify-center">
          {hasPairedSuccessfully ? (
            <div className="flex flex-col items-center text-center">
              <div className="pairing-success-orbit" aria-hidden="true">
                <svg
                  className="pairing-success-orbit__ring"
                  viewBox="0 0 128 128"
                >
                  <circle
                    className="pairing-success-orbit__circle"
                    cx="64"
                    cy="64"
                    r="54"
                    pathLength="1"
                  />
                </svg>
                <svg
                  className="pairing-success-orbit__check"
                  viewBox="0 0 128 128"
                >
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
                      Enter this code on the local CBT server. It can be used
                      once and expires {formatDateTime(pairingCode.expires_at)}.
                    </p>
                    <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-primary/15 bg-surface/80 px-4 py-2 text-xs font-semibold text-text-muted">
                      <LoaderCircle className="h-4 w-4 animate-spin text-primary" />
                      Waiting for backend confirmation of server pairing
                    </div>
                    {confirmationError ? (
                      <p className="mt-4 max-w-xl text-sm leading-6 text-amber-700">
                        {confirmationError}
                      </p>
                    ) : null}
                    <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                      <Button
                        type="button"
                        onClick={handleCopy}
                        disabled={copying}
                      >
                        <Copy className="h-4 w-4" />
                        Copy code
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => navigate("/admin/cbt")}
                      >
                        Back to servers
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    <p className="mt-6 max-w-xl text-sm leading-6 text-text-muted">
                      No active pairing code is available on this page yet.
                      Generate a fresh pairing code from the CBT servers page to
                      open it here.
                    </p>
                    <div className="mt-8">
                      <Button
                        type="button"
                        onClick={() => navigate("/admin/cbt")}
                      >
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
