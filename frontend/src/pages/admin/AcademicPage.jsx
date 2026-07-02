import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  CalendarDays,
  FileText,
  GraduationCap,
  Lock,
  Pencil,
  Plus,
  Printer,
  RefreshCw,
  Search,
  Unlock,
  Users,
} from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import LoadingState from "../../components/shared/LoadingState";
import EmptyState from "../../components/shared/EmptyState";
import {
  CheckboxField,
  SelectField,
  TextField,
} from "../../components/academic/AcademicSelectors";
import { displayClass, displayPerson, displayTerm } from "../../components/academic/academicDisplay";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { reportCardService } from "../../services/reportCardService";
import { searchService } from "../../services/searchService";
import { studentService } from "../../services/studentService";
import { subjectService } from "../../services/subject.service";
import { teacherService } from "../../services/teacherService";
import { useToast } from "../../hooks/useToast";

const sections = [
  {
    name: "Academic Sessions",
    description: "Create school years, choose the active session, and retire old sessions safely.",
    icon: BookOpen,
  },
  {
    name: "Academic Terms",
    description: "Manage first, second, and third term windows for each academic session.",
    icon: CalendarDays,
  },
  {
    name: "Grading Scale",
    description: "Define score ranges used by the backend to compute grades and remarks.",
    icon: GraduationCap,
  },
  {
    name: "Teacher Assignments",
    description: "Assign teachers to class-subject pairs offered by each class.",
    icon: Users,
  },
  {
    name: "Student Results",
    description: "Review, draft, publish, lock, or unlock student scores by class and subject.",
    icon: Pencil,
  },
  {
    name: "Report Cards",
    description: "Generate immutable report card snapshots when all class scores are submitted.",
    icon: FileText,
  },
  {
    name: "Academic Search",
    description: "Search students, teachers, parents, subjects, and classes across this tenant.",
    icon: Search,
  },
];

const blankSession = { name: "", start_date: "", end_date: "", is_current: false, is_active: true };
const blankTerm = { academic_session_id: "", name: "first_term", start_date: "", end_date: "", is_current: false, is_active: true };
const blankScale = { grade: "", min_score: "", max_score: "", remark: "", is_active: true };
const blankAssignment = { class_id: "", class_subject_id: "", subject_id: "", teacher_id: "", is_core: true };
const blankResult = { student_id: "", test_score: "", assessment_score: "", exam_score: "", status: "draft" };
const blankReportCard = { student_id: "" };

const compactDate = (value) => (value ? new Date(value).toLocaleDateString() : "-");
const cleanText = (value, fallback = "-") => (value === undefined || value === null || value === "" ? fallback : String(value));
const studentName = (student) => displayPerson(student) || student?.admission_number || "Student";

const badgeTone = (value) => {
  if (value === true || value === "active" || value === "published" || value === "complete") return "green";
  if (value === "current" || value === "selected" || value === "primary") return "blue";
  if (value === "locked" || value === false || value === "inactive" || value === "draft" || value === "pending") return "gray";
  return "gray";
};

