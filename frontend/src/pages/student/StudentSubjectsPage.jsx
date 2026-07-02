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
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";
import { formatMetricNumber, getAcademicContext, statusVariant } from "./studentPageUtils";

function scoreSummary(result) {
  if (result.total_score !== undefined && result.total_score !== null) {
    return formatMetricNumber(result.total_score);
  }
  return "-";
}

function StudentSubjectsPage() {
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
        const response = await academicService.listMyResults();
        if (!mounted) return;
        setResults(response?.items || []);
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
      description={`${cleanText(context.sessionLabel, "No session")} / ${cleanText(context.termLabel, "No term")} / ${cleanText(context.classLabel, "No class")}`}
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

      {!loadError && results.length === 0 && (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={BookOpen}
            title="No subjects available"
            description="Subject results will appear here after your school publishes academic records."
          />
        </Card>
      )}

      {!loadError && results.length > 0 && (
        <section
          className={cn(
            "grid gap-4",
            isGridView ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" : "grid-cols-1"
          )}
        >
          {results.map((result) => {
            const subjectName = cleanText(result.subject_name, "Subject");
            const classLabel = cleanText(result.class_name, cleanText(context.classLabel, "Class"));
            const statusLabel = cleanText(result.status);
            const totalScore = scoreSummary(result);
            const grade = cleanText(result.grade, "-");
            const teacherName = cleanText(result.teacher_name, "Teacher not assigned");

            return (
              <Card
                key={result.id}
                as={Link}
                to={`/student/subjects/${result.id}`}
                className={cn(
                  "group w-full overflow-hidden rounded-[1.5rem] border border-border/80 bg-surface p-0 text-left shadow-[0_1px_0_rgba(255,255,255,0.04)] transition-all duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-premium",
                  isGridView ? "min-h-[228px]" : ""
                )}
              >
                {isGridView ? (
                  <div className="flex h-full flex-col p-4">
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[1rem] border border-border/70 bg-surface-muted/25 text-primary">
                        <BookOpen className="h-5 w-5" />
                      </span>
                      <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
                    </div>

                    <div className="mt-3 min-w-0">
                      <h2 className="truncate text-base font-semibold text-text">{subjectName}</h2>
                      <p className="mt-1 text-xs font-medium text-text-muted">{classLabel}</p>
                      <div className="mt-2">
                        <Badge variant={statusVariant(result.status)}>{statusLabel}</Badge>
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
                      <p className="mt-1 truncate text-sm font-semibold text-text">{teacherName}</p>
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
                            <h2 className="truncate text-lg font-semibold text-text">{subjectName}</h2>
                            <Badge variant={statusVariant(result.status)}>{statusLabel}</Badge>
                          </div>
                          <p className="mt-1 text-sm font-medium text-text-muted">{classLabel}</p>
                          <p className="mt-2 text-sm text-text-muted">{teacherName}</p>
                        </div>
                      </div>
                      <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
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
                          Tap to view
                        </p>
                        <p className="mt-2 text-base font-semibold text-text">Full breakdown</p>
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
