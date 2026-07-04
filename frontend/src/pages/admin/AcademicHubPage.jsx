import { useEffect, useMemo, useState } from "react";
import { BookOpen, ClipboardList, Edit3, FileText, Pencil, Plus, Search, Users, X } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import EmptyState from "../../components/shared/EmptyState";
import { CheckboxField, SelectField, TextField } from "../../components/academic/AcademicSelectors";
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
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";

const tabs = [
  { id: "setup", label: "Setup", icon: BookOpen, description: "Sessions, terms, grading scales, and subjects" },
  { id: "assignments", label: "Teacher Assignments", icon: Users, description: "Assign subject teachers to class subjects" },
  { id: "results", label: "Results", icon: Pencil, description: "Record, correct, submit, and reopen scores" },
  { id: "reportCards", label: "Report Cards", icon: FileText, description: "Generate, regenerate, publish, and print" },
  { id: "search", label: "Search", icon: Search, description: "Find academic records quickly" },
];

const blankSession = { name: "", start_date: "", end_date: "", is_current: false, is_active: true };
const blankTerm = { academic_session_id: "", name: "first_term", start_date: "", end_date: "", is_current: false, is_active: true };
const blankScale = { grade: "", min_score: "", max_score: "", remark: "", is_active: true };
const blankSubject = { name: "", code: "", description: "" };
const blankAssignment = { class_id: "", class_subject_id: "", teacher_id: "", is_core: true };
const blankResult = { student_id: "", teacher_assignment_id: "", test_score: "", assessment_score: "", exam_score: "", status: "draft" };
const blankResultFilters = { class_id: "", subject_id: "", academic_session_id: "", academic_term_id: "" };

const compactDate = (value) => (value ? new Date(value).toLocaleDateString() : "--");
const displayScore = (value) => (value === null || value === undefined || value === "" ? "--" : value);
const toNullableScore = (value) => (value === "" || value === null || value === undefined ? null : Number(value));
const isSubmitted = (result) => result?.status === "submitted";
const subjectLabel = (item) => item?.subject_name || item?.name || item?.subject_code || item?.code || "Subject";
const classLabel = (item) => [item?.class_name || item?.name, item?.class_arm || item?.arm].filter(Boolean).join(" ") || "Class";
const teacherLabel = (teacher) => displayPerson(teacher) || teacher?.teacher_name || teacher?.teacher_staff_id || "Teacher";
const studentLabel = (student) => displayPerson(student) || student?.student_name || student?.admission_number || "Student";
const scoreTotal = (form) => [form.test_score, form.assessment_score, form.exam_score].reduce((sum, value) => sum + (Number(value) || 0), 0);
const hasAllScores = (form) => [form.test_score, form.assessment_score, form.exam_score].every((value) => value !== "" && value !== null && value !== undefined);
const studentClassId = (student) => student?.class_id || student?.classroom_id || student?.class?.id || student?.classroom?.id || "";

