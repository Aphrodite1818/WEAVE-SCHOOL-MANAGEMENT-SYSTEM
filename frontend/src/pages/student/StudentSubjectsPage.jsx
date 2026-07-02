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
import { displayStatusLabel, scoreDisplayValue, statusVariant } from "./studentPageUtils";

function StudentSubjectsPage() {
  const [subjectCards, setSubjectCards] = useState([]);
  const [context, setContext] = useState(null);
  const [viewMode, setViewMode] = useState("grid");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function loadSubjects() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const response = await academicService.listMySubjectCards();
        if (!mounted) return;
        setSubjectCards(response?.items || []);
        setContext(response?.context || null);
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

  const isGridView = viewMode === "grid";
  const classLabel = cleanText(
    context?.class_name
      ? [context.class_name, context.class_arm].filter(Boolean).join(" ")
      : null,
    context?.class_id ? "Class" : "No class assigned"
  );
  const academicContextLabel = useMemo(() => {
    const session = cleanText(context?.academic_session_name, "No session");
    const term = cleanText(context?.academic_term_name, "No term");
    return `${session} / ${term} / ${classLabel}`;
  }, [classLabel, context]);

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
      description={academicContextLabel}
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
              context?.class_id
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
            const statusLabel = displayStatusLabel(card.status, card.result_id ? "Pending" : "Awaiting marks");
            const totalScore = scoreDisplayValue(card.total_score);
            const grade = cleanText(card.grade, "--");
            const testScore = scoreDisplayValue(card.test_score);
            const assessmentScore = scoreDisplayValue(card.assessment_score);
            const examScore = scoreDisplayValue(card.exam_score);
            const teacherName = cleanText(card.teacher_name, "Teacher not assigned");

            return (
              <Card
                key={card.id}
                as={card.result_id ? Link : "div"}
                to={card.result_id ? `/student/subjects/${card.result_id}` : undefined}
                className={cn(
                  "group w-full overflow-hidden rounded-[1.5rem] border border-border/80 bg-surface p-0 text-left shadow-[0_1px_0_rgba(255,255,255,0.04)] transition-all duration-200",
                  card.result_id
                    ? "hover:-translate-y-0.5 hover:border-border-strong hover:shadow-premium"
                    : "cursor-default"
                )}
              >
                {isGridView ? (
                  <div className="flex h-full flex-col p-4">
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[1rem] border border-border/70 bg-surface-muted/25 text-primary">
                        <BookOpen className="h-5 w-5" />
                      </span>
                      {card.result_id ? (
                        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
                      ) : (
                        <span className="mt-1 text-[11px] font-medium text-text-faint">Awaiting marks</span>
                      )}
                    </div>

                    <div className="mt-3 min-w-0">
                      <h2 className="truncate text-base font-semibold text-text">{cleanText(card.subject_name, "Subject")}</h2>
                      <p className="mt-1 text-xs font-medium text-text-muted">{classLabel}</p>
                      <div className="mt-2">
                        <Badge variant={statusVariant(card.status)}>{statusLabel}</Badge>
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                      <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Score</p>
                        <p className="mt-2 text-2xl font-semibold leading-none text-text">{totalScore}</p>
                      </div>
                      <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-3">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Grade</p>
                        <p className="mt-2 text-2xl font-semibold leading-none text-text">{grade}</p>
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-3 gap-2">
                      <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-2 text-center">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Test</p>
                        <p className="mt-1 text-sm font-semibold text-text">{testScore}</p>
                      </div>
                      <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-2 text-center">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Assess.</p>
                        <p className="mt-1 text-sm font-semibold text-text">{assessmentScore}</p>
                      </div>
                      <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-2 text-center">
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Exam</p>
                        <p className="mt-1 text-sm font-semibold text-text">{examScore}</p>
                      </div>
                    </div>

                    <div className="mt-auto pt-3">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Teacher</p>
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
                            <h2 className="truncate text-lg font-semibold text-text">{cleanText(card.subject_name, "Subject")}</h2>
                            <Badge variant={statusVariant(card.status)}>{statusLabel}</Badge>
                          </div>
                          <p className="mt-1 text-sm font-medium text-text-muted">{card.class_name || classLabel}</p>
                          <p className="mt-2 text-sm text-text-muted">{teacherName}</p>
                        </div>
                      </div>
                      {card.result_id ? (
                        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
                      ) : (
                        <span className="mt-1 text-xs font-medium text-text-faint">Awaiting marks</span>
                      )}
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Test</p>
                        <p className="mt-2 text-2xl font-semibold text-text">{testScore}</p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Assessment</p>
                        <p className="mt-2 text-2xl font-semibold text-text">{assessmentScore}</p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Exam</p>
                        <p className="mt-2 text-2xl font-semibold text-text">{examScore}</p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Total / Grade</p>
                        <p className="mt-2 text-2xl font-semibold text-text">
                          {totalScore} <span className="text-base text-text-muted">/ {grade}</span>
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
