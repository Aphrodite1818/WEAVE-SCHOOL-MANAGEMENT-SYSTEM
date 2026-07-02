import { Children, cloneElement, isValidElement, useEffect, useMemo, useState } from "react";
import { BookOpen, ClipboardList, FileText, Pencil, Plus, Search, Users } from "lucide-react";
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

const sections = [
  { id: "setup", name: "Academic Setup", icon: BookOpen, description: "Sessions, terms, grading scales, and subject catalogue." },
  { id: "assignments", name: "Teacher Assignments", icon: Users, description: "Attach subjects to classes and assign subject teachers." },
  { id: "results", name: "Student Results", icon: Pencil, description: "Review drafts, submit, reopen, and correct scores." },
  { id: "reportCards", name: "Report Cards", icon: FileText, description: "Generate, regenerate, publish, and print official report cards." },
  { id: "search", name: "Academic Search", icon: Search, description: "Find academic records across the tenant." },
];

const blankSession = { name: "", start_date: "", end_date: "", is_current: false, is_active: true };
const blankTerm = { academic_session_id: "", name: "first_term", start_date: "", end_date: "", is_current: false, is_active: true };
const blankScale = { grade: "", min_score: "", max_score: "", remark: "", is_active: true };
const blankSubject = { name: "", code: "", description: "" };
const blankAssignment = { class_id: "", class_subject_id: "", teacher_id: "", is_core: true };
const blankResult = { student_id: "", test_score: "", assessment_score: "", exam_score: "", status: "draft" };

const toNullableScore = (value) => (value === "" || value === null || value === undefined ? null : Number(value));
const displayScore = (value) => (value === null || value === undefined || value === "" ? "--" : value);
const compactDate = (value) => (value ? new Date(value).toLocaleDateString() : "--");
const classLabel = (item) => [item?.class_name || item?.name, item?.class_arm || item?.arm].filter(Boolean).join(" ") || "Class";
const studentName = (student) => displayPerson(student) || student?.admission_number || "Student";
const isSubmitted = (result) => result?.status === "submitted";