function AcademicPage() {
  const [activeSection, setActiveSection] = useState("Academic Sessions");
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [scales, setScales] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [classSubjects, setClassSubjects] = useState([]);
  const [reportCardOverview, setReportCardOverview] = useState(null);
  const [results, setResults] = useState([]);
  const [reportCards, setReportCards] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [sessionForm, setSessionForm] = useState(blankSession);
  const [termForm, setTermForm] = useState(blankTerm);
  const [scaleForm, setScaleForm] = useState(blankScale);
  const [assignmentForm, setAssignmentForm] = useState(blankAssignment);
  const [resultForm, setResultForm] = useState(blankResult);
  const [reportCardForm, setReportCardForm] = useState(blankReportCard);
  const [editingSessionId, setEditingSessionId] = useState("");
  const [editingTermId, setEditingTermId] = useState("");
  const [editingScaleId, setEditingScaleId] = useState("");
  const [editingAssignmentId, setEditingAssignmentId] = useState("");
  const [editingResultId, setEditingResultId] = useState("");
  const [filters, setFilters] = useState({ class_id: "", subject_id: "", teacher_id: "", academic_session_id: "", academic_term_id: "" });
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState("");
  const [error, setError] = useState(null);
  const { showSuccess, showError } = useToast();

  const currentSession = sessions.find((item) => item.is_current);
  const currentSection = sections.find((section) => section.name === activeSection) || sections[0];

  const loadWorkspace = async () => {
    setError(null);
    const [
      sessionResponse,
      termResponse,
      scaleResponse,
      assignmentResponse,
      resultResponse,
      reportCardResponse,
      classResponse,
      subjectResponse,
      teacherResponse,
      studentResponse,
    ] = await Promise.all([
      academicService.listSessions(),
      academicService.listTerms(),
      academicService.listGradingScales(),
      academicService.listTeacherAssignments(),
      academicService.listAdminResults(),
      reportCardService.listAdminReportCards(),
      classService.getClasses(),
      subjectService.getSubjects(),
      teacherService.getTeachers(),
      studentService.getAdminStudents(),
    ]);

    const nextSessions = sessionResponse?.items || [];
    const nextTerms = termResponse?.items || [];

    setSessions(nextSessions);
    setTerms(nextTerms);
    setScales(scaleResponse?.items || []);
    setAssignments(assignmentResponse?.items || []);
    setResults(resultResponse?.items || []);
    setReportCards(reportCardResponse?.items || []);
    setClasses(classResponse?.items || []);
    setSubjects(subjectResponse?.items || []);
    setTeachers(teacherResponse?.items || []);
    setStudents(studentResponse?.items || []);

    setFilters((current) => ({
      ...current,
      academic_session_id:
        current.academic_session_id ||
        nextSessions.find((item) => item.is_current)?.id ||
        nextSessions[0]?.id ||
        "",
      academic_term_id:
        current.academic_term_id ||
        nextTerms.find((item) => item.is_current)?.id ||
        nextTerms[0]?.id ||
        "",
    }));
  };

  useEffect(() => {
    let mounted = true;
    async function load() {
      setIsLoading(true);
      try {
        await loadWorkspace();
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, "Could not load academic workspace."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    async function runSearch() {
      if (searchQuery.trim().length < 2) {
        setSearchResults([]);
        return;
      }
      try {
        const response = await searchService.searchTenant(searchQuery.trim(), 8);
        if (mounted) setSearchResults(response?.items || []);
      } catch {
        if (mounted) setSearchResults([]);
      }
    }
    const timeout = window.setTimeout(runSearch, 250);
    return () => {
      mounted = false;
      window.clearTimeout(timeout);
    };
  }, [searchQuery]);

  const termsForSelectedSession = useMemo(
    () => terms.filter((term) => !filters.academic_session_id || term.academic_session_id === filters.academic_session_id),
    [terms, filters.academic_session_id]
  );

  const studentsForClass = useMemo(
    () => students.filter((student) => !filters.class_id || student.class_id === filters.class_id),
    [students, filters.class_id]
  );

  const filteredAssignments = useMemo(
    () =>
      assignments.filter(
        (item) =>
          (!filters.class_id || item.class_id === filters.class_id) &&
          (!filters.subject_id || item.subject_id === filters.subject_id) &&
          (!filters.teacher_id || item.teacher_id === filters.teacher_id)
      ),
    [assignments, filters]
  );

  const selectedAssignment = filteredAssignments.find(
    (item) =>
      item.class_id === filters.class_id &&
      item.subject_id === filters.subject_id &&
      item.is_active
  );

  useEffect(() => {
    let mounted = true;
    async function loadClassSubjects() {
      if (!assignmentForm.class_id) {
        if (mounted) setClassSubjects([]);
        return;
      }
      try {
        const response = await academicService.listClassSubjects(assignmentForm.class_id, { active_only: true });
        if (mounted) setClassSubjects(response?.items || []);
      } catch {
        if (mounted) setClassSubjects([]);
      }
    }
    loadClassSubjects();
    return () => {
      mounted = false;
    };
  }, [assignmentForm.class_id]);

  useEffect(() => {
    let mounted = true;
    async function loadOverview() {
      if (
        activeSection !== "Report Cards" ||
        !filters.class_id ||
        !filters.academic_session_id ||
        !filters.academic_term_id
      ) {
        if (mounted) setReportCardOverview(null);
        return;
      }
      try {
        const response = await reportCardService.getClassOverview({
          class_id: filters.class_id,
          academic_session_id: filters.academic_session_id,
          academic_term_id: filters.academic_term_id,
        });
        if (mounted) setReportCardOverview(response);
      } catch {
        if (mounted) setReportCardOverview(null);
      }
    }
    loadOverview();
    return () => {
      mounted = false;
    };
  }, [activeSection, filters.class_id, filters.academic_session_id, filters.academic_term_id]);

  const visibleResults = useMemo(
    () =>
      results.filter(
        (item) =>
          (!filters.academic_session_id || item.academic_session_id === filters.academic_session_id) &&
          (!filters.academic_term_id || item.academic_term_id === filters.academic_term_id) &&
          (!filters.class_id || item.class_id === filters.class_id) &&
          (!filters.subject_id || item.subject_id === filters.subject_id)
      ),
    [results, filters]
  );

  const visibleReportCards = useMemo(
    () =>
      reportCards.filter(
        (card) =>
          (!filters.academic_session_id || card.academic_session_id === filters.academic_session_id) &&
          (!filters.academic_term_id || card.academic_term_id === filters.academic_term_id) &&
          (!filters.class_id || card.class_id === filters.class_id)
      ),
    [reportCards, filters]
  );

  const scrollToForm = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const resetSessionForm = () => {
    setEditingSessionId("");
    setSessionForm(blankSession);
  };

  const resetTermForm = () => {
    setEditingTermId("");
    setTermForm({ ...blankTerm, academic_session_id: currentSession?.id || filters.academic_session_id || "" });
  };

  const resetScaleForm = () => {
    setEditingScaleId("");
    setScaleForm(blankScale);
  };

  const resetAssignmentForm = () => {
    setEditingAssignmentId("");
    setAssignmentForm(blankAssignment);
  };

  const resetResultForm = () => {
    setEditingResultId("");
    setResultForm(blankResult);
  };

  const resetReportCardForm = () => {
    setReportCardForm(blankReportCard);
  };

  const saveSession = async (event) => {
    event.preventDefault();
    setIsSaving("session");
    setError(null);
    try {
      const payload = {
        name: sessionForm.name,
        start_date: sessionForm.start_date || null,
        end_date: sessionForm.end_date || null,
        is_current: sessionForm.is_current ?? false,
        is_active: sessionForm.is_active ?? true,
      };
      const saved = editingSessionId
        ? await academicService.updateSession(editingSessionId, payload)
        : await academicService.createSession(payload);
      setSessions((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetSessionForm();
      showSuccess("Academic session saved.");
      if (saved.is_current) await loadWorkspace();
    } catch (err) {
      const message = getErrorMessage(err, "Could not save academic session.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const saveTerm = async (event) => {
    event.preventDefault();
    setIsSaving("term");
    setError(null);
    try {
      const payload = editingTermId
        ? {
            name: termForm.name,
            start_date: termForm.start_date || null,
            end_date: termForm.end_date || null,
            is_current: termForm.is_current ?? false,
            is_active: termForm.is_active ?? true,
          }
        : {
            academic_session_id: termForm.academic_session_id || currentSession?.id,
            name: termForm.name,
            start_date: termForm.start_date || null,
            end_date: termForm.end_date || null,
            is_current: termForm.is_current ?? false,
            is_active: termForm.is_active ?? true,
          };
      const saved = editingTermId
        ? await academicService.updateTerm(editingTermId, payload)
        : await academicService.createTerm(payload);
      setTerms((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetTermForm();
      showSuccess("Academic term saved.");
      if (saved.is_current) await loadWorkspace();
    } catch (err) {
      const message = getErrorMessage(err, "Could not save academic term.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const patchScale = async (scale, payload) => {
    setIsSaving(scale.id);
    setError(null);
    try {
      const saved = await academicService.updateGradingScale(scale.id, payload);
      setScales((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      showSuccess("Grading scale updated.");
    } catch (err) {
      const message = getErrorMessage(err, "Could not update grading scale.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const saveScale = async (event) => {
    event.preventDefault();
    setIsSaving("scale");
    setError(null);
    try {
      const payload = {
        grade: scaleForm.grade,
        min_score: Number(scaleForm.min_score),
        max_score: Number(scaleForm.max_score),
        remark: scaleForm.remark || null,
        is_active: scaleForm.is_active ?? true,
      };
      const saved = editingScaleId
        ? await academicService.updateGradingScale(editingScaleId, payload)
        : await academicService.createGradingScale(payload);
      setScales((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetScaleForm();
      showSuccess("Grading scale saved.");
    } catch (err) {
      const message = getErrorMessage(err, "Could not save grading scale. Check that ranges do not overlap.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const saveAssignment = async (event) => {
    event.preventDefault();
    setIsSaving("assignment");
    setError(null);
    try {
      let classSubjectId = assignmentForm.class_subject_id;
      if (!classSubjectId && assignmentForm.class_id && assignmentForm.subject_id) {
        const createdSubject = await academicService.addClassSubject(assignmentForm.class_id, {
          subject_id: assignmentForm.subject_id,
          is_core: assignmentForm.is_core,
        });
        classSubjectId = createdSubject.id;
      }
      const saved = editingAssignmentId
        ? await academicService.reassignTeacherAssignment(editingAssignmentId, {
            teacher_id: assignmentForm.teacher_id,
          })
        : await academicService.createTeacherAssignment({
            class_subject_id: classSubjectId,
            teacher_id: assignmentForm.teacher_id,
          });
      setAssignments((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetAssignmentForm();
      showSuccess("Teacher assignment saved.");
    } catch (err) {
      const message = getErrorMessage(err, "Could not save teacher assignment.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const saveResult = async (event) => {
    event.preventDefault();
    if (!selectedAssignment || !filters.academic_session_id || !filters.academic_term_id || !resultForm.student_id) {
      const message = "Choose a session, term, class, subject, and student before saving a result.";
      setError(message);
      showError(message);
      return;
    }
    setIsSaving("result");
    setError(null);
    try {
      const saved = await academicService.saveAdminResult({
        student_id: resultForm.student_id,
        teacher_assignment_id: selectedAssignment.id,
        academic_session_id: filters.academic_session_id,
        academic_term_id: filters.academic_term_id,
        test_score: Number(resultForm.test_score || 0),
        assessment_score: Number(resultForm.assessment_score || 0),
        exam_score: Number(resultForm.exam_score || 0),
        status: resultForm.status,
      });
      setResults((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetResultForm();
      showSuccess("Student result saved.");
    } catch (err) {
      const message = getErrorMessage(err, "Could not save result. Confirm grading scales cover the computed total.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const updateResultStatus = async (result, status) => {
    setIsSaving(result.id);
    setError(null);
    try {
      const saved = await academicService.updateResultStatus(result.id, { status });
      setResults((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      showSuccess(`Result marked ${status}.`);
    } catch (err) {
      const message = getErrorMessage(err, "Could not update result status.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const generateReportCard = async (event) => {
    event.preventDefault();
    if (!filters.academic_session_id || !filters.academic_term_id || !reportCardForm.student_id) {
      const message = "Choose a session, term, class, and student before generating a report card.";
      setError(message);
      showError(message);
      return;
    }
    setIsSaving("report-card");
    setError(null);
    try {
      const card = await reportCardService.generateReportCard({
        student_id: reportCardForm.student_id,
        academic_session_id: filters.academic_session_id,
        academic_term_id: filters.academic_term_id,
      });
      setReportCards((current) => [card, ...current.filter((item) => item.id !== card.id)]);
      resetReportCardForm();
      showSuccess("Report card generated.");
    } catch (err) {
      const message = getErrorMessage(err, "Could not generate report card.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const publishReportCard = async (card) => {
    setIsSaving(card.id);
    setError(null);
    try {
      const saved = await reportCardService.publishReportCard(card.id);
      setReportCards((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      showSuccess("Report card published.");
    } catch (err) {
      const message = getErrorMessage(err, "Could not publish report card.");
      setError(message);
      showError(message);
    } finally {
      setIsSaving("");
    }
  };

  const printReportCard = async (card) => {
    setError(null);
    try {
      await reportCardService.printAdminReportCard(card.id);
    } catch (err) {
      const message = getErrorMessage(err, "Could not open report card.");
      setError(message);
      showError(message);
    }
  };

  const startSessionEdit = (session) => {
    setEditingSessionId(session.id);
    setSessionForm({
      name: session.name || "",
      start_date: session.start_date || "",
      end_date: session.end_date || "",
      is_current: session.is_current || false,
      is_active: session.is_active !== false,
    });
    scrollToForm("academic-form-session");
  };

  const startTermEdit = (term) => {
    setEditingTermId(term.id);
    setTermForm({
      academic_session_id: term.academic_session_id || "",
      name: term.name || "first_term",
      start_date: term.start_date || "",
      end_date: term.end_date || "",
      is_current: term.is_current || false,
      is_active: term.is_active !== false,
    });
    scrollToForm("academic-form-term");
  };

  const startScaleEdit = (scale) => {
    setEditingScaleId(scale.id);
    setScaleForm({
      grade: scale.grade || "",
      min_score: scale.min_score ?? "",
      max_score: scale.max_score ?? "",
      remark: scale.remark || "",
      is_active: scale.is_active !== false,
    });
    scrollToForm("academic-form-scale");
  };

  const startAssignmentEdit = (assignment) => {
    setEditingAssignmentId(assignment.id);
    setAssignmentForm({
      class_id: assignment.class_id || "",
      class_subject_id: assignment.class_subject_id || "",
      subject_id: assignment.subject_id || "",
      teacher_id: assignment.teacher_id || "",
      is_core: true,
    });
    scrollToForm("academic-form-assignment");
  };

  const startResultEdit = (result) => {
    setEditingResultId(result.id);
    setFilters((current) => ({
      ...current,
      academic_session_id: result.academic_session_id || current.academic_session_id,
      academic_term_id: result.academic_term_id || current.academic_term_id,
      class_id: result.class_id || current.class_id,
      subject_id: result.subject_id || current.subject_id,
    }));
    setResultForm({
      student_id: result.student_id || "",
      test_score: result.test_score ?? "",
      assessment_score: result.assessment_score ?? "",
      exam_score: result.exam_score ?? "",
      status: result.status || "draft",
    });
    scrollToForm("academic-form-result");
  };

  const startReportCardEdit = (card) => {
    setFilters((current) => ({
      ...current,
      academic_session_id: card.academic_session_id || current.academic_session_id,
      academic_term_id: card.academic_term_id || current.academic_term_id,
      class_id: card.class_id || current.class_id,
    }));
    setReportCardForm({ student_id: card.student_id || "" });
    scrollToForm("academic-form-report-card");
  };

  if (isLoading) {
    return (
      <DashboardLayout role="admin" title="Academic Workspace">
        <LoadingState label="Loading academic workspace..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="admin"
      title="Academic Workspace"
      description="Manage sessions, terms, grading, subject assignments, results, report cards, and academic search."
      actions={
        <Button variant="outline" onClick={loadWorkspace} disabled={Boolean(isSaving)}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      }
    >
      {error ? <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div> : null}

      <section className="space-y-4">
        <nav aria-label="Academic workspace sections" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
          {sections.map((section) => (
            <button
              key={section.name}
              type="button"
              onClick={() => setActiveSection(section.name)}
              className={`min-h-16 min-w-[190px] flex-1 rounded-xl border px-4 py-3 text-left transition ${
                activeSection === section.name
                  ? "border-primary bg-primary-subtle text-primary"
                  : "border-border bg-surface text-text-soft hover:border-primary/30 hover:bg-surface-muted/60"
              }`}
            >
              <span className="flex items-center gap-2 text-sm font-semibold">
                <section.icon className="h-4 w-4 shrink-0" />
                {section.name}
              </span>
              <span className="mt-1 line-clamp-2 block text-xs text-text-muted">{section.description}</span>
            </button>
          ))}
        </nav>

        <p className="tab-description">{currentSection.description}</p>

        <div className="space-y-[14px]">
          {activeSection === "Academic Sessions" ? (
            <>
              <SectionCard
                title="New session"
                subtitle={editingSessionId ? "Update the selected session while keeping the shared field pattern intact." : "Create an academic session and choose whether it is current and active."}
              >
                <form id="academic-form-session" onSubmit={saveSession} className="form-grid">
                  <div className="form-grid-field">
                    <TextField label="Name" value={sessionForm.name} onChange={(value) => setSessionForm((current) => ({ ...current, name: value }))} placeholder="2026/2027" required />
                  </div>
                  <div className="form-grid-field">
                    <TextField label="Start date" type="date" value={sessionForm.start_date} onChange={(value) => setSessionForm((current) => ({ ...current, start_date: value }))} />
                  </div>
                  <div className="form-grid-field">
                    <TextField label="End date" type="date" value={sessionForm.end_date} onChange={(value) => setSessionForm((current) => ({ ...current, end_date: value }))} />
                  </div>
                  <div className="form-grid-field">
                    <CheckboxField
                      label="Current"
                      checked={sessionForm.is_current}
                      onChange={(value) => setSessionForm((current) => ({ ...current, is_current: value }))}
                    />
                  </div>
                  <div className="form-grid-field">
                    <CheckboxField
                      label="Active"
                      checked={sessionForm.is_active}
                      onChange={(value) => setSessionForm((current) => ({ ...current, is_active: value }))}
                    />
                  </div>
                  <div className="form-grid-actions">
                    {editingSessionId ? <button type="button" className="btn-ghost" onClick={resetSessionForm}>Cancel</button> : null}
                    <button type="submit" className="btn-create" disabled={isSaving === "session"}>
                      <Plus className="h-3.5 w-3.5" />
                      Create
                    </button>
                  </div>
                </form>
              </SectionCard>

              <SectionCard title="All sessions" subtitle={`${sessions.length} session${sessions.length === 1 ? "" : "s"} available in this workspace.`}>
                <TableShell>
                  <table className="aw-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Start date</th>
                        <th>End date</th>
                        <th>Status</th>
                        <th>Current</th>
                        <th>Created</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((session) => (
                        <tr key={session.id}>
                          <td className="primary-cell">{session.name}</td>
                          <td>{compactDate(session.start_date)}</td>
                          <td>{compactDate(session.end_date)}</td>
                          <td><StatusBadge tone={session.is_active ? "green" : "gray"} label={session.is_active ? "Active" : "Inactive"} /></td>
                          <td><StatusBadge tone={session.is_current ? "blue" : "gray"} label={session.is_current ? "Current" : "Pending"} /></td>
                          <td>{compactDate(session.created_at)}</td>
                          <td>
                            <RowActions
                              onEdit={() => startSessionEdit(session)}
                              rightLabel={session.is_active ? "Deactivate" : "Activate"}
                              onRight={() => saveSessionToggle(session, setSessions, academicService.updateSession, showSuccess, setError, setIsSaving)}
                              disabled={isSaving === session.id}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableShell>
              </SectionCard>
            </>
          ) : null}

          {activeSection === "Academic Terms" ? (
            <>
              <SectionCard
                title="New term"
                subtitle={editingTermId ? "Update the selected term with the same shared form spacing and control order." : "Create a term for a session and optionally mark it as current."}
              >
                <form id="academic-form-term" onSubmit={saveTerm} className="form-grid">
                  <div className="form-grid-field">
                    <SelectField label="Name" value={termForm.name} onChange={(value) => setTermForm((current) => ({ ...current, name: value }))}>
                      <option value="first_term">First Term</option>
                      <option value="second_term">Second Term</option>
                      <option value="third_term">Third Term</option>
                    </SelectField>
                  </div>
                  <div className="form-grid-field">
                    <SelectField label="Academic session" value={termForm.academic_session_id || currentSession?.id || ""} onChange={(value) => setTermForm((current) => ({ ...current, academic_session_id: value }))} required>
                      <option value="">Select session</option>
                      {sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}
                    </SelectField>
                  </div>
                  <div className="form-grid-field">
                    <TextField label="Start date" type="date" value={termForm.start_date} onChange={(value) => setTermForm((current) => ({ ...current, start_date: value }))} />
                  </div>
                  <div className="form-grid-field">
                    <TextField label="End date" type="date" value={termForm.end_date} onChange={(value) => setTermForm((current) => ({ ...current, end_date: value }))} />
                  </div>
                  <div className="form-grid-field">
                    <CheckboxField
                      label="Current"
                      checked={termForm.is_current}
                      onChange={(value) => setTermForm((current) => ({ ...current, is_current: value }))}
                    />
                  </div>
                  <div className="form-grid-field">
                    <CheckboxField
                      label="Active"
                      checked={termForm.is_active}
                      onChange={(value) => setTermForm((current) => ({ ...current, is_active: value }))}
                    />
                  </div>
                  <div className="form-grid-actions">
                    {editingTermId ? <button type="button" className="btn-ghost" onClick={resetTermForm}>Cancel</button> : null}
                    <button type="submit" className="btn-create" disabled={isSaving === "term"}>
                      <Plus className="h-3.5 w-3.5" />
                      Create
                    </button>
                  </div>
                </form>
              </SectionCard>

              <SectionCard title="All terms" subtitle={`${terms.length} term${terms.length === 1 ? "" : "s"} across every academic session.`}>
                <TableShell>
                  <table className="aw-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Start date</th>
                        <th>End date</th>
                        <th>Status</th>
                        <th>Session</th>
                        <th>Current</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {terms.map((term) => {
                        const session = sessions.find((item) => item.id === term.academic_session_id);
                        return (
                          <tr key={term.id}>
                            <td className="primary-cell">{displayTerm(term.name)}</td>
                            <td>{compactDate(term.start_date)}</td>
                            <td>{compactDate(term.end_date)}</td>
                            <td><StatusBadge tone={term.is_active ? "green" : "gray"} label={term.is_active ? "Active" : "Inactive"} /></td>
                            <td>{session?.name || "-"}</td>
                            <td><StatusBadge tone={term.is_current ? "blue" : "gray"} label={term.is_current ? "Current" : "Pending"} /></td>
                            <td>
                              <RowActions
                                onEdit={() => startTermEdit(term)}
                                rightLabel={term.is_active ? "Deactivate" : "Activate"}
                                onRight={() => saveTermToggle(term, setTerms, academicService.updateTerm, showSuccess, setError, setIsSaving)}
                                disabled={isSaving === term.id}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </TableShell>
              </SectionCard>
            </>
          ) : null}

          {activeSection === "Grading Scale" ? (
            <>
              <SectionCard
                title="New grading scale"
                subtitle={editingScaleId ? "Update a grading band without changing the shared card anatomy." : "Create a grading band that the backend can use for computed grades."}
              >
                <form id="academic-form-scale" onSubmit={saveScale} className="form-grid">
                  <div className="form-grid-field">
                    <TextField label="Grade" value={scaleForm.grade} onChange={(value) => setScaleForm((current) => ({ ...current, grade: (value || "").toUpperCase() }))} placeholder="A" required />
                  </div>
                  <div className="form-grid-field">
                    <TextField label="Min score" value={scaleForm.min_score} onChange={(value) => setScaleForm((current) => ({ ...current, min_score: value }))} type="number" min="0" max="100" required />
                  </div>
                  <div className="form-grid-field">
                    <TextField label="Max score" value={scaleForm.max_score} onChange={(value) => setScaleForm((current) => ({ ...current, max_score: value }))} type="number" min="0" max="100" required />
                  </div>
                  <div className="form-grid-field">
                    <TextField label="Remark" value={scaleForm.remark} onChange={(value) => setScaleForm((current) => ({ ...current, remark: value }))} placeholder="Excellent" />
                  </div>
                  <div className="form-grid-field">
                    <CheckboxField
                      label="Active"
                      checked={scaleForm.is_active}
                      onChange={(value) => setScaleForm((current) => ({ ...current, is_active: value }))}
                    />
                  </div>
                  <div className="form-grid-actions">
                    {editingScaleId ? <button type="button" className="btn-ghost" onClick={resetScaleForm}>Cancel</button> : null}
                    <button type="submit" className="btn-create" disabled={isSaving === "scale"}>
                      <Plus className="h-3.5 w-3.5" />
                      Create
                    </button>
                  </div>
                </form>
              </SectionCard>

              <SectionCard title="All grading scales" subtitle={`${scales.length} grading scale${scales.length === 1 ? "" : "s"} defined for result computation.`}>
                <TableShell>
                  <table className="aw-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Min score</th>
                        <th>Max score</th>
                        <th>Status</th>
                        <th>Range</th>
                        <th>Remark</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scales.map((scale) => (
                        <tr key={scale.id}>
                          <td className="primary-cell">{scale.grade}</td>
                          <td>{cleanText(scale.min_score)}</td>
                          <td>{cleanText(scale.max_score)}</td>
                          <td><StatusBadge tone={scale.is_active ? "green" : "gray"} label={scale.is_active ? "Active" : "Inactive"} /></td>
                          <td>{`${cleanText(scale.min_score)} - ${cleanText(scale.max_score)}`}</td>
                          <td>{scale.remark || "-"}</td>
                          <td>
                            <RowActions
                              onEdit={() => startScaleEdit(scale)}
                              rightLabel={scale.is_active ? "Deactivate" : "Activate"}
                              onRight={() => patchScale(scale, { is_active: !scale.is_active })}
                              disabled={isSaving === scale.id}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableShell>
              </SectionCard>
            </>
          ) : null}

          {activeSection === "Teacher Assignments" ? (
            <>
              <SectionCard
                title="New teacher assignment"
                subtitle={editingAssignmentId ? "Reassign the teacher for this class-subject pair." : "Pick a class, subject offered by that class, and teacher."}
              >
                <form id="academic-form-assignment" onSubmit={saveAssignment} className="form-grid">
                  <div className="form-grid-field">
                    <SelectField label="Class" value={assignmentForm.class_id} onChange={(value) => setAssignmentForm((current) => ({ ...current, class_id: value, class_subject_id: "", subject_id: "" }))} required>
                      <option value="">Select class</option>
                      {classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}
                    </SelectField>
                  </div>
                  <div className="form-grid-field">
                    <SelectField label="Subject" value={assignmentForm.class_subject_id || assignmentForm.subject_id} onChange={(value) => {
                      const match = classSubjects.find((item) => item.id === value || item.subject_id === value);
                      setAssignmentForm((current) => ({
                        ...current,
                        class_subject_id: match?.id || "",
                        subject_id: match?.subject_id || value,
                      }));
                    }} required>
                      <option value="">Select subject</option>
                      {classSubjects.map((item) => <option key={item.id} value={item.id}>{item.subject_name || item.subject_id}</option>)}
                    </SelectField>
                  </div>
                  <div className="form-grid-field">
                    <SelectField label="Teacher" value={assignmentForm.teacher_id} onChange={(value) => setAssignmentForm((current) => ({ ...current, teacher_id: value }))} required>
                      <option value="">Select teacher</option>
                      {teachers.map((item) => <option key={item.id} value={item.id}>{displayPerson(item)}{item.staff_id ? ` - ${item.staff_id}` : ""}</option>)}
                    </SelectField>
                  </div>
                  <div className="form-grid-field">
                    <CheckboxField
                      label="Core subject"
                      checked={assignmentForm.is_core}
                      onChange={(value) => setAssignmentForm((current) => ({ ...current, is_core: value }))}
                    />
                  </div>
                  <div className="form-grid-actions">
                    {editingAssignmentId ? <button type="button" className="btn-ghost" onClick={resetAssignmentForm}>Cancel</button> : null}
                    <button type="submit" className="btn-create" disabled={isSaving === "assignment"}>
                      <Plus className="h-3.5 w-3.5" />
                      {editingAssignmentId ? "Reassign" : "Assign"}
                    </button>
                  </div>
                </form>
              </SectionCard>

              <SectionCard title="All teacher assignments" subtitle={`${assignments.length} active class-subject teaching assignment${assignments.length === 1 ? "" : "s"}.`}>
                <TableShell>
                  <table className="aw-table">
                    <thead>
                      <tr>
                        <th>Subject</th>
                        <th>Class</th>
                        <th>Teacher</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {assignments.map((item) => (
                        <tr key={item.id}>
                          <td className="primary-cell">{item.subject_name || "Subject"}</td>
                          <td>{[item.class_name, item.class_arm].filter(Boolean).join(" ") || "-"}</td>
                          <td>{item.teacher_name || "-"}</td>
                          <td><StatusBadge tone={item.is_active ? "green" : "gray"} label={item.is_active ? "Active" : "Inactive"} /></td>
                          <td>
                            <RowActions
                              onEdit={() => startAssignmentEdit(item)}
                              rightLabel={item.is_active ? "Deactivate" : "Activate"}
                              onRight={async () => {
                                setIsSaving(item.id);
                                setError(null);
                                try {
                                  const saved = item.is_active
                                    ? await academicService.deactivateTeacherAssignment(item.id)
                                    : item;
                                  setAssignments((current) => [saved, ...current.filter((entry) => entry.id !== saved.id)]);
                                  showSuccess("Teacher assignment updated.");
                                } catch (err) {
                                  setError(getErrorMessage(err, "Could not update teacher assignment."));
                                } finally {
                                  setIsSaving("");
                                }
                              }}
                              disabled={isSaving === item.id}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableShell>
              </SectionCard>
            </>
          ) : null}

          {activeSection === "Student Results" ? (
            <>
              <SectionCard
                title="New result"
                subtitle={selectedAssignment ? "Choose a student and scores, then let the backend compute the total, grade, and remark." : "Choose a session, term, class, and subject before saving a result."}
              >
                <form id="academic-form-result" onSubmit={saveResult} className="space-y-3">
                  <FilterRow
                    filters={filters}
                    setFilters={setFilters}
                    classes={classes}
                    subjects={subjects}
                    sessions={sessions}
                    terms={termsForSelectedSession}
                  />
                  <div className="form-grid">
                    <div className="form-grid-field">
                      <SelectField label="Student" value={resultForm.student_id} onChange={(value) => setResultForm((current) => ({ ...current, student_id: value }))} required>
                        <option value="">Select student</option>
                        {studentsForClass.map((item) => <option key={item.id} value={item.id}>{studentName(item)}{item.admission_number ? ` - ${item.admission_number}` : ""}</option>)}
                      </SelectField>
                    </div>
                    <div className="form-grid-field">
                      <TextField label="Test score" type="number" min="0" max="100" value={resultForm.test_score} onChange={(value) => setResultForm((current) => ({ ...current, test_score: value }))} />
                    </div>
                    <div className="form-grid-field">
                      <TextField label="Assessment score" type="number" min="0" max="100" value={resultForm.assessment_score} onChange={(value) => setResultForm((current) => ({ ...current, assessment_score: value }))} />
                    </div>
                    <div className="form-grid-field">
                      <TextField label="Exam score" type="number" min="0" max="100" value={resultForm.exam_score} onChange={(value) => setResultForm((current) => ({ ...current, exam_score: value }))} />
                    </div>
                    <div className="form-grid-field">
                      <SelectField label="Status" value={resultForm.status} onChange={(value) => setResultForm((current) => ({ ...current, status: value }))}>
                        <option value="draft">Draft</option>
                        <option value="submitted">Submitted</option>
                      </SelectField>
                    </div>
                    <div className="form-grid-actions">
                      {editingResultId ? <button type="button" className="btn-ghost" onClick={resetResultForm}>Cancel</button> : null}
                      <button type="submit" className="btn-create" disabled={!selectedAssignment || isSaving === "result"}>
                        <Plus className="h-3.5 w-3.5" />
                        Create
                      </button>
                    </div>
                  </div>
                </form>
              </SectionCard>

              <SectionCard title="All results" subtitle={`${visibleResults.length} result${visibleResults.length === 1 ? "" : "s"} match the current academic filters.`}>
                {!selectedAssignment && filters.class_id && filters.subject_id ? (
                  <p className="sc-body pt-0 text-[12.5px] text-warning">Assign a teacher to this class-subject before saving results.</p>
                ) : null}
                {visibleResults.length === 0 ? (
                  <div className="sc-body pt-0">
                    <EmptyState icon={GraduationCap} title="No results found" description="Create a result with the form above once your filters are ready." />
                  </div>
                ) : (
                  <TableShell>
                    <table className="aw-table">
                      <thead>
                      <tr>
                        <th>Name</th>
                        <th>Session</th>
                        <th>Term</th>
                        <th>Status</th>
                        <th>Subject</th>
                        <th>Total</th>
                          <th>Grade</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleResults.map((result) => {
                          const student = students.find((item) => item.id === result.student_id);
                          return (
                            <tr key={result.id}>
                              <td className="primary-cell">{student ? studentName(student) : "Student"}</td>
                              <td>{result.academic_session_name || "-"}</td>
                              <td>{result.academic_term_name ? displayTerm(result.academic_term_name) : "-"}</td>
                              <td><StatusBadge tone={badgeTone(result.status)} label={cleanLabel(result.status)} /></td>
                              <td>{result.subject_name || "-"}</td>
                              <td>{cleanText(result.total_score)}</td>
                              <td>{result.grade || "-"}</td>
                              <td>
                                <RowActions
                                  onEdit={() => startResultEdit(result)}
                                  rightLabel={result.status === "locked" ? "Unlock" : "Lock"}
                                  onRight={() => updateResultStatus(result, result.status === "locked" ? "published" : "locked")}
                                  disabled={isSaving === result.id}
                                  rightIcon={result.status === "locked" ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </TableShell>
                )}
              </SectionCard>
            </>
          ) : null}

          {activeSection === "Report Cards" ? (
            <>
              <SectionCard
                title="Class report card overview"
                subtitle="One row per student: score completion, report card status, and admin actions."
              >
                <FilterRow
                  filters={filters}
                  setFilters={setFilters}
                  classes={classes}
                  subjects={[]}
                  sessions={sessions}
                  terms={termsForSelectedSession}
                />
                {!reportCardOverview?.items?.length ? (
                  <div className="sc-body pt-0">
                    <EmptyState icon={FileText} title="Select class, session, and term" description="Choose filters above to review score completion and report card status for each student." />
                  </div>
                ) : (
                  <TableShell>
                    <table className="aw-table">
                      <thead>
                        <tr>
                          <th>Student</th>
                          <th>Score completion</th>
                          <th>Report card status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reportCardOverview.items.map((row) => {
                          const complete = row.submitted_count >= row.expected_count && row.expected_count > 0;
                          const statusLabel = row.report_card_id
                            ? `Published v${row.report_card_version}${row.is_outdated ? " · Outdated" : ""}`
                            : "Not generated";
                          return (
                            <tr key={row.student_id}>
                              <td className="primary-cell">{row.student_name || row.admission_number || "Student"}</td>
                              <td>{`${row.submitted_count}/${row.expected_count} subjects submitted`}</td>
                              <td>
                                <StatusBadge
                                  tone={row.is_outdated ? "gray" : row.report_card_id ? "green" : "gray"}
                                  label={statusLabel}
                                />
                              </td>
                              <td>
                                <div className="aw-actions">
                                  <RowActions
                                    rightLabel={row.report_card_id ? "View" : "Generate"}
                                    onRight={async () => {
                                      setIsSaving(row.student_id);
                                      try {
                                        if (row.report_card_id) {
                                          await reportCardService.printAdminReportCard(row.report_card_id);
                                        } else {
                                          const card = await reportCardService.generateReportCard({
                                            student_id: row.student_id,
                                            academic_session_id: filters.academic_session_id,
                                            academic_term_id: filters.academic_term_id,
                                          });
                                          setReportCards((current) => [card, ...current.filter((item) => item.id !== card.id)]);
                                          showSuccess("Report card generated.");
                                        }
                                      } catch (err) {
                                        showError(getErrorMessage(err, "Report card action failed."));
                                      } finally {
                                        setIsSaving("");
                                      }
                                    }}
                                    disabled={!complete && !row.report_card_id || isSaving === row.student_id}
                                  />
                                  {row.report_card_id && (row.is_outdated || complete) ? (
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      disabled={isSaving === `${row.student_id}-regen`}
                                      onClick={async () => {
                                        setIsSaving(`${row.student_id}-regen`);
                                        try {
                                          const card = await reportCardService.regenerateReportCard(row.report_card_id);
                                          setReportCards((current) => [card, ...current.filter((item) => item.id !== card.id)]);
                                          showSuccess("Report card regenerated.");
                                        } catch (err) {
                                          showError(getErrorMessage(err, "Could not regenerate report card."));
                                        } finally {
                                          setIsSaving("");
                                        }
                                      }}
                                    >
                                      <RefreshCw className="h-3.5 w-3.5" />
                                      Regenerate
                                    </Button>
                                  ) : null}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </TableShell>
                )}
              </SectionCard>

              <SectionCard
                title="Bulk generate for class"
                subtitle="Generate report cards for every score-complete student in the selected class."
              >
                <div className="form-grid-actions">
                  <button
                    type="button"
                    className="btn-create"
                    disabled={!filters.class_id || isSaving === "bulk-report-card"}
                    onClick={async () => {
                      setIsSaving("bulk-report-card");
                      try {
                        const response = await reportCardService.generateReportCard({
                          class_id: filters.class_id,
                          academic_session_id: filters.academic_session_id,
                          academic_term_id: filters.academic_term_id,
                        });
                        if (response?.generated?.length) {
                          setReportCards((current) => [...response.generated, ...current]);
                        }
                        showSuccess(`Generated ${response?.generated?.length || 0} report cards. Skipped ${response?.skipped?.length || 0}.`);
                      } catch (err) {
                        showError(getErrorMessage(err, "Bulk generation failed."));
                      } finally {
                        setIsSaving("");
                      }
                    }}
                  >
                    Generate for class
                  </button>
                </div>
              </SectionCard>
              <SectionCard
                title="All report cards"
                subtitle="Review generated report cards and publish or print them."
              >
                {visibleReportCards.length === 0 ? (
                  <div className="sc-body pt-0">
                    <EmptyState icon={FileText} title="No report cards found" description="Generate a report card with the form above for the selected class and term." />
                  </div>
                ) : (
                  <TableShell>
                    <table className="aw-table">
                      <thead>
                      <tr>
                        <th>Name</th>
                        <th>Session</th>
                        <th>Term</th>
                        <th>Status</th>
                        <th>Average</th>
                        <th>Class</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleReportCards.map((card) => {
                          const student = students.find((item) => item.id === card.student_id);
                          const classItem = classes.find((item) => item.id === card.class_id);
                          return (
                            <tr key={card.id}>
                              <td className="primary-cell">{student ? studentName(student) : "Student"}</td>
                              <td>{card.academic_session_name || "-"}</td>
                              <td>{card.academic_term_name ? displayTerm(card.academic_term_name) : "-"}</td>
                              <td><StatusBadge tone={badgeTone(card.status)} label={cleanLabel(card.status)} /></td>
                              <td>{cleanText(card.average_score)}</td>
                              <td>{classItem ? displayClass(classItem) : "-"}</td>
                              <td>
                                <RowActions
                                  onEdit={() => startReportCardEdit(card)}
                                  rightLabel={card.status === "published" ? "Print" : "Publish"}
                                  onRight={() => (card.status === "published" ? printReportCard(card) : publishReportCard(card))}
                                  disabled={isSaving === card.id}
                                  rightIcon={card.status === "published" ? <Printer className="h-3.5 w-3.5" /> : null}
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </TableShell>
                )}
              </SectionCard>
            </>
          ) : null}

          {activeSection === "Academic Search" ? (
            <>
              <SectionCard title="New search" subtitle="Search across tenant records without resetting the rest of the academic workspace forms.">
                <form className="form-grid" onSubmit={(event) => event.preventDefault()}>
                  <div className="form-grid-field">
                    <TextField label="Name" value={searchQuery} onChange={setSearchQuery} placeholder="Search students, teachers, parents, subjects, classes" />
                  </div>
                  <div className="form-grid-actions">
                    <button type="submit" className="btn-create">
                      <Plus className="h-3.5 w-3.5" />
                      Create
                    </button>
                  </div>
                </form>
              </SectionCard>

              <SectionCard title="All records" subtitle={`${searchResults.length} record${searchResults.length === 1 ? "" : "s"} match the current search query.`}>
                {searchResults.length === 0 ? (
                  <div className="sc-body pt-0">
                    <EmptyState icon={Search} title="Search tenant records" description="Type at least two characters to find matching students, teachers, parents, classes, or subjects." />
                  </div>
                ) : (
                  <TableShell>
                    <table className="aw-table">
                      <thead>
                        <tr>
                          <th>Name</th>
                          <th>Start date</th>
                          <th>End date</th>
                          <th>Status</th>
                          <th>Type</th>
                          <th>Summary</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {searchResults.map((item) => (
                          <tr key={`${item.role}-${item.href}-${item.label}`}>
                            <td className="primary-cell">{item.label}</td>
                            <td>-</td>
                            <td>-</td>
                            <td><StatusBadge tone="blue" label="Found" /></td>
                            <td>{item.role}</td>
                            <td>{[item.admission_number, item.staff_id, item.class_name, item.subject_name, item.email, item.metadata].filter(Boolean).join(" | ") || "Record"}</td>
                            <td>
                              <div className="aw-actions">
                                <a className="btn-ghost" href={item.href}>Edit</a>
                                <a className="btn-deact" href={item.href}>Inspect</a>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </TableShell>
                )}
              </SectionCard>
            </>
          ) : null}
        </div>
      </section>
    </DashboardLayout>
  );
}

function SectionCard({ title, subtitle, children }) {
  return (
    <div className="sc-card">
      <div className="sc-head">
        <h2 className="sc-title">{title}</h2>
        <p className="sc-subtitle">{subtitle}</p>
      </div>
      <div className="sc-body">{children}</div>
    </div>
  );
}

function TableShell({ children }) {
  return <div className="aw-table-wrap -mx-[14px] -mb-[14px] px-[14px] pb-[14px]">{children}</div>;
}

function StatusBadge({ tone, label }) {
  return <span className={`badge ${tone}`}>{label}</span>;
}

function ReadOnlyField({ label, value }) {
  return (
    <div>
      <span className="mb-1.5 block text-[11.5px] font-medium text-text-muted">{label}</span>
      <div className="flex h-[34px] min-h-[34px] items-center rounded-lg border border-border bg-background/60 px-3 text-[13px] font-medium text-text">
        {value}
      </div>
    </div>
  );
}

function RowActions({ onEdit, rightLabel, onRight, disabled = false, rightIcon = null }) {
  return (
    <div className="aw-actions">
      <button type="button" className="btn-ghost" onClick={onEdit} disabled={disabled}>
        <Pencil className="h-3.5 w-3.5" />
        Edit
      </button>
      <button type="button" className="btn-deact" onClick={onRight} disabled={disabled}>
        {rightIcon}
        {rightLabel}
      </button>
    </div>
  );
}

function FilterRow({ filters, setFilters, classes, subjects = [], teachers = [], sessions = [], terms = [] }) {
  return (
    <div className="form-grid">
      <div className="form-grid-field">
        <SelectField label="Session" value={filters.academic_session_id} onChange={(value) => setFilters((current) => ({ ...current, academic_session_id: value, academic_term_id: "" }))}>
          <option value="">Select session</option>
          {sessions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </SelectField>
      </div>
      <div className="form-grid-field">
        <SelectField label="Term" value={filters.academic_term_id} onChange={(value) => setFilters((current) => ({ ...current, academic_term_id: value }))}>
          <option value="">Select term</option>
          {terms.map((item) => <option key={item.id} value={item.id}>{displayTerm(item.name)}</option>)}
        </SelectField>
      </div>
      <div className="form-grid-field">
        <SelectField label="Class" value={filters.class_id} onChange={(value) => setFilters((current) => ({ ...current, class_id: value }))}>
          <option value="">All classes</option>
          {classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}
        </SelectField>
      </div>
      {subjects.length > 0 ? (
        <div className="form-grid-field">
          <SelectField label="Subject" value={filters.subject_id} onChange={(value) => setFilters((current) => ({ ...current, subject_id: value }))}>
            <option value="">All subjects</option>
            {subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </SelectField>
        </div>
      ) : null}
      {teachers.length > 0 ? (
        <div className="form-grid-field">
          <SelectField label="Teacher" value={filters.teacher_id} onChange={(value) => setFilters((current) => ({ ...current, teacher_id: value }))}>
            <option value="">All teachers</option>
            {teachers.map((item) => <option key={item.id} value={item.id}>{displayPerson(item)}</option>)}
          </SelectField>
        </div>
      ) : null}
    </div>
  );
}

async function saveSessionToggle(session, setSessions, updateFn, showSuccess, setError, setIsSaving) {
  setIsSaving(session.id);
  setError(null);
  try {
    const saved = await updateFn(session.id, { is_active: !session.is_active });
    setSessions((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    showSuccess("Academic session updated.");
  } catch (err) {
    setError(getErrorMessage(err, "Could not update academic session."));
  } finally {
    setIsSaving("");
  }
}

async function saveTermToggle(term, setTerms, updateFn, showSuccess, setError, setIsSaving) {
  setIsSaving(term.id);
  setError(null);
  try {
    const saved = await updateFn(term.id, { is_active: !term.is_active });
    setTerms((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    showSuccess("Academic term updated.");
  } catch (err) {
    setError(getErrorMessage(err, "Could not update academic term."));
  } finally {
    setIsSaving("");
  }
}

function cleanLabel(value) {
  return cleanText(value, "Pending")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default AcademicPage;
