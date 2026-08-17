import {
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { sessionClosureService } from "../../services/sessionClosureService";
import { realtimeClient } from "../../services/realtimeClient";
import {
  SESSION_PROGRESSION_REALTIME_EVENTS,
  matchesSessionProgressionEvent,
} from "../../services/realtimeEventMatchers";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const emptySessionForm = { next_academic_session_id: "" };

const dateLabel = (value) =>
  value ? new Date(value).toLocaleDateString() : "Not configured";

const runCounts = (run) => [
  ["Total", run?.total_students || 0],
  ["Promoted", run?.promoted_students || 0],
  ["Graduated", run?.graduated_students || 0],
  ["Skipped", run?.skipped_students || 0],
  ["Pending", run?.pending_students || 0],
  ["Failed", run?.failed_students || 0],
];

function SessionLifecycleWorkspace({ activeTab, onContextChange }) {
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [sessionForm, setSessionForm] = useState(emptySessionForm);
  const [configureOpen, setConfigureOpen] = useState(false);
  const [audit, setAudit] = useState(null);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [confirmation, setConfirmation] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const isClosingPage = activeTab === "closing";

  const selectedSession = useMemo(
    () => sessions.find((item) => item.id === selectedSessionId) || null,
    [sessions, selectedSessionId],
  );

  const currentSession = useMemo(
    () => sessions.find((item) => item.is_current) || null,
    [sessions],
  );

  const draftNextSessionOptions = useMemo(
    () =>
      sessions.filter(
        (item) => item.status === "draft" && item.id !== selectedSessionId,
      ),
    [sessions, selectedSessionId],
  );

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await academicService.listSessions({ limit: 100 });
      const rows = asItems(response);
      setSessions(rows);

      const preferred = isClosingPage
        ? rows.find((item) => item.status === "closing") ||
          rows.find((item) => item.status === "open" && item.is_current) ||
          null
        : rows.find((item) => item.is_current) ||
          rows.find((item) => item.status === "open") ||
          null;

      setSelectedSessionId((current) =>
        rows.some((item) => item.id === current)
          ? current
          : preferred?.id || "",
      );
      onContextChange?.({
        currentSession: rows.find((item) => item.is_current) || null,
      });
    } catch (error) {
      showError(getErrorMessage(error, "Could not load academic sessions."));
    } finally {
      setLoading(false);
    }
  }, [isClosingPage, onContextChange, showError]);

  const loadClosingWorkflow = useCallback(async () => {
    if (!isClosingPage || !selectedSessionId) {
      setAudit(null);
      setStatus(null);
      return;
    }

    try {
      const current = sessions.find((item) => item.id === selectedSessionId);
      if (current?.status === "closing") {
        const response =
          await sessionClosureService.getStatus(selectedSessionId);
        setStatus(response);
        setAudit(response?.audit || null);
      } else {
        const response =
          await sessionClosureService.getAudit(selectedSessionId);
        setAudit(response);
        setStatus(null);
      }
    } catch (error) {
      showError(
        getErrorMessage(error, "Could not load the session closure audit."),
      );
    }
  }, [isClosingPage, selectedSessionId, sessions, showError]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    loadClosingWorkflow();
  }, [loadClosingWorkflow]);

  useEffect(() => {
    setSessionForm({
      next_academic_session_id: selectedSession?.next_academic_session_id || "",
    });
  }, [selectedSession]);

  useEffect(() => {
    if (!isClosingPage || !selectedSessionId) return undefined;

    const reconcile = () =>
      Promise.all([loadClosingWorkflow(), loadSessions()]);
    const unsubscribers = SESSION_PROGRESSION_REALTIME_EVENTS.map((eventType) =>
      realtimeClient.subscribe(eventType, (message) => {
        if (matchesSessionProgressionEvent(selectedSessionId, message)) {
          reconcile();
        }
      }),
    );
    unsubscribers.push(
      realtimeClient.subscribeConnection((state) => {
        if (
          state.status === "reconnected" &&
          selectedSession?.status === "closing"
        ) {
          reconcile();
        }
      }),
    );

    return () => unsubscribers.forEach((unsubscribe) => unsubscribe());
  }, [
    isClosingPage,
    loadClosingWorkflow,
    loadSessions,
    selectedSession?.status,
    selectedSessionId,
  ]);

  const openConfiguration = (session) => {
    setSelectedSessionId(session.id);
    setSessionForm({
      next_academic_session_id: session.next_academic_session_id || "",
    });
    setConfigureOpen(true);
  };

  const updateOpenSession = async (event) => {
    event.preventDefault();
    if (!selectedSession || selectedSession.status !== "open") return;

    setBusy("configure");
    try {
      await academicService.updateSession(selectedSession.id, {
        next_academic_session_id: sessionForm.next_academic_session_id || null,
      });
      showSuccess("Next academic session updated.");
      setConfigureOpen(false);
      await loadSessions();
      if (isClosingPage) await loadClosingWorkflow();
    } catch (error) {
      showError(
        getErrorMessage(error, "Could not update progression configuration."),
      );
    } finally {
      setBusy("");
    }
  };

  const terminalStudents = Number(audit?.terminal_students || 0);
  const requiresTerminalConfirmation = Boolean(
    audit?.requires_terminal_confirmation && terminalStudents > 0,
  );

  const startClosing = async () => {
    if (!selectedSession) return;
    setBusy("start");
    try {
      const response = await sessionClosureService.startClosing(
        selectedSession.id,
        `session-closing-${selectedSession.id}`,
        requiresTerminalConfirmation,
      );
      setAudit(response?.audit || null);
      if (!response?.started) {
        showWarning(
          "The closure audit found items that must be resolved first.",
        );
        return;
      }
      showSuccess(
        "Session moved to closing. Student progression is running in the background.",
      );
      await loadSessions();
      await loadClosingWorkflow();
    } catch (error) {
      showError(getErrorMessage(error, "Could not start session closing."));
    } finally {
      setBusy("");
      setConfirmation(null);
    }
  };

  const retryProgression = async () => {
    if (!selectedSession) return;
    setBusy("retry");
    try {
      const response = await sessionClosureService.retryProgression(
        selectedSession.id,
      );
      setStatus(response);
      setAudit(response?.audit || null);
      showSuccess("Progression was queued again.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not retry progression."));
    } finally {
      setBusy("");
      setConfirmation(null);
    }
  };

  const finalizeClose = async () => {
    if (!selectedSession) return;
    setBusy("finalize");
    try {
      const response = await sessionClosureService.finalizeClose(
        selectedSession.id,
      );
      const closedName = response?.closed_session?.name || "Session";
      const nextName = response?.next_session?.name;
      showSuccess(
        nextName
          ? `${closedName} closed. ${nextName} remains in draft for separate opening.`
          : `${closedName} closed.`,
      );
      await loadSessions();
      setStatus(null);
      setAudit(null);
    } catch (error) {
      showError(getErrorMessage(error, "Could not finalize session closure."));
    } finally {
      setBusy("");
      setConfirmation(null);
    }
  };

  if (loading) return <LoadingState label="Loading academic sessions..." />;

  const run = status?.progression_run;
  const blockers = audit?.blocker_messages || [];
  const canStart = selectedSession?.status === "open" && audit?.is_ready;
  const canRetry =
    selectedSession?.status === "closing" && run?.status === "failed";
  const canFinalize = Boolean(status?.can_finalize);

  const configureModal = (
    <Modal
      open={configureOpen}
      title="Configure progression"
      description="The current session name and dates are locked after opening. Select the draft session students should progress into when this session closes."
      onClose={busy ? undefined : () => setConfigureOpen(false)}
      closeOnOverlay={!busy}
      footer={null}
    >
      <form className="grid gap-4" onSubmit={updateOpenSession}>
        <label className="grid gap-1.5 text-sm font-medium text-text">
          <span>Next academic session</span>
          <select
            className="min-h-11 rounded-xl border border-border bg-surface px-3 text-sm text-text"
            value={sessionForm.next_academic_session_id}
            onChange={(event) =>
              setSessionForm({ next_academic_session_id: event.target.value })
            }
          >
            <option value="">Not configured</option>
            {draftNextSessionOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <div className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={Boolean(busy)}
            onClick={() => setConfigureOpen(false)}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={Boolean(busy)}>
            {busy === "configure" ? "Saving..." : "Save progression"}
          </Button>
        </div>
      </form>
    </Modal>
  );

  if (!isClosingPage) {
    return (
      <div className="space-y-5">
        <Card className="p-4 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Current active session
              </p>
              {currentSession ? (
                <>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <h2 className="section-title">{currentSession.name}</h2>
                    <Badge variant="success">{currentSession.status}</Badge>
                  </div>
                  <div className="mt-4 grid gap-3 text-sm text-text-muted sm:grid-cols-3">
                    <div>
                      <p className="font-medium text-text">Start date</p>
                      <p>{dateLabel(currentSession.start_date)}</p>
                    </div>
                    <div>
                      <p className="font-medium text-text">End date</p>
                      <p>{dateLabel(currentSession.end_date)}</p>
                    </div>
                    <div>
                      <p className="font-medium text-text">Next session</p>
                      <p>
                        {sessions.find(
                          (item) =>
                            item.id === currentSession.next_academic_session_id,
                        )?.name || "Not configured"}
                      </p>
                    </div>
                  </div>
                </>
              ) : (
                <p className="mt-2 text-sm text-text-muted">
                  No active academic session.
                </p>
              )}
            </div>
            {currentSession?.status === "open" ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => openConfiguration(currentSession)}
              >
                Configure progression
              </Button>
            ) : null}
          </div>
        </Card>
        {configureModal}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Card className="p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="section-title">Close academic session</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-text-muted">
              Review closure readiness, start background level progression, and
              finalize only after the worker completes successfully.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              className="min-h-10 rounded-xl border border-border bg-surface px-3 text-sm text-text"
              value={selectedSessionId}
              onChange={(event) => setSelectedSessionId(event.target.value)}
            >
              {sessions
                .filter((item) => ["open", "closing"].includes(item.status))
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.status}
                  </option>
                ))}
            </select>
            <Button
              type="button"
              variant="outline"
              size="small"
              className="manual-refresh-action"
              onClick={loadClosingWorkflow}
            >
              <RefreshCw className="h-4 w-4" /> Refresh
            </Button>
            {selectedSession?.status === "open" ? (
              <Button
                type="button"
                variant="outline"
                size="small"
                onClick={() => openConfiguration(selectedSession)}
              >
                Configure progression
              </Button>
            ) : null}
          </div>
        </div>

        {selectedSession ? (
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Badge
              variant={
                selectedSession.status === "closing" ? "warning" : "success"
              }
            >
              {selectedSession.status}
            </Badge>
            {selectedSession.status === "closing" ? (
              <Badge variant="warning">Academic writes paused</Badge>
            ) : null}
            {run?.status ? <Badge>{run.status}</Badge> : null}
          </div>
        ) : null}
      </Card>

      <Card className="p-4 sm:p-6">
        <div className="flex items-start gap-3">
          {audit?.is_ready ? (
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-success" />
          ) : (
            <AlertTriangle className="mt-0.5 h-5 w-5 text-warning" />
          )}
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-text">Closure readiness audit</h3>
            <p className="mt-1 text-sm text-text-muted">
              {audit?.is_ready
                ? "Every required structural and lifecycle check currently passes."
                : "Resolve every blocker below before the session can enter closing."}
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-2">
          {(audit?.checked_items || []).map((item) => (
            <div
              key={item}
              className="flex gap-2 rounded-xl border border-border/70 px-3 py-2 text-sm text-text-muted"
            >
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <span>{item}</span>
            </div>
          ))}
        </div>

        {blockers.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-warning/40 bg-warning-soft p-4">
            <p className="font-semibold text-amber-950">Blocking items</p>
            <ul className="mt-2 grid gap-2 text-sm text-amber-950">
              {blockers.map((message) => (
                <li key={message}>• {message}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {requiresTerminalConfirmation && selectedSession?.status === "open" ? (
          <div className="mt-4 rounded-2xl border border-warning/40 bg-warning-soft p-4 text-sm text-amber-950">
            <p className="font-semibold">
              Terminal graduation confirmation required
            </p>
            <p className="mt-1">
              {terminalStudents} student{terminalStudents === 1 ? "" : "s"} are
              in the final configured level of the institution path. Starting
              closure will graduate them, end their active enrollment, and
              deactivate student access. Missing intermediate categories never
              count as graduation.
            </p>
          </div>
        ) : null}
      </Card>

      {run ? (
        <Card className="p-4 sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="font-semibold text-text">
                Background progression
              </h3>
              <p className="mt-1 text-sm text-text-muted">
                The worker progresses students by academic level only. New
                enrollments have no class placement, and terminal students
                graduate only when that outcome was explicitly confirmed at
                closure start.
              </p>
            </div>
            <Badge
              variant={
                run.status === "completed"
                  ? "success"
                  : run.status === "failed"
                    ? "error"
                    : "warning"
              }
            >
              {run.status}
            </Badge>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-6">
            {runCounts(run).map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-border/70 px-3 py-3"
              >
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  {label}
                </p>
                <p className="mt-1 text-xl font-semibold text-text">{value}</p>
              </div>
            ))}
          </div>
          {run.failure_reason ? (
            <p className="mt-4 rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm text-error">
              {run.failure_reason}
            </p>
          ) : null}
        </Card>
      ) : null}

      <Card className="p-4 sm:p-6">
        <div className="flex flex-wrap gap-3">
          {selectedSession?.status === "open" ? (
            <Button
              type="button"
              variant="danger"
              disabled={!canStart || Boolean(busy)}
              onClick={() =>
                setConfirmation({
                  type: "start",
                  title: requiresTerminalConfirmation
                    ? "Confirm terminal graduation and start closing"
                    : "Start closing this academic session",
                  description: requiresTerminalConfirmation
                    ? `${terminalStudents} terminal student${terminalStudents === 1 ? "" : "s"} will be graduated. Academic writes will pause and the progression worker will then start.`
                    : "Academic write activities will pause immediately and the progression worker will start.",
                  confirmationText: requiresTerminalConfirmation
                    ? "GRADUATE_TERMINAL_STUDENTS"
                    : "START_SESSION_CLOSING",
                  confirmLabel: "Start closing",
                })
              }
            >
              Start closing
            </Button>
          ) : null}
          {canRetry ? (
            <Button
              type="button"
              variant="outline"
              disabled={Boolean(busy)}
              onClick={() =>
                setConfirmation({
                  type: "retry",
                  title: "Retry student progression",
                  description:
                    "Retry the failed background progression after resolving the reported issue. The original terminal-graduation decision is preserved.",
                  confirmationText: "RETRY_SESSION_PROGRESSION",
                  confirmLabel: "Retry progression",
                })
              }
            >
              Retry progression
            </Button>
          ) : null}
          {selectedSession?.status === "closing" ? (
            <Button
              type="button"
              variant="success"
              disabled={!canFinalize || Boolean(busy)}
              onClick={() =>
                setConfirmation({
                  type: "finalize",
                  title: "Finalize session closure",
                  description:
                    "This permanently closes the current session. The configured next session remains in draft for calendar setup and a separate opening step.",
                  confirmationText: "FINALIZE_SESSION_CLOSE",
                  confirmLabel: "Finalize closure",
                })
              }
            >
              Finalize closure
            </Button>
          ) : null}
        </div>
      </Card>

      {configureModal}
      <TypedConfirmationDialog
        open={Boolean(confirmation)}
        title={confirmation?.title}
        description={confirmation?.description}
        confirmationText={confirmation?.confirmationText || ""}
        confirmLabel={confirmation?.confirmLabel}
        variant={
          confirmation?.type === "start" || confirmation?.type === "finalize"
            ? "danger"
            : "primary"
        }
        isLoading={Boolean(busy)}
        onCancel={() => setConfirmation(null)}
        onConfirm={() => {
          if (confirmation?.type === "start") startClosing();
          if (confirmation?.type === "retry") retryProgression();
          if (confirmation?.type === "finalize") finalizeClose();
        }}
      />
    </div>
  );
}

export default SessionLifecycleWorkspace;
