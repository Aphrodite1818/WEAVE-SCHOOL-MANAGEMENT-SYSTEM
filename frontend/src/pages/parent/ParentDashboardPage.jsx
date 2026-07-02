import { useEffect, useMemo, useState } from "react";
import { BarChart3, FileText, GraduationCap, Link2, Users } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import AnalyticsBarChart from "../../components/charts/AnalyticsBarChart";
import AnalyticsLineChart from "../../components/charts/AnalyticsLineChart";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import StatCard from "../../components/shared/StatCard";
import { authSession, getErrorMessage } from "../../services/api";
import { parentService } from "../../services/parentService";
import { academicService } from "../../services/academicService";
import { reportCardService } from "../../services/reportCardService";
import { displayName } from "../../utils/user";
import {
  averageByAcademicPeriod,
  averageScore,
  bestAndWeakestSubject,
  chartFromCounts,
  cleanText,
  reportCardStatusChart,
  subjectPerformanceChart,
} from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";

function ParentDashboardPage() {
  const [children, setChildren] = useState([]);
  const [requests, setRequests] = useState([]);
  const [selectedChildId, setSelectedChildId] = useState("");
  const [childResults, setChildResults] = useState([]);
  const [childReportCards, setChildReportCards] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLinking, setIsLinking] = useState(false);
  const [admissionNumber, setAdmissionNumber] = useState("");
  const [relationshipType, setRelationshipType] = useState("guardian");
  const [loadError, setLoadError] = useState(null);
  const [linkError, setLinkError] = useState(null);
  const [linkSuccess, setLinkSuccess] = useState(null);
  const user = authSession.getUser();
  const firstName = user?.first_name || user?.firstname || "Parent";

  const loadDashboardData = async () => {
    const [studentsResponse, requestsResponse] = await Promise.all([
      parentService.getMyStudents(),
      parentService.getMyStudentLinkRequests(),
    ]);
    setChildren(studentsResponse?.items || []);
    setRequests(requestsResponse?.items || []);
    if (!selectedChildId && studentsResponse?.items?.[0]?.student?.id) {
      setSelectedChildId(studentsResponse.items[0].student.id);
    }
  };

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      setIsLoading(true);
      setLoadError(null);

      try {
        await loadDashboardData();
      } catch (error) {
        if (mounted) setLoadError(getErrorMessage(error, "Failed to load linked students."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadDashboard();

    return () => {
      mounted = false;
    };
  }, []);

  const handleLinkSubmit = async (event) => {
    event.preventDefault();
    const normalizedAdmissionNumber = admissionNumber.trim().toUpperCase();
    if (!normalizedAdmissionNumber) return;

    setIsLinking(true);
    setLinkError(null);
    setLinkSuccess(null);

    try {
      await parentService.createStudentLinkRequest({
        admission_number: normalizedAdmissionNumber,
        relationship_type: relationshipType,
      });
      await loadDashboardData();
      setAdmissionNumber("");
      setLinkSuccess(
        "Link request submitted. The student must approve it before you can view their dashboard."
      );
    } catch (error) {
      setLinkError(getErrorMessage(error, "Could not submit link request."));
    } finally {
      setIsLinking(false);
    }
  };

  const printReportCard = async (card) => {
    setLoadError(null);
    try {
      await reportCardService.printParentReportCard(selectedChildId, card.id);
    } catch (error) {
      setLoadError(getErrorMessage(error, "Could not open report card."));
    }
  };

  const selectedChildRecord = children.find((item) => item.student?.id === selectedChildId) || null;
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
  const recentResults = useMemo(() => childResults.slice(0, 4), [childResults]);
  const gradeBreakdown = useMemo(
    () => chartFromCounts(childResults, "grade", "ungraded"),
    [childResults]
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
      } catch {
        if (!mounted) return;
        setChildResults([]);
        setChildReportCards([]);
      }
    }

    loadChildAcademics();

    return () => {
      mounted = false;
    };
  }, [selectedChildId]);

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
      description="A parent overview built around the selected child, instead of stacking every family workflow onto one page."
    >
      {loadError && (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      )}

      {!loadError && (
        <>
          <Card className="p-5 sm:p-6">
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={children.length > 0 ? "success" : "warning"}>
                    {children.length > 0 ? "Linked children available" : "No linked children"}
                  </Badge>
                  <Badge variant="info">{selectedChildAcademicLabel}</Badge>
                </div>

                <h2 className="mt-3 text-xl font-semibold text-text sm:text-2xl">
                  Family overview for {selectedChildRecord ? displayName(selectedChildRecord.student) : firstName}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                  Switch the selected child here, then use the dashboard to track performance, report cards, and link activity.
                </p>

                {children.length > 0 ? (
                  <label className="mt-4 block">
                    <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-text-muted">
                      Selected child
                    </span>
                    <select
                      value={selectedChildId}
                      onChange={(event) => setSelectedChildId(event.target.value)}
                      className="min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm font-medium text-text outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
                    >
                      {children.map(({ student }) => (
                        <option key={student.id} value={student.id}>
                          {displayName(student)} / {student.admission_number}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <div className="mt-4 rounded-[1.25rem] border border-dashed border-border bg-surface-muted/15 px-4 py-4">
                    <p className="text-sm text-text-muted">
                      Add a student admission number to start tracking attendance, results, and report cards here.
                    </p>
                  </div>
                )}
              </div>

              <div className="grid gap-3">
                {children.length > 0 ? (
                  children.map(({ student, link }) => (
                    <div
                      key={link.id}
                      className={cn(
                        "rounded-[1.2rem] border px-4 py-3 transition",
                        student.id === selectedChildId
                          ? "border-primary/35 bg-primary-subtle"
                          : "border-border/70 bg-surface-muted/15"
                      )}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-text">
                            {displayName(student)}
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            {cleanText(student.admission_number)} / {cleanText(student.profile_status)}
                          </p>
                        </div>
                        <Badge variant={link.is_primary_contact ? "success" : "default"}>
                          {cleanText(link.relationship_type)}
                        </Badge>
                      </div>
                    </div>
                  ))
                ) : (
                  <EmptyState
                    icon={GraduationCap}
                    title="No linked students yet"
                    description="Submit a student admission number to request access. The student must approve it before the link becomes active."
                  />
                )}
              </div>
            </div>
          </Card>

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

          <section className="dashboard-grid xl:grid-cols-3">
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

          <section className="dashboard-grid lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
            <Card className="p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="section-title">Academic Snapshot</h3>
                  <p className="mt-1 text-sm text-text-muted">
                    A focused reading view for the selected child's latest results and report card.
                  </p>
                </div>
                {latestReportCard && (
                  <Badge variant="success">
                    {cleanText(latestReportCard.academic_term_name, "Latest term")}
                  </Badge>
                )}
              </div>

              {selectedChildRecord ? (
                <>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                        Admission number
                      </p>
                      <p className="mt-2 text-sm font-semibold text-text">
                        {cleanText(selectedChildRecord.student.admission_number)}
                      </p>
                    </div>
                    <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                        Profile status
                      </p>
                      <p className="mt-2 text-sm font-semibold text-text">
                        {cleanText(selectedChildRecord.student.profile_status)}
                      </p>
                    </div>
                    <div className="rounded-[1.15rem] border border-border/70 bg-surface-muted/20 px-4 py-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                        Relationship
                      </p>
                      <p className="mt-2 text-sm font-semibold text-text">
                        {cleanText(selectedChildRecord.link?.relationship_type)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 rounded-[1.25rem] border border-border/70 bg-surface-muted/15 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-text">Latest report card</p>
                      {latestReportCard ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => printReportCard(latestReportCard)}
                        >
                          Print or download
                        </Button>
                      ) : null}
                    </div>

                    {latestReportCard ? (
                      <div className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-[1rem] border border-border/60 bg-surface px-4 py-3">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Average</p>
                          <p className="mt-2 text-lg font-semibold text-text">
                            {cleanText(latestReportCard.average_score)}
                          </p>
                        </div>
                        <div className="rounded-[1rem] border border-border/60 bg-surface px-4 py-3">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Subjects</p>
                          <p className="mt-2 text-lg font-semibold text-text">
                            {latestReportCard.lines?.length || 0}
                          </p>
                        </div>
                        <div className="rounded-[1rem] border border-border/60 bg-surface px-4 py-3">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Position</p>
                          <p className="mt-2 text-lg font-semibold text-text">
                            {cleanText(latestReportCard.position, "-")}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <p className="mt-4 text-sm text-text-muted">
                        No report card available yet for this child.
                      </p>
                    )}
                  </div>

                  <div className="mt-5">
                    <div className="flex items-center justify-between gap-3">
                      <h4 className="text-sm font-semibold text-text">Recent subject results</h4>
                      <Badge variant="info">{recentResults.length} visible</Badge>
                    </div>

                    <div className="mt-3 grid gap-3">
                      {recentResults.length === 0 ? (
                        <p className="text-sm text-text-muted">No result available yet.</p>
                      ) : (
                        recentResults.map((result) => (
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
                                  Teacher: {cleanText(result.teacher_name)} / Total{" "}
                                  {cleanText(result.total_score)}
                                </p>
                              </div>
                              <Badge variant="success">{cleanText(result.grade)}</Badge>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <EmptyState
                  icon={GraduationCap}
                  title="Choose a child to begin"
                  description="Linked student records and report summaries will appear here after a child is selected."
                />
              )}
            </Card>

            <div className="grid gap-4">
              <Card className="p-5 sm:p-6">
                <h3 className="section-title">Link Student</h3>
                <p className="mt-1 text-sm text-text-muted">
                  Add another child without crowding the main academic view.
                </p>

                <form onSubmit={handleLinkSubmit} className="mt-4 space-y-3">
                  <label className="block">
                    <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-text-muted">
                      Admission number
                    </span>
                    <input
                      value={admissionNumber}
                      onChange={(event) => {
                        setAdmissionNumber(event.target.value);
                        setLinkError(null);
                        setLinkSuccess(null);
                      }}
                      placeholder="NHS-2026-12345"
                      className="min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm font-medium text-text outline-none transition placeholder:text-text-faint focus:border-primary focus:ring-4 focus:ring-primary/10"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-text-muted">
                      Relationship
                    </span>
                    <select
                      value={relationshipType}
                      onChange={(event) => setRelationshipType(event.target.value)}
                      className="min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm font-medium text-text outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
                    >
                      <option value="father">Father</option>
                      <option value="mother">Mother</option>
                      <option value="guardian">Guardian</option>
                      <option value="sponsor">Sponsor</option>
                      <option value="other">Other</option>
                    </select>
                  </label>

                  {linkError && <p className="text-sm font-medium text-error">{linkError}</p>}
                  {linkSuccess && <p className="text-sm font-medium text-success">{linkSuccess}</p>}

                  <Button type="submit" className="w-full" disabled={isLinking || !admissionNumber.trim()}>
                    <Link2 className="h-4 w-4" />
                    {isLinking ? "Submitting..." : "Request student link"}
                  </Button>
                </form>
              </Card>

              <Card className="p-5 sm:p-6">
                <h3 className="section-title">Request Status</h3>
                <p className="mt-1 text-sm text-text-muted">
                  Track approvals without mixing them into the child performance area.
                </p>

                <div className="mt-4 space-y-3">
                  {requests.length === 0 ? (
                    <p className="text-sm text-text-muted">No parent-student link requests yet.</p>
                  ) : (
                    requests.map((request) => (
                      <div
                        key={request.id}
                        className="rounded-[1.1rem] border border-border/70 bg-surface px-4 py-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-text">
                              {displayName(request.student)}
                            </p>
                            <p className="mt-1 text-xs text-text-muted">
                              {request.admission_number_snapshot ||
                                request.student?.admission_number ||
                                "No admission number"}
                            </p>
                          </div>
                          <Badge
                            variant={
                              request.status === "approved"
                                ? "success"
                                : request.status === "rejected"
                                  ? "error"
                                  : "warning"
                            }
                          >
                            {request.status}
                          </Badge>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </Card>

              <Card className="p-5 sm:p-6">
                <h3 className="section-title">Result Health</h3>
                <p className="mt-1 text-sm text-text-muted">
                  Quick grading signals for the selected child.
                </p>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1rem] border border-border/60 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Best subject</p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {subjectHighlights.best?.label || "Awaiting results"}
                    </p>
                  </div>
                  <div className="rounded-[1rem] border border-border/60 bg-surface-muted/20 px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Needs attention</p>
                    <p className="mt-2 text-sm font-semibold text-text">
                      {subjectHighlights.weakest?.label || "No weak area yet"}
                    </p>
                  </div>
                </div>

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
            </div>
          </section>
        </>
      )}
    </DashboardLayout>
  );
}

export default ParentDashboardPage;
