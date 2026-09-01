import { ArrowLeft, RefreshCw } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import { cn } from "../../utils/cn";
import AcademicOrbitNavigator from "./AcademicOrbitNavigator";
import {
  AcademicLifecycleStepper,
  AcademicStatusBadge,
} from "./AcademicWorkspacePrimitives";
import { academicWorkflowConfig } from "./academicWorkflowConfig";

const lifecycleSteps = [
  {
    id: "draft",
    label: "Draft",
    helper: "Setup can still change before school work starts.",
  },
  {
    id: "open",
    label: "Open",
    helper: "This period is active for normal academic work.",
  },
  {
    id: "closing",
    label: "Closing",
    helper: "Final checks are being completed before closure.",
  },
  {
    id: "closed",
    label: "Closed",
    helper: "This period is read-only for history and reports.",
  },
];

const normalizeTab = (workflow, tab) => {
  const config = academicWorkflowConfig[workflow];
  if (!config) return "";
  return config.tabs.some((item) => item.id === tab) ? tab : config.defaultTab;
};

function AcademicWorkflowShell({
  workflow,
  children,
  currentSession,
  currentTerm,
  loading = false,
  actions,
}) {
  const config = academicWorkflowConfig[workflow];
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = normalizeTab(
    workflow,
    searchParams.get("view") || searchParams.get("tab"),
  );

  const selectTab = (tabId) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", tabId);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  return (
    <DashboardLayout
      role="admin"
      title={config.title}
      description={config.description}
      actions={actions}
    >
      <section className="min-w-0 space-y-4">
        <div className="flex flex-col gap-3 border-b border-border/70 pb-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
            <Link
              to="/admin/academic"
              className="inline-flex min-h-9 items-center gap-2 rounded-lg pr-2 text-sm font-semibold text-primary transition hover:text-primary-hover"
            >
              <ArrowLeft className="h-4 w-4" />
              Academic Hub
            </Link>
            <span className="hidden h-5 w-px bg-border sm:block" />
            <AcademicStatusBadge
              label="Session"
              status={
                currentSession?.status ||
                (currentSession ? "ready" : "not configured")
              }
              helper={currentSession?.name || ""}
            />
            <AcademicStatusBadge
              label="Term"
              status={
                currentTerm?.status ||
                (currentTerm ? "ready" : "not configured")
              }
              helper={currentTerm?.display_name || currentTerm?.name || ""}
            />
          </div>
          {loading ? (
            <Badge variant="default">
              <RefreshCw className="mr-1 h-3.5 w-3.5 animate-spin" />
              Refreshing
            </Badge>
          ) : null}
        </div>

        {["sessions", "terms"].includes(workflow) ? (
          <div className="rounded-xl border border-border/70 bg-surface px-3 py-3">
            <AcademicLifecycleStepper
              steps={lifecycleSteps}
              current={
                workflow === "sessions"
                  ? currentSession?.status || "draft"
                  : currentTerm?.status || "draft"
              }
            />
          </div>
        ) : null}

        {config.tabs.length > 1 ? (
          <div
            data-academic-workflow-switcher="true"
            className="overflow-x-auto border-b border-border/70"
          >
            <div className="flex min-w-max gap-5 px-1">
              {config.tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => selectTab(tab.id)}
                  className={cn(
                    "relative min-h-11 whitespace-nowrap px-1 pb-3 pt-1 text-sm font-semibold transition",
                    activeTab === tab.id
                      ? "text-primary after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full after:bg-primary"
                      : "text-text-muted hover:text-text",
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {children(activeTab)}
      </section>
      <AcademicOrbitNavigator currentWorkflow={workflow} />
    </DashboardLayout>
  );
}

export default AcademicWorkflowShell;