function AcademicHubPage() {
  const [activeTab, setActiveTab] = useState("setup");
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [scales, setScales] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [classes, setClasses] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [classSubjects, setClassSubjects] = useState([]);
  const [results, setResults] = useState([]);
  const [reportCards, setReportCards] = useState([]);
  const [reportCardOverview, setReportCardOverview] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [sessionForm, setSessionForm] = useState(blankSession);
  const [termForm, setTermForm] = useState(blankTerm);
  const [scaleForm, setScaleForm] = useState(blankScale);
  const [subjectForm, setSubjectForm] = useState(blankSubject);
  const [assignmentForm, setAssignmentForm] = useState(blankAssignment);
  const [resultForm, setResultForm] = useState(blankResult);
  const [editingSessionId, setEditingSessionId] = useState("");
  const [editingTermId, setEditingTermId] = useState("");
  const [editingScaleId, setEditingScaleId] = useState("");
  const [editingSubjectId, setEditingSubjectId] = useState("");
  const [editingAssignmentId, setEditingAssignmentId] = useState("");
  const [editingResultId, setEditingResultId] = useState("");
  const [assignmentFilters, setAssignmentFilters] = useState({ class_id: "", subject_id: "", teacher_id: "" });
  const [resultFilters, setResultFilters] = useState(blankResultFilters);
  const [reportFilters, setReportFilters] = useState(blankResultFilters);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState("");
  const [error, setError] = useState(null);
  const { showSuccess, showError, showWarning } = useToast();
  const { getFeatureGuard } = useSubscription();
  const reportCardGuard = getFeatureGuard(FEATURE_CODES.REPORT_CARDS);

  const currentSession = sessions.find((item) => item.is_current) || sessions[0];
  const currentTerm = terms.find((item) => item.is_current) || terms[0];
  const activeTabMeta = tabs.find((item) => item.id === activeTab) || tabs[0];
  const assignmentSubject = classSubjects.find((item) => item.id === assignmentForm.class_subject_id);
  const termsForResultSession = useMemo(() => terms.filter((term) => !resultFilters.academic_session_id || term.academic_session_id === resultFilters.academic_session_id), [terms, resultFilters.academic_session_id]);
  const termsForReportSession = useMemo(() => terms.filter((term) => !reportFilters.academic_session_id || term.academic_session_id === reportFilters.academic_session_id), [terms, reportFilters.academic_session_id]);
  const visibleAssignments = useMemo(() => assignments.filter((item) => (!assignmentFilters.class_id || item.class_id === assignmentFilters.class_id) && (!assignmentFilters.subject_id || item.subject_id === assignmentFilters.subject_id) && (!assignmentFilters.teacher_id || item.teacher_id === assignmentFilters.teacher_id)), [assignments, assignmentFilters]);
  const selectedAssignment = useMemo(() => {
    if (editingResultId && resultForm.teacher_assignment_id) return assignments.find((item) => item.id === resultForm.teacher_assignment_id);
    return assignments.find((item) => item.is_active && item.class_id === resultFilters.class_id && item.subject_id === resultFilters.subject_id);
  }, [assignments, editingResultId, resultForm.teacher_assignment_id, resultFilters.class_id, resultFilters.subject_id]);
  const visibleResults = useMemo(() => results.filter((item) => !resultFilters.subject_id || item.subject_id === resultFilters.subject_id), [results, resultFilters.subject_id]);
  const visibleReportCards = useMemo(() => reportCards.filter((card) => (!reportFilters.academic_session_id || card.academic_session_id === reportFilters.academic_session_id) && (!reportFilters.academic_term_id || card.academic_term_id === reportFilters.academic_term_id) && (!reportFilters.class_id || card.class_id === reportFilters.class_id)), [reportCards, reportFilters]);
  const stats = useMemo(() => ({ sessions: sessions.length, terms: terms.length, subjects: subjects.length, assignments: assignments.filter((item) => item.is_active).length, drafts: results.filter((item) => item.status === "draft").length, submitted: results.filter((item) => item.status === "submitted").length }), [sessions, terms, subjects, assignments, results]);

  const loadWorkspace = async () => {
    setError(null);
    const [sessionResponse, termResponse, scaleResponse, subjectResponse, classResponse, teacherResponse, assignmentResponse, reportCardResponse] = await Promise.all([
      academicService.listSessions(), academicService.listTerms(), academicService.listGradingScales(), subjectService.getSubjects({ isActive: true, limit: 100 }), classService.getClasses({ limit: 100 }), teacherService.getTeachers({ limit: 100 }), academicService.listTeacherAssignments({ limit: 100 }), reportCardService.listAdminReportCards({ limit: 100 }),
    ]);
    const nextSessions = sessionResponse?.items || [];
    const nextTerms = termResponse?.items || [];
    const defaultSessionId = nextSessions.find((item) => item.is_current)?.id || nextSessions[0]?.id || "";
    const defaultTermId = nextTerms.find((item) => item.is_current)?.id || nextTerms[0]?.id || "";
    setSessions(nextSessions); setTerms(nextTerms); setScales(scaleResponse?.items || []); setSubjects(subjectResponse?.items || []); setClasses(classResponse?.items || []); setTeachers(teacherResponse?.items || []); setAssignments(assignmentResponse?.items || []); setReportCards(reportCardResponse?.items || []);
    setTermForm((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId }));
    setResultFilters((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId, academic_term_id: current.academic_term_id || defaultTermId }));
    setReportFilters((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId, academic_term_id: current.academic_term_id || defaultTermId }));
  };

  useEffect(() => { let mounted = true; async function load() { setIsLoading(true); try { await loadWorkspace(); } catch (err) { if (mounted) setError(getErrorMessage(err, "Could not load academic hub.")); } finally { if (mounted) setIsLoading(false); } } load(); return () => { mounted = false; }; }, []);
  useEffect(() => { let mounted = true; async function loadClassSubjects() { if (!assignmentForm.class_id) { setClassSubjects([]); return; } try { const response = await academicService.listClassSubjects(assignmentForm.class_id, { active_only: true }); if (mounted) setClassSubjects(response?.items || []); } catch (err) { if (mounted) setClassSubjects([]); showError(getErrorMessage(err, "Could not load subjects for this class.")); } } loadClassSubjects(); return () => { mounted = false; }; }, [assignmentForm.class_id, showError]);
  useEffect(() => { let mounted = true; async function loadStudentsForClass() { if (!resultFilters.class_id) { setStudents([]); return; } try { const response = await studentService.getAdminStudents({ classId: resultFilters.class_id, limit: 100 }); const items = (response?.items || []).filter((student) => studentClassId(student) === resultFilters.class_id); if (mounted) setStudents(items); } catch (err) { if (mounted) setStudents([]); showError(getErrorMessage(err, "Could not load students for this class.")); } } loadStudentsForClass(); return () => { mounted = false; }; }, [resultFilters.class_id, showError]);
  useEffect(() => { let mounted = true; async function loadFilteredResults() { if (!resultFilters.class_id || !resultFilters.academic_session_id || !resultFilters.academic_term_id) { setResults([]); return; } try { const response = await academicService.listAdminResults({ class_id: resultFilters.class_id, academic_session_id: resultFilters.academic_session_id, academic_term_id: resultFilters.academic_term_id, limit: 100 }); if (mounted) setResults(response?.items || []); } catch (err) { if (mounted) setResults([]); showError(getErrorMessage(err, "Could not load results for this filter.")); } } loadFilteredResults(); return () => { mounted = false; }; }, [resultFilters.class_id, resultFilters.academic_session_id, resultFilters.academic_term_id, showError]);
  useEffect(() => { let mounted = true; async function loadOverview() { if (activeTab !== "reportCards" || !reportFilters.class_id || !reportFilters.academic_session_id || !reportFilters.academic_term_id) { if (mounted) setReportCardOverview(null); return; } try { const response = await reportCardService.getClassOverview({ class_id: reportFilters.class_id, academic_session_id: reportFilters.academic_session_id, academic_term_id: reportFilters.academic_term_id }); if (mounted) setReportCardOverview(response); } catch { if (mounted) setReportCardOverview(null); } } loadOverview(); return () => { mounted = false; }; }, [activeTab, reportFilters.class_id, reportFilters.academic_session_id, reportFilters.academic_term_id]);
  useEffect(() => { let mounted = true; const timeout = window.setTimeout(async () => { if (searchQuery.trim().length < 2) { setSearchResults([]); return; } try { const response = await searchService.searchTenant(searchQuery.trim(), 8); if (mounted) setSearchResults(response?.items || []); } catch { if (mounted) setSearchResults([]); } }, 250); return () => { mounted = false; window.clearTimeout(timeout); }; }, [searchQuery]);

  const refreshAssignments = async () => { const response = await academicService.listTeacherAssignments({ limit: 100 }); setAssignments(response?.items || []); };
  const resetSessionForm = () => { setSessionForm(blankSession); setEditingSessionId(""); };
  const resetTermForm = () => { setTermForm({ ...blankTerm, academic_session_id: resultFilters.academic_session_id || currentSession?.id || "" }); setEditingTermId(""); };
  const resetScaleForm = () => { setScaleForm(blankScale); setEditingScaleId(""); };
  const resetSubjectForm = () => { setSubjectForm(blankSubject); setEditingSubjectId(""); };
  const resetAssignmentForm = () => { setAssignmentForm(blankAssignment); setEditingAssignmentId(""); setClassSubjects([]); };
  const resetResultForm = () => { setResultForm(blankResult); setEditingResultId(""); };
  const updateResultFilter = (key, value) => { setResultFilters((current) => ({ ...current, [key]: value, ...(key === "academic_session_id" ? { academic_term_id: "" } : {}) })); resetResultForm(); };
  const updateReportFilter = (key, value) => setReportFilters((current) => ({ ...current, [key]: value, ...(key === "academic_session_id" ? { academic_term_id: "" } : {}) }));

  const saveSession = async (event) => { event.preventDefault(); setIsSaving("session"); try { const payload = { name: sessionForm.name, start_date: sessionForm.start_date || null, end_date: sessionForm.end_date || null, is_current: sessionForm.is_current, is_active: sessionForm.is_active }; const saved = editingSessionId ? await academicService.updateSession(editingSessionId, payload) : await academicService.createSession(payload); setSessions((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); resetSessionForm(); showSuccess(editingSessionId ? "Academic session updated." : "Academic session created."); if (saved.is_current) await loadWorkspace(); } catch (err) { showError(getErrorMessage(err, "Could not save academic session.")); } finally { setIsSaving(""); } };
  const saveTerm = async (event) => { event.preventDefault(); setIsSaving("term"); try { const payload = { academic_session_id: termForm.academic_session_id, name: termForm.name, start_date: termForm.start_date || null, end_date: termForm.end_date || null, is_current: termForm.is_current, is_active: termForm.is_active }; const saved = editingTermId ? await academicService.updateTerm(editingTermId, payload) : await academicService.createTerm(payload); setTerms((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); resetTermForm(); showSuccess(editingTermId ? "Academic term updated." : "Academic term created."); if (saved.is_current) await loadWorkspace(); } catch (err) { showError(getErrorMessage(err, "Could not save academic term.")); } finally { setIsSaving(""); } };
  const saveScale = async (event) => { event.preventDefault(); setIsSaving("scale"); try { const payload = { grade: scaleForm.grade, min_score: Number(scaleForm.min_score), max_score: Number(scaleForm.max_score), remark: scaleForm.remark || null, is_active: scaleForm.is_active }; const saved = editingScaleId ? await academicService.updateGradingScale(editingScaleId, payload) : await academicService.createGradingScale(payload); setScales((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); resetScaleForm(); showSuccess(editingScaleId ? "Grading scale updated." : "Grading scale created."); } catch (err) { showError(getErrorMessage(err, "Could not save grading scale.")); } finally { setIsSaving(""); } };
  const saveSubject = async (event) => { event.preventDefault(); setIsSaving("subject"); try { const payload = { name: subjectForm.name, code: subjectForm.code || null, description: subjectForm.description || null }; const saved = editingSubjectId ? await subjectService.updateSubject(editingSubjectId, payload) : await subjectService.createSubject(payload); setSubjects((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); resetSubjectForm(); showSuccess(editingSubjectId ? "Subject updated." : "Subject created."); } catch (err) { showError(getErrorMessage(err, "Could not save subject.")); } finally { setIsSaving(""); } };
  const saveAssignment = async (event) => { event.preventDefault(); if (!assignmentForm.class_id || !assignmentForm.class_subject_id || !assignmentForm.teacher_id) { showWarning("Select a class, subject, and teacher before saving."); return; } setIsSaving("assignment"); try { const saved = editingAssignmentId ? await academicService.reassignTeacherAssignment(editingAssignmentId, { teacher_id: assignmentForm.teacher_id }) : await academicService.createTeacherAssignment({ class_subject_id: assignmentForm.class_subject_id, teacher_id: assignmentForm.teacher_id, is_core: assignmentForm.is_core }); await refreshAssignments(); if (assignmentForm.class_id) { const classSubjectResponse = await academicService.listClassSubjects(assignmentForm.class_id, { active_only: true }); setClassSubjects(classSubjectResponse?.items || []); } setAssignmentFilters({ class_id: saved.class_id || assignmentForm.class_id, subject_id: saved.subject_id || assignmentSubject?.subject_id || "", teacher_id: saved.teacher_id || assignmentForm.teacher_id }); resetAssignmentForm(); showSuccess(editingAssignmentId ? "Subject teacher changed." : "Subject teacher assigned."); } catch (err) { showError(getErrorMessage(err, "Could not save teacher assignment.")); } finally { setIsSaving(""); } };
  const deactivateAssignment = async (assignment) => { setIsSaving(assignment.id); try { const saved = await academicService.deactivateTeacherAssignment(assignment.id); setAssignments((current) => current.map((item) => (item.id === saved.id ? saved : item))); showSuccess("Assignment deactivated. The subject remains attached to the class."); } catch (err) { showError(getErrorMessage(err, "Could not deactivate assignment.")); } finally { setIsSaving(""); } };
  const loadResultsForCurrentFilter = async () => { if (!resultFilters.class_id || !resultFilters.academic_session_id || !resultFilters.academic_term_id) return; const response = await academicService.listAdminResults({ class_id: resultFilters.class_id, academic_session_id: resultFilters.academic_session_id, academic_term_id: resultFilters.academic_term_id, limit: 100 }); setResults(response?.items || []); };
  const saveResult = async (event) => { event.preventDefault(); const assignmentId = editingResultId && resultForm.teacher_assignment_id ? resultForm.teacher_assignment_id : selectedAssignment?.id; if (!resultFilters.class_id || !resultFilters.subject_id) { showWarning("Select a class and subject before recording scores."); return; } if (!assignmentId) { showWarning("Assign a teacher to this class-subject before saving scores."); return; } if (!resultForm.student_id || !resultFilters.academic_session_id || !resultFilters.academic_term_id) { showWarning("Select student, session, and term before saving scores."); return; } if (resultForm.status === "submitted" && !hasAllScores(resultForm)) { showWarning("All three scores are required before submitting a result."); return; } if (scoreTotal(resultForm) > 100) { showWarning("The combined score cannot exceed 100."); return; } setIsSaving("result"); try { const saved = await academicService.saveAdminResult({ student_id: resultForm.student_id, teacher_assignment_id: assignmentId, academic_session_id: resultFilters.academic_session_id, academic_term_id: resultFilters.academic_term_id, test_score: toNullableScore(resultForm.test_score), assessment_score: toNullableScore(resultForm.assessment_score), exam_score: toNullableScore(resultForm.exam_score), status: resultForm.status }); await loadResultsForCurrentFilter(); setResults((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); resetResultForm(); showSuccess(saved.status === "submitted" ? "Result submitted." : "Result saved as draft."); } catch (err) { showError(getErrorMessage(err, "Could not save result.")); } finally { setIsSaving(""); } };
  const updateResultStatus = async (result, nextStatus) => { setIsSaving(result.id); try { const saved = await academicService.updateResultStatus(result.id, { status: nextStatus }); setResults((current) => current.map((item) => (item.id === saved.id ? saved : item))); showSuccess(nextStatus === "submitted" ? "Result submitted." : "Result reopened as draft."); } catch (err) { showError(getErrorMessage(err, "Could not update result status.")); } finally { setIsSaving(""); } };
  const generateReportCard = async (payload, label) => { setIsSaving(label); try { const response = await reportCardService.generateReportCard(payload); if (Array.isArray(response?.generated)) { setReportCards((current) => [...response.generated, ...current]); showSuccess(`Generated ${response.generated.length} report cards. Skipped ${response.skipped?.length || 0}.`); } else { setReportCards((current) => [response, ...current.filter((item) => item.id !== response.id)]); showSuccess("Report card generated."); } } catch (err) { showError(getErrorMessage(err, "Could not generate report card.")); } finally { setIsSaving(""); } };
  const regenerateReportCard = async (reportCardId) => { setIsSaving(reportCardId); try { const saved = await reportCardService.regenerateReportCard(reportCardId); setReportCards((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); showSuccess("Report card regenerated."); } catch (err) { showError(getErrorMessage(err, "Could not regenerate report card.")); } finally { setIsSaving(""); } };
  const publishReportCard = async (reportCardId) => { setIsSaving(reportCardId); try { const saved = await reportCardService.publishReportCard(reportCardId); setReportCards((current) => current.map((item) => (item.id === saved.id ? saved : item))); showSuccess("Report card published."); } catch (err) { showError(getErrorMessage(err, "Could not publish report card.")); } finally { setIsSaving(""); } };

  const editSession = (session) => { setEditingSessionId(session.id); setSessionForm({ name: session.name || "", start_date: session.start_date || "", end_date: session.end_date || "", is_current: Boolean(session.is_current), is_active: session.is_active !== false }); };
  const editTerm = (term) => { setEditingTermId(term.id); setTermForm({ academic_session_id: term.academic_session_id || "", name: term.name || "first_term", start_date: term.start_date || "", end_date: term.end_date || "", is_current: Boolean(term.is_current), is_active: term.is_active !== false }); };
  const editScale = (scale) => { setEditingScaleId(scale.id); setScaleForm({ grade: scale.grade || "", min_score: scale.min_score ?? "", max_score: scale.max_score ?? "", remark: scale.remark || "", is_active: scale.is_active !== false }); };
  const editSubject = (subject) => { setEditingSubjectId(subject.id); setSubjectForm({ name: subject.name || "", code: subject.code || "", description: subject.description || "" }); };
  const editAssignment = (assignment) => { setEditingAssignmentId(assignment.id); setAssignmentForm({ class_id: assignment.class_id || "", class_subject_id: assignment.class_subject_id || "", teacher_id: assignment.teacher_id || "", is_core: true }); };
  const editResult = (result) => { setEditingResultId(result.id); setResultFilters({ class_id: result.class_id || "", subject_id: result.subject_id || "", academic_session_id: result.academic_session_id || "", academic_term_id: result.academic_term_id || "" }); setResultForm({ student_id: result.student_id || "", teacher_assignment_id: result.teacher_assignment_id || "", test_score: result.test_score ?? "", assessment_score: result.assessment_score ?? "", exam_score: result.exam_score ?? "", status: result.status || "draft" }); };

  if (isLoading) return <DashboardLayout role="admin" title="Academic Hub"><LoadingState label="Loading academic hub..." /></DashboardLayout>;

  return (
    <DashboardLayout role="admin" title="Academic Hub" description="Configure academic setup, teacher assignments, results, and official report cards.">
      {error ? <Alert tone="error">{error}</Alert> : null}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6"><Metric label="Sessions" value={stats.sessions} /><Metric label="Terms" value={stats.terms} /><Metric label="Subjects" value={stats.subjects} /><Metric label="Assignments" value={stats.assignments} /><Metric label="Drafts" value={stats.drafts} /><Metric label="Submitted" value={stats.submitted} /></section>
      <section className="rounded-[1.35rem] border border-border bg-surface p-3 shadow-sm"><div className="flex flex-col gap-2 lg:flex-row">{tabs.map((tab) => { const Icon = tab.icon; const active = activeTab === tab.id; return <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`flex flex-1 items-start gap-3 rounded-2xl px-3 py-3 text-left transition ${active ? "bg-primary text-text-inverse shadow-sm" : "text-text-soft hover:bg-surface-muted hover:text-text"}`}><Icon className="mt-0.5 h-4 w-4 shrink-0" /><span className="min-w-0"><span className="block text-sm font-semibold">{tab.label}</span><span className={`mt-1 block text-xs leading-5 ${active ? "text-white/80" : "text-text-muted"}`}>{tab.description}</span></span></button>; })}</div></section>
      <section className="rounded-[1.35rem] border border-border bg-surface p-4 shadow-sm sm:p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-semibold text-primary">{activeTabMeta.label}</p><h2 className="mt-1 text-lg font-semibold text-text sm:text-xl">{activeTabMeta.description}</h2></div><div className="grid grid-cols-2 gap-2 text-xs sm:min-w-[280px]"><Context label="Current Session" value={currentSession?.name || "Not set"} /><Context label="Current Term" value={currentTerm?.name ? displayTerm(currentTerm.name) : "Not set"} /></div></div></section>
      {activeTab === "setup" ? <SetupTab sessions={sessions} terms={terms} scales={scales} subjects={subjects} sessionForm={sessionForm} setSessionForm={setSessionForm} termForm={termForm} setTermForm={setTermForm} scaleForm={scaleForm} setScaleForm={setScaleForm} subjectForm={subjectForm} setSubjectForm={setSubjectForm} saveSession={saveSession} saveTerm={saveTerm} saveScale={saveScale} saveSubject={saveSubject} editSession={editSession} editTerm={editTerm} editScale={editScale} editSubject={editSubject} resetSessionForm={resetSessionForm} resetTermForm={resetTermForm} resetScaleForm={resetScaleForm} resetSubjectForm={resetSubjectForm} editingSessionId={editingSessionId} editingTermId={editingTermId} editingScaleId={editingScaleId} editingSubjectId={editingSubjectId} isSaving={isSaving} /> : null}
      {activeTab === "assignments" ? <AssignmentsTab classes={classes} subjects={subjects} teachers={teachers} classSubjects={classSubjects} assignments={assignments} assignmentFilters={assignmentFilters} setAssignmentFilters={setAssignmentFilters} assignmentForm={assignmentForm} setAssignmentForm={setAssignmentForm} visibleAssignments={visibleAssignments} saveAssignment={saveAssignment} editAssignment={editAssignment} resetAssignmentForm={resetAssignmentForm} editingAssignmentId={editingAssignmentId} deactivateAssignment={deactivateAssignment} isSaving={isSaving} /> : null}
      {activeTab === "results" ? <ResultsTab classes={classes} subjects={subjects} sessions={sessions} terms={termsForResultSession} students={students} resultFilters={resultFilters} updateResultFilter={updateResultFilter} selectedAssignment={selectedAssignment} resultForm={resultForm} setResultForm={setResultForm} saveResult={saveResult} editResult={editResult} resetResultForm={resetResultForm} editingResultId={editingResultId} visibleResults={visibleResults} updateResultStatus={updateResultStatus} isSaving={isSaving} /> : null}
      {activeTab === "reportCards" ? <ReportCardsTab classes={classes} sessions={sessions} terms={termsForReportSession} reportFilters={reportFilters} updateReportFilter={updateReportFilter} reportCardOverview={reportCardOverview} reportCards={visibleReportCards} generateReportCard={generateReportCard} regenerateReportCard={regenerateReportCard} publishReportCard={publishReportCard} isSaving={isSaving} reportCardGuard={reportCardGuard} /> : null}
      {activeTab === "search" ? <SearchTab searchQuery={searchQuery} setSearchQuery={setSearchQuery} searchResults={searchResults} /> : null}
    </DashboardLayout>
  );
}

function SetupTab({ sessions, terms, scales, subjects, sessionForm, setSessionForm, termForm, setTermForm, scaleForm, setScaleForm, subjectForm, setSubjectForm, saveSession, saveTerm, saveScale, saveSubject, editSession, editTerm, editScale, editSubject, resetSessionForm, resetTermForm, resetScaleForm, resetSubjectForm, editingSessionId, editingTermId, editingScaleId, editingSubjectId, isSaving }) {
  return <div className="grid gap-5 xl:grid-cols-2"><Panel title={editingSessionId ? "Edit session" : "Create session"} subtitle="Manage academic years like 2026/2027."><form onSubmit={saveSession} className="form-grid"><TextField label="Session" value={sessionForm.name} onChange={(value) => setSessionForm((c) => ({ ...c, name: value }))} placeholder="2026/2027" required /><TextField label="Start" type="date" value={sessionForm.start_date} onChange={(value) => setSessionForm((c) => ({ ...c, start_date: value }))} /><TextField label="End" type="date" value={sessionForm.end_date} onChange={(value) => setSessionForm((c) => ({ ...c, end_date: value }))} /><CheckboxField label="Current" checked={sessionForm.is_current} onChange={(value) => setSessionForm((c) => ({ ...c, is_current: value }))} /><FormActions editing={Boolean(editingSessionId)} onCancel={resetSessionForm} isSaving={isSaving === "session"} label={editingSessionId ? "Update session" : "Create session"} /></form><DataTable headers={["Session", "Dates", "Status", "Actions"]} emptyText="No academic sessions yet." rows={sessions} renderRow={(session) => <tr key={session.id}><Cell label="Session"><strong>{session.name}</strong></Cell><Cell label="Dates">{compactDate(session.start_date)} - {compactDate(session.end_date)}</Cell><Cell label="Status"><StatusPill value={session.is_current ? "current" : session.is_active ? "active" : "inactive"} /></Cell><Cell label="Actions"><button type="button" className="btn-ghost" onClick={() => editSession(session)}><Edit3 className="h-3.5 w-3.5" /> Edit</button></Cell></tr>} /></Panel><Panel title={editingTermId ? "Edit term" : "Create term"} subtitle="Terms are scoped to a session."><form onSubmit={saveTerm} className="form-grid"><SelectField label="Session" value={termForm.academic_session_id} onChange={(value) => setTermForm((c) => ({ ...c, academic_session_id: value }))} required><option value="">Select session</option>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</SelectField><SelectField label="Term" value={termForm.name} onChange={(value) => setTermForm((c) => ({ ...c, name: value }))}><option value="first_term">First Term</option><option value="second_term">Second Term</option><option value="third_term">Third Term</option></SelectField><TextField label="Start" type="date" value={termForm.start_date} onChange={(value) => setTermForm((c) => ({ ...c, start_date: value }))} /><TextField label="End" type="date" value={termForm.end_date} onChange={(value) => setTermForm((c) => ({ ...c, end_date: value }))} /><CheckboxField label="Current" checked={termForm.is_current} onChange={(value) => setTermForm((c) => ({ ...c, is_current: value }))} /><FormActions editing={Boolean(editingTermId)} onCancel={resetTermForm} isSaving={isSaving === "term"} label={editingTermId ? "Update term" : "Create term"} /></form><DataTable headers={["Term", "Session", "Dates", "Actions"]} emptyText="No academic terms yet." rows={terms} renderRow={(term) => <tr key={term.id}><Cell label="Term"><strong>{displayTerm(term.name)}</strong></Cell><Cell label="Session">{sessions.find((session) => session.id === term.academic_session_id)?.name || "--"}</Cell><Cell label="Dates">{compactDate(term.start_date)} - {compactDate(term.end_date)}</Cell><Cell label="Actions"><button type="button" className="btn-ghost" onClick={() => editTerm(term)}><Edit3 className="h-3.5 w-3.5" /> Edit</button></Cell></tr>} /></Panel><Panel title={editingScaleId ? "Edit grading scale" : "Create grading scale"} subtitle="Grades are assigned only after all score components are filled."><form onSubmit={saveScale} className="form-grid"><TextField label="Grade" value={scaleForm.grade} onChange={(value) => setScaleForm((c) => ({ ...c, grade: value }))} placeholder="A" required /><TextField label="Min" type="number" min="0" max="100" value={scaleForm.min_score} onChange={(value) => setScaleForm((c) => ({ ...c, min_score: value }))} required /><TextField label="Max" type="number" min="0" max="100" value={scaleForm.max_score} onChange={(value) => setScaleForm((c) => ({ ...c, max_score: value }))} required /><TextField label="Remark" value={scaleForm.remark} onChange={(value) => setScaleForm((c) => ({ ...c, remark: value }))} placeholder="Excellent" /><CheckboxField label="Active" checked={scaleForm.is_active} onChange={(value) => setScaleForm((c) => ({ ...c, is_active: value }))} /><FormActions editing={Boolean(editingScaleId)} onCancel={resetScaleForm} isSaving={isSaving === "scale"} label={editingScaleId ? "Update scale" : "Create scale"} /></form><DataTable headers={["Grade", "Range", "Remark", "Actions"]} emptyText="No grading scales yet." rows={scales} renderRow={(scale) => <tr key={scale.id}><Cell label="Grade"><strong>{scale.grade}</strong></Cell><Cell label="Range">{scale.min_score} - {scale.max_score}</Cell><Cell label="Remark">{scale.remark || "--"}</Cell><Cell label="Actions"><button type="button" className="btn-ghost" onClick={() => editScale(scale)}><Edit3 className="h-3.5 w-3.5" /> Edit</button></Cell></tr>} /></Panel><Panel title={editingSubjectId ? "Edit subject" : "Create subject"} subtitle="Subjects are tenant-wide. Case and spacing duplicates are blocked by the backend."><form onSubmit={saveSubject} className="form-grid"><TextField label="Name" value={subjectForm.name} onChange={(value) => setSubjectForm((c) => ({ ...c, name: value }))} placeholder="Biology" required /><TextField label="Code" value={subjectForm.code} onChange={(value) => setSubjectForm((c) => ({ ...c, code: value }))} placeholder="BIO" /><TextField label="Description" value={subjectForm.description} onChange={(value) => setSubjectForm((c) => ({ ...c, description: value }))} placeholder="Optional" /><FormActions editing={Boolean(editingSubjectId)} onCancel={resetSubjectForm} isSaving={isSaving === "subject"} label={editingSubjectId ? "Update subject" : "Create subject"} /></form><DataTable headers={["Subject", "Code", "Status", "Actions"]} emptyText="No subjects yet." rows={subjects} renderRow={(subject) => <tr key={subject.id}><Cell label="Subject"><strong>{subject.name}</strong></Cell><Cell label="Code">{subject.code || "--"}</Cell><Cell label="Status"><StatusPill value={subject.is_active === false ? "inactive" : "active"} /></Cell><Cell label="Actions"><button type="button" className="btn-ghost" onClick={() => editSubject(subject)}><Edit3 className="h-3.5 w-3.5" /> Edit</button></Cell></tr>} /></Panel></div>;
}

function AssignmentsTab({ classes, subjects, teachers, classSubjects, assignments, assignmentFilters, setAssignmentFilters, assignmentForm, setAssignmentForm, visibleAssignments, saveAssignment, editAssignment, resetAssignmentForm, editingAssignmentId, deactivateAssignment, isSaving }) {
  const selectedClassSubject = classSubjects.find((item) => item.id === assignmentForm.class_subject_id);
  const selectedSubjectId = selectedClassSubject?.subject_id;
  const selectedClassSubjectAssignments = assignments.filter((assignment) => assignmentForm.class_id && selectedSubjectId && assignment.class_id === assignmentForm.class_id && assignment.subject_id === selectedSubjectId).sort((a, b) => Number(Boolean(b.is_active)) - Number(Boolean(a.is_active)));
  return <div className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.25fr)]"><Panel title={editingAssignmentId ? "Change teacher" : "Assign subject teacher"} subtitle="Select a class, choose a subject, then assign the teacher who teaches it."><form onSubmit={saveAssignment} className="grid gap-3"><SelectField label="Class" value={assignmentForm.class_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, class_id: value, class_subject_id: "" }))} required><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField><SelectField label="Subject" value={assignmentForm.class_subject_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, class_subject_id: value }))} disabled={!assignmentForm.class_id} required><option value="">Select subject</option>{classSubjects.map((item) => <option key={item.id} value={item.id}>{subjectLabel(item)}{item.is_offered_by_class === false ? " · add to class" : ""}</option>)}</SelectField><ClassSubjectTeacherList classSubject={selectedClassSubject} assignments={selectedClassSubjectAssignments} onChange={editAssignment} onDeactivate={deactivateAssignment} isSaving={isSaving} /><SelectField label="Teacher" value={assignmentForm.teacher_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, teacher_id: value }))} required><option value="">Select teacher</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacherLabel(teacher)}{teacher.staff_id ? ` · ${teacher.staff_id}` : ""}</option>)}</SelectField><CheckboxField label="Core subject" checked={assignmentForm.is_core} onChange={(value) => setAssignmentForm((c) => ({ ...c, is_core: value }))} disabled={Boolean(editingAssignmentId)} helperText={editingAssignmentId ? "Only the teacher changes during reassignment." : "Used if this subject is being added to the class."} /><FormActions editing={Boolean(editingAssignmentId)} onCancel={resetAssignmentForm} isSaving={isSaving === "assignment"} label={editingAssignmentId ? "Change teacher" : "Assign teacher"} /></form></Panel><Panel title="Teacher assignment map" subtitle="Old assignments should be inactive, not deleted."><AssignmentFilterGrid filters={assignmentFilters} setFilters={setAssignmentFilters} classes={classes} subjects={subjects} teachers={teachers} /><DataTable headers={["Class", "Subject", "Teacher", "Status", "Actions"]} emptyText="No assignments match these filters." rows={visibleAssignments} renderRow={(assignment) => <tr key={assignment.id}><Cell label="Class"><strong>{classLabel(assignment)}</strong></Cell><Cell label="Subject">{subjectLabel(assignment)}</Cell><Cell label="Teacher">{assignment.teacher_name || assignment.teacher_staff_id || "--"}</Cell><Cell label="Status"><StatusPill value={assignment.is_active ? "active" : "inactive"} /></Cell><Cell label="Actions"><ActionRow><button type="button" className="btn-ghost" onClick={() => editAssignment(assignment)}><Edit3 className="h-3.5 w-3.5" /> Change</button>{assignment.is_active ? <button type="button" className="btn-deact" disabled={isSaving === assignment.id} onClick={() => deactivateAssignment(assignment)}>Deactivate</button> : null}</ActionRow></Cell></tr>} /></Panel></div>;
}

function ClassSubjectTeacherList({ classSubject, assignments, onChange, onDeactivate, isSaving }) {
  if (!classSubject) return <div className="rounded-2xl border border-dashed border-border bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">Select a subject to see teacher assignments for that class-subject.</div>;
  if (classSubject.is_offered_by_class === false) return <div className="rounded-2xl border border-primary/20 bg-primary-soft/10 px-4 py-3 text-sm text-text-soft"><p className="font-semibold text-text">No teacher assigned yet.</p><p className="mt-1">This subject will be attached to the selected class before the teacher assignment is created.</p></div>;
  if (!assignments.length) return <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-amber-700"><p className="font-semibold">No teacher assigned to this class-subject yet.</p><p className="mt-1">Choose a teacher below to create the first active assignment.</p></div>;
  return <div className="rounded-2xl border border-border bg-surface-muted/30 p-3"><div className="flex items-center justify-between gap-3"><div><p className="text-sm font-semibold text-text">Teachers assigned to this class-subject</p><p className="text-xs text-text-muted">Active teacher appears first. Inactive rows are assignment history.</p></div><StatusPill value={`${assignments.length} record${assignments.length === 1 ? "" : "s"}`} /></div><div className="mt-3 grid gap-2">{assignments.map((assignment) => <div key={assignment.id} className="rounded-xl border border-border bg-surface px-3 py-3"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><p className="truncate text-sm font-semibold text-text">{assignment.teacher_name || assignment.teacher_staff_id || "Teacher"}</p><p className="mt-1 text-xs text-text-muted">{subjectLabel(assignment)} · {classLabel(assignment)}</p></div><div className="flex flex-col gap-2 sm:flex-row"><StatusPill value={assignment.is_active ? "active" : "inactive"} /><button type="button" className="btn-ghost" onClick={() => onChange(assignment)}><Edit3 className="h-3.5 w-3.5" /> Change</button>{assignment.is_active ? <button type="button" className="btn-deact" disabled={isSaving === assignment.id} onClick={() => onDeactivate(assignment)}>Deactivate</button> : null}</div></div></div>)}</div></div>;
}

function ResultsTab({ classes, subjects, sessions, terms, students, resultFilters, updateResultFilter, selectedAssignment, resultForm, setResultForm, saveResult, editResult, resetResultForm, editingResultId, visibleResults, updateResultStatus, isSaving }) { const submitBlocked = resultForm.status === "submitted" && (!hasAllScores(resultForm) || scoreTotal(resultForm) > 100); return <div className="space-y-5"><Panel title="Result filters" subtitle="Choose a class-subject first. The student dropdown loads from the selected class."><ResultFilterGrid filters={resultFilters} updateFilter={updateResultFilter} classes={classes} subjects={subjects} sessions={sessions} terms={terms} />{selectedAssignment ? <AssignmentSummary assignment={selectedAssignment} /> : resultFilters.class_id && resultFilters.subject_id ? <Alert tone="warning">No active teacher assignment found for this class-subject. Assign a teacher before saving scores.</Alert> : null}</Panel><Panel title={editingResultId ? "Correct result" : "Create result"} subtitle="Use blank fields for missing scores. Grades appear only after all three score components are filled."><form onSubmit={saveResult} className="form-grid"><SelectField label="Student" value={resultForm.student_id} onChange={(value) => setResultForm((c) => ({ ...c, student_id: value }))} disabled={!resultFilters.class_id} required><option value="">{resultFilters.class_id ? "Select student" : "Select class first"}</option>{students.map((student) => <option key={student.id} value={student.id}>{studentLabel(student)}{student.admission_number ? ` · ${student.admission_number}` : ""}</option>)}</SelectField><TextField label="Test" type="number" min="0" max="100" value={resultForm.test_score} onChange={(value) => setResultForm((c) => ({ ...c, test_score: value }))} /><TextField label="Assessment" type="number" min="0" max="100" value={resultForm.assessment_score} onChange={(value) => setResultForm((c) => ({ ...c, assessment_score: value }))} /><TextField label="Exam" type="number" min="0" max="100" value={resultForm.exam_score} onChange={(value) => setResultForm((c) => ({ ...c, exam_score: value }))} /><SelectField label="Status" value={resultForm.status} onChange={(value) => setResultForm((c) => ({ ...c, status: value }))}><option value="draft">Draft</option><option value="submitted">Submitted</option></SelectField><FormActions editing={Boolean(editingResultId)} onCancel={resetResultForm} isSaving={isSaving === "result"} disabled={!selectedAssignment || submitBlocked} label={editingResultId ? "Save correction" : "Save result"} /></form>{submitBlocked ? <p className="mt-3 text-xs font-semibold text-amber-600">Submitted results require all three scores and a combined total not above 100.</p> : null}</Panel><Panel title="Results" subtitle="Submitted scores feed report cards. Draft scores remain internal."><DataTable headers={["Student", "Subject", "Scores", "Total", "Grade", "Status", "Actions"]} emptyText="No results match these filters." rows={visibleResults} renderRow={(result) => <tr key={result.id}><Cell label="Student"><strong>{result.student_name || result.admission_number || "Student"}</strong></Cell><Cell label="Subject">{subjectLabel(result)}</Cell><Cell label="Scores">{displayScore(result.test_score)} / {displayScore(result.assessment_score)} / {displayScore(result.exam_score)}</Cell><Cell label="Total">{displayScore(result.total_score)}</Cell><Cell label="Grade">{result.grade || "--"}</Cell><Cell label="Status"><StatusPill value={result.status} /></Cell><Cell label="Actions"><ActionRow><button type="button" className="btn-ghost" onClick={() => editResult(result)}><Edit3 className="h-3.5 w-3.5" /> {isSubmitted(result) ? "Correct" : "Edit"}</button><button type="button" className="btn-ghost" disabled={isSaving === result.id} onClick={() => updateResultStatus(result, isSubmitted(result) ? "draft" : "submitted")}>{isSubmitted(result) ? "Reopen draft" : "Submit"}</button></ActionRow></Cell></tr>} /></Panel></div>; }
function ReportCardsTab({
  classes,
  sessions,
  terms,
  reportFilters,
  updateReportFilter,
  reportCardOverview,
  reportCards,
  generateReportCard,
  regenerateReportCard,
  publishReportCard,
  isSaving,
  reportCardGuard,
}) {
  const reportCardsLocked = !reportCardGuard.allowed;

  return (
    <div className="space-y-5">
      <Panel
        title="Report card filters"
        subtitle="Report cards are official snapshots generated after submitted scores are complete."
      >
        <ResultFilterGrid
          filters={reportFilters}
          updateFilter={updateReportFilter}
          classes={classes}
          sessions={sessions}
          terms={terms}
          hideSubject
        />

        {reportCardsLocked ? (
          <Alert tone="warning">{reportCardGuard.reason}</Alert>
        ) : null}

        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            className="btn-create"
            disabled={
              reportCardsLocked ||
              !reportFilters.class_id ||
              !reportFilters.academic_session_id ||
              !reportFilters.academic_term_id ||
              isSaving === "bulk-report"
            }
            onClick={() =>
              generateReportCard(
                {
                  class_id: reportFilters.class_id,
                  academic_session_id: reportFilters.academic_session_id,
                  academic_term_id: reportFilters.academic_term_id,
                },
                "bulk-report"
              )
            }
          >
            <Plus className="h-3.5 w-3.5" /> Bulk generate for class
          </button>
        </div>
      </Panel>

      <Panel
        title="Completion overview"
        subtitle="Generate one student when submitted score count matches expected class subjects."
      >
        <DataTable
          headers={["Student", "Completion", "Report Card", "Actions"]}
          emptyText="Select class, session, and term to view completion."
          rows={reportCardOverview?.items || []}
          renderRow={(row) => {
            const complete =
              row.expected_count > 0 &&
              row.submitted_count >= row.expected_count;

            return (
              <tr key={row.student_id}>
                <Cell label="Student">
                  <strong>{row.student_name || row.admission_number || "Student"}</strong>
                </Cell>
                <Cell label="Completion">
                  {row.submitted_count}/{row.expected_count} submitted
                </Cell>
                <Cell label="Report Card">
                  <StatusPill
                    value={
                      row.report_card_id
                        ? row.is_outdated
                          ? "outdated"
                          : "generated"
                        : "pending"
                    }
                  />
                </Cell>
                <Cell label="Actions">
                  <ActionRow>
                    {!row.report_card_id ? (
                      <button
                        type="button"
                        className="btn-create"
                        disabled={
                          reportCardsLocked ||
                          !complete ||
                          isSaving === row.student_id
                        }
                        onClick={() =>
                          generateReportCard(
                            {
                              student_id: row.student_id,
                              academic_session_id:
                                reportFilters.academic_session_id,
                              academic_term_id:
                                reportFilters.academic_term_id,
                            },
                            row.student_id
                          )
                        }
                      >
                        Generate
                      </button>
                    ) : null}
                    {row.report_card_id ? (
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() =>
                          reportCardService.printAdminReportCard(
                            row.report_card_id
                          )
                        }
                      >
                        Print
                      </button>
                    ) : null}
                    {row.report_card_id ? (
                      <button
                        type="button"
                        className="btn-ghost"
                        disabled={
                          reportCardsLocked || isSaving === row.report_card_id
                        }
                        onClick={() =>
                          regenerateReportCard(row.report_card_id)
                        }
                      >
                        Regenerate
                      </button>
                    ) : null}
                  </ActionRow>
                </Cell>
              </tr>
            );
          }}
        />
      </Panel>

      <Panel
        title="Generated report cards"
        subtitle="Publish only after review. Students and parents should see published report cards only."
      >
        <DataTable
          headers={["Student", "Session", "Term", "Status", "Average", "Actions"]}
          emptyText="No report cards match these filters."
          rows={reportCards}
          renderRow={(card) => (
            <tr key={card.id}>
              <Cell label="Student">
                <strong>{card.student_name || card.admission_number || "Student"}</strong>
              </Cell>
              <Cell label="Session">{card.academic_session_name || "--"}</Cell>
              <Cell label="Term">
                {card.academic_term_name
                  ? displayTerm(card.academic_term_name)
                  : "--"}
              </Cell>
              <Cell label="Status">
                <StatusPill value={card.status} />
              </Cell>
              <Cell label="Average">{displayScore(card.average_score)}</Cell>
              <Cell label="Actions">
                <ActionRow>
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => reportCardService.printAdminReportCard(card.id)}
                  >
                    Print
                  </button>
                  <button
                    type="button"
                    className="btn-ghost"
                    disabled={reportCardsLocked || isSaving === card.id}
                    onClick={() => regenerateReportCard(card.id)}
                  >
                    Regenerate
                  </button>
                  {card.status !== "published" ? (
                    <button
                      type="button"
                      className="btn-create"
                      disabled={reportCardsLocked || isSaving === card.id}
                      onClick={() => publishReportCard(card.id)}
                    >
                      Publish
                    </button>
                  ) : null}
                </ActionRow>
              </Cell>
            </tr>
          )}
        />
      </Panel>
    </div>
  );
}
function SearchTab({ searchQuery, setSearchQuery, searchResults }) { return <Panel title="Academic search" subtitle="Search students, teachers, classes, subjects, and parent-linked records."><TextField label="Search" value={searchQuery} onChange={setSearchQuery} placeholder="Type at least 2 characters" /><div className="mt-4 grid gap-3">{searchResults.length === 0 ? <EmptyState icon={Search} title="No results yet" description="Search by name, class, subject, staff ID, or admission number." /> : searchResults.map((item, index) => <div key={`${item.type}-${item.id || index}`} className="rounded-2xl border border-border bg-surface-muted/30 p-4"><p className="font-semibold text-text">{item.title || item.name || item.label || "Result"}</p><p className="mt-1 text-xs font-semibold uppercase tracking-wide text-text-muted">{item.type || "academic record"}</p></div>)}</div></Panel>; }
function AssignmentFilterGrid({ filters, setFilters, classes = [], subjects = [], teachers = [] }) { return <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3"><SelectField label="Class" value={filters.class_id} onChange={(value) => setFilters((c) => ({ ...c, class_id: value }))}><option value="">All classes</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField><SelectField label="Subject" value={filters.subject_id} onChange={(value) => setFilters((c) => ({ ...c, subject_id: value }))}><option value="">All subjects</option>{subjects.map((item) => <option key={item.id} value={item.id}>{item.name || item.code || "Subject"}</option>)}</SelectField><SelectField label="Teacher" value={filters.teacher_id} onChange={(value) => setFilters((c) => ({ ...c, teacher_id: value }))}><option value="">All teachers</option>{teachers.map((item) => <option key={item.id} value={item.id}>{teacherLabel(item)}</option>)}</SelectField></div>; }
function ResultFilterGrid({ filters, updateFilter, classes = [], subjects = [], sessions = [], terms = [], hideSubject = false }) { return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><SelectField label="Class" value={filters.class_id} onChange={(value) => updateFilter("class_id", value)}><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField>{!hideSubject ? <SelectField label="Subject" value={filters.subject_id} onChange={(value) => updateFilter("subject_id", value)}><option value="">Select subject</option>{subjects.map((item) => <option key={item.id} value={item.id}>{item.name || item.code || "Subject"}</option>)}</SelectField> : null}<SelectField label="Session" value={filters.academic_session_id} onChange={(value) => updateFilter("academic_session_id", value)}><option value="">Select session</option>{sessions.map((item) => <option key={item.id} value={item.id}>{item.name}{item.is_current ? " · Current" : ""}</option>)}</SelectField><SelectField label="Term" value={filters.academic_term_id} onChange={(value) => updateFilter("academic_term_id", value)}><option value="">Select term</option>{terms.map((item) => <option key={item.id} value={item.id}>{displayTerm(item.name)}{item.is_current ? " · Current" : ""}</option>)}</SelectField></div>; }
function AssignmentSummary({ assignment }) { return <div className="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-text-soft"><p className="font-semibold text-text">Recording for {assignment.subject_name || "subject"} in {classLabel(assignment)}</p><p className="mt-1">Active teacher: {assignment.teacher_name || assignment.teacher_staff_id || "Teacher assigned"}</p></div>; }
function Panel({ title, subtitle, children }) { return <section className="rounded-[1.35rem] border border-border bg-surface shadow-sm"><div className="border-b border-border/70 p-4 sm:p-5"><h2 className="text-base font-semibold text-text sm:text-lg">{title}</h2>{subtitle ? <p className="mt-1 text-sm leading-6 text-text-muted">{subtitle}</p> : null}</div><div className="p-4 sm:p-5">{children}</div></section>; }
function DataTable({ headers, rows, renderRow, emptyText }) { if (!rows.length) return <EmptyState icon={ClipboardList} title="Nothing to show" description={emptyText} />; return <div className="table-wrap mt-4"><table className="data-table"><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map(renderRow)}</tbody></table></div>; }
function Cell({ label, children }) { return <td data-label={label}><span>{children}</span></td>; }
function ActionRow({ children }) { return <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">{children}</div>; }
function FormActions({ editing, onCancel, isSaving, label, disabled = false }) { return <div className="form-grid-actions">{editing ? <button type="button" className="btn-ghost" onClick={onCancel}><X className="h-3.5 w-3.5" /> Cancel</button> : null}<button type="submit" className="btn-create" disabled={isSaving || disabled}><Plus className="h-3.5 w-3.5" /> {label}</button></div>; }
function Metric({ label, value }) { return <div className="rounded-2xl border border-border bg-surface px-4 py-3 shadow-sm"><p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p><p className="mt-1 text-2xl font-semibold text-text">{value}</p></div>; }
function Context({ label, value }) { return <div className="rounded-xl border border-border bg-surface-muted/40 px-3 py-2"><p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">{label}</p><p className="mt-1 truncate text-xs font-semibold text-text">{value}</p></div>; }
function StatusPill({ value }) { const normalized = String(value || "pending").toLowerCase(); const tone = ["active", "current", "submitted", "published", "generated"].includes(normalized) ? "green" : ["draft", "pending", "inactive", "outdated"].includes(normalized) ? "gray" : "blue"; return <span className={`badge ${tone}`}>{normalized.replaceAll("_", " ")}</span>; }
function Alert({ children, tone = "info" }) { const styles = tone === "error" ? "border-error/30 bg-error-soft text-error" : tone === "warning" ? "border-warning/30 bg-warning-soft text-amber-700" : "border-primary/20 bg-primary-soft/20 text-primary-deep"; return <div className={`mt-4 rounded-2xl border px-4 py-3 text-sm font-medium ${styles}`}>{children}</div>; }

export default AcademicHubPage;