function AcademicHubPage() {
  const [activeSection, setActiveSection] = useState("setup");
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
  const [editingAssignmentId, setEditingAssignmentId] = useState("");
  const [editingResultId, setEditingResultId] = useState("");
  const [filters, setFilters] = useState({ class_id: "", subject_id: "", teacher_id: "", academic_session_id: "", academic_term_id: "" });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState("");
  const [error, setError] = useState(null);
  const { showSuccess, showError } = useToast();

  const currentSection = sections.find((section) => section.id === activeSection) || sections[0];
  const currentSession = sessions.find((item) => item.is_current) || sessions[0];
  const currentTerm = terms.find((item) => item.is_current) || terms[0];
  const termsForSelectedSession = useMemo(() => terms.filter((term) => !filters.academic_session_id || term.academic_session_id === filters.academic_session_id), [terms, filters.academic_session_id]);
  const studentsForClass = useMemo(() => students.filter((student) => !filters.class_id || student.class_id === filters.class_id), [students, filters.class_id]);
  const visibleAssignments = useMemo(() => assignments.filter((item) => (!filters.class_id || item.class_id === filters.class_id) && (!filters.subject_id || item.subject_id === filters.subject_id) && (!filters.teacher_id || item.teacher_id === filters.teacher_id)), [assignments, filters.class_id, filters.subject_id, filters.teacher_id]);
  const selectedAssignment = useMemo(() => assignments.find((item) => item.is_active && item.class_id === filters.class_id && item.subject_id === filters.subject_id), [assignments, filters.class_id, filters.subject_id]);
  const visibleResults = useMemo(() => results.filter((item) => (!filters.academic_session_id || item.academic_session_id === filters.academic_session_id) && (!filters.academic_term_id || item.academic_term_id === filters.academic_term_id) && (!filters.class_id || item.class_id === filters.class_id) && (!filters.subject_id || item.subject_id === filters.subject_id)), [results, filters]);
  const visibleReportCards = useMemo(() => reportCards.filter((card) => (!filters.academic_session_id || card.academic_session_id === filters.academic_session_id) && (!filters.academic_term_id || card.academic_term_id === filters.academic_term_id) && (!filters.class_id || card.class_id === filters.class_id)), [reportCards, filters]);
  const stats = useMemo(() => ({ sessions: sessions.length, terms: terms.length, subjects: subjects.length, assignments: assignments.filter((item) => item.is_active).length, drafts: results.filter((item) => item.status === "draft").length, submitted: results.filter((item) => item.status === "submitted").length }), [sessions, terms, subjects, assignments, results]);

  const loadWorkspace = async () => {
    setError(null);
    const [sessionResponse, termResponse, scaleResponse, subjectResponse, classResponse, teacherResponse, studentResponse, assignmentResponse, resultResponse, reportCardResponse] = await Promise.all([
      academicService.listSessions(),
      academicService.listTerms(),
      academicService.listGradingScales(),
      subjectService.getSubjects({ isActive: true, limit: 100 }),
      classService.getClasses({ limit: 100 }),
      teacherService.getTeachers({ limit: 100 }),
      studentService.getAdminStudents(),
      academicService.listTeacherAssignments({ limit: 100 }),
      academicService.listAdminResults({ limit: 100 }),
      reportCardService.listAdminReportCards({ limit: 100 }),
    ]);
    const nextSessions = sessionResponse?.items || [];
    const nextTerms = termResponse?.items || [];
    const defaultSessionId = nextSessions.find((item) => item.is_current)?.id || nextSessions[0]?.id || "";
    const defaultTermId = nextTerms.find((item) => item.is_current)?.id || nextTerms[0]?.id || "";
    setSessions(nextSessions);
    setTerms(nextTerms);
    setScales(scaleResponse?.items || []);
    setSubjects(subjectResponse?.items || []);
    setClasses(classResponse?.items || []);
    setTeachers(teacherResponse?.items || []);
    setStudents(studentResponse?.items || []);
    setAssignments(assignmentResponse?.items || []);
    setResults(resultResponse?.items || []);
    setReportCards(reportCardResponse?.items || []);
    setFilters((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId, academic_term_id: current.academic_term_id || defaultTermId }));
    setTermForm((current) => ({ ...current, academic_session_id: current.academic_session_id || defaultSessionId }));
  };

  useEffect(() => {
    let mounted = true;
    async function load() {
      setIsLoading(true);
      try { await loadWorkspace(); } catch (err) { if (mounted) setError(getErrorMessage(err, "Could not load academic workspace.")); } finally { if (mounted) setIsLoading(false); }
    }
    load();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    let mounted = true;
    async function loadClassSubjects() {
      if (!assignmentForm.class_id) { if (mounted) setClassSubjects([]); return; }
      try {
        const response = await academicService.listClassSubjects(assignmentForm.class_id, { active_only: true });
        if (mounted) setClassSubjects(response?.items || []);
      } catch { if (mounted) setClassSubjects([]); }
    }
    loadClassSubjects();
    return () => { mounted = false; };
  }, [assignmentForm.class_id]);

  useEffect(() => {
    let mounted = true;
    async function loadOverview() {
      if (activeSection !== "reportCards" || !filters.class_id || !filters.academic_session_id || !filters.academic_term_id) { if (mounted) setReportCardOverview(null); return; }
      try {
        const response = await reportCardService.getClassOverview({ class_id: filters.class_id, academic_session_id: filters.academic_session_id, academic_term_id: filters.academic_term_id });
        if (mounted) setReportCardOverview(response);
      } catch { if (mounted) setReportCardOverview(null); }
    }
    loadOverview();
    return () => { mounted = false; };
  }, [activeSection, filters.class_id, filters.academic_session_id, filters.academic_term_id]);

  useEffect(() => {
    let mounted = true;
    async function runSearch() {
      if (searchQuery.trim().length < 2) { setSearchResults([]); return; }
      try { const response = await searchService.searchTenant(searchQuery.trim(), 8); if (mounted) setSearchResults(response?.items || []); } catch { if (mounted) setSearchResults([]); }
    }
    const timeout = window.setTimeout(runSearch, 250);
    return () => { mounted = false; window.clearTimeout(timeout); };
  }, [searchQuery]);

  const refreshAssignments = async () => setAssignments((await academicService.listTeacherAssignments({ limit: 100 }))?.items || []);
  const saveSession = async (event) => { event.preventDefault(); setIsSaving("session"); try { const saved = await academicService.createSession({ ...sessionForm, start_date: sessionForm.start_date || null, end_date: sessionForm.end_date || null }); setSessions((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); setSessionForm(blankSession); showSuccess("Academic session created."); if (saved.is_current) await loadWorkspace(); } catch (err) { showError(getErrorMessage(err, "Could not create academic session.")); } finally { setIsSaving(""); } };
  const saveTerm = async (event) => { event.preventDefault(); setIsSaving("term"); try { const saved = await academicService.createTerm({ ...termForm, start_date: termForm.start_date || null, end_date: termForm.end_date || null }); setTerms((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); setTermForm({ ...blankTerm, academic_session_id: termForm.academic_session_id }); showSuccess("Academic term created."); if (saved.is_current) await loadWorkspace(); } catch (err) { showError(getErrorMessage(err, "Could not create academic term.")); } finally { setIsSaving(""); } };
  const saveScale = async (event) => { event.preventDefault(); setIsSaving("scale"); try { const saved = await academicService.createGradingScale({ grade: scaleForm.grade, min_score: Number(scaleForm.min_score), max_score: Number(scaleForm.max_score), remark: scaleForm.remark || null, is_active: scaleForm.is_active }); setScales((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); setScaleForm(blankScale); showSuccess("Grading scale saved."); } catch (err) { showError(getErrorMessage(err, "Could not save grading scale.")); } finally { setIsSaving(""); } };
  const saveSubject = async (event) => { event.preventDefault(); setIsSaving("subject"); try { const saved = await subjectService.createSubject({ name: subjectForm.name, code: subjectForm.code || null, description: subjectForm.description || null }); setSubjects((current) => [saved, ...current.filter((item) => item.id !== saved.id)]); setSubjectForm(blankSubject); showSuccess("Subject created."); } catch (err) { showError(getErrorMessage(err, "Could not create subject.")); } finally { setIsSaving(""); } };

  const saveAssignment = async (event) => {
    event.preventDefault();
    if (!assignmentForm.class_id || !assignmentForm.class_subject_id || !assignmentForm.teacher_id) { showError("Select a class, subject, and teacher before saving."); return; }
    setIsSaving("assignment");
    try {
      const saved = editingAssignmentId ? await academicService.reassignTeacherAssignment(editingAssignmentId, { teacher_id: assignmentForm.teacher_id }) : await academicService.createTeacherAssignment({ class_subject_id: assignmentForm.class_subject_id, teacher_id: assignmentForm.teacher_id, is_core: assignmentForm.is_core });
      await refreshAssignments();
      setAssignmentForm(blankAssignment);
      setEditingAssignmentId("");
      setFilters((current) => ({ ...current, class_id: saved.class_id || current.class_id, subject_id: saved.subject_id || current.subject_id, teacher_id: saved.teacher_id || current.teacher_id }));
      showSuccess(editingAssignmentId ? "Teacher changed for this subject." : "Teacher assigned to class-subject.");
    } catch (err) { showError(getErrorMessage(err, "Could not save teacher assignment.")); } finally { setIsSaving(""); }
  };
  const startAssignmentChange = (assignment) => { setEditingAssignmentId(assignment.id); setAssignmentForm({ class_id: assignment.class_id || "", class_subject_id: assignment.class_subject_id || "", teacher_id: assignment.teacher_id || "", is_core: true }); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const deactivateAssignment = async (assignment) => { setIsSaving(assignment.id); try { const saved = await academicService.deactivateTeacherAssignment(assignment.id); setAssignments((current) => current.map((item) => (item.id === saved.id ? saved : item))); showSuccess("Teacher assignment deactivated. The subject remains attached to the class."); } catch (err) { showError(getErrorMessage(err, "Could not deactivate assignment.")); } finally { setIsSaving(""); } };

  const saveResult = async (event) => {
    event.preventDefault();
    if (!selectedAssignment) { showError("Assign a teacher to this class-subject before saving scores."); return; }
    if (!resultForm.student_id || !filters.academic_session_id || !filters.academic_term_id) { showError("Select student, session, and term before saving scores."); return; }
    setIsSaving("result");
    try {
      const saved = await academicService.saveAdminResult({ student_id: resultForm.student_id, teacher_assignment_id: selectedAssignment.id, academic_session_id: filters.academic_session_id, academic_term_id: filters.academic_term_id, test_score: toNullableScore(resultForm.test_score), assessment_score: toNullableScore(resultForm.assessment_score), exam_score: toNullableScore(resultForm.exam_score), status: resultForm.status });
      setResults((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setResultForm(blankResult); setEditingResultId(""); showSuccess(saved.status === "submitted" ? "Result submitted." : "Result saved as draft.");
    } catch (err) { showError(getErrorMessage(err, "Could not save result.")); } finally { setIsSaving(""); }
  };
  const startResultEdit = (result) => { setEditingResultId(result.id); setFilters((current) => ({ ...current, class_id: result.class_id || current.class_id, subject_id: result.subject_id || current.subject_id, academic_session_id: result.academic_session_id || current.academic_session_id, academic_term_id: result.academic_term_id || current.academic_term_id })); setResultForm({ student_id: result.student_id, test_score: result.test_score ?? "", assessment_score: result.assessment_score ?? "", exam_score: result.exam_score ?? "", status: result.status || "draft" }); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const updateResultStatus = async (result, nextStatus) => { setIsSaving(result.id); try { const saved = await academicService.updateResultStatus(result.id, { status: nextStatus }); setResults((current) => current.map((item) => (item.id === saved.id ? saved : item))); showSuccess(nextStatus === "submitted" ? "Result submitted." : "Result reopened as draft."); } catch (err) { showError(getErrorMessage(err, "Could not update result status.")); } finally { setIsSaving(""); } };
  const generateReportCard = async (payload, label) => { setIsSaving(label); try { const response = await reportCardService.generateReportCard(payload); if (Array.isArray(response?.generated)) { setReportCards((current) => [...response.generated, ...current]); showSuccess(`Generated ${response.generated.length} report cards. Skipped ${response.skipped?.length || 0}.`); } else { setReportCards((current) => [response, ...current.filter((item) => item.id !== response.id)]); showSuccess("Report card generated."); } } catch (err) { showError(getErrorMessage(err, "Could not generate report card.")); } finally { setIsSaving(""); } };

  if (isLoading) return <DashboardLayout role="admin" title="Academic Hub"><LoadingState label="Loading academic hub..." /></DashboardLayout>;

  return (
    <DashboardLayout role="admin" title="Academic Hub" description="Set up academic periods, assign class-subject teachers, review scores, and generate official report cards.">
      {error ? <Alert tone="error">{error}</Alert> : null}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6"><MiniStat label="Sessions" value={stats.sessions} /><MiniStat label="Terms" value={stats.terms} /><MiniStat label="Subjects" value={stats.subjects} /><MiniStat label="Assignments" value={stats.assignments} /><MiniStat label="Drafts" value={stats.drafts} /><MiniStat label="Submitted" value={stats.submitted} /></section>
      <section className="grid gap-3 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-4 lg:self-start"><div className="rounded-[1.35rem] border border-border bg-surface p-2 shadow-sm">{sections.map((section) => <NavButton key={section.id} section={section} active={activeSection === section.id} onClick={() => setActiveSection(section.id)} />)}</div></aside>
        <main className="min-w-0 space-y-4"><HeaderCard section={currentSection} currentSession={currentSession} currentTerm={currentTerm} />
          {activeSection === "setup" ? <SetupSection sessionForm={sessionForm} setSessionForm={setSessionForm} saveSession={saveSession} termForm={termForm} setTermForm={setTermForm} saveTerm={saveTerm} scaleForm={scaleForm} setScaleForm={setScaleForm} saveScale={saveScale} subjectForm={subjectForm} setSubjectForm={setSubjectForm} saveSubject={saveSubject} sessions={sessions} terms={terms} scales={scales} subjects={subjects} isSaving={isSaving} /> : null}
          {activeSection === "assignments" ? <AssignmentsSection assignmentForm={assignmentForm} setAssignmentForm={setAssignmentForm} editingAssignmentId={editingAssignmentId} setEditingAssignmentId={setEditingAssignmentId} classSubjects={classSubjects} classes={classes} subjects={subjects} teachers={teachers} filters={filters} setFilters={setFilters} visibleAssignments={visibleAssignments} saveAssignment={saveAssignment} startAssignmentChange={startAssignmentChange} deactivateAssignment={deactivateAssignment} isSaving={isSaving} /> : null}
          {activeSection === "results" ? <ResultsSection filters={filters} setFilters={setFilters} classes={classes} subjects={subjects} sessions={sessions} terms={termsForSelectedSession} studentsForClass={studentsForClass} selectedAssignment={selectedAssignment} resultForm={resultForm} setResultForm={setResultForm} saveResult={saveResult} editingResultId={editingResultId} setEditingResultId={setEditingResultId} visibleResults={visibleResults} startResultEdit={startResultEdit} updateResultStatus={updateResultStatus} isSaving={isSaving} /> : null}
          {activeSection === "reportCards" ? <ReportCardsSection filters={filters} setFilters={setFilters} classes={classes} sessions={sessions} terms={termsForSelectedSession} reportCardOverview={reportCardOverview} visibleReportCards={visibleReportCards} generateReportCard={generateReportCard} setReportCards={setReportCards} isSaving={isSaving} /> : null}
          {activeSection === "search" ? <SearchSection searchQuery={searchQuery} setSearchQuery={setSearchQuery} searchResults={searchResults} /> : null}
        </main>
      </section>
    </DashboardLayout>
  );
}

function SetupSection({ sessionForm, setSessionForm, saveSession, termForm, setTermForm, saveTerm, scaleForm, setScaleForm, saveScale, subjectForm, setSubjectForm, saveSubject, sessions, terms, scales, subjects, isSaving }) {
  return (
    <div className="space-y-4">
      <Panel title="New session" subtitle="Create an academic session and choose whether it is current.">
        <form onSubmit={saveSession} className="form-grid">
          <TextField label="Session" value={sessionForm.name} onChange={(value) => setSessionForm((c) => ({ ...c, name: value }))} placeholder="2026/2027" required />
          <TextField label="Start date" type="date" value={sessionForm.start_date} onChange={(value) => setSessionForm((c) => ({ ...c, start_date: value }))} />
          <TextField label="End date" type="date" value={sessionForm.end_date} onChange={(value) => setSessionForm((c) => ({ ...c, end_date: value }))} />
          <CheckboxField label="Current" checked={sessionForm.is_current} onChange={(value) => setSessionForm((c) => ({ ...c, is_current: value }))} />
          <ActionButton disabled={isSaving === "session"}>Create session</ActionButton>
        </form>
      </Panel>

      <Panel title="All sessions" subtitle={`${sessions.length} session${sessions.length === 1 ? "" : "s"} configured for this tenant.`}>
        <ResponsiveTable empty={sessions.length === 0} emptyText="No academic sessions have been created yet." headers={["Name", "Start date", "End date", "Current", "Status"]}>
          {sessions.map((item) => (
            <tr key={item.id}>
              <Td strong>{item.name}</Td>
              <Td>{compactDate(item.start_date)}</Td>
              <Td>{compactDate(item.end_date)}</Td>
              <Td><StatusPill value={item.is_current ? "current" : "not current"} /></Td>
              <Td><StatusPill value={item.is_active ? "active" : "inactive"} /></Td>
            </tr>
          ))}
        </ResponsiveTable>
      </Panel>

      <Panel title="New term" subtitle="Create a term for a session and optionally mark it as current.">
        <form onSubmit={saveTerm} className="form-grid">
          <SelectField label="Session" value={termForm.academic_session_id} onChange={(value) => setTermForm((c) => ({ ...c, academic_session_id: value }))} required>
            <option value="">Select session</option>
            {sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}
          </SelectField>
          <SelectField label="Term" value={termForm.name} onChange={(value) => setTermForm((c) => ({ ...c, name: value }))}>
            <option value="first_term">First Term</option>
            <option value="second_term">Second Term</option>
            <option value="third_term">Third Term</option>
          </SelectField>
          <TextField label="Start date" type="date" value={termForm.start_date} onChange={(value) => setTermForm((c) => ({ ...c, start_date: value }))} />
          <TextField label="End date" type="date" value={termForm.end_date} onChange={(value) => setTermForm((c) => ({ ...c, end_date: value }))} />
          <CheckboxField label="Current" checked={termForm.is_current} onChange={(value) => setTermForm((c) => ({ ...c, is_current: value }))} />
          <ActionButton disabled={isSaving === "term"}>Create term</ActionButton>
        </form>
      </Panel>

      <Panel title="All terms" subtitle="Terms are shown with their owning session so date windows are easier to audit.">
        <ResponsiveTable empty={terms.length === 0} emptyText="No academic terms have been created yet." headers={["Term", "Session", "Start date", "End date", "Current", "Status"]}>
          {terms.map((item) => (
            <tr key={item.id}>
              <Td strong>{displayTerm(item.name)}</Td>
              <Td>{sessions.find((session) => session.id === item.academic_session_id)?.name || item.academic_session_name || "--"}</Td>
              <Td>{compactDate(item.start_date)}</Td>
              <Td>{compactDate(item.end_date)}</Td>
              <Td><StatusPill value={item.is_current ? "current" : "not current"} /></Td>
              <Td><StatusPill value={item.is_active ? "active" : "inactive"} /></Td>
            </tr>
          ))}
        </ResponsiveTable>
      </Panel>

      <Panel title="New grading scale" subtitle="Create a grading band that the backend can use for computed grades.">
        <form onSubmit={saveScale} className="form-grid">
          <TextField label="Grade" value={scaleForm.grade} onChange={(value) => setScaleForm((c) => ({ ...c, grade: value }))} placeholder="A" required />
          <TextField label="Min" type="number" min="0" max="100" value={scaleForm.min_score} onChange={(value) => setScaleForm((c) => ({ ...c, min_score: value }))} required />
          <TextField label="Max" type="number" min="0" max="100" value={scaleForm.max_score} onChange={(value) => setScaleForm((c) => ({ ...c, max_score: value }))} required />
          <TextField label="Remark" value={scaleForm.remark} onChange={(value) => setScaleForm((c) => ({ ...c, remark: value }))} placeholder="Excellent" />
          <ActionButton disabled={isSaving === "scale"}>Save scale</ActionButton>
        </form>
      </Panel>

      <Panel title="All grading scales" subtitle="Ranges should not overlap; complete scores use these bands for grade and remark.">
        <ResponsiveTable empty={scales.length === 0} emptyText="No grading scale has been created yet." headers={["Grade", "Min", "Max", "Remark", "Status"]}>
          {scales.map((item) => (
            <tr key={item.id}>
              <Td strong>{item.grade}</Td>
              <Td>{item.min_score}</Td>
              <Td>{item.max_score}</Td>
              <Td>{item.remark || "--"}</Td>
              <Td><StatusPill value={item.is_active ? "active" : "inactive"} /></Td>
            </tr>
          ))}
        </ResponsiveTable>
      </Panel>

      <Panel title="New subject" subtitle="Subjects are tenant-wide. Case and spacing duplicates are blocked by normalized identity.">
        <form onSubmit={saveSubject} className="form-grid">
          <TextField label="Subject name" value={subjectForm.name} onChange={(value) => setSubjectForm((c) => ({ ...c, name: value }))} placeholder="Biology" required />
          <TextField label="Code" value={subjectForm.code} onChange={(value) => setSubjectForm((c) => ({ ...c, code: value }))} placeholder="BIO" />
          <TextField label="Description" value={subjectForm.description} onChange={(value) => setSubjectForm((c) => ({ ...c, description: value }))} placeholder="Optional" />
          <ActionButton disabled={isSaving === "subject"}>Create subject</ActionButton>
        </form>
      </Panel>

      <Panel title="All subjects" subtitle={`${subjects.length} subject${subjects.length === 1 ? "" : "s"} available for class offerings.`}>
        <ResponsiveTable empty={subjects.length === 0} emptyText="No subjects have been created yet." headers={["Subject", "Code", "Description", "Status"]}>
          {subjects.map((item) => (
            <tr key={item.id}>
              <Td strong>{item.name}</Td>
              <Td>{item.code || "--"}</Td>
              <Td>{item.description || "--"}</Td>
              <Td><StatusPill value={item.is_active === false ? "inactive" : "active"} /></Td>
            </tr>
          ))}
        </ResponsiveTable>
      </Panel>
    </div>
  );
}

function AssignmentsSection({ assignmentForm, setAssignmentForm, editingAssignmentId, setEditingAssignmentId, classSubjects, classes, subjects, teachers, filters, setFilters, visibleAssignments, saveAssignment, startAssignmentChange, deactivateAssignment, isSaving }) {
  return <div className="space-y-4"><Panel title={editingAssignmentId ? "Change subject teacher" : "Assign teacher to class-subject"} subtitle="Class teacher is separate. This controls who teaches a subject in a class."><form onSubmit={saveAssignment} className="form-grid"><SelectField label="Class" value={assignmentForm.class_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, class_id: value, class_subject_id: "" }))} required><option value="">Select class</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField><SelectField label="Subject" value={assignmentForm.class_subject_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, class_subject_id: value }))} disabled={!assignmentForm.class_id} required><option value="">Select subject</option>{classSubjects.map((item) => <option key={item.id} value={item.id}>{item.subject_name || "Subject"}{item.is_offered_by_class === false ? " · add to class" : ""}</option>)}</SelectField><SelectField label="Teacher" value={assignmentForm.teacher_id} onChange={(value) => setAssignmentForm((c) => ({ ...c, teacher_id: value }))} required><option value="">Select teacher</option>{teachers.map((t) => <option key={t.id} value={t.id}>{displayPerson(t)}{t.staff_id ? ` · ${t.staff_id}` : ""}</option>)}</SelectField><CheckboxField label="Core subject" checked={assignmentForm.is_core} onChange={(value) => setAssignmentForm((c) => ({ ...c, is_core: value }))} disabled={Boolean(editingAssignmentId)} helperText={editingAssignmentId ? "Only teacher changes here." : "Used if the subject is being added to the class."} /><div className="form-grid-actions">{editingAssignmentId ? <button type="button" className="btn-ghost" onClick={() => { setEditingAssignmentId(""); setAssignmentForm(blankAssignment); }}>Cancel</button> : null}<ActionButton disabled={isSaving === "assignment"}>{editingAssignmentId ? "Change teacher" : "Assign teacher"}</ActionButton></div></form></Panel><Panel title="Assignment map" subtitle="Teacher changes deactivate the old assignment; the class subject remains."><FilterRow filters={filters} setFilters={setFilters} classes={classes} subjects={subjects} teachers={teachers} /><ResponsiveTable empty={visibleAssignments.length === 0} emptyText="No teacher assignments match these filters." headers={["Class", "Subject", "Teacher", "Status", "Actions"]}>{visibleAssignments.map((item) => <tr key={item.id}><Td>{classLabel(item)}</Td><Td>{item.subject_name || item.subject_code || "Subject"}</Td><Td>{item.teacher_name || item.teacher_staff_id || "Teacher"}</Td><Td><StatusPill value={item.is_active ? "active" : "inactive"} /></Td><Td><RowActions><button type="button" className="btn-ghost" onClick={() => startAssignmentChange(item)}>Change teacher</button>{item.is_active ? <button type="button" className="btn-deact" disabled={isSaving === item.id} onClick={() => deactivateAssignment(item)}>Deactivate</button> : null}</RowActions></Td></tr>)}</ResponsiveTable></Panel></div>;
}

