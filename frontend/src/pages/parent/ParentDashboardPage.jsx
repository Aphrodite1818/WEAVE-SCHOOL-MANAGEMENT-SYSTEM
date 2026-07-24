import { useEffect, useState } from "react";
import { BarChart3, Bell, FileText, GraduationCap, Link2, Users } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import {
  DashboardFocusCard,
  DashboardListCard,
  DashboardMetricCard,
  DashboardQuickActions,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import { academicService } from "../../services/academicService";
import { authSession, getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { getCachedDashboardBundle, getDashboardSessionCacheKey } from "../../services/dashboardSessionCache";
import { reportCardService } from "../../services/reportCardService";
import {
  averageScore,
  bestAndWeakestSubject,
  cleanText,
} from "../../utils/academicDashboard";
import { displayName } from "../../utils/user";
import ParentChildSelector from "./ParentChildSelector";
import { normalizeParentChildRecord } from "./parentPageUtils";
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
  const [parentMetrics, setParentMetrics] = useState(null);
  const [childResults, setChildResults] = useState([]);
  const [childReportCards, setChildReportCards] = useState([]);
  const [childAcademicsLoading, setChildAcademicsLoading] = useState(false);

  const childAverage = averageScore(childResults);
  const subjectHighlights = bestAndWeakestSubject(childResults);
  const latestReportCard = childReportCards[0] || null;
  const parentStats = parentMetrics?.stats || {};

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadParentMetrics() {
      try {
        const cacheKey = getDashboardSessionCacheKey("parent:dashboard:metrics");
        const data = await getCachedDashboardBundle(cacheKey, () =>
          dashboardService.getParentAnalytics({ signal: controller.signal }),
        );
        if (!mounted || controller.signal.aborted) return;
        setParentMetrics(data);
      } catch (error) {
        if (!mounted || isAbortError(error)) return;
        setParentMetrics(null);
      }
    }

    loadParentMetrics();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadChildAcademics() {
      if (!selectedChildId) {
        setChildAcademicsLoading(false);
        setChildResults([]);
        setChildReportCards([]);
        return;
      }

      setChildAcademicsLoading(true);

      try {
        const cacheKey = getDashboardSessionCacheKey(`parent:child:${selectedChildId}:academics`);
        const bundle = await getCachedDashboardBundle(cacheKey, async () => {
          const [resultResponse, reportCardResponse] = await Promise.all([
            academicService.listChildResults(selectedChildId, { signal: controller.signal }),
            reportCardService.listChildReportCards(selectedChildId, { signal: controller.signal }),
          ]);

          return {
            results: resultResponse?.items || [],
            reportCards: reportCardResponse?.items || [],
          };
        });

        if (!mounted || controller.signal.aborted) return;
        setChildResults(bundle.results);
        setChildReportCards(bundle.reportCards);
      } catch (error) {
        if (!mounted || isAbortError(error)) return;
        setChildResults([]);
        setChildReportCards([]);
        setLoadError(getErrorMessage(error, "Failed to load child academic summary."));
      } finally {
        if (mounted && !controller.signal.aborted) setChildAcademicsLoading(false);
      }
    }

    loadChildAcademics();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [selectedChildId, setLoadError]);

  if (isLoading || childAcademicsLoading) {
    return (
      <DashboardLayout role="parent" title={`${firstName}'s Portal`}>
        <LoadingState label="Loading parent dashboard..." />
      </DashboardLayout>
    );
  }

  const latestResult = childResults[0];
  const latestCard = childReportCards[0];
  const selectedChildAcademicLabel = [
    latestResult?.academic_session_name || latestCard?.academic_session_name,
    cleanText(latestResult?.academic_term_name || latestCard?.academic_term_name, ""),
  ].filter(Boolean).join(" / ") || "-";
  const selectedChild = normalizeParentChildRecord(selectedChildRecord).student;
  const selectedChildName = selectedChild ? displayName(selectedChild) : "No child selected";
  const linkedStudents = parentStats.linked_students ?? children.length;
  const primaryContacts = parentStats.primary_contacts ?? children.filter((item) => item.link?.is_primary_contact).length;
  const unreadNotices = parentStats.unread_count ?? 0;
  const hasChildResults = childResults.length > 0;
  const latestAverageValue = latestReportCard
    ? cleanText(latestReportCard.average_score)
    : hasChildResults
      ? cleanText(childAverage, "-")
      : "-";

  const attentionItems = [
    unreadNotices > 0
      ? {
          key: "unread-notices",
          title: "Unread school notices",
          description: `${unreadNotices} school update${unreadNotices === 1 ? "" : "s"} waiting for you.`,
          icon: Bell,
          tone: "primary",
          to: "/parent/notices",
          value: unreadNotices,
        }
      : null,
    !selectedChildId
      ? {
          key: "link-child",
          title: "No child selected",
          description: "Link or select a child to see academic information here.",
          icon: Link2,
          tone: "warning",
          to: "/parent/student-linking",
        }
      : null,
    selectedChildId && !latestReportCard
      ? {
          key: "no-report-card",
          title: "Report card not released yet",
          description: "Published report cards will appear once the school releases them.",
          icon: FileText,
          tone: "neutral",
          to: "/parent/report-cards",
        }
      : null,
  ].filter(Boolean);

  return (
    <DashboardLayout role="parent" title={`${firstName}'s Portal`}>
      {loadError ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {loadError}
        </div>
      ) : null}

      {!loadError ? (
        <>
          <DashboardWelcomePanel
            variant="blue"
            eyebrow="Parent dashboard"
            title={`Welcome, ${firstName}`}
            description="Your child's progress, school updates, and next actions."
            profileCompletion={user?.profile_completed}
            chips={[
              { label: "Viewing", value: selectedChildName, tone: selectedChildRecord ? "primary" : "warning" },
              { label: selectedChildAcademicLabel, tone: selectedChildAcademicLabel !== "-" ? "success" : "neutral" },
            ]}
          >
            <ParentChildSelector
              linkedChildren={children}
              selectedChildId={selectedChildId}
              onSelectChild={setSelectedChildId}
              academicLabel={selectedChildAcademicLabel}
            />
          </DashboardWelcomePanel>

          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <DashboardMetricCard
              label="Linked children"
              value={linkedStudents}
              description={`${primaryContacts} primary contact${primaryContacts === 1 ? "" : "s"}`}
              icon={Users}
              tone={linkedStudents > 0 ? "primary" : "warning"}
              to="/parent/student-linking"
            />
            <DashboardMetricCard
              label="Latest average"
              value={latestAverageValue}
              description="Selected child"
              icon={BarChart3}
              tone={hasChildResults || latestReportCard ? "success" : "warning"}
              to="/parent/results"
            />
            <DashboardMetricCard
              label="Report cards"
              value={childReportCards.length}
              description={latestReportCard ? cleanText(latestReportCard.academic_term_name, "Latest term") : "Awaiting release"}
              icon={FileText}
              tone={childReportCards.length > 0 ? "success" : "warning"}
              to="/parent/report-cards"
            />
            <DashboardMetricCard
              label="Unread notices"
              value={unreadNotices}
              description="School updates"
              icon={Bell}
              tone={unreadNotices > 0 ? "warning" : "success"}
              to="/parent/notices"
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
            <DashboardFocusCard
              title="Your child this week"
              description="A quick view of the selected child's academics."
              icon={GraduationCap}
              tone="primary"
              primaryAction={{ to: "/parent/results", label: "View results", icon: BarChart3, disabled: !selectedChildId }}
              secondaryAction={{ to: "/parent/report-cards", label: "Report cards", icon: FileText, disabled: !selectedChildId }}
            >
              <div className="grid grid-cols-2 gap-3">
                <InfoTile label="Selected child" value={selectedChildName} />
                <InfoTile label="Latest average" value={latestAverageValue} />
                <InfoTile label="Strongest subject" value={subjectHighlights.best?.label || "Awaiting results"} />
                <InfoTile label="Needs support" value={subjectHighlights.weakest?.label || "No weak spot yet"} />
              </div>
            </DashboardFocusCard>

            <DashboardListCard
              title="Needs attention"
              description="Parent tasks or updates that need a quick look."
              items={attentionItems}
              emptyTitle="Everything looks calm"
              emptyDescription="No unread notices, linking issues, or report-card actions need attention right now."
            />
          </section>

          <DashboardQuickActions
            title="Family actions"
            description="Common parent workflows."
            actions={[
              { label: "Student linking", description: "Request or manage child access", to: "/parent/student-linking", icon: Link2, tone: "primary" },
              { label: "Results", description: "View academic scores", to: "/parent/results", icon: BarChart3, tone: "success" },
              { label: "Report cards", description: "Open published reports", to: "/parent/report-cards", icon: FileText, tone: "warning" },
              { label: "Notices", description: "School updates", to: "/parent/notices", icon: Bell, tone: "accent" },
            ]}
          />
        </>
      ) : null}
    </DashboardLayout>
  );
}

function InfoTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-surface-muted/20 px-3 py-3 sm:px-4">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted sm:text-[11px]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

export default ParentDashboardPage;
