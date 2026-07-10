import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  ClipboardList,
  FileSearch,
  FileText,
  GraduationCap,
  Layers3,
  Library,
  Pencil,
  Settings2,
  Users,
} from "lucide-react";

import Card from "../../components/ui/Card";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import {
  DashboardListCard,
  DashboardMetricCard,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import { getCachedDashboardBundle, getDashboardSessionCacheKey } from "../../services/dashboardSessionCache";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";

const ACADEMIC_HUB_CACHE_KEY = getDashboardSessionCacheKey("admin:academic-hub-overview");

const metricNumber = (value, fallback = 0) => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

const workflowCards = [
  {
    key: "setup",
    title: "Academic setup",
    description: "Create sessions, terms, grading scales, and subjects.",
    to: "/admin/academic/setup",
    icon: BookOpen,
    tone: "primary",
    meta: "Session • Term • Grades",
  },
  {
    key: "class-subjects",
    title: "Classes & subjects",
    description: "Review classes, subjects, and the subjects attached to each class.",
    to: "/admin/academic/class-subjects",
    icon: Layers3,
    tone: "success",
    meta: "Classes • Subjects",
  },
  {
    key: "assignments",
    title: "Teacher assignments",
    description: "Assign teachers to class-subjects and review existing assignments.",
    to: "/admin/academic/assignments",
    icon: Users,
    tone: "warning",
    meta: "Assign • Review",
  },
  {
    key: "results",
    title: "Results",
    description: "Record, correct, submit, and reopen student scores.",
    to: "/admin/academic/results",
    icon: Pencil,
    tone: "accent",
    meta: "Scores • Drafts",
  },
  {
    key: "report-cards",
    title: "Report cards",
    description: "Generate, review, publish, and search report cards.",
    to: "/admin/academic/report-cards",
    icon: FileText,
    tone: "primary",
    meta: "Generate • Publish",
  },
  {
    key: "search",
    title: "Academic search",
    description: "Find students, report cards, and academic records quickly.",
    to: "/admin/academic/search",
    icon: FileSearch,
    tone: "success",
    meta: "Search records",
  },
];

const supportCards = [
  {
    key: "full-workbench",
    title: "Full workbench",
    description: "Open the original all-in-one academic workspace when you need every form on one page.",
    to: "/admin/academic/manage",
    icon: ClipboardList,
    tone: "neutral",
  },
  {
    key: "analytics",
    title: "Academic analytics",
    description: "View deeper result, class, grade, and report-card charts.",
    to: "/admin/analytics",
    icon: BarChart3,
    tone: "primary",
  },
  {
    key: "students",
    title: "Student records",
    description: "Open academic profiles and student account records.",
    to: "/admin/students",
    icon: GraduationCap,
    tone: "accent",
  },
];

const toneStyles = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-amber-950",
  accent: "bg-accent-soft text-accent",
  neutral: "bg-surface-muted text-text-muted",
};

