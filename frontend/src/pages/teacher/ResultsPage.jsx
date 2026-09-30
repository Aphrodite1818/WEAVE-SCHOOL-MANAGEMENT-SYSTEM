import { LockKeyhole, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { SelectField } from "../../components/academic/AcademicSelectors";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";

const assignmentLabel = (assignment) =>
  `${assignment.subject_name || "Subject"} · ${assignment.class_name || "Class"} ${assignment.class_arm || ""}`.trim();

const studentName = (student) =>
  [student.first_name, student.last_name].filter(Boolean).join(" ") ||
  student.student_name ||
  student.admission_number ||
  "Student";

const scoreKey = (studentId, componentId) => `${studentId}:${componentId}`;

function ResultsPage() {
  const [assignments, setAssignments] = useState([]);
  const [scheme, setScheme] = useState(null);
  const [session, setSession] = useState(null);
  const [term, setTerm] = useState(null);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [students, setStudents] = useState([]);
  const [resultsByStudent, setResultsByStudent] = useState({});
  const [draftScores, setDraftScores] = useState({});
  const [savingStudentId, setSavingStudentId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [error, setError] = useState(null);
  const { showSuccess, showError } = useToast();

  useEffect(() => {
    let mounted = true;

    async function loadContext() {
      setLoading(true);
      setError(null);
      try {
        const [assignmentResponse, assessmentScheme, sessionResponse, termResponse] =
          await Promise.all([
            academicService.listMyTeacherAssignments(),
            academicService.getTeacherAssessmentScheme(),
            academicService.listTeacherSessions({ is_current: true, limit: 10 }),
            academicService.listTeacherTerms({ is_current: true, limit: 10 }),
          ]);
        if (!mounted) return;

        const nextAssignments = assignmentResponse?.items || [];
        setAssignments(nextAssignments);
        setSelectedAssignmentId(nextAssignments[0]?.id || "");
        setScheme(assessmentScheme || null);
        setSession((sessionResponse?.items || [])[0] || null);
        setTerm((termResponse?.items || [])[0] || null);
      } catch (err) {
        if (mounted) {
          setError(getErrorMessage(err, "Could not load the teacher grading workspace."));
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadContext();
    return () => {
      mounted = false;
    };
  }, []);

  const loadAssignment = useCallback(async () => {
    if (!selectedAssignmentId || !session?.id || !term?.id) {
      setStudents([]);
      setResultsByStudent({});
      setDraftScores({});
      return;
    }

    setRosterLoading(true);
    setError(null);
    try {
      const [rosterResponse, resultsResponse] = await Promise.all([
        academicService.listMyAssignmentStudents(selectedAssignmentId, { limit: 100 }),
        academicService.listTeacherResults({
          teacher_assignment_id: selectedAssignmentId,
          academic_session_id: session.id,
          academic_term_id: term.id,
          limit: 100,
        }),
      ]);

      const nextStudents = rosterResponse?.items || [];
      const results = resultsResponse?.items || [];
      const nextResults = Object.fromEntries(results.map((result) => [result.student_id, result]));
      const nextDrafts = {};

      results.forEach((result) => {
        (result.components || []).forEach((component) => {
          nextDrafts[scoreKey(result.student_id, component.assessment_component_id)] =
            component.score ?? "";
        });
      });

      setStudents(nextStudents);
      setResultsByStudent(nextResults);
      setDraftScores(nextDrafts);
    } catch (err) {
      setStudents([]);
      setResultsByStudent({});
      setDraftScores({});
      setError(getErrorMessage(err, "Could not load students and scores."));
    } finally {
      setRosterLoading(false);
    }
  }, [selectedAssignmentId, session?.id, term?.id]);

  useEffect(() => {
    void loadAssignment();
  }, [loadAssignment]);

  const components = useMemo(
    () => [...(scheme?.components || [])].sort((a, b) => a.position - b.position),
    [scheme],
  );
  const manualComponents = useMemo(
    () => components.filter((component) => component.is_examinable === false),
    [components],
  );
  const selectedAssignment = assignments.find(
    (assignment) => assignment.id === selectedAssignmentId,
  );

  const updateScore = (studentId, componentId, value) => {
    setDraftScores((current) => ({
      ...current,
      [scoreKey(studentId, componentId)]: value,
    }));
  };

  const saveStudent = async (student) => {
    if (!selectedAssignment || !session?.id || !term?.id || !manualComponents.length) return;

    setSavingStudentId(student.id);
    try {
      const componentScores = manualComponents.map((component) => {
        const rawValue = draftScores[scoreKey(student.id, component.id)];
        return {
          assessment_component_id: component.id,
          score: rawValue === "" || rawValue === undefined ? null : Number(rawValue),
        };
      });

      const saved = await academicService.saveTeacherResult({
        student_id: student.id,
        teacher_assignment_id: selectedAssignment.id,
        academic_session_id: session.id,
        academic_term_id: term.id,
        component_scores: componentScores,
        status: "draft",
      });

      setResultsByStudent((current) => ({ ...current, [student.id]: saved }));
      setDraftScores((current) => {
        const next = { ...current };
        (saved.components || []).forEach((component) => {
          next[scoreKey(student.id, component.assessment_component_id)] = component.score ?? "";
        });
        return next;
      });
      showSuccess(`${studentName(student)} scores saved.`);
    } catch (err) {
      showError(getErrorMessage(err, "Could not save the student's manual scores."));
    } finally {
      setSavingStudentId(null);
    }
  };

  if (loading) {
    return (
      <DashboardLayout role="teacher" title="Results">
        <LoadingState label="Loading grading workspace..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="teacher"
      title="Results"
      description="Record teacher-managed assessment scores. Examinable components are locked because CBT or an administrator owns those scores."
    >
      <div className="space-y-4">
        {error ? (
          <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">
            {error}
          </div>
        ) : null}

        <Card className="p-4">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <SelectField
              label="Class and subject"
              value={selectedAssignmentId}
              onChange={(event) => setSelectedAssignmentId(event.target.value)}
            >
              {assignments.map((assignment) => (
                <option key={assignment.id} value={assignment.id}>
                  {assignmentLabel(assignment)}
                </option>
              ))}
            </SelectField>
            <div className="flex flex-wrap gap-2 text-xs">
              {session ? <Badge variant="default">{session.name}</Badge> : null}
              {term ? <Badge variant="default">{term.name}</Badge> : null}
              {scheme ? <Badge variant="info">{scheme.name}</Badge> : null}
            </div>
          </div>
        </Card>

        {components.length ? (
          <div className="flex flex-wrap gap-2">
            {components.map((component) => (
              <Badge
                key={component.id}
                variant={component.is_examinable === false ? "success" : "default"}
              >
                {component.name} · {component.maximum_score} · {component.is_examinable === false ? "Manual" : "CBT locked"}
              </Badge>
            ))}
          </div>
        ) : null}

        {rosterLoading ? (
          <LoadingState label="Loading student scores..." />
        ) : !selectedAssignmentId ? (
          <EmptyState title="No subject assignment" description="You do not currently have a subject assignment available for result entry." />
        ) : !students.length ? (
          <EmptyState title="No students" description="No students are available in this assignment roster." />
        ) : !manualComponents.length ? (
          <EmptyState title="No teacher-managed components" description="Every component in the active assessment scheme is examinable, so scores are managed by CBT or an administrator." />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {students.map((student) => {
              const result = resultsByStudent[student.id];
              const resultScores = Object.fromEntries(
                (result?.components || []).map((component) => [
                  component.assessment_component_id,
                  component.score,
                ]),
              );
              const locked = result && result.status !== "draft";

              return (
                <Card key={student.id} className="p-4">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-text">{studentName(student)}</h3>
                      <p className="text-xs text-text-muted">{student.admission_number || "No admission number"}</p>
                    </div>
                    <Badge variant={locked ? "default" : "info"}>{result?.status || "draft"}</Badge>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {components.map((component) => {
                      const examinable = component.is_examinable !== false;
                      const draftValue = draftScores[scoreKey(student.id, component.id)];
                      const visibleValue = examinable
                        ? resultScores[component.id] ?? ""
                        : draftValue ?? resultScores[component.id] ?? "";

                      return (
                        <label key={component.id} className="space-y-1.5">
                          <span className="flex items-center justify-between gap-2 text-xs font-medium text-text-muted">
                            <span>{component.name} / {component.maximum_score}</span>
                            {examinable ? (
                              <span className="inline-flex items-center gap-1 text-text-muted">
                                <LockKeyhole className="h-3 w-3" /> CBT
                              </span>
                            ) : (
                              <span className="text-success">Manual</span>
                            )}
                          </span>
                          <input
                            type="number"
                            min="0"
                            max={component.maximum_score}
                            step="0.01"
                            value={visibleValue}
                            disabled={examinable || locked}
                            placeholder={examinable ? "Awaiting CBT/admin score" : "Enter score"}
                            onChange={(event) =>
                              updateScore(student.id, component.id, event.target.value)
                            }
                            className={`h-10 w-full rounded-lg border px-3 text-sm outline-none ${
                              examinable || locked
                                ? "cursor-not-allowed border-border/60 bg-surface-muted/60 text-text-muted"
                                : "border-border bg-surface text-text focus:border-primary"
                            }`}
                          />
                        </label>
                      );
                    })}
                  </div>

                  <div className="mt-4 flex items-center justify-between gap-3">
                    <p className="text-xs text-text-muted">
                      {locked
                        ? "This result is no longer a draft."
                        : "Only manual component values are sent when you save."}
                    </p>
                    <Button
                      type="button"
                      disabled={locked || savingStudentId === student.id}
                      onClick={() => saveStudent(student)}
                    >
                      <Save className="mr-2 h-4 w-4" />
                      {savingStudentId === student.id ? "Saving..." : "Save scores"}
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default ResultsPage;
