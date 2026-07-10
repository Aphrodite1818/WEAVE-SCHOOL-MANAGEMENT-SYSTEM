import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  ClipboardList,
  Edit3,
  FileSearch,
  FileText,
  GraduationCap,
  Layers3,
  Library,
  Pencil,
  Plus,
  Search,
  Settings2,
  Users,
  X,
} from "lucide-react";

import { CheckboxField, SelectField, TextField } from "../../components/academic/AcademicSelectors";
import { displayClass, displayPerson, displayTerm } from "../../components/academic/academicDisplay";
import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { reportCardService } from "../../services/reportCardService";
import { searchService } from "../../services/searchService";
import { studentService } from "../../services/studentService";
import { subjectService } from "../../services/subject.service";
import { teacherService } from "../../services/teacherService";
import { useToast } from "../../hooks/useToast";
import { cn } from "../../utils/cn";

const blankSession = { name: "", start_date: "", end_date: "", is_current: false, is_active: true };
const blankTerm = { academic_session_id: "", name: "first_term", start_date: "", end_date: "", is_current: false, is_active: true };
const blankScale = { grade: "", min_score: "", max_score: "", remark: "", is_active: true };
const blankSubject = { name: "", code: "", description: "" };
const blankClass = { name: "", arm: "", level: "", teacher_id: "", is_active: true };
const blankClassSubject = { class_id: "", subject_id: "", is_core: true };
const blankAssignment = { class_id: "", class_subject_id: "", teacher_id: "", is_core: true };
const blankResult = { student_id: "", teacher_assignment_id: "", test_score: "", assessment_score: "", exam_score: "", status: "draft" };
const blankFilters = { class_id: "", subject_id: "", academic_session_id: "", academic_term_id: "" };

const workflowSections = {
  setup: {
    title: "Academic setup",
    description: "Create sessions, terms, grading scales, and subjects directly on this page.",
    icon: BookOpen,
    tone: "primary",
    tabs: [
      { id: "sessions", label: "Sessions", icon: Library, description: "Create and activate academic years." },
      { id: "terms", label: "Terms", icon: ClipboardList, description: "Create terms under an academic session." },
      { id: "grading", label: "Grading", icon: BarChart3, description: "Create grade bands and remarks." },
      { id: "subjects", label: "Subjects", icon: BookOpen, description: "Create and update subject catalogue records." },
    ],
  },
  "class-subjects": {
    title: "Classes & subjects",
    description: "Create classes, manage subjects, and attach subjects to classes.",
    icon: Layers3,
    tone: "success",
    tabs: [
      { id: "classes", label: "Classes", icon: Library, description: "Create and update class records." },
      { id: "subjects", label: "Subjects", icon: BookOpen, description: "Create and update subjects." },
      { id: "class-subjects", label: "Class subjects", icon: Layers3, description: "Attach or remove subjects from a class." },
      { id: "review", label: "Review", icon: FileSearch, description: "Review classes, subjects, and assignments." },
    ],
  },
  assignments: {
    title: "Teacher assignments",
    description: "Assign teachers to class-subject records and review existing assignments.",
    icon: Users,
    tone: "warning",
    tabs: [
      { id: "assign-subject", label: "Assign", icon: Users, description: "Attach a teacher to a class subject." },
      { id: "view-assigned", label: "View assigned", icon: ClipboardList, description: "Review active and inactive teacher assignments." },
      { id: "change-teacher", label: "Change teacher", icon: Settings2, description: "Pick an assignment and reassign it." },
    ],
  },
  results: {
    title: "Results",
    description: "Filter records, enter scores, and manage draft/submitted result rows.",
    icon: Pencil,
    tone: "accent",
    tabs: [
      { id: "filters", label: "Select records", icon: FileSearch, description: "Choose session, term, class, and subject." },
      { id: "entry", label: "Score entry", icon: Pencil, description: "Record test, assessment, and exam scores." },
      { id: "drafts", label: "Drafts", icon: ClipboardList, description: "Review draft rows." },
      { id: "submitted", label: "Submitted", icon: GraduationCap, description: "Review submitted rows." },
    ],
  },
  "report-cards": {
    title: "Report cards",
    description: "Generate, review, publish, and search report cards.",
    icon: FileText,
    tone: "primary",
    tabs: [
      { id: "overview", label: "Overview", icon: BarChart3, description: "Check readiness for a class." },
      { id: "generate", label: "Generate", icon: FileText, description: "Generate report cards from submitted results." },
      { id: "review", label: "Review", icon: FileSearch, description: "Review generated report cards." },
      { id: "publish", label: "Publish", icon: ArrowRight, description: "Publish report cards." },
    ],
  },
  search: {
    title: "Academic search",
    description: "Search students, report cards, and academic records.",
    icon: Search,
    tone: "success",
    tabs: [
      { id: "search", label: "Search records", icon: Search, description: "Use the tenant search endpoint." },
    ],
  },
};

const workflowAliases = { reports: "report-cards" };
const sectionOrder = ["setup", "class-subjects", "assignments", "results", "report-cards", "search"];
const toneStyles = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-amber-950",
  accent: "bg-accent-soft text-accent",
  neutral: "bg-surface-muted text-text-muted",
};

const compactDate = (value) => (value ? new Date(value).toLocaleDateString() : "--");
const toNullableScore = (value) => value === "" || value === null || value === undefined ? null : Number(value);
const scoreTotal = (form) => [form.test_score, form.assessment_score, form.exam_score].reduce((sum, value) => sum + (Number(value) || 0), 0);
const hasAllScores = (form) => [form.test_score, form.assessment_score, form.exam_score].every((value) => value !== "" && value !== null && value !== undefined);
const studentClassId = (student) => student?.class_id || student?.classroom_id || student?.class?.id || student?.classroom?.id || "";
const subjectLabel = (item) => item?.subject_name || item?.name || item?.subject_code || item?.code || "Subject";
const teacherLabel = (teacher) => displayPerson(teacher) || teacher?.teacher_name || teacher?.teacher_staff_id || "Teacher";
const studentLabel = (student) => displayPerson(student) || student?.student_name || student?.admission_number || "Student";
const statusLabel = (value) => String(value || "--").replaceAll("_", " ");
const getResolvedWorkflow = (workflow) => workflowAliases[workflow] || workflow || "setup";

