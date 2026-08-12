import { GitBranch } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { sessionClosureService } from "../../services/sessionClosureService";
import { studentService } from "../../services/studentService";
import { Input, SelectControl, WorkspacePanel } from "./AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "./TypedConfirmationDialog";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];
const CONFIRM_CLOSE_AND_PROGRESS = "START_SESSION_CLOSING";

function ProgressionWorkspace({ activeTab }) {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [confirmingClose, setConfirmingClose] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [runDetail, setRunDetail] = useState(null);
  const [studentProgressions, setStudentProgressions] = useState({});
  const [classes, setClasses] = useState([]);
  const [placementByStudent, setPlacementByStudent] = useState({});
  const [destinationByStudent, setDestinationByStudent] = useState({});
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

  useEffect(() => {
    if (!["completed", "failed", "outcomes"].includes(activeTab) || !sessionId) return;
    let mounted = true;
    const loadOutcomes = async () => {
      setLoading(true);
      try {
        const [statusResponse, classResponse] = await Promise.all([
          sessionClosureService.getStatus(sessionId),
          classService.getClasses({ activeOnly: true, limit: 500 }),
        ]);
        if (!mounted) return;
        const detail = statusResponse?.progression_run || null;
        setRunDetail(detail);
        setClasses(asItems(classResponse));
        const selectionItems = (detail?.items || []).filter(
          (item) => item.action === "student_selection",
        );
        const rows = await Promise.all(
          selectionItems.map(async (item) => [
            item.student_id,
            await studentService.getStudentProgression(item.student_id),
          ]),
        );
        if (mounted) setStudentProgressions(Object.fromEntries(rows));
      } catch (error) {
        if (mounted) showError(getErrorMessage(error, "Could not load progression outcomes."));
      } finally {
        if (mounted) setLoading(false);
      }
    };
    loadOutcomes();
    return () => { mounted = false; };
  }, [activeTab, sessionId, showError]);

  const placeStudent = async (studentId) => {
    const classroomId = placementByStudent[studentId];
    if (!classroomId) return;
    setSaving(studentId);
    try {
      const updated = await studentService.placeProgressionStudent(studentId, classroomId);
      setStudentProgressions((current) => ({ ...current, [studentId]: updated }));
      setRunDetail((current) => ({
        ...current,
        items: (current?.items || []).map((item) =>
          item.student_id === studentId ? updated.item : item
        ),
      }));
      showSuccess("Student classroom placement completed.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not place this student."));
    } finally {
      setSaving(false);
    }
  };

  const updateDestination = async (studentId) => {
    const destinationId = destinationByStudent[studentId];
    if (!destinationId) return;
    setSaving(studentId);
    try {
      const updated = await studentService.overrideProgressionSelection(studentId, destinationId);
      setStudentProgressions((current) => ({ ...current, [studentId]: updated }));
      setRunDetail((current) => ({
        ...current,
        items: (current?.items || []).map((item) =>
          item.student_id === studentId ? updated.item : item
        ),
      }));
      showSuccess("Student progression destination updated.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not update this destination."));
    } finally {
      setSaving(false);
    }
  };

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
      await academicService.startSessionClosing(sessionId, {
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
        title="Progression outcomes"
        description="Review student selections and supply a concrete classroom only when level selection cannot resolve safely."
      >
        <SelectControl
          label="Academic session"
          value={sessionId}
          onChange={setSessionId}
          options={sessionOptions}
          required
        />
        <div className="mt-4 grid gap-3">
          {(runDetail?.items || []).map((item) => {
            const progression = studentProgressions[item.student_id];
            const selectedLevelId = progression?.item?.selected_level_id;
            const availableClasses = classes.filter(
              (classroom) => classroom.academic_level_id === selectedLevelId,
            );
            return (
              <div key={item.id} className="rounded-2xl border border-border/70 bg-surface p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-text">
                      {progression?.student_name || `Student ${item.student_id}`}
                    </p>
                    <p className="mt-1 text-sm text-text-muted">
                      {[progression?.admission_number, progression?.source_class_label, progression?.selected_destination_label]
                        .filter(Boolean).join(" · ") || item.reason || "No destination selected"}
                    </p>
                  </div>
                  <Badge variant={item.status === "completed" ? "success" : "warning"}>
                    {String(item.status).replaceAll("_", " ")}
                  </Badge>
                </div>
                {progression?.destinations?.length && item.status !== "completed" && item.status !== "cancelled" ? (
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
                    <div className="min-w-0 flex-1">
                      <SelectControl
                        label="Progression destination"
                        value={destinationByStudent[item.student_id] || progression.item.selected_level_id || progression.item.selected_classroom_id || ""}
                        onChange={(value) => setDestinationByStudent((current) => ({ ...current, [item.student_id]: value }))}
                        options={progression.destinations.map((destination) => ({
                          value: destination.id,
                          label: destination.label,
                        }))}
                        required
                      />
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={saving === item.student_id || !destinationByStudent[item.student_id]}
                      onClick={() => updateDestination(item.student_id)}
                    >
                      Update destination
                    </Button>
                  </div>
                ) : null}
                {item.status === "awaiting_class_placement" ? (
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
                    <div className="min-w-0 flex-1">
                      <SelectControl
                        label="Final classroom"
                        value={placementByStudent[item.student_id] || ""}
                        onChange={(value) => setPlacementByStudent((current) => ({
                          ...current,
                          [item.student_id]: value,
                        }))}
                        options={availableClasses.map((classroom) => ({
                          value: classroom.id,
                          label: `${classroom.academic_level_name} ${classroom.arm}`,
                        }))}
                        required
                      />
                    </div>
                    <Button
                      type="button"
                      disabled={saving === item.student_id || !placementByStudent[item.student_id]}
                      onClick={() => placeStudent(item.student_id)}
                    >
                      Assign class
                    </Button>
                  </div>
                ) : null}
              </div>
            );
          })}
          {!loading && !(runDetail?.items || []).length ? (
            <p className="text-sm text-text-muted">No progression outcomes for this session.</p>
          ) : null}
        </div>
      </WorkspacePanel>
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
      <WorkspacePanel
        title="Plan progression"
        description="The worker applies direct progression, creates student-selection tasks, and graduates terminal levels."
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
            ["Route", "POST /tenant-admin/academics/sessions/{session_id}/start-closing"],
            ["Payload", "confirmation: START_SESSION_CLOSING, idempotency_key"],
            ["Run statuses", "pending, processing, completed, failed"],
            ["Item states", "awaiting selection, awaiting class placement, completed, blocked, cancelled"],
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
