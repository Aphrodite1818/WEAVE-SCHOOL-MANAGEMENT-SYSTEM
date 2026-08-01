import { Calculator, ClipboardList, Save, Search, Send, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  SelectField,
  TextField,
} from "../../components/academic/AcademicSelectors";
import { displayTerm } from "../../components/academic/academicDisplay";
import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import assessmentLimitsService from "../../services/assessmentLimitsService";
import { getErrorMessage } from "../../services/api";
import { bulkAcademicService } from "../../services/bulkAcademicService";
import { subscriptionService } from "../../services/subscriptionService";

const emptyScores = {
  test_score: "",
  assessment_score: "",
  exam_score: "",
};
const scoreFields = ["test_score", "assessment_score", "exam_score"];
const scoreLabels = {
  test_score: "Test",
  assessment_score: "Assessment",
  exam_score: "Exam",
};
const toNullableScore = (value) =>
  value === "" || value === null || value === undefined ? null : Number(value);
const scoreTotal = (draft) =>
  scoreFields.reduce((sum, field) => sum + (Number(draft[field]) || 0), 0);
const isEditable = (result) => !result || result.status === "draft";
const displayStudent = (student) =>
  [student.first_name, student.last_name].filter(Boolean).join(" ") ||
  student.admission_number ||
  "Student";
const assignmentLabel = (assignment) =>
  `${assignment.subject_name || "Subject"} - ${assignment.class_name || "Class"} ${assignment.class_arm || ""}`.trim();

