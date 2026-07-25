import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle2,
  FileSearch,
  FileText,
  GraduationCap,
  Layers3,
  Pencil,
  Users,
} from "lucide-react";

import {
  DashboardListCard,
  DashboardMetricCard,
  DashboardWelcomePanel,
} from "../../components/dashboard/DashboardPrimitives";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import { isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import {
  getCachedDashboardBundle,
  getDashboardSessionCacheKey,
} from "../../services/dashboardSessionCache";
import { cleanText } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";

const ACADEMIC_HUB_CACHE_KEY = getDashboardSessionCacheKey(
  "admin:academic-hub-overview",
);

const metricNumber = (value, fallback = "-") => {
  const nextValue = Number(value);
  return Number.isFinite(nextValue) ? nextValue : fallback;
};

const workflowGroups = [
  {
    key: "foundation",
    eyebrow: "1. Foundation",
    title: "Build the academic structure",
    description:
      "Set the active academic period, grading rules, classes, and subject offerings before operational work begins.",
    tone: "primary",
    items: [
      {
        title: "Academic Setup",
        description: "Sessions, terms, grading scales, and the subject catalog.",
        to: "/admin/academic/setup",
        icon: BookOpen,
      },
      {
        title: "Class Structure",
        description: "Classes, class teachers, progression visibility, and offered subjects.",
        to: "/admin/academic/class-subjects",
        icon: Layers3,
      },
    ],
  },
  {
    key: "teaching",
    eyebrow: "2. Teaching",
    title: "Connect teachers to subjects",
    description:
      "Assign active teacher memberships to the class-subject records they are permitted to teach and score.",
    tone: "warning",
    items: [
      {
        title: "Teacher Assignments",
        description: "Create, reassign, activate, or end class-subject assignments.",
        to: "/admin/academic/assignments",
        icon: Users,
      },
    ],
  },
  {
    key: "assessment",
    eyebrow: "3. Assessment",
    title: "Record and publish academic performance",
    description:
      "Enter validated scores, submit complete results, generate report cards, and publish final records.",
    tone: "accent",
    items: [
      {
        title: "Results Management",
        description: "Score entry, draft review, submission, correction, and reopening.",
        to: "/admin/academic/results",
        icon: Pencil,
      },
      {
        title: "Report Cards",
        description: "Readiness review, generation, regeneration, and publication.",
        to: "/admin/academic/report-cards",
        icon: FileText,
      },
    ],
  },
  {
    key: "records",
    eyebrow: "4. Records",
    title: "Find academic information quickly",
    description:
      "Search school records without moving through every workflow manually.",
    tone: "success",
    items: [
      {
        title: "Academic Search",
        description: "Find students, classes, subjects, report cards, and related records.",
        to: "/admin/academic/search",
        icon: FileSearch,
      },
    ],
  },
];

const toneStyles = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-amber-900",
  accent: "bg-accent-soft text-accent",
};

function scheduleBackgroundTask(callback) {
  if (typeof window === "undefined") return undefined;
  if (typeof window.requestIdleCallback === "function") {
    const id = window.requestIdleCallback(callback, { timeout: 1200 });
    return () => window.cancelIdleCallback(id);
  }
  const id = window.setTimeout(callback, 250);
  return () => window.clearTimeout(id);
}

