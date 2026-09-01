import { ClipboardList, GraduationCap, LockKeyhole } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { studentService } from "../../services/studentService";
import {
  Input,
  RecordList,
  SelectControl,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const BLANK_FORM = {
  result_id: "",
  student_id: "",
  teacher_assignment_id: "",
  component_scores: {},
};

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  item?.display_name ||
  [item?.academic_level_name, item?.arm_label || item?.arm]
    .filter(Boolean)
    .join(" ") ||
  "Unnamed class";

const studentLabel = (item) =>
  `${[item?.first_name, item?.last_name].filter(Boolean).join(" ") || "Student"} · ${item?.admission_number || "No admission number"}`;

const assignmentLabel = (item) =>
  `${item?.subject_name || "Subject"} · ${item?.teacher_name || item?.teacher_staff_id || "Teacher"}`;

const scoreValue = (value) =>
  value === "" || value === null || value === undefined ? null : Number(value);

const readableTerm = (item) =>
  String(item?.display_name || item?.name || "No term").replaceAll("_", " ");

const statusTitle = (status) =>
  ({
    submitted: "Submit result",
    approved: "Approve result",
    locked: "Lock result",
  })[status] || "Confirm result action";

const statusDescription = (status, item) =>
  ({
    submitted: `Submit ${item.student_name || "this student's"} ${item.subject_name || "result"} for administrative review?`,
    approved: `Approve ${item.student_name || "this student's"} ${item.subject_name || "result"} after reviewing the recorded scores?`,
    locked: `Lock ${item.student_name || "this student's"} ${item.subject_name || "result"}? Locked results become final for report-card workflows until explicitly reopened.`,
  })[status] || "Confirm this result lifecycle action.";

const badgeVariant = (status) => {
  if (status === "draft") return "warning";
  if (status === "locked") return "default";
  return "success";
};

function ResultsWorkspace({ activeTab, onContextChange }) {
  const [, setSearchParams] = useSearchParams();
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [classes, setClasses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [students, setStudents] = useState([]);
  const [results, setResults] = useState([]);
  const [assessmentConfig, setAssessmentConfig] = useState(null);
  const [contextFilters, setContextFilters] = useState({
    class_id: "",
    academic_session_id: "",
    academic_term_id: "",
  });
  const [pageSearch, setPageSearch] = useState("");
  const [form, setForm] = useState(BLANK_FORM);
  const [pendingAction, setPendingAction] = useState(null);
  const [reopenTarget, setReopenTarget] = useState(null);
  const [reopenReason, setReopenReason] = useState("");
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const resetForm = () => setForm(BLANK_FORM);

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        sessionResponse,
        termResponse,
        classResponse,
        assignmentResponse,
        configResponse,
      ] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        classService.getClasses({ limit: 100, activeOnly: true }),
        academicService.listTeacherAssignments({ active_only: true, limit: 100 }),
        academicService.getActiveAssessmentScheme().catch(() => null),
      ]);

      const nextSessions = asItems(sessionResponse);
      const nextTerms = asItems(termResponse);
      const nextClasses = asItems(classResponse);
      const currentSession = nextSessions.find((item) => item.is_current) || null;
      const currentTerm = nextTerms.find((item) => item.is_current) || null;

      setSessions(nextSessions);
      setTerms(nextTerms);
      setClasses(nextClasses);
      setAssignments(asItems(assignmentResponse).filter((item) => item.is_active));
      setAssessmentConfig(configResponse || null);
      setContextFilters((current) => ({
        class_id: current.class_id || nextClasses[0]?.id || "",
        academic_session_id:
          current.academic_session_id || currentSession?.id || nextSessions[0]?.id || "",
        academic_term_id:
          current.academic_term_id || currentTerm?.id || nextTerms[0]?.id || "",
      }));
      onContextChange?.({ currentSession, currentTerm });
    } catch (requestError) {
      const message = getErrorMessage(requestError, "Could not load results workspace.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [onContextChange, showError]);

  const loadClassStudents = useCallback(async () => {
    if (!contextFilters.class_id) {
      setStudents([]);
      return;
    }
    try {
      const response = await studentService.getAdminStudents({
        classId: contextFilters.class_id,
        status: "active",
        limit: 100,
      });
      setStudents(asItems(response));
    } catch (requestError) {
      setStudents([]);
      showError(
        getErrorMessage(requestError, "Could not load students for this class."),
      );
    }
  }, [contextFilters.class_id, showError]);

  const loadResults = useCallback(async () => {
    if (
      !contextFilters.class_id ||
      !contextFilters.academic_session_id ||
      !contextFilters.academic_term_id
    ) {
      setResults([]);
      return;
    }
    try {
      const response = await academicService.listAdminResults({
        class_id: contextFilters.class_id,
        academic_session_id: contextFilters.academic_session_id,
        academic_term_id: contextFilters.academic_term_id,
        search: pageSearch || undefined,
        limit: 100,
      });
      setResults(asItems(response));
    } catch (requestError) {
      setResults([]);
      showError(getErrorMessage(requestError, "Could not load results."));
    }
  }, [contextFilters, pageSearch, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadClassStudents();
  }, [loadClassStudents]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  useEffect(() => {
    setPageSearch("");
    setPendingAction(null);
    setReopenTarget(null);
    setReopenReason("");
    if (activeTab !== "entry") resetForm();
  }, [activeTab]);

  const selectedClass = classes.find((item) => item.id === contextFilters.class_id);
  const selectedSession = sessions.find(
    (item) => item.id === contextFilters.academic_session_id,
  );
  const selectedTerm = terms.find(
    (item) => item.id === contextFilters.academic_term_id,
  );
  const periodEditable = Boolean(
    selectedSession?.status === "open" &&
      selectedSession?.is_current &&
      selectedTerm?.status === "open" &&
      selectedTerm?.is_current &&
      selectedTerm?.academic_session_id === selectedSession?.id,
  );
  const limitsConfigured = Boolean(
    assessmentConfig?.is_configured && assessmentConfig.components?.length,
  );

  const sessionOptions = sessions.map((item) => ({ value: item.id, label: item.name }));
  const termOptions = terms
    .filter(
      (item) =>
        !contextFilters.academic_session_id ||
        item.academic_session_id === contextFilters.academic_session_id,
    )
    .map((item) => ({ value: item.id, label: readableTerm(item) }));
  const classOptions = classes.map((item) => ({ value: item.id, label: classLabel(item) }));
  const assignmentOptions = assignments
    .filter((item) => item.class_id === contextFilters.class_id)
    .map((item) => ({ value: item.id, label: assignmentLabel(item) }));
  const studentOptions = students.map((item) => ({ value: item.id, label: studentLabel(item) }));

  const statusCounts = useMemo(
    () =>
      results.reduce(
        (counts, item) => ({
          ...counts,
          [item.status]: (counts[item.status] || 0) + 1,
        }),
        { draft: 0, submitted: 0, approved: 0, locked: 0 },
      ),
    [results],
  );

  const visibleResults = useMemo(() => {
    if (["draft", "submitted", "approved", "locked"].includes(activeTab)) {
      return results.filter((item) => item.status === activeTab);
    }
    return results;
  }, [activeTab, results]);

  const scoreTotal = (assessmentConfig?.components || []).reduce(
    (sum, component) => sum + (Number(form.component_scores?.[component.id]) || 0),
    0,
  );
  const totalMaximum = limitsConfigured
    ? Number(assessmentConfig.total_maximum_score)
    : null;

  const validateScores = () => {
    if (!limitsConfigured) {
      showWarning("Configure and activate an assessment scheme before entering scores.");
      return false;
    }
    for (const component of assessmentConfig.components) {
      const value = form.component_scores?.[component.id];
      const maximum = component.maximum_score;
      if (
        value !== "" &&
        (Number(value) < 0 || Number(value) > Number(maximum))
      ) {
        showWarning(`${component.name} must be between 0 and ${maximum}.`);
        return false;
      }
    }
    return true;
  };

  const saveDraft = async (event) => {
    event.preventDefault();
    if (!periodEditable) {
      showWarning("Results can only be edited in the current open session and term.");
      return;
    }
    if (!form.student_id || !form.teacher_assignment_id) {
      showWarning("Select a student and subject assignment.");
      return;
    }
    if (!validateScores()) return;

    setSaving("result");
    try {
      await academicService.saveAdminResult({
        student_id: form.student_id,
        teacher_assignment_id: form.teacher_assignment_id,
        academic_session_id: contextFilters.academic_session_id,
        academic_term_id: contextFilters.academic_term_id,
        component_scores: assessmentConfig.components.map((component) => ({
          assessment_component_id: component.id,
          score: scoreValue(form.component_scores?.[component.id]),
        })),
        status: "draft",
      });
      showSuccess(form.result_id ? "Draft result updated." : "Draft result saved.");
      resetForm();
      await loadResults();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not save result draft."));
    } finally {
      setSaving("");
    }
  };

  const handleEditScore = (item) => {
    setForm({
      result_id: item.id,
      student_id: item.student_id || "",
      teacher_assignment_id: item.teacher_assignment_id || "",
      component_scores: Object.fromEntries(
        (item.components || []).map((component) => [
          component.assessment_component_id,
          component.score ?? "",
        ]),
      ),
    });
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("view", "entry");
        next.delete("tab");
        return next;
      },
      { replace: true },
    );
  };

  const executeLifecycleAction = async () => {
    if (!pendingAction) return;
    const { item, status } = pendingAction;
    setSaving(item.id);
    try {
      await academicService.updateResultStatus(item.id, { status });
      showSuccess(`Result moved to ${status}.`);
      setPendingAction(null);
      await loadResults();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not update result status."));
    } finally {
      setSaving("");
    }
  };

  const reopenResult = async () => {
    if (!reopenTarget || !reopenReason.trim()) return;
    setSaving(reopenTarget.id);
    try {
      await academicService.reopenResult(reopenTarget.id, {
        reason: reopenReason.trim(),
      });
      showSuccess("Result reopened for correction.");
      setReopenTarget(null);
      setReopenReason("");
      await loadResults();
    } catch (requestError) {
      showError(getErrorMessage(requestError, "Could not reopen result."));
    } finally {
      setSaving("");
    }
  };

  const contextSummary = (
    <div className="rounded-xl border border-border/70 bg-surface px-4 py-3 text-sm text-text-muted">
      <span className="font-semibold text-text">Selected context:</span>{" "}
      {classLabel(selectedClass)} · {selectedSession?.name || "No session"} · {readableTerm(selectedTerm)}
    </div>
  );

  const resultActions = (item) => (
    <ResultActions
      item={item}
      periodEditable={periodEditable}
      busy={saving === item.id}
      onEdit={handleEditScore}
      onTransition={(status) => setPendingAction({ item, status })}
      onReopen={() => {
        setReopenTarget(item);
        setReopenReason("");
      }}
    />
  );

  const resultsList = (
    <RecordList
      title={`${activeTab.charAt(0).toUpperCase()}${activeTab.slice(1)} results`}
      description={`${visibleResults.length} result row${visibleResults.length === 1 ? "" : "s"} in this lifecycle stage.`}
      items={visibleResults}
      emptyIcon={ClipboardList}
      emptyTitle={`No ${activeTab} results`}
      emptyDescription="No records in this stage match the selected class, academic period, and search."
      renderTitle={(item) => item.student_name || item.admission_number || "Student"}
      renderMeta={(item) => item.subject_name || item.subject_code || "Subject"}
      renderDescription={(item) =>
        `Total ${item.total_score ?? "–"}${item.maximum_score != null ? `/${item.maximum_score}` : ""} · Grade ${item.grade || "Pending"}`
      }
      renderStatus={(item) => item.status}
      renderActions={resultActions}
      renderInspector={(item) => (
        <ResultInspector item={item} actions={resultActions(item)} />
      )}
      actions={
        <Input
          label="Search"
          value={pageSearch}
          placeholder="Student or subject"
          onChange={(event) => setPageSearch(event.target.value)}
        />
      }
    />
  );

  if (error && !loading) {
    return (
      <WorkspacePanel title="Results unavailable">
        <p className="text-sm text-error">{error}</p>
        <Button type="button" className="mt-4" onClick={loadBase}>
          Retry
        </Button>
      </WorkspacePanel>
    );
  }

  let pageContent;
  if (activeTab === "overview") {
    pageContent = (
      <WorkspacePanel
        title="Results context"
        description="Choose the class and academic period once. Lifecycle pages reuse this selection until it changes."
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <SelectControl
            label="Class"
            value={contextFilters.class_id}
            onChange={(value) => {
              setContextFilters((current) => ({ ...current, class_id: value }));
              resetForm();
            }}
            options={classOptions}
            required
          />
          <SelectControl
            label="Academic session"
            value={contextFilters.academic_session_id}
            onChange={(value) => {
              const nextTerm =
                terms.find((item) => item.academic_session_id === value && item.is_current) ||
                terms.find((item) => item.academic_session_id === value);
              setContextFilters((current) => ({
                ...current,
                academic_session_id: value,
                academic_term_id: nextTerm?.id || "",
              }));
              resetForm();
            }}
            options={sessionOptions}
            required
          />
          <SelectControl
            label="Academic term"
            value={contextFilters.academic_term_id}
            onChange={(value) => {
              setContextFilters((current) => ({ ...current, academic_term_id: value }));
              resetForm();
            }}
            options={termOptions}
            required
          />
        </div>

        <div
          className={`mt-4 rounded-xl border px-4 py-3 text-sm ${
            periodEditable
              ? "border-success/30 bg-success/5 text-success"
              : "border-warning/30 bg-warning/5 text-warning"
          }`}
        >
          {periodEditable
            ? "Current period is open. Score entry and lifecycle actions are available."
            : "The selected period is read-only. Choose the current open session and term to make changes."}
        </div>

        {!limitsConfigured ? (
          <div className="mt-3 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning">
            No assessment scheme is active. Score entry remains unavailable until an admin activates one under Grading.
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-2 overflow-hidden rounded-xl border border-border/70 sm:grid-cols-4">
          {[
            ["Draft", statusCounts.draft],
            ["Submitted", statusCounts.submitted],
            ["Approved", statusCounts.approved],
            ["Locked", statusCounts.locked],
          ].map(([label, count], index) => (
            <div
              key={label}
              className={`px-4 py-3 ${index ? "border-l border-border/70" : ""}`}
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">{label}</p>
              <p className="mt-1 text-xl font-semibold text-text">{count}</p>
            </div>
          ))}
        </div>
      </WorkspacePanel>
    );
  } else if (activeTab === "entry") {
    pageContent = (
      <div className="space-y-4">
        {contextSummary}
        <WorkspacePanel
          title={form.result_id ? "Edit draft scores" : "Score entry"}
          description="Enter the configured assessment components and save the record as a draft."
        >
          {!limitsConfigured ? (
            <p className="rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">
              No assessment scheme is active. Open Grading → Assessment Scheme before entering scores.
            </p>
          ) : null}
          <form className="mt-3 space-y-3" onSubmit={saveDraft}>
            <div className="grid gap-3 lg:grid-cols-2">
              <SelectControl
                label="Student"
                value={form.student_id}
                onChange={(value) =>
                  setForm((current) => ({ ...current, student_id: value }))
                }
                options={studentOptions}
                placeholder="Select student"
                disabled={!periodEditable || !limitsConfigured || Boolean(form.result_id)}
                required
              />
              <SelectControl
                label="Subject assignment"
                value={form.teacher_assignment_id}
                onChange={(value) =>
                  setForm((current) => ({
                    ...current,
                    teacher_assignment_id: value,
                  }))
                }
                options={assignmentOptions}
                placeholder={
                  assignmentOptions.length === 0
                    ? "No active assignments for this class"
                    : "Select assignment"
                }
                disabled={
                  !periodEditable ||
                  !limitsConfigured ||
                  assignmentOptions.length === 0 ||
                  Boolean(form.result_id)
                }
                required
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {(assessmentConfig?.components || []).map((component) => (
                <Input
                  key={component.id}
                  label={`${component.name} (0–${component.maximum_score})`}
                  type="number"
                  min="0"
                  max={component.maximum_score}
                  disabled={!periodEditable || !limitsConfigured}
                  value={form.component_scores?.[component.id] ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      component_scores: {
                        ...current.component_scores,
                        [component.id]: event.target.value,
                      },
                    }))
                  }
                />
              ))}
            </div>
            <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-3 py-2 text-sm text-text-muted">
              Combined score: <span className="font-semibold text-text">{scoreTotal}</span>
              {totalMaximum != null ? ` / ${totalMaximum}` : ""}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="submit"
                disabled={
                  !periodEditable ||
                  !limitsConfigured ||
                  saving === "result" ||
                  assignmentOptions.length === 0
                }
              >
                {saving === "result"
                  ? "Saving..."
                  : form.result_id
                    ? "Update draft"
                    : "Save draft"}
              </Button>
              {form.result_id ? (
                <Button type="button" variant="outline" onClick={resetForm}>
                  Cancel edit
                </Button>
              ) : null}
            </div>
          </form>
        </WorkspacePanel>
      </div>
    );
  } else {
    pageContent = (
      <div className="space-y-4">
        {contextSummary}
        {resultsList}
      </div>
    );
  }

  return (
    <>
      {pageContent}

      <Modal
        open={Boolean(pendingAction)}
        title={pendingAction ? statusTitle(pendingAction.status) : "Confirm result action"}
        description={
          pendingAction
            ? statusDescription(pendingAction.status, pendingAction.item)
            : ""
        }
        onClose={saving ? undefined : () => setPendingAction(null)}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              disabled={Boolean(saving)}
              onClick={() => setPendingAction(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant={pendingAction?.status === "locked" ? "danger" : "primary"}
              disabled={Boolean(saving)}
              onClick={executeLifecycleAction}
            >
              {saving ? "Saving..." : pendingAction ? statusTitle(pendingAction.status) : "Confirm"}
            </Button>
          </div>
        }
      />

      <Modal
        open={Boolean(reopenTarget)}
        title="Reopen locked result"
        description="Reopening returns the result to draft and marks generated report cards outdated."
        onClose={saving ? undefined : () => setReopenTarget(null)}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="outline"
              disabled={Boolean(saving)}
              onClick={() => setReopenTarget(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              disabled={Boolean(saving) || !reopenReason.trim()}
              onClick={reopenResult}
            >
              {saving ? "Reopening..." : "Reopen result"}
            </Button>
          </div>
        }
      >
        <Input
          label="Reason"
          value={reopenReason}
          onChange={(event) => setReopenReason(event.target.value)}
          placeholder="Explain why this locked result must be corrected"
        />
      </Modal>
    </>
  );
}

function ResultActions({
  item,
  periodEditable,
  busy,
  onEdit,
  onTransition,
  onReopen,
}) {
  if (item.status === "draft") {
    return (
      <>
        <Button
          type="button"
          size="small"
          variant="outline"
          disabled={!periodEditable || busy}
          onClick={() => onEdit(item)}
        >
          Edit scores
        </Button>
        <Button
          type="button"
          size="small"
          variant="success"
          disabled={!periodEditable || busy}
          onClick={() => onTransition("submitted")}
        >
          Submit
        </Button>
      </>
    );
  }
  if (item.status === "submitted") {
    return (
      <Button
        type="button"
        size="small"
        variant="success"
        disabled={!periodEditable || busy}
        onClick={() => onTransition("approved")}
      >
        Approve
      </Button>
    );
  }
  if (item.status === "approved") {
    return (
      <Button
        type="button"
        size="small"
        variant="danger"
        disabled={!periodEditable || busy}
        onClick={() => onTransition("locked")}
      >
        Lock
      </Button>
    );
  }
  return (
    <Button
      type="button"
      size="small"
      variant="outline"
      disabled={!periodEditable || busy}
      onClick={onReopen}
    >
      Reopen
    </Button>
  );
}

function ResultInspector({ item, actions }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-surface">
      <div className="border-b border-border/70 px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-text">
              {item.student_name || item.admission_number || "Student"}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {item.subject_name || item.subject_code || "Subject"}
            </p>
          </div>
          <Badge variant={badgeVariant(item.status)}>{item.status}</Badge>
        </div>
      </div>

      <div className="divide-y divide-border/70">
        <section className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            Scores
          </p>
          <dl className="mt-3 space-y-2 text-sm">
            {(item.components || []).map((component) => (
              <div key={component.assessment_component_id || component.name} className="flex justify-between gap-4">
                <dt className="text-text-muted">{component.name}</dt>
                <dd className="font-semibold text-text">
                  {component.score ?? "–"}
                  {component.maximum_score != null ? `/${component.maximum_score}` : ""}
                </dd>
              </div>
            ))}
            <div className="flex justify-between gap-4 border-t border-border/70 pt-2">
              <dt className="font-semibold text-text">Total</dt>
              <dd className="font-semibold text-text">
                {item.total_score ?? "–"}
                {item.maximum_score != null ? `/${item.maximum_score}` : ""}
              </dd>
            </div>
          </dl>
        </section>

        <section className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            Outcome
          </p>
          <div className="mt-2 flex items-center gap-2 text-sm text-text-muted">
            <GraduationCap className="h-4 w-4" />
            Grade: <span className="font-semibold text-text">{item.grade || "Pending"}</span>
          </div>
          {item.status === "locked" ? (
            <div className="mt-3 flex items-center gap-2 rounded-lg bg-surface-muted/50 px-3 py-2 text-xs text-text-muted">
              <LockKeyhole className="h-4 w-4" /> Finalized and read-only
            </div>
          ) : null}
        </section>

        <section className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            Lifecycle actions
          </p>
          <div className="mt-3 flex flex-wrap gap-2">{actions}</div>
        </section>
      </div>
    </div>
  );
}

export default ResultsWorkspace;
