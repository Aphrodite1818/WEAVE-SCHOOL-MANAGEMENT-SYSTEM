import { useEffect, useMemo, useState } from "react";
import { BookOpen, CheckSquare, ClipboardList, Users } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import LoadingState from "../../components/shared/LoadingState";
import EmptyState from "../../components/shared/EmptyState";
import { SelectField } from "../../components/academic/AcademicSelectors";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { studentService } from "../../services/studentService";

const studentName = (student) => [student.first_name, student.last_name].filter(Boolean).join(" ") || student.admission_number || "Student";
const classLabel = (item) => [item.name || item.class_name, item.arm || item.class_arm].filter(Boolean).join(" ") || "Class";
const assignmentLabel = (item) => `${item.subject_name || "Subject"} - ${item.class_name || "Class"} ${item.class_arm || ""}`.trim();
const subjectLabel = (item) => item.subject_name || item.subject_code || "Subject";

function StudentsPage() {
  const [classTeacherClasses, setClassTeacherClasses] = useState([]);
  const [subjectAssignments, setSubjectAssignments] = useState([]);
  const [selectedClassId, setSelectedClassId] = useState("");
  const [selectedSubjectId, setSelectedSubjectId] = useState("");
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [classStudents, setClassStudents] = useState([]);
  const [subjectStudents, setSubjectStudents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRosterLoading, setIsRosterLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const [classResponse, assignmentResponse] = await Promise.all([
          classService.getClasses({ limit: 100, active_only: true }),
          academicService.listMyTeacherAssignments(),
        ]);
        if (!mounted) return;
        const classes = classResponse?.items || [];
        const assignments = assignmentResponse?.items || [];
        setClassTeacherClasses(classes);
        setSubjectAssignments(assignments);
        setSelectedClassId(classes[0]?.id || "");
        setSelectedSubjectId(assignments[0]?.subject_id || "");
        setSelectedAssignmentId(assignments[0]?.id || "");
      } catch (err) {
        if (mounted) setError(getErrorMessage(err, "Could not load teacher rosters."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  const subjectOptions = useMemo(() => {
    const map = new Map();
    subjectAssignments.forEach((assignment) => {
      if (assignment.subject_id && !map.has(assignment.subject_id)) {
        map.set(assignment.subject_id, subjectLabel(assignment));
      }
    });
    return [...map.entries()].map(([id, label]) => ({ id, label }));
  }, [subjectAssignments]);

  const filteredAssignments = useMemo(
    () => subjectAssignments.filter((assignment) => !selectedSubjectId || assignment.subject_id === selectedSubjectId),
    [subjectAssignments, selectedSubjectId]
  );

  useEffect(() => {
    if (!filteredAssignments.some((assignment) => assignment.id === selectedAssignmentId)) {
      setSelectedAssignmentId(filteredAssignments[0]?.id || "");
    }
  }, [filteredAssignments, selectedAssignmentId]);

  useEffect(() => {
    let mounted = true;
    async function loadClassStudents() {
      if (!selectedClassId) {
        setClassStudents([]);
        return;
      }
      try {
        const response = await studentService.getStudents({ classId: selectedClassId, limit: 100 });
        if (mounted) setClassStudents(response?.items || []);
      } catch (err) {
        if (mounted) setClassStudents([]);
        if (mounted) setError(getErrorMessage(err, "Could not load class-teacher students."));
      }
    }
    loadClassStudents();
    return () => {
      mounted = false;
    };
  }, [selectedClassId]);

  useEffect(() => {
    let mounted = true;
    async function loadSubjectRoster() {
      if (!selectedAssignmentId) {
        setSubjectStudents([]);
        return;
      }
      setIsRosterLoading(true);
      try {
        const response = await academicService.listMyAssignmentStudents(selectedAssignmentId, { limit: 100 });
        if (mounted) setSubjectStudents(response?.items || []);
      } catch (err) {
        if (mounted) {
          setSubjectStudents([]);
          setError(getErrorMessage(err, "Could not load subject-teaching roster."));
        }
      } finally {
        if (mounted) setIsRosterLoading(false);
      }
    }
    loadSubjectRoster();
    return () => {
      mounted = false;
    };
  }, [selectedAssignmentId]);

  if (isLoading) {
    return (
      <DashboardLayout role="teacher" title="Teaching Rosters">
        <LoadingState label="Loading rosters..." />
      </DashboardLayout>
    );
  }

  const selectedAssignment = subjectAssignments.find((item) => item.id === selectedAssignmentId);

  return (
    <DashboardLayout
      role="teacher"
      title="Teaching Rosters"
      description="View students by duty type: full class roster for class teachers, and class-subject roster for subject teachers."
    >
      {error ? <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div> : null}

      <section className="grid gap-5 xl:grid-cols-2">
        <Card className="p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl bg-primary-soft p-3 text-primary"><BookOpen className="h-5 w-5" /></div>
            <div>
              <h2 className="section-title">Subject-teaching rosters</h2>
              <p className="mt-1 text-sm text-text-muted">Filter by subject, then class. This is based on class-subject teacher assignments.</p>
            </div>
          </div>
          {subjectAssignments.length === 0 ? (
            <EmptyState icon={ClipboardList} title="No subject-teacher assignment" description="When an admin assigns you to a class-subject, the student roster for that class-subject will appear here." />
          ) : (
            <>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <SelectField label="Subject" value={selectedSubjectId} onChange={setSelectedSubjectId}>
                  {subjectOptions.map((subject) => <option key={subject.id} value={subject.id}>{subject.label}</option>)}
                </SelectField>
                <SelectField label="Class for that subject" value={selectedAssignmentId} onChange={setSelectedAssignmentId}>
                  {filteredAssignments.map((assignment) => <option key={assignment.id} value={assignment.id}>{assignment.class_name} {assignment.class_arm || ""}</option>)}
                </SelectField>
              </div>
              <RosterList
                title={selectedAssignment ? assignmentLabel(selectedAssignment) : "Subject roster"}
                students={subjectStudents}
                isLoading={isRosterLoading}
                empty="No students found for this assigned class-subject."
              />
            </>
          )}
        </Card>

        <Card className="p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl bg-success-soft p-3 text-success"><CheckSquare className="h-5 w-5" /></div>
            <div>
              <h2 className="section-title">Class-teacher roster</h2>
              <p className="mt-1 text-sm text-text-muted">Only available when you are assigned as the main class teacher for a class.</p>
            </div>
          </div>
          {classTeacherClasses.length === 0 ? (
            <EmptyState icon={Users} title="No class-teacher class" description="You are not assigned as a class teacher, so full class oversight features are hidden." />
          ) : (
            <>
              <div className="mt-4">
                <SelectField label="Class you oversee" value={selectedClassId} onChange={setSelectedClassId}>
                  {classTeacherClasses.map((item) => <option key={item.id} value={item.id}>{classLabel(item)}</option>)}
                </SelectField>
              </div>
              <RosterList title="Full class roster" students={classStudents} empty="No students found in this class." />
            </>
          )}
        </Card>
      </section>
    </DashboardLayout>
  );
}

function RosterList({ title, students, empty, isLoading = false }) {
  return (
    <div className="mt-4 rounded-2xl border border-border bg-surface-muted/20 p-3">
      <div className="flex items-center justify-between gap-3 px-1 py-1">
        <p className="text-sm font-semibold text-text">{title}</p>
        <Badge variant="default">{students.length} students</Badge>
      </div>
      {isLoading ? <LoadingState label="Loading students..." /> : null}
      {!isLoading && students.length === 0 ? <p className="px-1 py-4 text-sm text-text-muted">{empty}</p> : null}
      {!isLoading && students.length > 0 ? (
        <div className="mt-3 grid gap-2">
          {students.map((student) => (
            <div key={student.id} className="flex flex-col gap-1 rounded-xl border border-border bg-surface px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-text">{studentName(student)}</p>
                <p className="text-xs text-text-muted">{student.admission_number || "No admission number"}</p>
              </div>
              <Badge variant={student.status === "active" ? "success" : "warning"}>{student.status || "student"}</Badge>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default StudentsPage;
