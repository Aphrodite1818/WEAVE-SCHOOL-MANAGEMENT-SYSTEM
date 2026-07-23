import { BarChart3, CheckCircle2, ClipboardList, GraduationCap } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import { useToast } from "../../hooks/useToast";
import { classService } from "../../services/academicsService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { studentService } from "../../services/studentService";
import {
  Input,
  SelectControl,
  WorkspaceGrid,
  WorkspacePanel,
} from "./AcademicWorkspacePrimitives";

const BLANK_FORM = {
  result_id: "",
  student_id: "",
  teacher_assignment_id: "",
  test_score: "",
  assessment_score: "",
  exam_score: "",
  status: "draft",
};

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const classLabel = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || "Unnamed class";

const studentLabel = (item) =>
  `${[item?.first_name, item?.last_name].filter(Boolean).join(" ") || "Student"} · ${item?.admission_number || "No admission number"}`;

const assignmentLabel = (item) =>
  `${item?.subject_name || "Subject"} · ${item?.teacher_name || item?.teacher_staff_id || "Teacher"}`;

const scoreValue = (value) =>
  value === "" || value === null || value === undefined ? null : Number(value);

function ResultsWorkspace({ activeTab, onContextChange }) {
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [classes, setClasses] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [students, setStudents] = useState([]);
  const [results, setResults] = useState([]);
  const [filters, setFilters] = useState({
    class_id: "",
    academic_session_id: "",
    academic_term_id: "",
  });
  const [form, setForm] = useState(BLANK_FORM);
  const [saving, setSaving] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessionResponse, termResponse, classResponse, assignmentResponse] =
        await Promise.all([
          academicService.listSessions({ limit: 100 }),
          academicService.listTerms({ limit: 100 }),
          classService.getClasses({ limit: 100, activeOnly: true }),
          academicService.listTeacherAssignments({ active_only: true, limit: 100 }),
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
      setFilters((current) => ({
        class_id: current.class_id || nextClasses[0]?.id || "",
        academic_session_id:
          current.academic_session_id || currentSession?.id || nextSessions[0]?.id || "",
        academic_term_id:
          current.academic_term_id || currentTerm?.id || nextTerms[0]?.id || "",
      }));
      onContextChange?.({ currentSession, currentTerm });
    } catch (err) {
      const message = getErrorMessage(err, "Could not load results workspace.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
    }
  }, [onContextChange, showError]);

  const loadClassStudents = useCallback(async () => {
    if (!filters.class_id) {
      setStudents([]);
      return;
    }
    try {
      const response = await studentService.getAdminStudents({
        classId: filters.class_id,
        status: "active",
        limit: 100,
      });
      setStudents(asItems(response));
    } catch (err) {
      setStudents([]);
      showError(getErrorMessage(err, "Could not load students for this class."));
    }
  }, [filters.class_id, showError]);

  const loadResults = useCallback(async () => {
    if (
      !filters.class_id ||
      !filters.academic_session_id ||
      !filters.academic_term_id
    ) {
      setResults([]);
      return;
    }
    try {
      const response = await academicService.listAdminResults({
        class_id: filters.class_id,
        academic_session_id: filters.academic_session_id,
        academic_term_id: filters.academic_term_id,
        limit: 100,
      });
      setResults(asItems(response));
    } catch (err) {
      setResults([]);
      showError(getErrorMessage(err, "Could not load results."));
    }
  }, [filters, showError]);

  useEffect(() => {
    loadBase();
  }, [loadBase]);

  useEffect(() => {
    loadClassStudents();
  }, [loadClassStudents]);

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  const sessionOptions = useMemo(
    () => sessions.map((item) => ({ value: item.id, label: item.name })),
    [sessions],
  );
  const termOptions = useMemo(
    () =>
      terms
        .filter(
          (item) =>
            !filters.academic_session_id ||
            item.academic_session_id === filters.academic_session_id,
        )
        .map((item) => ({
          value: item.id,
          label: String(item.name || "").replaceAll("_", " "),
        })),
    [filters.academic_session_id, terms],
  );
  const classOptions = useMemo(
    () => classes.map((item) => ({ value: item.id, label: classLabel(item) })),
    [classes],
  );
  const assignmentOptions = useMemo(
    () =>
      assignments
        .filter((item) => item.class_id === filters.class_id)
        .map((item) => ({ value: item.id, label: assignmentLabel(item) })),
    [assignments, filters.class_id],
  );
  const studentOptions = useMemo(
    () => students.map((item) => ({ value: item.id, label: studentLabel(item) })),
    [students],
  );
  const visibleResults = useMemo(() => {
    if (activeTab === "drafts") {
      return results.filter((item) => item.status === "draft");
    }
    if (activeTab === "submitted") {
      return results.filter((item) => item.status === "submitted");
    }
    return results;
  }, [activeTab, results]);

  const scoreTotal =
    Number(form.test_score || 0) +
    Number(form.assessment_score || 0) +
    Number(form.exam_score || 0);

  const resetForm = () => setForm(BLANK_FORM);

  const saveResult = async (event) => {
    event.preventDefault();
    if (!form.student_id || !form.teacher_assignment_id) {
      showWarning("Select a student and subject assignment.");
      return;
    }
    if (scoreTotal > 100) {
      showWarning("The combined score cannot exceed 100.");
      return;
    }
    if (
      form.status === "submitted" &&
      [form.test_score, form.assessment_score, form.exam_score].some(
        (value) => value === "",
      )
    ) {
      showWarning("All scores are required before submission.");
      return;
    }

    setSaving("result");
    try {
      await academicService.saveAdminResult({
        student_id: form.student_id,
        teacher_assignment_id: form.teacher_assignment_id,
        academic_session_id: filters.academic_session_id,
        academic_term_id: filters.academic_term_id,
        test_score: scoreValue(form.test_score),
        assessment_score: scoreValue(form.assessment_score),
        exam_score: scoreValue(form.exam_score),
        status: form.status,
      });
      showSuccess(form.result_id ? "Result updated." : "Result saved.");
      resetForm();
      await loadResults();
    } catch (err) {
      showError(getErrorMessage(err, "Could not save result."));
    } finally {
      setSaving("");
    }
  };

  const updateStatus = async (item, status) => {
    setSaving(item.id);
    try {
      await academicService.updateResultStatus(item.id, { status });
      showSuccess(status === "submitted" ? "Result submitted." : "Result reopened as draft.");
      await loadResults();
    } catch (err) {
      showError(getErrorMessage(err, "Could not update result status."));
    } finally {
      setSaving("");
    }
  };

  const contextFilters = (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <SelectControl
        label="Class"
        value={filters.class_id}
        onChange={(value) => {
          setFilters((current) => ({ ...current, class_id: value }));
          resetForm();
        }}
        options={classOptions}
        required
      />
      <SelectControl
        label="Academic session"
        value={filters.academic_session_id}
        onChange={(value) => {
          const nextTerm = terms.find(
            (item) => item.academic_session_id === value && item.is_current,
          );
          setFilters((current) => ({
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
        value={filters.academic_term_id}
        onChange={(value) => {
          setFilters((current) => ({ ...current, academic_term_id: value }));
          resetForm();
        }}
        options={termOptions}
        required
      />
    </div>
  );

  const resultEditor = (
    <WorkspacePanel
      title={form.result_id ? "Edit result" : "Enter result"}
      description="The selected assignment determines the subject and responsible teacher."
    >
      <form className="space-y-3" onSubmit={saveResult}>
        <SelectControl
          label="Student"
          value={form.student_id}
          onChange={(value) => setForm((current) => ({ ...current, student_id: value }))}
          options={studentOptions}
          placeholder="Select student"
          required
        />
        <SelectControl
          label="Subject assignment"
          value={form.teacher_assignment_id}
          onChange={(value) =>
            setForm((current) => ({ ...current, teacher_assignment_id: value }))
          }
          options={assignmentOptions}
          placeholder={
            assignmentOptions.length === 0
              ? "No active assignments for this class"
              : "Select assignment"
          }
          disabled={assignmentOptions.length === 0}
          required
        />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input
            label="Test"
            type="number"
            min="0"
            max="100"
            value={form.test_score}
            onChange={(event) =>
              setForm((current) => ({ ...current, test_score: event.target.value }))
            }
          />
          <Input
            label="Assessment"
            type="number"
            min="0"
            max="100"
            value={form.assessment_score}
            onChange={(event) =>
              setForm((current) => ({ ...current, assessment_score: event.target.value }))
            }
          />
          <Input
            label="Exam"
            type="number"
            min="0"
            max="100"
            value={form.exam_score}
            onChange={(event) =>
              setForm((current) => ({ ...current, exam_score: event.target.value }))
            }
          />
        </div>
        <div className="rounded-xl border border-border/70 bg-surface-muted/30 px-3 py-2 text-sm text-text-muted">
          Combined score: <span className="font-semibold text-text">{scoreTotal}</span> / 100
        </div>
        <SelectControl
          label="Save as"
          value={form.status}
          onChange={(value) => setForm((current) => ({ ...current, status: value }))}
          options={[
            { value: "draft", label: "Draft" },
            { value: "submitted", label: "Submitted" },
          ]}
          required
        />
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button type="submit" disabled={saving === "result" || assignmentOptions.length === 0}>
            {saving === "result" ? "Saving..." : form.result_id ? "Update result" : "Save result"}
          </Button>
          {form.result_id ? (
            <Button type="button" variant="outline" onClick={resetForm}>
              Cancel
            </Button>
          ) : null}
        </div>
      </form>
    </WorkspacePanel>
  );

  const resultsList = (
    <WorkspacePanel
      title={
        activeTab === "drafts"
          ? "Draft results"
          : activeTab === "submitted"
            ? "Submitted results"
            : "Results in selected context"
      }
      description={`${visibleResults.length} result row${visibleResults.length === 1 ? "" : "s"} found.`}
    >
      {visibleResults.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center">
          <ClipboardList className="mx-auto h-7 w-7 text-text-muted" />
          <p className="mt-3 text-sm font-semibold text-text">No matching results</p>
          <p className="mt-1 text-sm text-text-muted">
            Adjust the context or enter the first result.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {visibleResults.map((item) => (
            <div
              key={item.id}
              className="flex min-h-[13rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words font-semibold text-text">
                    {item.student_name || item.admission_number || "Student"}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    {item.subject_name || item.subject_code || "Subject"}
                  </p>
                </div>
                <Badge variant={item.status === "submitted" ? "success" : "warning"}>
                  {item.status}
                </Badge>
              </div>
              <div className="mt-4 grid grid-cols-4 gap-2 text-center">
                {[
                  ["Test", item.test_score],
                  ["Assess", item.assessment_score],
                  ["Exam", item.exam_score],
                  ["Total", item.total_score],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl bg-surface-muted/40 px-2 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-text-muted">{label}</p>
                    <p className="mt-1 text-sm font-semibold text-text">{value ?? "–"}</p>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center gap-2 text-sm text-text-muted">
                <GraduationCap className="h-4 w-4" />
                Grade: {item.grade || "Pending"}
              </div>
              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  onClick={() =>
                    setForm({
                      result_id: item.id,
                      student_id: item.student_id || "",
                      teacher_assignment_id: item.teacher_assignment_id || "",
                      test_score: item.test_score ?? "",
                      assessment_score: item.assessment_score ?? "",
                      exam_score: item.exam_score ?? "",
                      status: item.status || "draft",
                    })
                  }
                >
                  Edit scores
                </Button>
                <Button
                  type="button"
                  size="small"
                  variant={item.status === "submitted" ? "outline" : "success"}
                  disabled={saving === item.id}
                  onClick={() =>
                    updateStatus(item, item.status === "submitted" ? "draft" : "submitted")
                  }
                >
                  {saving === item.id
                    ? "Saving..."
                    : item.status === "submitted"
                      ? "Reopen"
                      : "Submit"}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </WorkspacePanel>
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

  return (
    <div className="space-y-4">
      <WorkspacePanel
        title="Academic context"
        description="Choose the class, session, and term before entering or reviewing scores."
      >
        {contextFilters}
      </WorkspacePanel>
      {activeTab === "entry" ? (
        <WorkspaceGrid editor={resultEditor} content={resultsList} wide />
      ) : (
        resultsList
      )}
    </div>
  );
}

export default ResultsWorkspace;
