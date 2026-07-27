import { BookOpen, LayoutGrid, List } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StudentSubjectPerformanceCard from "../../components/student/StudentSubjectPerformanceCard";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { academicService } from "../../services/academicService";
import { assessmentLimitsService } from "../../services/assessmentLimitsService";
import { getErrorMessage } from "../../services/api";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";

function StudentSubjectsPage() {
  const [subjectCards, setSubjectCards] = useState([]);
  const [context, setContext] = useState(null);
  const [assessmentLimits, setAssessmentLimits] = useState({ is_configured: false });
  const [viewMode, setViewMode] = useState("grid");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function loadSubjects() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const [response, limitsResponse] = await Promise.all([
          academicService.listMySubjectCards(),
          assessmentLimitsService.getStudentLimits(),
        ]);
        if (!mounted) return;
        setSubjectCards(response?.items || []);
        setContext(response?.context || null);
        setAssessmentLimits(limitsResponse || { is_configured: false });
      } catch (error) {
        if (mounted) {
          setLoadError(getErrorMessage(error, "Failed to load subjects."));
        }
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
    context?.class_id ? "Class" : "No class assigned",
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
        <div className="hidden rounded-2xl border border-border bg-surface p-1 shadow-sm md:inline-flex">
          <Button
            type="button"
            variant={isGridView ? "primary" : "ghost"}
            size="sm"
            className="rounded-xl"
            onClick={() => setViewMode("grid")}
            aria-label="Show subjects as cards"
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
      <section className="student-subject-page-shell space-y-5 sm:space-y-6">
        <Card className="overflow-hidden p-5 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0">
              <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-text-muted">
                Current academic view
              </p>
              <h2 className="mt-2 text-xl font-semibold leading-tight text-text sm:text-2xl">
                Subject performance
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
                Review each class subject with score components, configured limits, grade, status, and assigned teacher.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:min-w-[18rem]">
              <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-2 text-center">
                <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Subjects</p>
                <p className="mt-1 text-lg font-semibold text-text">{subjectCards.length}</p>
              </div>
              <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-2 text-center">
                <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Session</p>
                <p className="mt-1 truncate text-sm font-semibold text-text">{cleanText(context?.academic_session_name, "-")}</p>
              </div>
              <div className="rounded-[1rem] border border-border/70 bg-surface-muted/20 px-3 py-2 text-center">
                <p className="text-[10px] font-bold uppercase tracking-wide text-text-muted">Term</p>
                <p className="mt-1 truncate text-sm font-semibold text-text">{cleanText(context?.academic_term_name, "-")}</p>
              </div>
            </div>
          </div>
        </Card>

        {loadError ? (
          <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
            {loadError}
          </div>
        ) : null}

        {!loadError && subjectCards.length === 0 ? (
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
        ) : null}

        {!loadError && subjectCards.length > 0 ? (
          <section
            className={cn(
              "grid gap-4 sm:gap-5",
              isGridView
                ? "grid-cols-1 sm:grid-cols-2 2xl:grid-cols-3"
                : "grid-cols-1",
            )}
          >
            {subjectCards.map((card) => (
              <StudentSubjectPerformanceCard
                key={card.id}
                card={card}
                classLabel={classLabel}
                compact={!isGridView}
                limits={assessmentLimits}
              />
            ))}
          </section>
        ) : null}
      </section>
    </DashboardLayout>
  );
}

export default StudentSubjectsPage;
