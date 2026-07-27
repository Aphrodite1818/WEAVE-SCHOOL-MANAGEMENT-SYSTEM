import { GitBranch, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { Input, SelectControl, WorkspacePanel } from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];
const CONFIRM_CLOSE_AND_PROGRESS = "CLOSE_AND_PROGRESS";

function ProgressionWorkspace({ activeTab }) {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [confirmingClose, setConfirmingClose] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const { showSuccess, showError, showWarning } = useToast();

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await academicService.listSessions({ limit: 100 });
      const nextSessions = asItems(response);
      setSessions(nextSessions);
      setSessionId((current) => current || nextSessions.find((item) => item.status === "open")?.id || "");
    } catch (error) {
      showError(getErrorMessage(error, "Could not load academic sessions."));
    } finally {
      setLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const sessionOptions = useMemo(
    () =>
      sessions.map((item) => ({
        value: item.id,
        label: `${item.name} (${item.status})`,
      })),
    [sessions],
  );

  const selectedSession = sessions.find((item) => item.id === sessionId);

  const closeAndProgress = async (event) => {
    event.preventDefault();
    if (!sessionId) {
      showWarning("Select the open academic session first.");
      return;
    }
    if (!idempotencyKey.trim()) {
      showWarning("Enter an idempotency key before running progression.");
      return;
    }
    setConfirmingClose(true);
  };

  const runCloseAndProgress = async () => {
    setSaving(true);
    try {
      await academicService.closeSessionAndProgress(sessionId, {
        idempotency_key: idempotencyKey.trim(),
      });
      showSuccess("Academic session closure and progression started.");
      await loadSessions();
    } catch (error) {
      showError(getErrorMessage(error, "Could not run student progression."));
    } finally {
      setSaving(false);
      setConfirmingClose(false);
    }
  };

  if (["completed", "failed", "outcomes"].includes(activeTab)) {
    return (
      <WorkspacePanel
        title="Progression run history is not exposed"
        description="The local backend has progression run models and repositories, but no tenant-admin route for listing run history or per-student outcomes."
      >
        <div className="flex gap-3 rounded-2xl border border-warning/30 bg-warning-soft px-4 py-4 text-sm leading-6 text-amber-900">
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>
            I omitted fake history tables here. The supported frontend action is
            closing an open session through the dedicated close-and-progress endpoint.
          </p>
        </div>
      </WorkspacePanel>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
      <WorkspacePanel
        title="Plan progression"
        description="The backend computes PROMOTE, GRADUATE, and SKIP outcomes from class progression settings. REPEAT is not currently exposed as a manual frontend action."
      >
        <form className="space-y-3" onSubmit={closeAndProgress}>
          <SelectControl
            label="Academic session"
            value={sessionId}
            onChange={setSessionId}
            options={sessionOptions}
            placeholder={loading ? "Loading sessions" : "Select session"}
            required
          />
          <Input
            label="Idempotency key"
            value={idempotencyKey}
            onChange={(event) => setIdempotencyKey(event.target.value)}
            placeholder="close-2026-2027-term-run"
            minLength={8}
            maxLength={150}
            required
          />
          <div className="rounded-2xl border border-error/25 bg-error-soft px-4 py-3 text-sm leading-6 text-error">
            This closes the selected academic session and runs progression. Repeated clicks
            with the same idempotency key are treated as the same operation by the backend.
          </div>
          <Button
            type="submit"
            disabled={saving || selectedSession?.status !== "open"}
            variant="danger"
          >
            {saving ? "Running..." : "Close session and progress"}
          </Button>
        </form>
      </WorkspacePanel>

      <WorkspacePanel
        title="Supported progression contract"
        description="Only backend-supported behavior is shown."
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            ["Route", "POST /tenant-admin/academics/sessions/{session_id}/close-and-progress"],
            ["Payload", "confirmation: CLOSE_AND_PROGRESS, idempotency_key"],
            ["Run statuses", "pending, processing, completed, failed"],
            ["Item outcomes", "promote, graduate, skip"],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-border/70 bg-surface px-4 py-3">
              <p className="text-[11px] font-semibold uppercase text-text-muted">{label}</p>
              <p className="mt-2 break-words text-sm font-semibold text-text">{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-2 text-sm text-text-muted">
          <GitBranch className="h-4 w-4 text-primary" />
          {selectedSession ? (
            <>
              Selected: <span className="font-semibold text-text">{selectedSession.name}</span>
              <Badge variant={selectedSession.status === "open" ? "success" : "warning"}>
                {selectedSession.status}
              </Badge>
            </>
          ) : (
            "Select a session to inspect progression eligibility."
          )}
        </div>
      </WorkspacePanel>

      <TypedConfirmationDialog
        open={confirmingClose}
        title="Close session and progress"
        description={selectedSession?.name || "Selected academic session"}
        confirmationText={CONFIRM_CLOSE_AND_PROGRESS}
        confirmLabel="Close and progress"
        variant="danger"
        isLoading={saving}
        onConfirm={runCloseAndProgress}
        onCancel={() => setConfirmingClose(false)}
      />
    </div>
  );
}

export default ProgressionWorkspace;