function AcademicHubOverviewPage() {
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    async function loadOverview() {
      try {
        const data = await getCachedDashboardBundle(ACADEMIC_HUB_CACHE_KEY, () =>
          dashboardService.getTenantAdminAnalytics({ signal: controller.signal }),
        );
        if (!mounted || controller.signal.aborted) return;
        setAnalytics(data);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setError(getErrorMessage(err, "Failed to load academic hub overview."));
      }
    }

    loadOverview();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  if (!analytics && !error) {
    return (
      <DashboardLayout role="admin" title="Academic Hub">
        <LoadingState label="Loading academic hub..." />
      </DashboardLayout>
    );
  }

  const stats = analytics?.stats || {};
  const resultCompletion = metricNumber(stats.result_completion_percent);
  const reportCardsPublished = metricNumber(stats.report_cards_published);
  const reportCardsGenerated = metricNumber(stats.report_cards_generated);
  const incompleteProfiles = metricNumber(stats.student_profiles_incomplete);
  const needsSetup = !stats.active_academic_session || !stats.active_academic_term;

  const attentionItems = [
    needsSetup
      ? {
          key: "setup",
          title: "Academic period needs setup",
          description: "Set the active session and term before recording results.",
          icon: BookOpen,
          tone: "warning",
          to: "/admin/academic/setup",
        }
      : null,
    incompleteProfiles > 0
      ? {
          key: "profiles",
          title: "Incomplete student profiles",
          description: `${incompleteProfiles} student profile${incompleteProfiles === 1 ? "" : "s"} need updates.`,
          icon: GraduationCap,
          tone: "warning",
          to: "/admin/students",
          value: incompleteProfiles,
        }
      : null,
    reportCardsGenerated > reportCardsPublished
      ? {
          key: "reports",
          title: "Report cards pending publication",
          description: `${reportCardsPublished} published from ${reportCardsGenerated} generated.`,
          icon: FileText,
          tone: "warning",
          to: "/admin/academic/report-cards",
        }
      : null,
  ].filter(Boolean);

  return (
    <DashboardLayout
      role="admin"
      title="Academic Hub"
      description="A workflow-first academic hub for setup, subjects, assignments, results, report cards, and search."
    >
      {error ? (
        <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
          {error}
        </div>
      ) : null}

      {!error ? (
        <>
          <DashboardWelcomePanel
            eyebrow="Academic operations"
            title="Choose the academic workflow you want to manage"
            description="The hub now starts with clear route cards. Pick a workflow, use the focused switcher, then return here when you are done."
            chips={[
              { label: "Session", value: cleanText(stats.active_academic_session, "Not set"), tone: stats.active_academic_session ? "success" : "warning" },
              { label: "Term", value: cleanText(stats.active_academic_term, "Not set"), tone: stats.active_academic_term ? "primary" : "warning" },
            ]}
          />

          <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <DashboardMetricCard
              label="Students"
              value={metricNumber(stats.total_students)}
              description="Learners attached to this school"
              icon={GraduationCap}
              tone="primary"
              to="/admin/students"
            />
            <DashboardMetricCard
              label="Subjects"
              value={metricNumber(stats.total_subjects)}
              description="Catalog items available"
              icon={BookOpen}
              tone="success"
              to="/admin/academic/class-subjects"
            />
            <DashboardMetricCard
              label="Result completion"
              value={`${resultCompletion}%`}
              description="Submitted result rows"
              icon={BarChart3}
              tone={resultCompletion >= 80 ? "success" : resultCompletion > 0 ? "warning" : "neutral"}
              to="/admin/academic/results"
            />
            <DashboardMetricCard
              label="Report cards"
              value={reportCardsPublished}
              description={`${reportCardsGenerated} generated`}
              icon={FileText}
              tone={reportCardsGenerated > reportCardsPublished ? "warning" : "success"}
              to="/admin/academic/report-cards"
            />
          </section>

          <section className="space-y-4">
            <div>
              <h2 className="section-title">Academic workflows</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                These cards are actions. Each one opens a focused page with a smaller switcher instead of one long crowded workspace.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 2xl:grid-cols-6">
              {workflowCards.map((card) => <HubRouteCard key={card.key} {...card} />)}
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
            <Card className="p-4 sm:p-6">
              <div className="flex items-start gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                  <Settings2 className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <h2 className="section-title">Helpful admin shortcuts</h2>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    Use these when you need the old workbench, analytics, or student profile records.
                  </p>
                </div>
              </div>
              <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
                {supportCards.map((card) => <SupportRouteCard key={card.key} {...card} />)}
              </div>
            </Card>

            <DashboardListCard
              title="Needs attention"
              description="Academic blockers and follow-ups stay visible here."
              items={attentionItems}
              emptyTitle="Academic setup looks calm"
              emptyDescription="No active setup, profile, or report-card issue is showing right now."
            />
          </section>
        </>
      ) : null}
    </DashboardLayout>
  );
}

function HubRouteCard({ to, icon: Icon, title, description, meta, tone = "primary" }) {
  return (
    <Link
      to={to}
      className="group flex min-h-[10.5rem] flex-col rounded-2xl border border-border/70 bg-surface p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:bg-primary-subtle/20 hover:shadow-premium sm:min-h-[12rem] sm:p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl sm:h-11 sm:w-11", toneStyles[tone] || toneStyles.primary)}>
          <Icon className="h-5 w-5" />
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-text-faint transition group-hover:translate-x-0.5 group-hover:text-primary" />
      </div>
      <div className="mt-4 min-w-0">
        <p className="text-sm font-semibold leading-5 text-text sm:text-base">{title}</p>
        <p className="mt-2 line-clamp-3 text-xs leading-5 text-text-muted sm:text-sm sm:leading-6">{description}</p>
      </div>
      {meta ? (
        <span className="mt-auto pt-4 text-[10px] font-bold uppercase tracking-wide text-primary sm:text-[11px]">
          {meta}
        </span>
      ) : null}
    </Link>
  );
}

function SupportRouteCard({ to, icon: Icon, title, description, tone = "neutral" }) {
  return (
    <Link
      to={to}
      className="group rounded-2xl border border-border/70 bg-surface-muted/20 p-3 transition hover:border-primary/30 hover:bg-primary-subtle/20 hover:shadow-sm"
    >
      <div className="flex items-start gap-3">
        <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl", toneStyles[tone] || toneStyles.neutral)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text">{title}</p>
          <p className="mt-1 line-clamp-3 text-xs leading-5 text-text-muted">{description}</p>
        </div>
      </div>
    </Link>
  );
}

export default AcademicHubOverviewPage;