function AcademicHubOverviewPage() {
  const [analytics, setAnalytics] = useState(null);
  const [isMetricsRefreshing, setIsMetricsRefreshing] = useState(false);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();

    const cancelIdleTask = scheduleBackgroundTask(async () => {
      if (!mounted) return;
      setIsMetricsRefreshing(true);
      try {
        const data = await getCachedDashboardBundle(ACADEMIC_HUB_CACHE_KEY, () =>
          dashboardService.getTenantAdminAnalytics({ signal: controller.signal }),
        );
        if (!mounted || controller.signal.aborted) return;
        setAnalytics(data);
      } catch (err) {
        if (!mounted || isAbortError(err)) return;
        setAnalytics(null);
      } finally {
        if (mounted) setIsMetricsRefreshing(false);
      }
    });

    return () => {
      mounted = false;
      controller.abort();
      if (typeof cancelIdleTask === "function") cancelIdleTask();
    };
  }, []);

  const stats = analytics?.stats || {};
  const hasMetrics = Boolean(analytics?.stats);
  const resultCompletion = metricNumber(stats.result_completion_percent);
  const reportCardsPublished = metricNumber(stats.report_cards_published);
  const reportCardsGenerated = metricNumber(stats.report_cards_generated);
  const incompleteProfiles = Number(stats.student_profiles_incomplete || 0);
  const needsSetup =
    hasMetrics &&
    (!stats.active_academic_session || !stats.active_academic_term);

  const attentionItems = [
    needsSetup
      ? {
          key: "setup",
          title: "Academic period needs setup",
          description:
            "Open an academic session and set the current term before recording results.",
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
    Number(reportCardsGenerated) > Number(reportCardsPublished)
      ? {
          key: "reports",
          title: "Report cards pending publication",
          description: `${reportCardsPublished} published from ${reportCardsGenerated} generated.`,
          icon: FileText,
          tone: "warning",
          to: "/admin/academic/report-cards?tab=publish",
        }
      : null,
  ].filter(Boolean);

  return (
    <DashboardLayout
      role="admin"
      title="Academic Hub"
      description="Manage the complete academic lifecycle in a clear operational sequence."
    >
      <DashboardWelcomePanel
        eyebrow="Academic operations"
        title="Move from setup to published records without losing context"
        description="Each workflow is now independent, URL-addressable, and designed for desktop and installed mobile PWA use."
        chips={[
          {
            label: "Session",
            value: cleanText(
              stats.active_academic_session,
              hasMetrics ? "Not set" : "Loading",
            ),
            tone: stats.active_academic_session ? "success" : "warning",
          },
          {
            label: "Term",
            value: cleanText(
              stats.active_academic_term,
              hasMetrics ? "Not set" : "Loading",
            ),
            tone: stats.active_academic_term ? "primary" : "warning",
          },
          isMetricsRefreshing
            ? { label: "Metrics", value: "Refreshing", tone: "primary" }
            : null,
        ].filter(Boolean)}
      />

      <section className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <DashboardMetricCard
          label="Students"
          value={metricNumber(stats.total_students)}
          description="Active learner records"
          icon={GraduationCap}
          tone="primary"
          to="/admin/students"
        />
        <DashboardMetricCard
          label="Subjects"
          value={metricNumber(stats.total_subjects)}
          description="Tenant-scoped catalog items"
          icon={BookOpen}
          tone="success"
          to="/admin/academic/setup?tab=subjects"
        />
        <DashboardMetricCard
          label="Result completion"
          value={
            Number.isFinite(Number(resultCompletion))
              ? `${resultCompletion}%`
              : "-"
          }
          description="Submitted result rows"
          icon={BarChart3}
          tone={
            Number(resultCompletion) >= 80
              ? "success"
              : Number(resultCompletion) > 0
                ? "warning"
                : "neutral"
          }
          to="/admin/academic/results?tab=submitted"
        />
        <DashboardMetricCard
          label="Report cards"
          value={reportCardsPublished}
          description={
            hasMetrics ? `${reportCardsGenerated} generated` : "Published records"
          }
          icon={FileText}
          tone={
            Number(reportCardsGenerated) > Number(reportCardsPublished)
              ? "warning"
              : "success"
          }
          to="/admin/academic/report-cards?tab=publish"
        />
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="section-title">Academic operating flow</h2>
          <p className="mt-1 text-sm leading-6 text-text-muted">
            Follow the sequence for first-time setup, or open any module directly for daily operations.
          </p>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {workflowGroups.map((group) => (
            <WorkflowGroup key={group.key} {...group} />
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.72fr)]">
        <Card className="p-4 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-success-soft text-success">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <h2 className="section-title">Recommended setup order</h2>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                These dependencies prevent empty selectors and invalid academic records.
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {[
              "Create and open an academic session",
              "Create the current academic term",
              "Create grading scales and subjects",
              "Create classes and attach subjects",
              "Invite teachers and assign memberships",
              "Create students with class enrollment",
              "Enter and submit complete results",
              "Generate and publish report cards",
            ].map((step, index) => (
              <div
                key={step}
                className="flex items-start gap-3 rounded-2xl border border-border/70 bg-surface-muted/20 px-4 py-3"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-white">
                  {index + 1}
                </span>
                <p className="text-sm leading-6 text-text-soft">{step}</p>
              </div>
            ))}
          </div>
        </Card>

        <DashboardListCard
          title="Needs attention"
          description={
            hasMetrics
              ? "Academic blockers and follow-ups stay visible here."
              : "Metrics refresh quietly while workflows remain usable."
          }
          items={attentionItems}
          emptyTitle={
            hasMetrics ? "Academic operations look ready" : "Open a workflow now"
          }
          emptyDescription={
            hasMetrics
              ? "No active setup, profile, or publication issue is currently showing."
              : "You do not need to wait for metrics before using the Academic Hub."
          }
        />
      </section>
    </DashboardLayout>
  );
}

function WorkflowGroup({ eyebrow, title, description, items, tone }) {
  return (
    <Card className="flex h-full flex-col p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={tone === "accent" ? "accent" : tone}>{eyebrow}</Badge>
      </div>
      <h3 className="mt-3 text-lg font-semibold text-text">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
      <div className="mt-4 grid flex-1 gap-3 sm:grid-cols-2">
        {items.map((item) => (
          <WorkflowLink key={item.to} {...item} tone={tone} />
        ))}
      </div>
    </Card>
  );
}

function WorkflowLink({ to, icon: Icon, title, description, tone }) {
  return (
    <Link
      to={to}
      className="group flex min-h-[9.5rem] flex-col rounded-2xl border border-border/70 bg-surface px-4 py-4 transition hover:-translate-y-0.5 hover:border-primary/30 hover:bg-primary-subtle/20 hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-3">
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl",
            toneStyles[tone] || toneStyles.primary,
          )}
        >
          <Icon className="h-5 w-5" />
        </span>
        <ArrowRight className="h-4 w-4 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-primary" />
      </div>
      <p className="mt-4 font-semibold text-text">{title}</p>
      <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
    </Link>
  );
}

export default AcademicHubOverviewPage;