function AcademicWorkflowPage() {
  const { workflow = "setup" } = useParams();
  const resolvedWorkflow = getResolvedWorkflow(workflow);
  const section = workflowSections[resolvedWorkflow] || workflowSections.setup;
  const [activeStepId, setActiveStepId] = useState(section.tabs[0]?.id);
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [scales, setScales] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [classSubjects, setClassSubjects] = useState([]);
  const [students, setStudents] = useState([]);
  const [results, setResults] = useState([]);
  const [reportCards, setReportCards] = useState([]);
  const [reportCardOverview, setReportCardOverview] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [sessionForm, setSessionForm] = useState(blankSession);
  const [termForm, setTermForm] = useState(blankTerm);
  const [scaleForm, setScaleForm] = useState(blankScale);
  const [subjectForm, setSubjectForm] = useState(blankSubject);
  const [classForm, setClassForm] = useState(blankClass);
  const [classSubjectForm, setClassSubjectForm] = useState(blankClassSubject);
  const [assignmentForm, setAssignmentForm] = useState(blankAssignment);
  const [resultForm, setResultForm] = useState(blankResult);
  const [editingSessionId, setEditingSessionId] = useState("");
  const [editingTermId, setEditingTermId] = useState("");
  const [editingScaleId, setEditingScaleId] = useState("");
  const [editingSubjectId, setEditingSubjectId] = useState("");
  const [editingClassId, setEditingClassId] = useState("");
  const [editingAssignmentId, setEditingAssignmentId] = useState("");
  const [editingResultId, setEditingResultId] = useState("");
  const [assignmentFilters, setAssignmentFilters] = useState({ class_id: "", subject_id: "", teacher_id: "" });
  const [resultFilters, setResultFilters] = useState(blankFilters);
  const [reportFilters, setReportFilters] = useState(blankFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState("");
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();

  const activeStep = section.tabs.find((tab) => tab.id === activeStepId) || section.tabs[0];
  const currentSession = sessions.find((item) => item.is_current) || sessions[0];
  const currentTerm = terms.find((item) => item.is_current) || terms[0];
  const termsForResultSession = useMemo(() => terms.filter((term) => !resultFilters.academic_session_id || term.academic_session_id === resultFilters.academic_session_id), [terms, resultFilters.academic_session_id]);
  const termsForReportSession = useMemo(() => terms.filter((term) => !reportFilters.academic_session_id || term.academic_session_id === reportFilters.academic_session_id), [terms, reportFilters.academic_session_id]);
  const visibleAssignments = useMemo(() => assignments.filter((item) => (!assignmentFilters.class_id || item.class_id === assignmentFilters.class_id) && (!assignmentFilters.subject_id || item.subject_id === assignmentFilters.subject_id) && (!assignmentFilters.teacher_id || item.teacher_id === assignmentFilters.teacher_id)), [assignments, assignmentFilters]);
  const selectedAssignment = useMemo(() => assignments.find((item) => item.is_active && item.class_id === resultFilters.class_id && item.subject_id === resultFilters.subject_id), [assignments, resultFilters.class_id, resultFilters.subject_id]);
  const visibleResults = useMemo(() => results.filter((item) => !resultFilters.subject_id || item.subject_id === resultFilters.subject_id), [results, resultFilters.subject_id]);
  const visibleReportCards = useMemo(() => reportCards.filter((card) => (!reportFilters.academic_session_id || card.academic_session_id === reportFilters.academic_session_id) && (!reportFilters.academic_term_id || card.academic_term_id === reportFilters.academic_term_id) && (!reportFilters.class_id || card.class_id === reportFilters.class_id)), [reportCards, reportFilters]);

  useEffect(() => {
    setActiveStepId(section.tabs[0]?.id);
  }, [resolvedWorkflow]);

  const loadWorkspace = async () => {
    setError(null);
    const [sessionResponse, termResponse, scaleResponse, subjectResponse, classResponse, teacherResponse, assignmentResponse, reportCardResponse] = await Promise.all([
      academicService.listSessions(),
      academicService.listTerms(),
      academicService.listGradingScales(),
      subjectService.getSubjects({ isActive: true, limit: 100 }),
      classService.getClasses({ limit: 100 }),
      teacherService.getTeachers({ limit: 100 }),
      academicService.listTeacherAssignments({ limit: 100 }),
      reportCardService.listAdminReportCards({ limit: 100 }),
    ]);

    const nextSessions = sessionResponse?.items || [];
    const nextTerms = termResponse?.items || [];
    const nextClasses = classResponse?.items || [];
    const defaultSessionId = nextSessions.find((item) => item.is_current)?.id || nextSessions[0]?.id || "";
    const defaultTermId = nextTerms.find((item) => item.is_current)?.id || nextTerms[0]?.id || "";
    const defaultClassId = nextClasses[0]?.id || "";

    setSessions(nextSessions);
    setTerms(nextTerms);
    setScales(scaleResponse?.items || []);
    setSubjects(subjectResponse?.items || []);
    setClasses(nextClasses);
    setTeachers(teacherResponse?.items || []);
    setAssignments(assignmentResponse?.items || []);
    setReportCards(reportCardResponse?.items || []);
    setTermForm((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId }));
    setClassSubjectForm((current) => ({ ...current, class_id: current.class_id || defaultClassId }));
    setAssignmentForm((current) => ({ ...current, class_id: current.class_id || defaultClassId }));
    setResultFilters((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId, academic_term_id: current.academic_term_id || defaultTermId }));
    setReportFilters((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId, academic_term_id: current.academic_term_id || defaultTermId }));
  };

  useEffect(() => {
    let mounted = true;
    async function load() {
      setIsLoading(true);
      try {
        await loadWorkspace();
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, "Could not load academic workflow."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    let mounted = true;
    async function loadClassSubjects() {
      const classId = classSubjectForm.class_id || assignmentForm.class_id;
      if (!classId) {
        setClassSubjects([]);
        return;
      }
      try {
        const response = await academicService.listClassSubjects(classId, { active_only: false, limit: 100 });
        if (mounted) setClassSubjects(response?.items || []);
      } catch (err) {
        if (mounted) setClassSubjects([]);
        showError(getErrorMessage(err, "Could not load class subjects."));
      }
    }
    loadClassSubjects();
    return () => { mounted = false; };
  }, [classSubjectForm.class_id, assignmentForm.class_id, showError]);

  useEffect(() => {
    let mounted = true;
    async function loadStudentsForClass() {
      if (!resultFilters.class_id) {
        setStudents([]);
        return;
      }
      try {
        const response = await studentService.getAdminStudents({ classId: resultFilters.class_id, limit: 100 });
        const items = (response?.items || []).filter((student) => studentClassId(student) === resultFilters.class_id);
        if (mounted) setStudents(items);
      } catch (err) {
        if (mounted) setStudents([]);
        showError(getErrorMessage(err, "Could not load students for this class."));
      }
    }
    loadStudentsForClass();
    return () => { mounted = false; };
  }, [resultFilters.class_id, showError]);

  useEffect(() => {
    let mounted = true;
    async function loadResults() {
      if (!resultFilters.class_id || !resultFilters.academic_session_id || !resultFilters.academic_term_id) {
        setResults([]);
        return;
      }
      try {
        const response = await academicService.listAdminResults({ class_id: resultFilters.class_id, academic_session_id: resultFilters.academic_session_id, academic_term_id: resultFilters.academic_term_id, limit: 100 });
        if (mounted) setResults(response?.items || []);
      } catch (err) {
        if (mounted) setResults([]);
        showError(getErrorMessage(err, "Could not load results."));
      }
    }
    loadResults();
    return () => { mounted = false; };
  }, [resultFilters.class_id, resultFilters.academic_session_id, resultFilters.academic_term_id, showError]);

  useEffect(() => {
    let mounted = true;
    async function loadReportOverview() {
      if (!reportFilters.class_id || !reportFilters.academic_session_id || !reportFilters.academic_term_id) {
        setReportCardOverview(null);
        return;
      }
      try {
        const response = await reportCardService.getClassOverview({ class_id: reportFilters.class_id, academic_session_id: reportFilters.academic_session_id, academic_term_id: reportFilters.academic_term_id });
        if (mounted) setReportCardOverview(response);
      } catch {
        if (mounted) setReportCardOverview(null);
      }
    }
    loadReportOverview();
    return () => { mounted = false; };
  }, [reportFilters.class_id, reportFilters.academic_session_id, reportFilters.academic_term_id]);

  useEffect(() => {
    let mounted = true;
    const timeout = window.setTimeout(async () => {
      if (searchQuery.trim().length < 2) {
        setSearchResults([]);
        return;
      }
      try {
        const response = await searchService.searchTenant(searchQuery.trim(), 10);
        if (mounted) setSearchResults(response?.items || []);
      } catch {
        if (mounted) setSearchResults([]);
      }
    }, 250);
    return () => { mounted = false; window.clearTimeout(timeout); };
  }, [searchQuery]);

  const resetSessionForm = () => { setSessionForm(blankSession); setEditingSessionId(""); };
  const resetTermForm = () => { setTermForm({ ...blankTerm, academic_session_id: currentSession?.id || "" }); setEditingTermId(""); };
  const resetScaleForm = () => { setScaleForm(blankScale); setEditingScaleId(""); };
  const resetSubjectForm = () => { setSubjectForm(blankSubject); setEditingSubjectId(""); };
  const resetClassForm = () => { setClassForm(blankClass); setEditingClassId(""); };
  const resetAssignmentForm = () => { setAssignmentForm((current) => ({ ...blankAssignment, class_id: current.class_id })); setEditingAssignmentId(""); };
  const resetResultForm = () => { setResultForm(blankResult); setEditingResultId(""); };

  const updateResultFilter = (key, value) => {
    setResultFilters((current) => ({ ...current, [key]: value, ...(key === "academic_session_id" ? { academic_term_id: "" } : {}) }));
    resetResultForm();
  };
  const updateReportFilter = (key, value) => setReportFilters((current) => ({ ...current, [key]: value, ...(key === "academic_session_id" ? { academic_term_id: "" } : {}) }));

  const saveSession = async (event) => {
    event.preventDefault();
    setIsSaving("session");
    try {
      const payload = { name: sessionForm.name, start_date: sessionForm.start_date || null, end_date: sessionForm.end_date || null, is_current: sessionForm.is_current, is_active: sessionForm.is_active };
      const saved = editingSessionId ? await academicService.updateSession(editingSessionId, payload) : await academicService.createSession(payload);
      setSessions((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetSessionForm();
      showSuccess(editingSessionId ? "Academic session updated." : "Academic session created.");
      if (saved.is_current) await loadWorkspace();
    } catch (err) { showError(getErrorMessage(err, "Could not save academic session.")); }
    finally { setIsSaving(""); }
  };

  const saveTerm = async (event) => {
    event.preventDefault();
    setIsSaving("term");
    try {
      const payload = { academic_session_id: termForm.academic_session_id, name: termForm.name, start_date: termForm.start_date || null, end_date: termForm.end_date || null, is_current: termForm.is_current, is_active: termForm.is_active };
      const saved = editingTermId ? await academicService.updateTerm(editingTermId, payload) : await academicService.createTerm(payload);
      setTerms((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetTermForm();
      showSuccess(editingTermId ? "Academic term updated." : "Academic term created.");
      if (saved.is_current) await loadWorkspace();
    } catch (err) { showError(getErrorMessage(err, "Could not save academic term.")); }
    finally { setIsSaving(""); }
  };

  const saveScale = async (event) => {
    event.preventDefault();
    setIsSaving("scale");
    try {
      const payload = { grade: scaleForm.grade, min_score: Number(scaleForm.min_score), max_score: Number(scaleForm.max_score), remark: scaleForm.remark || null, is_active: scaleForm.is_active };
      const saved = editingScaleId ? await academicService.updateGradingScale(editingScaleId, payload) : await academicService.createGradingScale(payload);
      setScales((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetScaleForm();
      showSuccess(editingScaleId ? "Grading scale updated." : "Grading scale created.");
    } catch (err) { showError(getErrorMessage(err, "Could not save grading scale.")); }
    finally { setIsSaving(""); }
  };

  const saveSubject = async (event) => {
    event.preventDefault();
    setIsSaving("subject");
    try {
      const payload = { name: subjectForm.name, code: subjectForm.code || null, description: subjectForm.description || null };
      const saved = editingSubjectId ? await subjectService.updateSubject(editingSubjectId, payload) : await subjectService.createSubject(payload);
      setSubjects((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetSubjectForm();
      showSuccess(editingSubjectId ? "Subject updated." : "Subject created.");
    } catch (err) { showError(getErrorMessage(err, "Could not save subject.")); }
    finally { setIsSaving(""); }
  };

  const saveClass = async (event) => {
    event.preventDefault();
    setIsSaving("class");
    try {
      const payload = { name: classForm.name, arm: classForm.arm || null, level: classForm.level || null, teacher_id: classForm.teacher_id || null, is_active: classForm.is_active };
      const saved = editingClassId ? await classService.updateClass(editingClassId, payload) : await classService.createClass(payload);
      setClasses((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetClassForm();
      showSuccess(editingClassId ? "Class updated." : "Class created.");
    } catch (err) { showError(getErrorMessage(err, "Could not save class.")); }
    finally { setIsSaving(""); }
  };

  const attachClassSubject = async (event) => {
    event.preventDefault();
    if (!classSubjectForm.class_id || !classSubjectForm.subject_id) {
      showWarning("Select class and subject before attaching.");
      return;
    }
    setIsSaving("classSubject");
    try {
      await academicService.addClassSubject(classSubjectForm.class_id, { subject_id: classSubjectForm.subject_id, is_core: classSubjectForm.is_core });
      const response = await academicService.listClassSubjects(classSubjectForm.class_id, { active_only: false, limit: 100 });
      setClassSubjects(response?.items || []);
      showSuccess("Subject attached to class.");
    } catch (err) { showError(getErrorMessage(err, "Could not attach subject to class.")); }
    finally { setIsSaving(""); }
  };

  const deactivateClassSubject = async (item) => {
    if (!item?.id || !item?.is_offered_by_class) return;
    setIsSaving(item.id);
    try {
      await academicService.deactivateClassSubject(item.id);
      const response = await academicService.listClassSubjects(classSubjectForm.class_id, { active_only: false, limit: 100 });
      setClassSubjects(response?.items || []);
      showSuccess("Subject removed from class.");
    } catch (err) { showError(getErrorMessage(err, "Could not remove subject from class.")); }
    finally { setIsSaving(""); }
  };

  const saveAssignment = async (event) => {
    event.preventDefault();
    if (!assignmentForm.class_id || !assignmentForm.class_subject_id || !assignmentForm.teacher_id) {
      showWarning("Select a class, class subject, and teacher before saving.");
      return;
    }
    setIsSaving("assignment");
    try {
      const saved = editingAssignmentId
        ? await academicService.reassignTeacherAssignment(editingAssignmentId, { teacher_id: assignmentForm.teacher_id })
        : await academicService.createTeacherAssignment({ class_subject_id: assignmentForm.class_subject_id, teacher_id: assignmentForm.teacher_id, is_core: assignmentForm.is_core });
      const response = await academicService.listTeacherAssignments({ limit: 100 });
      setAssignments(response?.items || []);
      setAssignmentFilters({ class_id: saved.class_id || assignmentForm.class_id, subject_id: saved.subject_id || "", teacher_id: saved.teacher_id || assignmentForm.teacher_id });
      resetAssignmentForm();
      showSuccess(editingAssignmentId ? "Subject teacher changed." : "Subject teacher assigned.");
    } catch (err) { showError(getErrorMessage(err, "Could not save teacher assignment.")); }
    finally { setIsSaving(""); }
  };

  const updateAssignmentStatus = async (assignment, shouldActivate) => {
    setIsSaving(assignment.id);
    try {
      const saved = shouldActivate ? await academicService.activateTeacherAssignment(assignment.id) : await academicService.deactivateTeacherAssignment(assignment.id);
      setAssignments((current) => current.map((item) => item.id === saved.id ? saved : item));
      showSuccess(shouldActivate ? "Assignment reactivated." : "Assignment deactivated.");
    } catch (err) { showError(getErrorMessage(err, "Could not update assignment.")); }
    finally { setIsSaving(""); }
  };

  const saveResult = async (event) => {
    event.preventDefault();
    const assignmentId = editingResultId && resultForm.teacher_assignment_id ? resultForm.teacher_assignment_id : selectedAssignment?.id;
    if (!resultFilters.class_id || !resultFilters.subject_id) return showWarning("Select class and subject before recording scores.");
    if (!assignmentId) return showWarning("Assign a teacher to this class-subject before saving scores.");
    if (!resultForm.student_id || !resultFilters.academic_session_id || !resultFilters.academic_term_id) return showWarning("Select student, session, and term before saving scores.");
    if (resultForm.status === "submitted" && !hasAllScores(resultForm)) return showWarning("All three scores are required before submitting a result.");
    if (scoreTotal(resultForm) > 100) return showWarning("The combined score cannot exceed 100.");
    setIsSaving("result");
    try {
      const saved = await academicService.saveAdminResult({ student_id: resultForm.student_id, teacher_assignment_id: assignmentId, academic_session_id: resultFilters.academic_session_id, academic_term_id: resultFilters.academic_term_id, test_score: toNullableScore(resultForm.test_score), assessment_score: toNullableScore(resultForm.assessment_score), exam_score: toNullableScore(resultForm.exam_score), status: resultForm.status });
      setResults((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      resetResultForm();
      showSuccess(saved.status === "submitted" ? "Result submitted." : "Result saved as draft.");
    } catch (err) { showError(getErrorMessage(err, "Could not save result.")); }
    finally { setIsSaving(""); }
  };

  const updateResultStatus = async (result, nextStatus) => {
    setIsSaving(result.id);
    try {
      const saved = await academicService.updateResultStatus(result.id, { status: nextStatus });
      setResults((current) => current.map((item) => item.id === saved.id ? saved : item));
      showSuccess(nextStatus === "submitted" ? "Result submitted." : "Result reopened as draft.");
    } catch (err) { showError(getErrorMessage(err, "Could not update result status.")); }
    finally { setIsSaving(""); }
  };

  const generateReportCard = async (bulk = false) => {
    if (!reportFilters.class_id || !reportFilters.academic_session_id || !reportFilters.academic_term_id) return showWarning("Select class, session, and term first.");
    setIsSaving(bulk ? "reportBulk" : "reportSingle");
    try {
      const payload = { class_id: reportFilters.class_id, academic_session_id: reportFilters.academic_session_id, academic_term_id: reportFilters.academic_term_id, generate_for_class: bulk };
      const response = await reportCardService.generateReportCard(payload);
      if (Array.isArray(response?.generated)) {
        setReportCards((current) => [...response.generated, ...current]);
        showSuccess(`Generated ${response.generated.length} report cards.`);
      } else {
        setReportCards((current) => [response, ...current.filter((item) => item.id !== response.id)]);
        showSuccess("Report card generated.");
      }
    } catch (err) { showError(getErrorMessage(err, "Could not generate report card.")); }
    finally { setIsSaving(""); }
  };

  const publishReportCard = async (reportCardId) => {
    setIsSaving(reportCardId);
    try {
      const saved = await reportCardService.publishReportCard(reportCardId);
      setReportCards((current) => current.map((item) => item.id === saved.id ? saved : item));
      showSuccess("Report card published.");
    } catch (err) { showError(getErrorMessage(err, "Could not publish report card.")); }
    finally { setIsSaving(""); }
  };

  const editSession = (item) => { setEditingSessionId(item.id); setSessionForm({ name: item.name || "", start_date: item.start_date || "", end_date: item.end_date || "", is_current: Boolean(item.is_current), is_active: item.is_active !== false }); };
  const editTerm = (item) => { setEditingTermId(item.id); setTermForm({ academic_session_id: item.academic_session_id || "", name: item.name || "first_term", start_date: item.start_date || "", end_date: item.end_date || "", is_current: Boolean(item.is_current), is_active: item.is_active !== false }); };
  const editScale = (item) => { setEditingScaleId(item.id); setScaleForm({ grade: item.grade || "", min_score: item.min_score ?? "", max_score: item.max_score ?? "", remark: item.remark || "", is_active: item.is_active !== false }); };
  const editSubject = (item) => { setEditingSubjectId(item.id); setSubjectForm({ name: item.name || "", code: item.code || "", description: item.description || "" }); };
  const editClass = (item) => { setEditingClassId(item.id); setClassForm({ name: item.name || "", arm: item.arm || "", level: item.level || "", teacher_id: item.teacher_id || "", is_active: item.is_active !== false }); };
  const editAssignment = (item) => { setEditingAssignmentId(item.id); setAssignmentForm({ class_id: item.class_id || "", class_subject_id: item.class_subject_id || "", teacher_id: item.teacher_id || "", is_core: true }); };
  const editResult = (item) => { setEditingResultId(item.id); setResultFilters({ class_id: item.class_id || "", subject_id: item.subject_id || "", academic_session_id: item.academic_session_id || "", academic_term_id: item.academic_term_id || "" }); setResultForm({ student_id: item.student_id || "", teacher_assignment_id: item.teacher_assignment_id || "", test_score: item.test_score ?? "", assessment_score: item.assessment_score ?? "", exam_score: item.exam_score ?? "", status: item.status || "draft" }); };

  if (isLoading) {
    return (
      <DashboardLayout role="admin" title={section.title}>
        <LoadingState label="Loading academic workflow..." />
      </DashboardLayout>
    );
  }

  const editorProps = { sessions, terms, scales, subjects, classes, teachers, assignments, classSubjects, students, results: visibleResults, reportCards: visibleReportCards, reportCardOverview, searchQuery, searchResults, setSearchQuery, sessionForm, setSessionForm, termForm, setTermForm, scaleForm, setScaleForm, subjectForm, setSubjectForm, classForm, setClassForm, classSubjectForm, setClassSubjectForm, assignmentForm, setAssignmentForm, resultForm, setResultForm, assignmentFilters, setAssignmentFilters, resultFilters, updateResultFilter, reportFilters, updateReportFilter, termsForResultSession, termsForReportSession, selectedAssignment, saveSession, saveTerm, saveScale, saveSubject, saveClass, attachClassSubject, deactivateClassSubject, saveAssignment, updateAssignmentStatus, saveResult, updateResultStatus, generateReportCard, publishReportCard, editSession, editTerm, editScale, editSubject, editClass, editAssignment, editResult, resetSessionForm, resetTermForm, resetScaleForm, resetSubjectForm, resetClassForm, resetAssignmentForm, resetResultForm, editingSessionId, editingTermId, editingScaleId, editingSubjectId, editingClassId, editingAssignmentId, editingResultId, isSaving };

  return (
    <DashboardLayout role="admin" title={section.title} description={section.description}>
      {error ? <Alert tone="error">{error}</Alert> : null}

      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <div className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl", toneStyles[section.tone] || toneStyles.primary)}>
              <section.icon className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <Link to="/admin/academic" className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">
                <ArrowLeft className="h-3.5 w-3.5" /> Back to academic hub
              </Link>
              <h2 className="mt-2 text-xl font-semibold text-text sm:text-2xl">{section.title}</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">{section.description}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:grid-cols-3 xl:w-[44rem]">
            {sectionOrder.map((key) => {
              const item = workflowSections[key];
              const Icon = item.icon;
              const active = key === resolvedWorkflow;
              return <Link key={key} to={`/admin/academic/${key}`} className={cn("flex min-h-11 items-center justify-center gap-2 rounded-xl px-2 py-2 text-center text-[11px] font-semibold transition sm:px-3 sm:text-xs", active ? "bg-surface text-primary shadow-sm" : "text-text-muted hover:bg-surface/60 hover:text-text")}><Icon className="h-4 w-4 shrink-0" /><span className="line-clamp-1">{item.title}</span></Link>;
            })}
          </div>
        </div>
      </Card>

      <Card className="p-4 sm:p-5">
        <div className="grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:grid-cols-4">
          {section.tabs.map((tab) => {
            const Icon = tab.icon;
            const active = tab.id === activeStep.id;
            return <button key={tab.id} type="button" onClick={() => setActiveStepId(tab.id)} className={cn("flex min-h-12 items-center justify-center gap-2 rounded-xl px-3 py-2 text-center text-xs font-semibold transition sm:text-sm", active ? "bg-surface text-primary shadow-sm" : "text-text-muted hover:bg-surface/60 hover:text-text")}><Icon className="h-4 w-4 shrink-0" /><span className="line-clamp-1">{tab.label}</span></button>;
          })}
        </div>
      </Card>

      <WorkflowContent workflow={resolvedWorkflow} step={activeStep.id} {...editorProps} />
    </DashboardLayout>
  );
}

function WorkflowContent({ workflow, step, ...props }) {
  if (workflow === "setup") {
    if (step === "terms") return <EditView edit={<TermEditor {...props} />} view={<TermViewer {...props} />} />;
    if (step === "grading") return <EditView edit={<ScaleEditor {...props} />} view={<ScaleViewer {...props} />} />;
    if (step === "subjects") return <EditView edit={<SubjectEditor {...props} />} view={<SubjectViewer {...props} />} />;
    return <EditView edit={<SessionEditor {...props} />} view={<SessionViewer {...props} />} />;
  }
  if (workflow === "class-subjects") {
    if (step === "subjects") return <EditView edit={<SubjectEditor {...props} />} view={<SubjectViewer {...props} />} />;
    if (step === "class-subjects") return <EditView edit={<ClassSubjectEditor {...props} />} view={<ClassSubjectViewer {...props} />} />;
    if (step === "review") return <EditView edit={<ReviewFilters {...props} />} view={<StructureReview {...props} />} />;
    return <EditView edit={<ClassEditor {...props} />} view={<ClassViewer {...props} />} />;
  }
  if (workflow === "assignments") return <EditView edit={<AssignmentEditor {...props} />} view={<AssignmentViewer {...props} />} />;
  if (workflow === "results") {
    if (step === "drafts") return <EditView edit={<ResultFilters {...props} />} view={<ResultViewer {...props} status="draft" />} />;
    if (step === "submitted") return <EditView edit={<ResultFilters {...props} />} view={<ResultViewer {...props} status="submitted" />} />;
    if (step === "entry") return <EditView edit={<ResultEditor {...props} />} view={<ResultViewer {...props} />} />;
    return <EditView edit={<ResultFilters {...props} />} view={<ResultViewer {...props} />} />;
  }
  if (workflow === "report-cards") {
    if (step === "generate") return <EditView edit={<ReportFilters {...props} />} view={<ReportGenerate {...props} />} />;
    if (step === "publish") return <EditView edit={<ReportFilters {...props} />} view={<ReportCardViewer {...props} publishMode />} />;
    if (step === "review") return <EditView edit={<ReportFilters {...props} />} view={<ReportCardViewer {...props} />} />;
    return <EditView edit={<ReportFilters {...props} />} view={<ReportOverview {...props} />} />;
  }
  return <EditView edit={<SearchEditor {...props} />} view={<SearchViewer {...props} />} />;
}

function EditView({ edit, view }) {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(320px,0.85fr)_minmax(0,1.35fr)]">
      <div className="space-y-4">{edit}</div>
      <div className="space-y-4">{view}</div>
    </section>
  );
}

function Panel({ title, subtitle, children }) {
  return <Card className="p-4 sm:p-5"><h3 className="section-title">{title}</h3>{subtitle ? <p className="mt-1 text-sm leading-6 text-text-muted">{subtitle}</p> : null}<div className="mt-4">{children}</div></Card>;
}

function FormActions({ editing, onCancel, isSaving, label }) {
  return <div className="flex flex-col gap-2 sm:flex-row"><Button type="submit" disabled={isSaving}>{isSaving ? "Saving..." : label}</Button>{editing ? <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button> : null}</div>;
}

function SessionEditor({ sessionForm, setSessionForm, saveSession, resetSessionForm, editingSessionId, isSaving }) {
  return <Panel title={editingSessionId ? "Edit session" : "Create session"} subtitle="Editing area"><form onSubmit={saveSession} className="grid gap-3"><TextField label="Session" value={sessionForm.name} onChange={(value) => setSessionForm((c) => ({ ...c, name: value }))} placeholder="2026/2027" required /><TextField label="Start" type="date" value={sessionForm.start_date} onChange={(value) => setSessionForm((c) => ({ ...c, start_date: value }))} /><TextField label="End" type="date" value={sessionForm.end_date} onChange={(value) => setSessionForm((c) => ({ ...c, end_date: value }))} /><CheckboxField label="Current session" checked={sessionForm.is_current} onChange={(value) => setSessionForm((c) => ({ ...c, is_current: value }))} /><CheckboxField label="Active" checked={sessionForm.is_active} onChange={(value) => setSessionForm((c) => ({ ...c, is_active: value }))} /><FormActions editing={Boolean(editingSessionId)} onCancel={resetSessionForm} isSaving={isSaving === "session"} label={editingSessionId ? "Update session" : "Create session"} /></form></Panel>;
}
function SessionViewer({ sessions, editSession }) { return <CardList title="View sessions" items={sessions} empty="No academic sessions yet." render={(item) => <RecordCard key={item.id} title={item.name} meta={`${compactDate(item.start_date)} - ${compactDate(item.end_date)}`} status={item.is_current ? "current" : item.is_active ? "active" : "inactive"} onEdit={() => editSession(item)} />} />; }

function TermEditor({ sessions, termForm, setTermForm, saveTerm, resetTermForm, editingTermId, isSaving }) {
  return <Panel title={editingTermId ? "Edit term" : "Create term"} subtitle="Editing area"><form onSubmit={saveTerm} className="grid gap-3"><SelectField label="Session" value={termForm.academic_session_id} onChange={(value) => setTermForm((c) => ({ ...c, academic_session_id: value }))} required><option value="">Select session</option>{sessions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectField><SelectField label="Term" value={termForm.name} onChange={(value) => setTermForm((c) => ({ ...c, name: value }))} required><option value="first_term">First term</option><option value="second_term">Second term</option><option value="third_term">Third term</option></SelectField><TextField label="Start" type="date" value={termForm.start_date} onChange={(value) => setTermForm((c) => ({ ...c, start_date: value }))} /><TextField label="End" type="date" value={termForm.end_date} onChange={(value) => setTermForm((c) => ({ ...c, end_date: value }))} /><CheckboxField label="Current term" checked={termForm.is_current} onChange={(value) => setTermForm((c) => ({ ...c, is_current: value }))} /><FormActions editing={Boolean(editingTermId)} onCancel={resetTermForm} isSaving={isSaving === "term"} label={editingTermId ? "Update term" : "Create term"} /></form></Panel>;
}
function TermViewer({ terms, sessions, editTerm }) { return <CardList title="View terms" items={terms} empty="No academic terms yet." render={(item) => <RecordCard key={item.id} title={displayTerm(item.name)} meta={item.academic_session_name || sessions.find((s) => s.id === item.academic_session_id)?.name || "No session"} status={item.is_current ? "current" : item.is_active ? "active" : "inactive"} onEdit={() => editTerm(item)} />} />; }

function ScaleEditor({ scaleForm, setScaleForm, saveScale, resetScaleForm, editingScaleId, isSaving }) { return <Panel title={editingScaleId ? "Edit grading scale" : "Create grading scale"} subtitle="Editing area"><form onSubmit={saveScale} className="grid gap-3"><TextField label="Grade" value={scaleForm.grade} onChange={(value) => setScaleForm((c) => ({ ...c, grade: value }))} placeholder="A" required /><TextField label="Min score" type="number" min="0" max="100" value={scaleForm.min_score} onChange={(value) => setScaleForm((c) => ({ ...c, min_score: value }))} required /><TextField label="Max score" type="number" min="0" max="100" value={scaleForm.max_score} onChange={(value) => setScaleForm((c) => ({ ...c, max_score: value }))} required /><TextField label="Remark" value={scaleForm.remark} onChange={(value) => setScaleForm((c) => ({ ...c, remark: value }))} placeholder="Excellent" /><FormActions editing={Boolean(editingScaleId)} onCancel={resetScaleForm} isSaving={isSaving === "scale"} label={editingScaleId ? "Update scale" : "Create scale"} /></form></Panel>; }
function ScaleViewer({ scales, editScale }) { return <CardList title="View grading scales" items={scales} empty="No grading scales yet." render={(item) => <RecordCard key={item.id} title={item.grade} meta={`${item.min_score} - ${item.max_score}`} description={item.remark || "No remark"} status={item.is_active ? "active" : "inactive"} onEdit={() => editScale(item)} />} />; }

function SubjectEditor({ subjectForm, setSubjectForm, saveSubject, resetSubjectForm, editingSubjectId, isSaving }) { return <Panel title={editingSubjectId ? "Edit subject" : "Create subject"} subtitle="Editing area"><form onSubmit={saveSubject} className="grid gap-3"><TextField label="Subject name" value={subjectForm.name} onChange={(value) => setSubjectForm((c) => ({ ...c, name: value }))} placeholder="Mathematics" required /><TextField label="Code" value={subjectForm.code} onChange={(value) => setSubjectForm((c) => ({ ...c, code: value }))} placeholder="MTH" /><TextField label="Description" value={subjectForm.description} onChange={(value) => setSubjectForm((c) => ({ ...c, description: value }))} placeholder="Optional description" /><FormActions editing={Boolean(editingSubjectId)} onCancel={resetSubjectForm} isSaving={isSaving === "subject"} label={editingSubjectId ? "Update subject" : "Create subject"} /></form></Panel>; }
function SubjectViewer({ subjects, editSubject }) { return <CardList title="View subjects" items={subjects} empty="No subjects yet." render={(item) => <RecordCard key={item.id} title={item.name} meta={item.code || "No code"} description={item.description || "No description"} status={item.is_active === false ? "inactive" : "active"} onEdit={() => editSubject(item)} />} />; }

function ClassEditor({ teachers, classForm, setClassForm, saveClass, resetClassForm, editingClassId, isSaving }) { return <Panel title={editingClassId ? "Edit class" : "Create class"} subtitle="Editing area"><form onSubmit={saveClass} className="grid gap-3"><TextField label="Class name" value={classForm.name} onChange={(value) => setClassForm((c) => ({ ...c, name: value }))} placeholder="JSS 1" required /><TextField label="Arm" value={classForm.arm} onChange={(value) => setClassForm((c) => ({ ...c, arm: value }))} placeholder="A" /><TextField label="Level" value={classForm.level} onChange={(value) => setClassForm((c) => ({ ...c, level: value }))} placeholder="Junior Secondary 1" /><SelectField label="Class teacher" value={classForm.teacher_id} onChange={(value) => setClassForm((c) => ({ ...c, teacher_id: value }))}><option value="">No class teacher</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacherLabel(teacher)}</option>)}</SelectField><CheckboxField label="Active" checked={classForm.is_active} onChange={(value) => setClassForm((c) => ({ ...c, is_active: value }))} /><FormActions editing={Boolean(editingClassId)} onCancel={resetClassForm} isSaving={isSaving === "class"} label={editingClassId ? "Update class" : "Create class"} /></form></Panel>; }
function ClassViewer({ classes, teachers, editClass }) { return <CardList title="View classes" items={classes} empty="No classes yet." render={(item) => <RecordCard key={item.id} title={displayClass(item)} meta={item.level || "No level"} description={`Class teacher: ${teacherLabel(teachers.find((teacher) => teacher.id === item.teacher_id))}`} status={item.is_active === false ? "inactive" : "active"} onEdit={() => editClass(item)} />} />; }

function ClassSubjectEditor({ classes, subjects, classSubjectForm, setClassSubjectForm, attachClassSubject, isSaving }) { return <Panel title="Attach subject to class" subtitle="Editing area"><form onSubmit={attachClassSubject} className="grid gap-3"><SelectField label="Class" value={classSubjectForm.class_id} onChange={(value) => setClassSubjectForm((c) => ({ ...c, class_id: value }))} required><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField><SelectField label="Subject" value={classSubjectForm.subject_id} onChange={(value) => setClassSubjectForm((c) => ({ ...c, subject_id: value }))} required><option value="">Select subject</option>{subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectField><CheckboxField label="Core subject" checked={classSubjectForm.is_core} onChange={(value) => setClassSubjectForm((c) => ({ ...c, is_core: value }))} /><Button type="submit" disabled={isSaving === "classSubject"}>{isSaving === "classSubject" ? "Attaching..." : "Attach subject"}</Button></form></Panel>; }
function ClassSubjectViewer({ classSubjects, deactivateClassSubject, isSaving }) { return <CardList title="Subjects for selected class" items={classSubjects} empty="Select a class and attach subjects." render={(item) => <RecordCard key={item.id} title={subjectLabel(item)} meta={item.subject_code || item.code || "No code"} description={item.is_offered_by_class ? "Attached to this class" : "Available in catalogue"} status={item.is_offered_by_class ? "attached" : "not attached"} actions={item.is_offered_by_class ? <Button size="sm" variant="outline" disabled={isSaving === item.id} onClick={() => deactivateClassSubject(item)}><X className="h-4 w-4" /> Remove</Button> : null} />} />; }
function ReviewFilters({ classSubjectForm, setClassSubjectForm, classes }) { return <Panel title="Review filter" subtitle="Choose a class to inspect its academic setup."><SelectField label="Class" value={classSubjectForm.class_id} onChange={(value) => setClassSubjectForm((c) => ({ ...c, class_id: value }))}><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField></Panel>; }
function StructureReview({ classes, subjects, assignments, classSubjects }) { return <Panel title="Structure review" subtitle="Viewing area"><div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><MiniStat label="Classes" value={classes.length} /><MiniStat label="Subjects" value={subjects.length} /><MiniStat label="Class subjects" value={classSubjects.filter((item) => item.is_offered_by_class).length} /><MiniStat label="Assignments" value={assignments.length} /></div></Panel>; }

function AssignmentEditor({ classes, teachers, classSubjects, assignmentForm, setAssignmentForm, saveAssignment, resetAssignmentForm, editingAssignmentId, isSaving }) { return <Panel title={editingAssignmentId ? "Change teacher" : "Assign subject teacher"} subtitle="Editing area"><form onSubmit={saveAssignment} className="grid gap-3"><SelectField label="Class" value={assignmentForm.class_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, class_id: value, class_subject_id: "" }))} required><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField><SelectField label="Class subject" value={assignmentForm.class_subject_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, class_subject_id: value }))} disabled={!assignmentForm.class_id} required><option value="">{assignmentForm.class_id ? "Select subject" : "Select class first"}</option>{classSubjects.map((item) => <option key={item.id} value={item.id}>{subjectLabel(item)}</option>)}</SelectField><SelectField label="Teacher" value={assignmentForm.teacher_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, teacher_id: value }))} required><option value="">Select teacher</option>{teachers.map((item) => <option key={item.id} value={item.id}>{teacherLabel(item)}</option>)}</SelectField><CheckboxField label="Core subject" checked={assignmentForm.is_core} onChange={(value) => setAssignmentForm((c) => ({ ...c, is_core: value }))} /><FormActions editing={Boolean(editingAssignmentId)} onCancel={resetAssignmentForm} isSaving={isSaving === "assignment"} label={editingAssignmentId ? "Change teacher" : "Assign teacher"} /></form></Panel>; }
function AssignmentViewer({ classes, subjects, teachers, assignments, assignmentFilters, setAssignmentFilters, editAssignment, updateAssignmentStatus, isSaving }) { return <Panel title="View assigned subjects" subtitle="Viewing area"><div className="mb-4 grid gap-3 sm:grid-cols-3"><SelectField label="Class" value={assignmentFilters.class_id} onChange={(value) => setAssignmentFilters((c) => ({ ...c, class_id: value }))}><option value="">All classes</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField><SelectField label="Subject" value={assignmentFilters.subject_id} onChange={(value) => setAssignmentFilters((c) => ({ ...c, subject_id: value }))}><option value="">All subjects</option>{subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectField><SelectField label="Teacher" value={assignmentFilters.teacher_id} onChange={(value) => setAssignmentFilters((c) => ({ ...c, teacher_id: value }))}><option value="">All teachers</option>{teachers.map((item) => <option key={item.id} value={item.id}>{teacherLabel(item)}</option>)}</SelectField></div><div className="grid gap-3 sm:grid-cols-2">{assignments.length === 0 ? <EmptyState icon={Users} title="No assignments" description="Assign teachers to class subjects first." /> : assignments.map((item) => <RecordCard key={item.id} title={`${item.subject_name || "Subject"} - ${item.class_name || "Class"} ${item.class_arm || ""}`.trim()} meta={item.teacher_name || teacherLabel(teachers.find((teacher) => teacher.id === item.teacher_id))} status={item.is_active ? "active" : "inactive"} onEdit={() => editAssignment(item)} actions={<Button size="sm" variant="outline" disabled={isSaving === item.id} onClick={() => updateAssignmentStatus(item, !item.is_active)}>{item.is_active ? "Deactivate" : "Activate"}</Button>} />)}</div></Panel>; }

function ResultFilters({ classes, subjects, sessions, termsForResultSession, resultFilters, updateResultFilter }) { return <Panel title="Select result records" subtitle="Editing area"><div className="grid gap-3"><SelectField label="Session" value={resultFilters.academic_session_id} onChange={(value) => updateResultFilter("academic_session_id", value)}><option value="">Select session</option>{sessions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectField><SelectField label="Term" value={resultFilters.academic_term_id} onChange={(value) => updateResultFilter("academic_term_id", value)}><option value="">Select term</option>{termsForResultSession.map((item) => <option key={item.id} value={item.id}>{displayTerm(item.name)}</option>)}</SelectField><SelectField label="Class" value={resultFilters.class_id} onChange={(value) => updateResultFilter("class_id", value)}><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField><SelectField label="Subject" value={resultFilters.subject_id} onChange={(value) => updateResultFilter("subject_id", value)}><option value="">Select subject</option>{subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectField></div></Panel>; }
function ResultEditor(props) { const { students, resultForm, setResultForm, saveResult, resetResultForm, editingResultId, selectedAssignment, isSaving } = props; return <><ResultFilters {...props} /><Panel title={editingResultId ? "Edit result" : "Record score"} subtitle={selectedAssignment ? `Assigned teacher: ${selectedAssignment.teacher_name || "Teacher"}` : "Assign a teacher before score entry."}><form onSubmit={saveResult} className="grid gap-3"><SelectField label="Student" value={resultForm.student_id} onChange={(value) => setResultForm((c) => ({ ...c, student_id: value }))} required><option value="">Select student</option>{students.map((item) => <option key={item.id} value={item.id}>{studentLabel(item)}</option>)}</SelectField><TextField label="Test" type="number" min="0" max="100" value={resultForm.test_score} onChange={(value) => setResultForm((c) => ({ ...c, test_score: value }))} /><TextField label="Assessment" type="number" min="0" max="100" value={resultForm.assessment_score} onChange={(value) => setResultForm((c) => ({ ...c, assessment_score: value }))} /><TextField label="Exam" type="number" min="0" max="100" value={resultForm.exam_score} onChange={(value) => setResultForm((c) => ({ ...c, exam_score: value }))} /><SelectField label="Status" value={resultForm.status} onChange={(value) => setResultForm((c) => ({ ...c, status: value }))}><option value="draft">Draft</option><option value="submitted">Submitted</option></SelectField><p className="rounded-xl border border-border/70 bg-surface-muted/25 px-3 py-2 text-sm font-semibold text-text">Total: {scoreTotal(resultForm)}</p><FormActions editing={Boolean(editingResultId)} onCancel={resetResultForm} isSaving={isSaving === "result"} label={editingResultId ? "Update result" : "Save result"} /></form></Panel></>; }
function ResultViewer({ results, status, editResult, updateResultStatus, isSaving }) { const rows = status ? results.filter((item) => item.status === status) : results; return <CardList title="View results" items={rows} empty="No results for the selected filters." render={(item) => <RecordCard key={item.id} title={item.student_name || "Student"} meta={`${item.subject_name || "Subject"} / Total ${item.total_score ?? "--"}`} description={`Grade: ${item.grade || "--"}`} status={item.status} onEdit={() => editResult(item)} actions={<Button size="sm" variant="outline" disabled={isSaving === item.id} onClick={() => updateResultStatus(item, item.status === "submitted" ? "draft" : "submitted")}>{item.status === "submitted" ? "Reopen" : "Submit"}</Button>} />} />; }

function ReportFilters({ classes, sessions, termsForReportSession, reportFilters, updateReportFilter }) { return <Panel title="Report-card filters" subtitle="Editing area"><div className="grid gap-3"><SelectField label="Session" value={reportFilters.academic_session_id} onChange={(value) => updateReportFilter("academic_session_id", value)}><option value="">Select session</option>{sessions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</SelectField><SelectField label="Term" value={reportFilters.academic_term_id} onChange={(value) => updateReportFilter("academic_term_id", value)}><option value="">Select term</option>{termsForReportSession.map((item) => <option key={item.id} value={item.id}>{displayTerm(item.name)}</option>)}</SelectField><SelectField label="Class" value={reportFilters.class_id} onChange={(value) => updateReportFilter("class_id", value)}><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField></div></Panel>; }
function ReportOverview({ reportCardOverview }) { return <Panel title="Report-card overview" subtitle="Viewing area"><div className="grid grid-cols-2 gap-3 sm:grid-cols-4"><MiniStat label="Students" value={reportCardOverview?.total_students ?? 0} /><MiniStat label="Generated" value={reportCardOverview?.generated_count ?? 0} /><MiniStat label="Published" value={reportCardOverview?.published_count ?? 0} /><MiniStat label="Missing" value={reportCardOverview?.missing_count ?? 0} /></div></Panel>; }
function ReportGenerate({ generateReportCard, isSaving }) { return <Panel title="Generate report cards" subtitle="Use selected class/session/term filters."><div className="grid gap-3 sm:grid-cols-2"><Button disabled={isSaving === "reportSingle"} onClick={() => generateReportCard(false)}><Plus className="h-4 w-4" /> Generate one</Button><Button disabled={isSaving === "reportBulk"} onClick={() => generateReportCard(true)}><FileText className="h-4 w-4" /> Generate class batch</Button></div></Panel>; }
function ReportCardViewer({ reportCards, publishReportCard, publishMode, isSaving }) { return <CardList title={publishMode ? "Publish report cards" : "Review report cards"} items={reportCards} empty="No report cards for the selected filters." render={(item) => <RecordCard key={item.id} title={item.student_name || "Student"} meta={`${item.academic_term_name || "Term"} / Avg ${item.average_score ?? "--"}`} description={`Position: ${item.position || "--"}/${item.position_out_of || "--"}`} status={item.status} actions={item.status !== "published" ? <Button size="sm" variant="outline" disabled={isSaving === item.id} onClick={() => publishReportCard(item.id)}>Publish</Button> : null} />} />; }

function SearchEditor({ searchQuery, setSearchQuery }) { return <Panel title="Search academic records" subtitle="Editing area"><TextField label="Search" value={searchQuery} onChange={setSearchQuery} placeholder="Student name, admission number, report card..." /></Panel>; }
function SearchViewer({ searchResults }) { return <CardList title="Search results" items={searchResults} empty="Start typing at least two characters." render={(item) => <RecordCard key={item.id || item.label} title={item.title || item.name || item.label || "Record"} meta={item.type || item.category || "Academic record"} description={item.description || item.subtitle || ""} status={item.status || "found"} />} />; }

function CardList({ title, items, empty, render }) { return <Panel title={title} subtitle="Viewing area">{items.length === 0 ? <EmptyState icon={FileSearch} title={empty} description="Records will appear here when available." /> : <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">{items.map(render)}</div>}</Panel>; }
function RecordCard({ title, meta, description, status, onEdit, actions }) { return <div className="rounded-2xl border border-border/70 bg-surface px-4 py-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="break-words text-sm font-semibold text-text">{title}</p>{meta ? <p className="mt-1 break-words text-xs text-text-muted">{meta}</p> : null}</div>{status ? <StatusPill value={status} /> : null}</div>{description ? <p className="mt-3 line-clamp-3 text-xs leading-5 text-text-muted">{description}</p> : null}<div className="mt-4 flex flex-wrap gap-2">{onEdit ? <Button size="sm" variant="outline" onClick={onEdit}><Edit3 className="h-3.5 w-3.5" /> Edit</Button> : null}{actions}</div></div>; }
function MiniStat({ label, value }) { return <div className="rounded-2xl border border-border/70 bg-surface-muted/20 px-3 py-3"><p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">{label}</p><p className="mt-1 text-xl font-semibold text-text">{value}</p></div>; }
function StatusPill({ value }) { return <span className="shrink-0 rounded-full bg-primary-subtle px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-primary">{statusLabel(value)}</span>; }
function Alert({ children }) { return <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">{children}</div>; }

export default AcademicWorkflowPage;
