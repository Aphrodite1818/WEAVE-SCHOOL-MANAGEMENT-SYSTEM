import { useEffect, useMemo, useState } from "react";
import { Calculator, ClipboardList, Save, Send } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import LoadingState from "../../components/shared/LoadingState";
import EmptyState from "../../components/shared/EmptyState";
import { SelectField, TextField } from "../../components/academic/AcademicSelectors";
import { displayTerm } from "../../components/academic/academicDisplay";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { studentService } from "../../services/studentService";
import { useToast } from "../../hooks/useToast";

const emptyScores = { test_score: "", assessment_score: "", exam_score: "" };
const scoreFields = ["test_score", "assessment_score", "exam_score"];
const toNullableScore = (value) => (value === "" || value === null || value === undefined ? null : Number(value));
const scoreLabel = (field) => field.replace("_score", "").replace("_", " ");
const isSubmitted = (result) => result?.status === "submitted";
const scoreValue = (value) => (value === null || value === undefined || value === "" ? "--" : value);

function TeacherResultsPage() {
  const [assignments, setAssignments] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [academicSessionId, setAcademicSessionId] = useState("");
  const [academicTermId, setAcademicTermId] = useState("");
  const [students, setStudents] = useState([]);
  const [results, setResults] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState("");
  const [error, setError] = useState(null);
  const { showSuccess, showError } = useToast();

  useEffect(() => {
    let mounted = true;
    async function loadInitialData() {
      setIsLoading(true);
      setError(null);
      try {
        const [assignmentResponse, sessionResponse, termResponse] = await Promise.all([
          academicService.listMyTeacherAssignments(),
          academicService.listTeacherSessions(),
          academicService.listTeacherTerms(),
        ]);
        if (!mounted) return;
        const assignmentItems = assignmentResponse?.items || [];
        const sessionItems = sessionResponse?.items || [];
        const termItems = termResponse?.items || [];
        setAssignments(assignmentItems);
        setSessions(sessionItems);
        setTerms(termItems);
        setSelectedAssignmentId(assignmentItems[0]?.id || "");
        setAcademicSessionId(sessionItems.find((item) => item.is_current)?.id || sessionItems[0]?.id || "");
        setAcademicTermId(termItems.find((item) => item.is_current)?.id || termItems[0]?.id || "");
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, "Could not load result workspace."));
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
    [assignments, selectedAssignmentId]
  );

  const termsForSession = useMemo(
    () => terms.filter((item) => !academicSessionId || item.academic_session_id === academicSessionId),
    [terms, academicSessionId]
  );

  useEffect(() => {
    if (termsForSession.length > 0 && !termsForSession.some((item) => item.id === academicTermId)) {
      setAcademicTermId(termsForSession.find((item) => item.is_current)?.id || termsForSession[0].id);
    }
  }, [termsForSession, academicTermId]);

  useEffect(() => {
    let mounted = true;
    async function loadClassStudents() {
      if (!selectedAssignment?.class_id) {
        setStudents([]);
        return;
      }
      try {
        const response = await studentService.getStudents({ classId: selectedAssignment.class_id });
        if (mounted) setStudents(response?.items || []);
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, "Could not load class students."));
      }
    }
    loadClassStudents();
    return () => {
      mounted = false;
    };
  }, [selectedAssignment]);

  const loadResults = async () => {
    if (!selectedAssignment?.class_id || !academicSessionId || !academicTermId) {
      setResults([]);
      return;
    }
    const response = await academicService.listTeacherResults({
      class_id: selectedAssignment.class_id,
      academic_session_id: academicSessionId,
      academic_term_id: academicTermId,
    });
    setResults((response?.items || []).filter((item) => item.teacher_assignment_id === selectedAssignmentId));
  };

  useEffect(() => {
    let mounted = true;
    async function run() {
      try {
        const response = await academicService.listTeacherResults({
          class_id: selectedAssignment?.class_id,
          academic_session_id: academicSessionId,
          academic_term_id: academicTermId,
        });
        if (mounted) setResults((response?.items || []).filter((item) => item.teacher_assignment_id === selectedAssignmentId));
      } catch {
        if (mounted) setResults([]);
      }
    }
    if (selectedAssignment?.class_id && academicSessionId && academicTermId) run();
    return () => {
      mounted = false;
    };
  }, [selectedAssignment, selectedAssignmentId, academicSessionId, academicTermId]);

  const resultByStudent = useMemo(
    () => Object.fromEntries(results.map((result) => [result.student_id, result])),
    [results]
  );

  const updateDraft = (studentId, field, value) => {
    if (isSubmitted(resultByStudent[studentId])) return;
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

  const saveResult = async (studentId, status) => {
    const existing = resultByStudent[studentId];
    if (isSubmitted(existing)) {
      showError("Submitted scores are locked. Ask an admin to reopen or correct the result.");
      return;
    }
    if (!selectedAssignmentId || !academicSessionId || !academicTermId) {
      const message = "Select a subject, academic session, and term before saving scores.";
      setError(message);
      showError(message);
      return;
    }
    const draft = { ...emptyScores, ...(existing || {}), ...(drafts[studentId] || {}) };
    setIsSaving(`${studentId}-${status}`);
    setError(null);
    try {
      const saved = await academicService.saveTeacherResult({
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
      setResults((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setDrafts((current) => {
        const next = { ...current };
        delete next[studentId];
        return next;
      });
      showSuccess(status === "submitted" ? "Result submitted successfully." : "Draft saved successfully.");
    } catch (err) {
      const message = getErrorMessage(err, "Could not save scores.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title="Results">
        <LoadingState label="Loading result workspace..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="teacher"
      title="Results"
      description="Select an assigned class-subject, enter component scores, save drafts, and submit complete results. Submitted scores lock for teachers."
    >
      {error && <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div>}

      <Card className="p-4 sm:p-5">
        <div className="grid gap-3 lg:grid-cols-3">
          <SelectField label="Assigned class-subject" value={selectedAssignmentId} onChange={setSelectedAssignmentId}>
            {assignments.length === 0 ? <option value="">No assigned subjects</option> : assignments.map((assignment) => (
              <option key={assignment.id} value={assignment.id}>
                {assignment.subject_name || "Subject"} - {assignment.class_name || "Class"} {assignment.class_arm || ""}
              </option>
            ))}
          </SelectField>
          <SelectField label="Academic session" value={academicSessionId} onChange={(value) => { setAcademicSessionId(value); setAcademicTermId(""); }}>
            {sessions.map((session) => <option key={session.id} value={session.id}>{session.name}{session.is_current ? " (Current)" : ""}</option>)}
          </SelectField>
          <SelectField label="Academic term" value={academicTermId} onChange={setAcademicTermId}>
            {termsForSession.map((term) => <option key={term.id} value={term.id}>{displayTerm(term.name)}{term.is_current ? " (Current)" : ""}</option>)}
          </SelectField>
        </div>
      </Card>

      <section className="grid gap-3">
        {students.length === 0 ? (
          <EmptyState icon={ClipboardList} title="No students found" description="Select an assigned class-subject with enrolled students." />
        ) : (
          students.map((student) => {
            const existing = resultByStudent[student.id];
            const submitted = isSubmitted(existing);
            const draft = { ...emptyScores, ...(existing || {}), ...(drafts[student.id] || {}) };
            const canSubmit = scoreFields.every((field) => toNullableScore(draft[field]) !== null);
            return (
              <Card key={student.id} className="p-4 sm:p-5">
                <div className="grid gap-4 xl:grid-cols-[minmax(180px,1.1fr)_repeat(3,minmax(96px,0.55fr))_minmax(180px,0.85fr)_minmax(150px,auto)] xl:items-end">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-text">
                      {[student.first_name, student.last_name].filter(Boolean).join(" ") || student.admission_number || "Student"}
                    </p>
                    <p className="mt-1 text-sm text-text-muted">{student.admission_number || "No admission number"}</p>
                    {existing ? <Badge variant={submitted ? "success" : "warning"}>{submitted ? "Submitted" : "Draft"}</Badge> : <Badge variant="warning">Pending</Badge>}
                  </div>
                  {scoreFields.map((field) => (
                    <TextField
                      key={field}
                      label={scoreLabel(field)}
                      type="number"
                      min="0"
                      max="100"
                      value={draft[field] ?? ""}
                      onChange={(value) => updateDraft(student.id, field, value)}
                      disabled={submitted}
                    />
                  ))}
                  <div className="rounded-xl border border-border bg-surface px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Computed after complete scores</p>
                    <p className="mt-1 font-semibold text-text">
                      <Calculator className="mr-1 inline h-4 w-4" />
                      {existing && submitted ? `${scoreValue(existing.total_score)} / ${existing.grade || "--"}` : "-- / --"}
                    </p>
                    <p className="text-xs text-text-muted">{submitted ? existing?.remark || "No remark" : "Visible after submission"}</p>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row xl:flex-col">
                    <Button size="xs" onClick={() => saveResult(student.id, "draft")} disabled={submitted || isSaving === `${student.id}-draft`}>
                      <Save className="h-3.5 w-3.5" />
                      Save Draft
                    </Button>
                    <Button size="xs" variant="success" onClick={() => saveResult(student.id, "submitted")} disabled={submitted || !canSubmit || isSaving === `${student.id}-submitted`}>
                      <Send className="h-3.5 w-3.5" />
                      {submitted ? "Submitted" : "Submit"}
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

export default TeacherResultsPage;
