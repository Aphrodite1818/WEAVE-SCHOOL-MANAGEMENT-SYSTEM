import { useEffect, useMemo, useState } from "react";
import { BookOpen, ChevronRight, LayoutGrid, List } from "lucide-react";
import { Link } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { studentService } from "../../services/studentService";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";
import { formatMetricNumber, getAcademicContext, statusVariant } from "./studentPageUtils";

function scoreSummary(result, fallback = 0) {
  const value = formatMetricNumber(result?.total_score ?? result?.totalScore);
  return value ?? fallback;
}

function mergeSubjectCards(subjects = [], results = [], classLabel = "Class") {
  const resultBySubjectId = new Map();

  results.forEach((result) => {
    const subjectId = String(result.subject_id || "");
    if (!subjectId || resultBySubjectId.has(subjectId)) return;
    resultBySubjectId.set(subjectId, result);
  });

  return subjects.map((subject) => {
    const result = resultBySubjectId.get(String(subject.subject_id || "")) || null;
    return {
      id: result?.id || subject.id,
      subjectId: subject.subject_id,
      subjectName: cleanText(subject.subject_name, "Subject"),
      classLabel,
      status: result?.status || "pending",
      totalScore: result?.total_score ?? 0,
      grade: result?.grade ?? "--",
      teacherName: cleanText(result?.teacher_name, "Teacher not assigned"),
      resultId: result?.id || null,
    };
  });
}

function StudentSubjectsPage() {
  const [student, setStudent] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [results, setResults] = useState([]);
  const [viewMode, setViewMode] = useState("grid");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function loadSubjects() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const studentResponse = await studentService.getMyStudent();
        if (!mounted) return;

        const studentProfile = studentResponse || null;
        setStudent(studentProfile);

        if (!studentProfile?.class_id) {
          setSubjects([]);
          setResults([]);
          return;
        }

        const [subjectResponse, resultResponse] = await Promise.all([
          academicService.listClassSubjects(studentProfile.class_id, { active_only: true }),
          academicService.listMyResults(),
        ]);

        if (!mounted) return;
        setSubjects(subjectResponse?.items || []);
        setResults(resultResponse?.items || []);
      } catch (error) {
        if (mounted) setLoadError(getErrorMessage(error, "Failed to load subjects."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadSubjects();

    return () => {
      mounted = false;
    };
  }, []);

  const context = useMemo(() => getAcademicContext(results, []), [results]);
  const isGridView = viewMode === "grid";
  const classLabel = cleanText(student?.class_name, student?.class_id ? "Class" : "No class assigned");
  const subjectCards = useMemo(
    () => mergeSubjectCards(subjects, results, classLabel),
    [subjects, results, classLabel]
  );

  if (isLoading) {
    return (
      <DashboardLayout role="student" title="Subjects">
        <LoadingState label="Loading subjects..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="student"
      title="Subjects"
      description={`${cleanText(context.sessionLabel, "No session")} / ${cleanText(context.termLabel, "No term")} / ${classLabel}`}
      actions={
        <div className="inline-flex rounded-2xl border border-border bg-surface p-1 shadow-sm">
          <Button
            type="button"
            variant={isGridView ? "primary" : "ghost"}
            size="sm"
            className="rounded-xl"
            onClick={() => setViewMode("grid")}
            aria-label="Show subjects as compact cards"
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant={!isGridView ? "primary" : "ghost"}
            size="sm"
            className="rounded-xl"
            onClick={() => setViewMode("list")}
            aria-label="Show subjects as a list"
          >
            <List className="h-4 w-4" />
          </Button>
        </div>
      }
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && subjectCards.length === 0 && (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={BookOpen}
            title="No subjects available"
            description={
              student?.class_id
                ? "Your class has no active subjects yet, so there are no subject cards to show."
                : "No class has been assigned to your student profile yet."
            }
          />
        </Card>
      )}

      {!loadError && subjectCards.length > 0 && (
        <section
          className={cn(
            "grid gap-4",
            isGridView ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" : "grid-cols-1"
          )}
        >
          {subjectCards.map((card) => {
            const statusLabel = cleanText(card.status, "Pending");
            const totalScore = scoreSummary(card);
            const grade = cleanText(card.grade, "--");

            return (
              <Card
                key={card.id}
                as={card.resultId ? Link : "div"}
                to={card.resultId ? `/student/subjects/${card.resultId}` : undefined}
                className={cn(
                  "group w-full overflow-hidden rounded-[1.5rem] border border-border/80 bg-surface p-0 text-left shadow-[0_1px_0_rgba(255,255,255,0.04)] transition-all duration-200",
                  card.resultId
                    ? "hover:-translate-y-0.5 hover:border-border-strong hover:shadow-premium"
                    : "cursor-default",
                  isGridView ? "min-h-[228px]" : ""
                )}
              >
                {isGridView ? (
                  <div className="flex h-full flex-col p-4">
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[1rem] border border-border/70 bg-surface-muted/25 text-primary">
                        <BookOpen className="h-5 w-5" />
                      </span>
                      {card.resultId ? (
                        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
                      ) : (
                        <span className="mt-1 text-[11px] font-medium text-text-faint">Awaiting marks</span>
                      )}
                    </div>

                    <div className="mt-3 min-w-0">
                      <h2 className="truncate text-base font-semibold text-text">{card.subjectName}</h2>
                      <p className="mt-1 text-xs font-medium text-text-muted">{classLabel}</p>
                      <div className="mt-2">
                        <Badge variant={statusVariant(card.status)}>{statusLabel}</Badge>
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-2.5">
                      <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                          Score
                        </p>
                        <p className="mt-2 text-2xl font-semibold leading-none text-text">{totalScore}</p>
                      </div>
                      <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                          Grade
                        </p>
                        <p className="mt-2 text-2xl font-semibold leading-none text-text">{grade}</p>
                      </div>
                    </div>

                    <div className="mt-auto pt-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                        Teacher
                      </p>
                      <p className="mt-1 truncate text-sm font-semibold text-text">{card.teacherName}</p>
                    </div>
                  </div>
                ) : (
                  <div className="p-5 sm:p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex min-w-0 items-start gap-4">
                        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[1.1rem] border border-border/70 bg-surface-muted/25 text-primary">
                          <BookOpen className="h-5 w-5" />
                        </span>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h2 className="truncate text-lg font-semibold text-text">{card.subjectName}</h2>
                            <Badge variant={statusVariant(card.status)}>{statusLabel}</Badge>
                          </div>
                          <p className="mt-1 text-sm font-medium text-text-muted">{card.classLabel || classLabel}</p>
                          <p className="mt-2 text-sm text-text-muted">{card.teacherName}</p>
                        </div>
                      </div>
                      {card.resultId ? (
                        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
                      ) : (
                        <span className="mt-1 text-xs font-medium text-text-faint">Awaiting marks</span>
                      )}
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                          Total score
                        </p>
                        <p className="mt-2 text-2xl font-semibold text-text">{totalScore}</p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                          Grade
                        </p>
                        <p className="mt-2 text-2xl font-semibold text-text">{grade}</p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                          Status
                        </p>
                        <p className="mt-2 text-base font-semibold text-text">
                          {card.resultId ? "Full breakdown" : "Awaiting marks"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </section>
      )}
    </DashboardLayout>
  );
}

export default StudentSubjectsPage;