function ResultsSection({ filters, setFilters, classes, subjects, sessions, terms, studentsForClass, selectedAssignment, resultForm, setResultForm, saveResult, editingResultId, setEditingResultId, visibleResults, startResultEdit, updateResultStatus, isSaving }) {
  return <div className="space-y-4"><Panel title="Result filters" subtitle="Choose class, subject, session, and term."><FilterRow filters={filters} setFilters={setFilters} classes={classes} subjects={subjects} sessions={sessions} terms={terms} />{!selectedAssignment && filters.class_id && filters.subject_id ? <Alert tone="warning">Assign a teacher to this class-subject before saving scores.</Alert> : null}</Panel><Panel title={editingResultId ? "Correct result" : "Create result"} subtitle="Missing scores are blank, not zero. Grade appears after all three scores exist."><form onSubmit={saveResult} className="form-grid"><SelectField label="Student" value={resultForm.student_id} onChange={(value) => setResultForm((c) => ({ ...c, student_id: value }))} required><option value="">Select student</option>{studentsForClass.map((s) => <option key={s.id} value={s.id}>{studentName(s)}{s.admission_number ? ` · ${s.admission_number}` : ""}</option>)}</SelectField><TextField label="Test" type="number" min="0" max="100" value={resultForm.test_score} onChange={(value) => setResultForm((c) => ({ ...c, test_score: value }))} /><TextField label="Assessment" type="number" min="0" max="100" value={resultForm.assessment_score} onChange={(value) => setResultForm((c) => ({ ...c, assessment_score: value }))} /><TextField label="Exam" type="number" min="0" max="100" value={resultForm.exam_score} onChange={(value) => setResultForm((c) => ({ ...c, exam_score: value }))} /><SelectField label="Status" value={resultForm.status} onChange={(value) => setResultForm((c) => ({ ...c, status: value }))}><option value="draft">Draft</option><option value="submitted">Submitted</option></SelectField><div className="form-grid-actions">{editingResultId ? <button type="button" className="btn-ghost" onClick={() => { setEditingResultId(""); setResultForm(blankResult); }}>Cancel</button> : null}<ActionButton disabled={!selectedAssignment || isSaving === "result"}>{editingResultId ? "Save correction" : "Save result"}</ActionButton></div></form></Panel><Panel title="Results" subtitle="Submitted scores feed report cards. Drafts stay internal."><ResponsiveTable empty={visibleResults.length === 0} emptyText="No results match these filters." headers={["Student", "Subject", "Scores", "Total", "Grade", "Status", "Actions"]}>{visibleResults.map((result) => <tr key={result.id}><Td>{result.student_name || result.admission_number || "Student"}</Td><Td>{result.subject_name || result.subject_code || "Subject"}</Td><Td>{displayScore(result.test_score)} / {displayScore(result.assessment_score)} / {displayScore(result.exam_score)}</Td><Td>{displayScore(result.total_score)}</Td><Td>{result.grade || "--"}</Td><Td><StatusPill value={result.status} /></Td><Td><RowActions><button type="button" className="btn-ghost" onClick={() => startResultEdit(result)}>{isSubmitted(result) ? "Correct" : "Edit"}</button><button type="button" className="btn-ghost" disabled={isSaving === result.id} onClick={() => updateResultStatus(result, isSubmitted(result) ? "draft" : "submitted")}>{isSubmitted(result) ? "Reopen draft" : "Submit"}</button></RowActions></Td></tr>)}</ResponsiveTable></Panel></div>;
}

