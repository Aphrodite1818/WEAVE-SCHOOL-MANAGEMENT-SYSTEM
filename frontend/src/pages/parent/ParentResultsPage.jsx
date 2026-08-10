import { useEffect, useMemo, useState } from "react";
import { BarChart3, FileText } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import {
  averageScore,
  bestAndWeakestSubject,
  chartFromCounts,
  cleanText,
  subjectPerformanceChart,
} from "../../utils/academicDashboard";
import ParentChildSelector from "./ParentChildSelector";
import useParentChildren from "./useParentChildren";

function ParentResultsPage() {
  const {
    children,
    selectedChildId,
    selectedChildRecord,
    setSelectedChildId,
    isLoading,
    loadError,
    setLoadError,
  } = useParentChildren();
  const [childResults, setChildResults] = useState([]);
  const [isLoadingResults, setIsLoadingResults] = useState(false);

  const childAverage = averageScore(childResults);
  const subjectHighlights = bestAndWeakestSubject(childResults);
  const gradeBreakdown = useMemo(
    () => chartFromCounts(childResults, "grade", "ungraded"),
    [childResults]
  );
  const selectedChildAcademicLabel = useMemo(() => {
    const latestResult = childResults[0];
    const session = latestResult?.academic_session_name;
    const term = latestResult?.academic_term_name;
    return [session, cleanText(term, "")].filter(Boolean).join(" / ") || "-";
  }, [childResults]);

  useEffect(() => {
    let mounted = true;

    async function loadChildResults() {
      if (!selectedChildId) {
        setChildResults([]);
        return;
      }

      setIsLoadingResults(true);

      try {
        const response = await academicService.listChildResults(selectedChildId);
        if (!mounted) return;
        setChildResults(response?.items || []);
      } catch (error) {
        if (!mounted) return;
        setChildResults([]);
        setLoadError(getErrorMessage(error, "Failed to load child results."));
      } finally {
        if (mounted) setIsLoadingResults(false);
      }
    }

    loadChildResults();

    return () => {
      mounted = false;
    };
  }, [selectedChildId, setLoadError]);

  if (isLoading) {
    return (
      <DashboardLayout role="parent" title="Results">
        <LoadingState label="Loading results..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="parent"
      title="Results"
      description="Published subject scores and grade signals for the selected child."
    >
      {loadError && (
        <div className="rounded-[1.35rem] border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      <Card className="p-5 sm:p-6">
        <ParentChildSelector
          linkedChildren={children}
          selectedChildId={selectedChildId}
          onSelectChild={setSelectedChildId}
          academicLabel={selectedChildAcademicLabel}
          showCards={false}
        />
      </Card>

      {selectedChildRecord && (
        <>
          <section className="stat-grid stat-grid-four">
            <StatCard
              label="Average Score"
              value={childAverage}
              description="selected child"
              icon={BarChart3}
              tone={childResults.length > 0 ? "success" : "warning"}
              compact
            />
            <StatCard
              label="Published Results"
              value={childResults.length}
              description="subject records"
              icon={FileText}
              tone={childResults.length > 0 ? "primary" : "warning"}
              compact
            />
            <StatCard
              label="Best Subject"
              value={subjectHighlights.best?.label || "-"}
              description={subjectHighlights.best ? `${subjectHighlights.best.value} score` : "awaiting results"}
              icon={BarChart3}
              tone={subjectHighlights.best ? "success" : "warning"}
              compact
            />
            <StatCard
              label="Needs Attention"
              value={subjectHighlights.weakest?.label || "-"}
              description={subjectHighlights.weakest ? `${subjectHighlights.weakest.value} score` : "no weak area yet"}
              icon={FileText}
              tone={subjectHighlights.weakest ? "warning" : "primary"}
              compact
            />
          </section>

          <section className="dashboard-grid lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]">
            <AnalyticsBarChart
              title="Subject Performance"
              description="Published subject scores for the selected child."
              data={subjectPerformanceChart(childResults)}
              emptyMessage="No published subject results for the selected child yet."
            />

            <Card className="p-5 sm:p-6">
              <h3 className="section-title">Grade breakdown</h3>
              <p className="mt-1 text-sm text-text-muted">Distribution of published grades.</p>

              <div className="mt-4 space-y-2">
                {gradeBreakdown.length > 0 ? (
                  gradeBreakdown.map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center justify-between gap-3 rounded-[1rem] border border-border/60 bg-surface px-4 py-3"
                    >
                      <p className="text-sm font-medium text-text">{cleanText(item.label)}</p>
                      <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-text-soft">
                        {item.value}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-text-muted">No grade distribution available yet.</p>
                )}
              </div>
            </Card>
          </section>

          <Card className="p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <h3 className="section-title">Subject results</h3>
              <Badge variant="info">{childResults.length} visible</Badge>
            </div>

            {isLoadingResults ? (
              <LoadingState label="Loading subject results..." />
            ) : childResults.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="No results available"
                description="Published subject results will appear here when the school releases them."
              />
            ) : (
              <div className="mobile-scroll-list mt-4 grid gap-3">
                {childResults.map((result) => (
                  <div
                    key={result.id}
                    className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-text">
                          {cleanText(result.subject_name, "Subject")}
                        </p>
                        <p className="mt-1 text-xs text-text-muted">
                          Teacher: {cleanText(result.teacher_name)} / Total {cleanText(result.total_score)} /{" "}
                          {cleanText(result.academic_session_name)} / {cleanText(result.academic_term_name)}
                        </p>
                      </div>
                      <Badge variant="success">{cleanText(result.grade)}</Badge>
                    </div>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                      {(result.components || []).map((component) => (
                        <div key={component.assessment_component_id} className="rounded-xl bg-surface-muted/30 px-3 py-2 text-sm">
                          <p className="truncate text-xs text-text-muted">{component.name}</p>
                          <p className="mt-1 font-semibold text-text">{component.score ?? "—"} / {component.maximum_score}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}

      {!selectedChildRecord && (
        <Card className="p-5 sm:p-6">
          <EmptyState
            icon={BarChart3}
            title="Select a linked child"
            description="Link and approve a student first, then choose them here to review results."
          />
        </Card>
      )}
    </DashboardLayout>
  );
}

export default ParentResultsPage;