function TeacherResultsPage() {
  const [assignments, setAssignments] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [limits, setLimits] = useState(null);
  const [bulkSubmissionAllowed, setBulkSubmissionAllowed] = useState(false);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [academicSessionId, setAcademicSessionId] = useState("");
  const [academicTermId, setAcademicTermId] = useState("");
  const [students, setStudents] = useState([]);
  const [studentSearch, setStudentSearch] = useState("");
  const [results, setResults] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState("");
  const [isBulkSubmitting, setIsBulkSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  useEffect(() => {
    let mounted = true;
    async function loadInitialData() {
      setIsLoading(true);
      setError(null);
      try {
        const [
          assignmentResponse,
          sessionResponse,
          termResponse,
          limitsResponse,
          entitlementResponse,
        ] = await Promise.all([
          academicService.listMyTeacherAssignments(),
          academicService.listTeacherSessions(),
          academicService.listTeacherTerms(),
          assessmentLimitsService.getTeacherLimits(),
          subscriptionService.getActorEntitlements().catch(() => null),
        ]);
        if (!mounted) return;
        const assignmentItems = assignmentResponse?.items || [];
        const sessionItems = sessionResponse?.items || [];
        const termItems = termResponse?.items || [];
        setAssignments(assignmentItems);
        setSessions(sessionItems);
        setTerms(termItems);
        setLimits(limitsResponse);
        setBulkSubmissionAllowed(
          Boolean(
            entitlementResponse?.features?.bulk_academic_operations,
          ),
        );
        setSelectedAssignmentId(assignmentItems[0]?.id || "");
        setAcademicSessionId(
          sessionItems.find((item) => item.is_current)?.id ||
            sessionItems[0]?.id ||
            "",
        );
        setAcademicTermId(
          termItems.find((item) => item.is_current)?.id ||
            termItems[0]?.id ||
            "",
        );
      } catch (err) {
        if (mounted) {
          setError(
            getErrorMessage(err, "Could not load score entry workspace."),
          );
        }
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    loadInitialData();
    return () => {
      mounted = false;
    };
  }, []);

  const selectedAssignment = useMemo(
    () => assignments.find((item) => item.id === selectedAssignmentId),
    [assignments, selectedAssignmentId],
  );
  const termsForSession = useMemo(
    () =>
      terms.filter(
        (item) =>
          !academicSessionId ||
          item.academic_session_id === academicSessionId,
      ),
    [terms, academicSessionId],
  );

  useEffect(() => {
    if (
      !termsForSession.length ||
      termsForSession.some((item) => item.id === academicTermId)
    ) {
      return;
    }
    setAcademicTermId(
      termsForSession.find((item) => item.is_current)?.id ||
        termsForSession[0].id,
    );
  }, [termsForSession, academicTermId]);

  useEffect(() => {
    setDrafts({});
    setStudentSearch("");
  }, [selectedAssignmentId, academicSessionId, academicTermId]);

  useEffect(() => {
    let mounted = true;
    async function loadStudents() {
      if (!selectedAssignmentId) {
        setStudents([]);
        return;
      }
      try {
        const response = await academicService.listMyAssignmentStudents(
          selectedAssignmentId,
          { limit: 100 },
        );
        if (mounted) setStudents(response?.items || []);
      } catch (err) {
        if (mounted) setStudents([]);
        showError(
          getErrorMessage(
            err,
            "Could not load students for this class-subject.",
          ),
        );
      }
    }
    loadStudents();
    return () => {
      mounted = false;
    };
  }, [selectedAssignmentId, showError]);

  const loadResults = async () => {
    if (
      !selectedAssignment?.class_id ||
      !academicSessionId ||
      !academicTermId
    ) {
      setResults([]);
      return;
    }
    const response = await academicService.listTeacherResults({
      class_id: selectedAssignment.class_id,
      academic_session_id: academicSessionId,
      academic_term_id: academicTermId,
    });
    setResults(
      (response?.items || []).filter(
        (item) => item.teacher_assignment_id === selectedAssignmentId,
      ),
    );
  };

  useEffect(() => {
    loadResults().catch(() => setResults([]));
  }, [
    selectedAssignmentId,
    academicSessionId,
    academicTermId,
    selectedAssignment?.class_id,
  ]);

  const resultByStudent = useMemo(
    () =>
      Object.fromEntries(
        results.map((result) => [result.student_id, result]),
      ),
    [results],
  );
  const visibleStudents = useMemo(() => {
    const query = studentSearch.trim().toLowerCase();
    if (!query) return students;
    return students.filter((student) =>
      `${displayStudent(student)} ${student.admission_number || ""}`
        .toLowerCase()
        .includes(query),
    );
  }, [studentSearch, students]);

  const maximumFor = (field) => {
    if (field === "test_score") return limits?.test_max;
    if (field === "assessment_score") return limits?.assessment_max;
    return limits?.exam_max;
  };

  const updateDraft = (studentId, field, value) => {
    if (!isEditable(resultByStudent[studentId])) return;
    setDrafts((current) => ({
      ...current,
      [studentId]: {
        ...emptyScores,
        ...(resultByStudent[studentId] || {}),
        ...(current[studentId] || {}),
        [field]: value,
      },
    }));
  };

  const validateDraft = (draft, forSubmission) => {
    if (!limits?.is_configured) {
      showWarning(
        "Assessment limits have not been configured by the school admin.",
      );
      return false;
    }
    for (const field of scoreFields) {
      const value = toNullableScore(draft[field]);
      const maximum = Number(maximumFor(field));
      if (forSubmission && value === null) {
        showWarning(
          "All three assessment scores are required before submitting.",
        );
        return false;
      }
      if (value !== null && (value < 0 || value > maximum)) {
        showWarning(
          `${scoreLabels[field]} must be between 0 and ${maximum}.`,
        );
        return false;
      }
    }
    return true;
  };

  const saveResult = async (studentId, status) => {
    const existing = resultByStudent[studentId];
    if (!isEditable(existing)) {
      showError(
        "Only draft results can be edited. Submitted results cannot return to draft.",
      );
      return;
    }
    const draft = {
      ...emptyScores,
      ...(existing || {}),
      ...(drafts[studentId] || {}),
    };
    if (!validateDraft(draft, status === "submitted")) return;

    setIsSaving(`${studentId}-${status}`);
    try {
      await academicService.saveTeacherResult({
        student_id: studentId,
        teacher_assignment_id: selectedAssignmentId,
        academic_session_id: academicSessionId,
        academic_term_id: academicTermId,
        test_score: toNullableScore(draft.test_score),
        assessment_score: toNullableScore(draft.assessment_score),
        exam_score: toNullableScore(draft.exam_score),
        status,
      });
      await loadResults();
      setDrafts((current) => {
        const next = { ...current };
        delete next[studentId];
        return next;
      });
      showSuccess(
        status === "submitted"
          ? "Complete result submitted."
          : "Draft saved.",
      );
    } catch (err) {
      showError(getErrorMessage(err, "Could not save scores."));
    } finally {
      setIsSaving("");
    }
  };

  const submitAllSavedDrafts = async () => {
    if (!bulkSubmissionAllowed) {
      showWarning(
        "Bulk result submission requires an active paid school plan.",
      );
      return;
    }
    if (
      !selectedAssignment?.class_id ||
      !selectedAssignmentId ||
      !academicSessionId ||
      !academicTermId
    ) {
      showWarning("Select an assignment, session, and term first.");
      return;
    }
    setIsBulkSubmitting(true);
    try {
      const response = await bulkAcademicService.submitTeacherResults({
        class_id: selectedAssignment.class_id,
        teacher_assignment_id: selectedAssignmentId,
        academic_session_id: academicSessionId,
        academic_term_id: academicTermId,
        confirmation: "BULK_SUBMIT_RESULTS",
      });
      await loadResults();
      showSuccess(
        `${response?.processed || 0} saved draft result${
          response?.processed === 1 ? "" : "s"
        } submitted.`,
      );
      if (response?.skipped?.length) {
        showWarning(
          `${response.skipped.length} incomplete or ineligible result${
            response.skipped.length === 1 ? " was" : "s were"
          } skipped.`,
        );
      }
    } catch (err) {
      showError(
        getErrorMessage(err, "Could not submit saved draft results."),
      );
    } finally {
      setIsBulkSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title="Score Entry">
        <LoadingState label="Loading score entry workspace..." />
      </DashboardLayout>
    );
  }

  const submittedCount = results.filter(
    (result) => result.status !== "draft",
  ).length;
  const draftCount = results.filter(
    (result) => result.status === "draft",
  ).length;

  return (
    <DashboardLayout
      role="teacher"
      title="Score Entry"
      description="Save draft results and submit complete rows for active class-subject assignments."
    >
      {error ? (
        <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">
          {error}
        </div>
      ) : null}
      {!limits?.is_configured ? (
        <div className="rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-900">
          Score entry is disabled until the school admin configures assessment maximums.
        </div>
      ) : null}
      {!bulkSubmissionAllowed ? (
        <div className="rounded-xl border border-info/30 bg-info-soft px-4 py-3 text-sm font-medium text-info">
          Individual result entry remains available. “Submit all saved drafts” is a paid-plan bulk operation.
        </div>
      ) : null}

      <Card className="p-4 sm:p-5">
        <div className="grid gap-3 lg:grid-cols-3">
          <SelectField
            label="Assigned class-subject"
            value={selectedAssignmentId}
            onChange={setSelectedAssignmentId}
          >
            {assignments.length === 0 ? (
              <option value="">No assigned subjects</option>
            ) : (
              assignments.map((assignment) => (
                <option key={assignment.id} value={assignment.id}>
                  {assignmentLabel(assignment)}
                </option>
              ))
            )}
          </SelectField>
          <SelectField
            label="Academic session"
            value={academicSessionId}
            onChange={(value) => {
              setAcademicSessionId(value);
              setAcademicTermId("");
            }}
          >
            {sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {session.name}
                {session.is_current ? " (Current)" : ""}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Academic term"
            value={academicTermId}
            onChange={setAcademicTermId}
          >
            {termsForSession.map((term) => (
              <option key={term.id} value={term.id}>
                {displayTerm(term.name)}
                {term.is_current ? " (Current)" : ""}
              </option>
            ))}
          </SelectField>
        </div>
        {selectedAssignment ? (
          <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1.3fr)_repeat(3,minmax(0,0.45fr))]">
            <div className="rounded-2xl border border-border bg-surface-muted/30 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                Score context
              </p>
              <p className="mt-1 font-semibold text-text">
                {assignmentLabel(selectedAssignment)}
              </p>
            </div>
            <MiniStat label="Students" value={students.length} />
            <MiniStat label="Drafts" value={draftCount} />
            <MiniStat label="Submitted" value={submittedCount} />
          </div>
        ) : null}
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="section-title">
              Class-subject roster and score entry
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              Submitted, approved, and locked rows are read-only. Save rows first, then submit complete drafts.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Users className="hidden h-5 w-5 text-primary sm:block" />
            <Button
              type="button"
              variant="success"
              onClick={submitAllSavedDrafts}
              disabled={
                !bulkSubmissionAllowed ||
                isBulkSubmitting ||
                draftCount === 0 ||
                !limits?.is_configured
              }
              title={
                bulkSubmissionAllowed
                  ? "Submit every complete saved draft in this class-subject"
                  : "Requires an active paid school plan"
              }
            >
              <Send className="h-4 w-4" />
              {isBulkSubmitting
                ? "Submitting..."
                : bulkSubmissionAllowed
                  ? "Submit all saved drafts"
                  : "Paid plan required"}
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <label className="block min-w-0 flex-1">
            <span className="mb-1.5 block text-sm font-semibold text-text-soft">
              Search roster
            </span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-faint" />
              <input
                type="search"
                value={studentSearch}
                onChange={(event) => setStudentSearch(event.target.value)}
                placeholder="Student name or admission number"
                className="input-base pl-10"
              />
            </div>
          </label>
          <p className="text-sm font-medium text-text-muted">
            {visibleStudents.length} of {students.length} students
          </p>
        </div>
      </Card>

      <section className="mobile-scroll-list grid gap-3">
        {students.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="No students found"
            description="Select an assigned class-subject with enrolled students."
          />
        ) : visibleStudents.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No matching students"
            description="Try another student name or admission number. Unsaved scores remain in place."
          />
        ) : (
          visibleStudents.map((student) => {
            const existing = resultByStudent[student.id];
            const editable = isEditable(existing);
            const draft = {
              ...emptyScores,
              ...(existing || {}),
              ...(drafts[student.id] || {}),
            };
            const complete = scoreFields.every(
              (field) => toNullableScore(draft[field]) !== null,
            );
            return (
              <Card key={student.id} className="p-3 sm:p-4">
                <div className="grid gap-3 xl:grid-cols-[minmax(160px,1fr)_repeat(3,minmax(100px,0.5fr))_minmax(145px,0.7fr)_minmax(130px,auto)] xl:items-end">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-text">
                      {displayStudent(student)}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {student.admission_number || "No admission number"}
                    </p>
                    <Badge
                      variant={
                        existing?.status === "draft"
                          ? "warning"
                          : existing
                            ? "success"
                            : "warning"
                      }
                    >
                      {existing?.status || "pending"}
                    </Badge>
                  </div>
                  {scoreFields.map((field) => (
                    <TextField
                      key={field}
                      label={`${scoreLabels[field]} / ${maximumFor(field) ?? "-"}`}
                      type="number"
                      min="0"
                      max={maximumFor(field) ?? undefined}
                      value={draft[field] ?? ""}
                      onChange={(value) =>
                        updateDraft(student.id, field, value)
                      }
                      disabled={!editable || !limits?.is_configured}
                    />
                  ))}
                  <div className="rounded-xl border border-border bg-surface px-3 py-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      Total / grade
                    </p>
                    <p className="mt-1 font-semibold text-text">
                      <Calculator className="mr-1 inline h-4 w-4" />
                      {scoreTotal(draft) || "--"} / {existing?.grade || "--"}
                    </p>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row xl:flex-col">
                    <Button
                      size="xs"
                      onClick={() => saveResult(student.id, "draft")}
                      disabled={
                        !editable ||
                        !limits?.is_configured ||
                        isSaving === `${student.id}-draft`
                      }
                    >
                      <Save className="h-3.5 w-3.5" />
                      Save Draft
                    </Button>
                    <Button
                      size="xs"
                      variant="success"
                      onClick={() => saveResult(student.id, "submitted")}
                      disabled={
                        !editable ||
                        !complete ||
                        !limits?.is_configured ||
                        isSaving === `${student.id}-submitted`
                      }
                    >
                      <Send className="h-3.5 w-3.5" />
                      {editable ? "Submit" : "Submitted"}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })
        )}
      </section>
    </DashboardLayout>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-2xl border border-border bg-surface-muted/30 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold text-text">{value}</p>
    </div>
  );
}

export default TeacherResultsPage;