function ReportCardsSection({ filters, setFilters, classes, sessions, terms, reportCardOverview, visibleReportCards, generateReportCard, setReportCards, isSaving }) {
  return <div className="space-y-4"><Panel title="Report card filters" subtitle="Generate official snapshots after all expected subjects are submitted."><FilterRow filters={filters} setFilters={setFilters} classes={classes} sessions={sessions} terms={terms} /><div className="mt-3 flex flex-col gap-2 sm:flex-row"><button type="button" className="btn-create" disabled={!filters.class_id || !filters.academic_session_id || !filters.academic_term_id || isSaving === "bulk-report"} onClick={() => generateReportCard({ class_id: filters.class_id, academic_session_id: filters.academic_session_id, academic_term_id: filters.academic_term_id }, "bulk-report")}>Bulk generate for class</button></div></Panel><Panel title="Completion overview" subtitle="Generate one student's report card when complete."><ResponsiveTable empty={!reportCardOverview?.items?.length} emptyText="Select class, session, and term to view completion." headers={["Student", "Completion", "Report Card", "Actions"]}>{(reportCardOverview?.items || []).map((row) => { const complete = row.submitted_count >= row.expected_count && row.expected_count > 0; return <tr key={row.student_id}><Td>{row.student_name || row.admission_number || "Student"}</Td><Td>{row.submitted_count}/{row.expected_count} submitted</Td><Td><StatusPill value={row.report_card_id ? row.is_outdated ? "outdated" : "generated" : "pending"} /></Td><Td><RowActions>{!row.report_card_id ? <button type="button" className="btn-create" disabled={!complete || isSaving === row.student_id} onClick={() => generateReportCard({ student_id: row.student_id, academic_session_id: filters.academic_session_id, academic_term_id: filters.academic_term_id }, row.student_id)}>Generate</button> : null}{row.report_card_id ? <button type="button" className="btn-ghost" onClick={() => reportCardService.printAdminReportCard(row.report_card_id)}>Print</button> : null}{row.report_card_id && (row.is_outdated || complete) ? <button type="button" className="btn-ghost" onClick={async () => { const card = await reportCardService.regenerateReportCard(row.report_card_id); setReportCards((current) => [card, ...current.filter((item) => item.id !== card.id)]); }}>Regenerate</button> : null}</RowActions></Td></tr>; })}</ResponsiveTable></Panel><Panel title="Generated report cards" subtitle="Publish official report cards only after review."><ResponsiveTable empty={visibleReportCards.length === 0} emptyText="No report cards generated for this filter." headers={["Student", "Session", "Term", "Status", "Average", "Actions"]}>{visibleReportCards.map((card) => <tr key={card.id}><Td>{card.student_name || card.admission_number || "Student"}</Td><Td>{card.academic_session_name || "--"}</Td><Td>{card.academic_term_name ? displayTerm(card.academic_term_name) : "--"}</Td><Td><StatusPill value={card.status} /></Td><Td>{displayScore(card.average_score)}</Td><Td><RowActions><button type="button" className="btn-ghost" onClick={() => reportCardService.printAdminReportCard(card.id)}>Print</button>{card.status !== "published" ? <button type="button" className="btn-create" onClick={async () => { const published = await reportCardService.publishReportCard(card.id); setReportCards((current) => current.map((item) => item.id === published.id ? published : item)); }}>Publish</button> : null}</RowActions></Td></tr>)}</ResponsiveTable></Panel></div>;
}

