import { ArrowLeft, BookOpen } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";
import { cleanText } from "../../utils/academicDashboard";
import {
  displayStatusLabel,
  getAcademicContext,
  scoreDisplayValue,
  statusVariant,
} from "./studentPageUtils";

function metricValue(value) {
  return scoreDisplayValue(value);
}

function StudentSubjectDetailsPage() {
  const { subjectResultId } = useParams();
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function loadResults() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const response = await academicService.listMySubjectCards();
        if (!mounted) return;
        setResults(response?.items || []);
      } catch (error) {
        if (mounted)
          setLoadError(
            getErrorMessage(error, "Failed to load subject breakdown."),
          );
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadResults();

    return () => {
      mounted = false;
    };
  }, []);

  const result = useMemo(
    () =>
      results.find(
        (item) =>
          String(item.id) === String(subjectResultId) ||
          String(item.result_id) === String(subjectResultId),
      ) || null,
    [results, subjectResultId],
  );
  const context = useMemo(
    () => getAcademicContext(result ? [result] : results, []),
    [result, results],
  );

  if (isLoading) {
    return (
      <DashboardLayout role="student" title="Subject Breakdown">
        <LoadingState label="Loading subject breakdown..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="student"
      title={cleanText(result?.subject_name, "Subject Breakdown")}
      description={`${cleanText(context.sessionLabel, "No session")} / ${cleanText(context.termLabel, "No term")} / ${cleanText(result?.class_name, cleanText(context.classLabel, "No class"))}`}
      actions={
        <Link to="/student/subjects">
          <Button type="button" variant="outline">
            <ArrowLeft className="h-4 w-4" />
            Back to subjects
          </Button>
        </Link>
      }
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && result && (
        <section className="space-y-4 sm:space-y-5">
          <Card className="p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex min-w-0 items-start gap-4">
                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[1.2rem] border border-border/70 bg-surface-muted/25 text-primary">
                  <BookOpen className="h-6 w-6" />
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-xl font-semibold text-text">
                      {cleanText(result.subject_name, "Subject")}
                    </h2>
                    <Badge variant={statusVariant(result.status)}>
                      {displayStatusLabel(result.status)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm font-medium text-text-muted">
                    {cleanText(
                      result.class_name,
                      cleanText(context.classLabel, "Class"),
                    )}
                  </p>
                  <p className="mt-2 text-sm text-text-muted">
                    Teacher:{" "}
                    {cleanText(result.teacher_name, "Teacher not assigned")}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-4">
              <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Total score
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {metricValue(result.total_score)}
                </p>
              </div>
              <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Grade
                </p>
                <p className="mt-2 text-2xl font-semibold text-text">
                  {cleanText(result.grade, "-")}
                </p>
              </div>
              <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Session
                </p>
                <p className="mt-2 text-base font-semibold text-text">
                  {cleanText(result.academic_session_name)}
                </p>
              </div>
              <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Term
                </p>
                <p className="mt-2 text-base font-semibold text-text">
                  {cleanText(result.academic_term_name)}
                </p>
              </div>
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <h3 className="section-title">Score Breakdown</h3>
            <p className="mt-1 text-sm text-text-muted">
              The detailed subject marks live here so the subject index can stay
              compact and easy to scan.
            </p>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
              <div className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Test
                </p>
                <p className="mt-2 text-xl font-semibold text-text">
                  {metricValue(result.test_score)}
                </p>
              </div>
              <div className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Assessment
                </p>
                <p className="mt-2 text-xl font-semibold text-text">
                  {metricValue(result.assessment_score)}
                </p>
              </div>
              <div className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Exam
                </p>
                <p className="mt-2 text-xl font-semibold text-text">
                  {metricValue(result.exam_score)}
                </p>
              </div>
              <div className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Status
                </p>
                <p className="mt-2 text-base font-semibold capitalize text-text">
                  {displayStatusLabel(result.status)}
                </p>
              </div>
              <div className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3 sm:col-span-2 xl:col-span-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  Remark
                </p>
                <p className="mt-2 text-base font-semibold text-text">
                  {cleanText(result.remark, "No remark")}
                </p>
              </div>
            </div>
          </Card>
        </section>
      )}

      {!loadError && !result && (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={BookOpen}
            title="Subject not found"
            description="The subject record you opened could not be found in your published results."
          />
        </Card>
      )}
    </DashboardLayout>
  );
}

export default StudentSubjectDetailsPage;
