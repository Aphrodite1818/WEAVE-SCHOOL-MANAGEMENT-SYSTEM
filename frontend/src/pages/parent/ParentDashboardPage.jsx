import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3, FileText, GraduationCap, Link2, Users } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { authSession, getErrorMessage } from "../../services/api";
import { academicService } from "../../services/academicService";
import { reportCardService } from "../../services/reportCardService";
import { displayName } from "../../utils/user";
import {
  averageByAcademicPeriod,
  averageScore,
  bestAndWeakestSubject,
  cleanText,
  reportCardStatusChart,
  subjectPerformanceChart,
} from "../../utils/academicDashboard";
import ParentChildSelector from "./ParentChildSelector";
import useParentChildren from "./useParentChildren";

function ParentDashboardPage() {
  const user = authSession.getUser();
  const firstName = user?.first_name || user?.firstname || "Parent";
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
  const [childReportCards, setChildReportCards] = useState([]);

  const childAverage = averageScore(childResults);
  const subjectHighlights = bestAndWeakestSubject(childResults);
  const latestReportCard = childReportCards[0] || null;

  const selectedChildAcademicLabel = useMemo(() => {
    const latestResult = childResults[0];
    const latestCard = childReportCards[0];
    const session = latestResult?.academic_session_name || latestCard?.academic_session_name;
    const term = latestResult?.academic_term_name || latestCard?.academic_term_name;
    return [session, cleanText(term, "")].filter(Boolean).join(" / ") || "-";
  }, [childResults, childReportCards]);

  const performanceTrend = useMemo(
    () =>
      averageByAcademicPeriod(
        childReportCards.length > 0 ? childReportCards : childResults,
        childReportCards.length > 0 ? "average_score" : "total_score"
      ),
    [childReportCards, childResults]
  );

  useEffect(() => {
    let mounted = true;

    async function loadChildAcademics() {
      if (!selectedChildId) {
        setChildResults([]);
        setChildReportCards([]);
        return;
      }

      try {
        const [resultResponse, reportCardResponse] = await Promise.all([
          academicService.listChildResults(selectedChildId),
          reportCardService.listChildReportCards(selectedChildId),
        ]);
        if (!mounted) return;
        setChildResults(resultResponse?.items || []);
        setChildReportCards(reportCardResponse?.items || []);
      } catch (error) {
        if (!mounted) return;
        setChildResults([]);
        setChildReportCards([]);
        setLoadError(getErrorMessage(error, "Failed to load child academic summary."));
      }
    }

    loadChildAcademics();

    return () => {
      mounted = false;
    };
  }, [selectedChildId, setLoadError]);

  if (isLoading) {
    return (
      <DashboardLayout role="parent" title={`${firstName}'s Portal`}>
        <LoadingState label="Loading parent dashboard..." />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      role="parent"
      title={`${firstName}'s Portal`}
      description="A family overview for the selected child. Detailed workflows live in their own sidebar pages."
    >
      {loadError && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && (
        <>
          <section className="dashboard-grid xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
            <Card className="p-5 sm:p-6">
              <div className="mb-4">
                <h2 className="text-xl font-semibold text-text sm:text-2xl">
                  Family overview for {selectedChildRecord ? displayName(selectedChildRecord.student) : firstName}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                  Switch the selected child here, then use the sidebar for linking, results, report cards, and notices.
                </p>
              </div>

              <ParentChildSelector
                linkedChildren={children}
                selectedChildId={selectedChildId}
                onSelectChild={setSelectedChildId}
                academicLabel={selectedChildAcademicLabel}
              />
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <div>
                <h3 className="section-title">Selected child snapshot</h3>
                <p className="mt-1 text-sm text-text-muted">
                  A quick current-child summary so the page feels anchored before the charts below.
                </p>
              </div>

              <div className="dashboard-kpi-grid mt-auto pt-4 xl:grid-cols-1 2xl:grid-cols-2">
                <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Selected child</p>
                  <p className="mt-2 text-base font-semibold text-text">
                    {selectedChildRecord ? displayName(selectedChildRecord.student) : "No child selected"}
                  </p>
                </div>
                <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Latest average</p>
                  <p className="mt-2 text-base font-semibold text-text">
                    {latestReportCard ? cleanText(latestReportCard.average_score) : cleanText(childAverage, "-")}
                  </p>
                </div>
                <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Strongest subject</p>
                  <p className="mt-2 text-base font-semibold text-text">
                    {subjectHighlights.best?.label || "Awaiting results"}
                  </p>
                </div>
                <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Needs support</p>
                  <p className="mt-2 text-base font-semibold text-text">
                    {subjectHighlights.weakest?.label || "No weak spot yet"}
                  </p>
                </div>
              </div>
            </Card>
          </section>

          <section className="stat-grid stat-grid-five">
            <StatCard
              label="Linked Students"
              value={children.length}
              description="visible profiles"
              icon={Users}
              tone={children.length > 0 ? "primary" : "warning"}
              compact
            />
            <StatCard
              label="Primary Contacts"
              value={children.filter((item) => item.link?.is_primary_contact).length}
              description="marked primary"
              icon={Link2}
              tone="success"
              compact
            />
            <StatCard
              label="Average Score"
              value={childAverage}
              description="selected child"
              icon={BarChart3}
              tone={childResults.length > 0 ? "success" : "warning"}
              compact
            />
            <StatCard
              label="Academic Context"
              value={selectedChildAcademicLabel}
              description="selected child latest term"
              icon={GraduationCap}
              tone={selectedChildAcademicLabel !== "-" ? "primary" : "warning"}
              compact
            />
            <StatCard
              label="Best Subject"
              value={subjectHighlights.best?.label || "-"}
              description={subjectHighlights.best ? `${subjectHighlights.best.value} score` : "awaiting results"}
              icon={FileText}
              tone={subjectHighlights.best ? "success" : "warning"}
              compact
            />
          </section>

          <section className="dashboard-grid xl:grid-cols-2">
            <AnalyticsLineChart
              title="Performance Trend"
              description="Average score by academic term for the selected child."
              data={performanceTrend}
              emptyMessage="No term trend is available for the selected child yet."
            />
            <AnalyticsBarChart
              title="Subject Performance"
              description="Published subject scores for the selected child."
              data={subjectPerformanceChart(childResults)}
              emptyMessage="No published subject results for the selected child yet."
            />
            <AnalyticsBarChart
              title="Report Card Status"
              description="Report-card generation and publishing state."
              data={reportCardStatusChart(childReportCards)}
              emptyMessage="No report card status data available yet."
            />
          </section>

          <section className="dashboard-grid xl:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
            <Card className="flex h-full flex-col p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="section-title">Latest report card</h3>
                  <p className="mt-1 text-sm text-text-muted">
                    A quick summary of the newest published term for the selected child.
                  </p>
                </div>
                {latestReportCard && (
                  <Badge variant="success">
                    {cleanText(latestReportCard.academic_term_name, "Latest term")}
                  </Badge>
                )}
              </div>

              {latestReportCard ? (
                <>
                  <div className="mt-auto pt-4">
                    <div className="dashboard-kpi-grid sm:grid-cols-3">
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Average</p>
                        <p className="mt-2 text-lg font-semibold text-text">
                          {cleanText(latestReportCard.average_score)}
                        </p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Subjects</p>
                        <p className="mt-2 text-lg font-semibold text-text">
                          {latestReportCard.lines?.length || 0}
                        </p>
                      </div>
                      <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Position</p>
                        <p className="mt-2 text-lg font-semibold text-text">
                          {cleanText(latestReportCard.position, "-")}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4">
                    <Link
                      to="/parent/report-cards"
                      className="inline-flex min-h-9 items-center justify-center rounded-lg border border-border/80 bg-surface px-3 py-1.5 text-xs font-semibold text-text-soft shadow-sm transition hover:border-border hover:bg-surface-muted/50 hover:text-text"
                    >
                      Open full report cards
                    </Link>
                  </div>
                </>
              ) : (
                <p className="mt-auto pt-4 text-sm text-text-muted">
                  No report card available yet for this child.
                </p>
              )}
            </Card>

            <Card className="flex h-full flex-col p-5 sm:p-6">
              <h3 className="section-title">Family workflows</h3>
              <p className="mt-1 text-sm text-text-muted">
                Keep the dashboard focused on overview signals while the sidebar handles full workflows.
              </p>

              <div className="mt-auto pt-4 grid gap-3">
                <Link
                  to="/parent/student-linking"
                  className="rounded-[1.15rem] border border-border/70 bg-surface px-4 py-3 transition hover:border-primary/30 hover:bg-primary-subtle/40"
                >
                  <p className="text-sm font-semibold text-text">Student Linking</p>
                  <p className="mt-1 text-xs text-text-muted">
                    Request access to another child and track approval status.
                  </p>
                </Link>
                <Link
                  to="/parent/results"
                  className="rounded-[1.15rem] border border-border/70 bg-surface px-4 py-3 transition hover:border-primary/30 hover:bg-primary-subtle/40"
                >
                  <p className="text-sm font-semibold text-text">Results</p>
                  <p className="mt-1 text-xs text-text-muted">
                    Review published subject scores and grade breakdowns.
                  </p>
                </Link>
                <Link
                  to="/parent/report-cards"
                  className="rounded-[1.15rem] border border-border/70 bg-surface px-4 py-3 transition hover:border-primary/30 hover:bg-primary-subtle/40"
                >
                  <p className="text-sm font-semibold text-text">Report Cards</p>
                  <p className="mt-1 text-xs text-text-muted">
                    Read full term reports and print published cards.
                  </p>
                </Link>
                <Link
                  to="/parent/notices"
                  className="rounded-[1.15rem] border border-border/70 bg-surface px-4 py-3 transition hover:border-primary/30 hover:bg-primary-subtle/40"
                >
                  <p className="text-sm font-semibold text-text">Notices</p>
                  <p className="mt-1 text-xs text-text-muted">
                    School announcements sent to your parent account.
                  </p>
                </Link>
              </div>

              {children.length === 0 && (
                <p className="mt-4 text-xs text-text-muted">
                  Start from Student Linking to request access to a child's academic record.
                </p>
              )}
            </Card>
          </section>
        </>
      )}
    </DashboardLayout>
  );
}

export default ParentDashboardPage;