function SearchSection({ searchQuery, setSearchQuery, searchResults }) { return <Panel title="Search academic records" subtitle="Find students, teachers, parents, classes, and subjects quickly."><TextField label="Search" value={searchQuery} onChange={setSearchQuery} placeholder="Type at least 2 characters" /><div className="mt-4 grid gap-2">{searchResults.length === 0 ? <EmptyState icon={Search} title="No search results" description="Try a name, class, subject, or admission number." /> : searchResults.map((item, index) => <div key={`${item.type}-${item.id || index}`} className="rounded-2xl border border-border bg-surface-muted/30 p-4"><p className="text-sm font-semibold text-text">{item.title || item.name || item.label || "Result"}</p><p className="mt-1 text-xs text-text-muted">{item.type || "academic record"}</p></div>)}</div></Panel>; }
function FilterRow({ filters, setFilters, classes = [], subjects = [], teachers = [], sessions = [], terms = [] }) { return <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{classes.length > 0 ? <SelectField label="Class" value={filters.class_id} onChange={(value) => setFilters((c) => ({ ...c, class_id: value }))}><option value="">All classes</option>{classes.map((item) => <option key={item.id} value={item.id}>{displayClass(item)}</option>)}</SelectField> : null}{subjects.length > 0 ? <SelectField label="Subject" value={filters.subject_id} onChange={(value) => setFilters((c) => ({ ...c, subject_id: value }))}><option value="">All subjects</option>{subjects.map((item) => <option key={item.id} value={item.id}>{item.name || item.code || "Subject"}</option>)}</SelectField> : null}{teachers.length > 0 ? <SelectField label="Teacher" value={filters.teacher_id} onChange={(value) => setFilters((c) => ({ ...c, teacher_id: value }))}><option value="">All teachers</option>{teachers.map((item) => <option key={item.id} value={item.id}>{displayPerson(item)}</option>)}</SelectField> : null}{sessions.length > 0 ? <SelectField label="Session" value={filters.academic_session_id} onChange={(value) => setFilters((c) => ({ ...c, academic_session_id: value, academic_term_id: "" }))}><option value="">Select session</option>{sessions.map((item) => <option key={item.id} value={item.id}>{item.name}{item.is_current ? " · Current" : ""}</option>)}</SelectField> : null}{terms.length > 0 ? <SelectField label="Term" value={filters.academic_term_id} onChange={(value) => setFilters((c) => ({ ...c, academic_term_id: value }))}><option value="">Select term</option>{terms.map((item) => <option key={item.id} value={item.id}>{displayTerm(item.name)}{item.is_current ? " · Current" : ""}</option>)}</SelectField> : null}</div>; }
function NavButton({ section, active, onClick }) { const Icon = section.icon; return <button type="button" onClick={onClick} className={`mb-1 flex w-full items-start gap-3 rounded-2xl px-3 py-3 text-left transition last:mb-0 ${active ? "bg-primary text-text-inverse shadow-sm" : "text-text-soft hover:bg-surface-muted hover:text-text"}`}><Icon className="mt-0.5 h-4 w-4 shrink-0" /><span><span className="block text-sm font-semibold">{section.name}</span><span className={`mt-1 block text-xs leading-5 ${active ? "text-white/80" : "text-text-muted"}`}>{section.description}</span></span></button>; }
function HeaderCard({ section, currentSession, currentTerm }) { const Icon = section.icon; return <div className="rounded-[1.35rem] border border-border bg-surface p-4 shadow-sm sm:p-5"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div className="min-w-0"><div className="flex items-center gap-2 text-sm font-semibold text-primary"><Icon className="h-4 w-4" />{section.name}</div><p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{section.description}</p></div><div className="grid grid-cols-2 gap-2 text-xs sm:min-w-[260px]"><ContextChip label="Session" value={currentSession?.name || "Not set"} /><ContextChip label="Term" value={currentTerm?.name ? displayTerm(currentTerm.name) : "Not set"} /></div></div></div>; }
function Panel({ title, subtitle, children }) { return <section className="rounded-[1.35rem] border border-border bg-surface shadow-sm"><div className="border-b border-border/70 p-4 sm:p-5"><h2 className="text-base font-semibold text-text sm:text-lg">{title}</h2>{subtitle ? <p className="mt-1 text-sm leading-6 text-text-muted">{subtitle}</p> : null}</div><div className="p-4 sm:p-5">{children}</div></section>; }
function ResponsiveTable({ headers, children, empty, emptyText }) {
  if (empty) return <EmptyState icon={ClipboardList} title="Nothing to show" description={emptyText} />;

  const rows = Children.map(children, (row) => {
    if (!isValidElement(row)) return row;
    const cells = Children.map(row.props.children, (cell, index) => {
      if (!isValidElement(cell)) return cell;
      return cloneElement(cell, { "data-label": headers[index] || "" });
    });
    return cloneElement(row, undefined, cells);
  });

  return (
    <div className="table-wrap mt-4">
      <table className="data-table">
        <thead>
          <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  );
}
function Td({ children, strong = false }) { return <td className={`px-4 py-3 align-top ${strong ? "font-semibold text-text" : "text-text-soft"}`}>{children}</td>; }
function RowActions({ children }) { return <div className="flex flex-wrap gap-2">{children}</div>; }
function ActionButton({ children, disabled }) { return <button type="submit" className="btn-create" disabled={disabled}><Plus className="h-3.5 w-3.5" />{children}</button>; }
function StatusPill({ value }) { const normalized = String(value || "pending").toLowerCase(); const tone = ["active", "submitted", "published", "generated"].includes(normalized) ? "green" : normalized === "draft" || normalized === "pending" || normalized === "outdated" ? "gray" : "blue"; return <span className={`badge ${tone}`}>{normalized.replaceAll("_", " ")}</span>; }
function MiniStat({ label, value }) { return <div className="rounded-2xl border border-border bg-surface px-4 py-3 shadow-sm"><p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p><p className="mt-1 text-xl font-semibold text-text">{value}</p></div>; }
function ContextChip({ label, value }) { return <div className="rounded-xl border border-border bg-surface-muted/40 px-3 py-2"><p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">{label}</p><p className="mt-1 truncate text-xs font-semibold text-text">{value}</p></div>; }
function Alert({ children, tone = "info" }) { const styles = tone === "error" ? "border-error/30 bg-error-soft text-error" : tone === "warning" ? "border-warning/30 bg-warning-soft text-amber-700" : "border-primary/20 bg-primary-soft/20 text-primary-deep"; return <div className={`rounded-2xl border px-4 py-3 text-sm font-medium ${styles}`}>{children}</div>; }

export default AcademicHubPage;
