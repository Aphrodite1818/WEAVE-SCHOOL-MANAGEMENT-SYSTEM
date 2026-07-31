import { ArrowLeft, ChevronRight } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import { cn } from "../../utils/cn";
import {
  AcademicLifecycleStepper,
  AcademicStatusBadge,
} from "./AcademicWorkspacePrimitives";
import {
  academicToneStyles,
  academicWorkflowConfig,
  academicWorkflowOrder,
} from "./academicWorkflowConfig";

const lifecycleSteps = [
  { id: "draft", label: "Draft", helper: "Setup can still change before school work starts." },
  { id: "open", label: "Open", helper: "This period is active for normal academic work." },
  { id: "closing", label: "Closing", helper: "Final checks are being completed before closure." },
  { id: "closed", label: "Closed", helper: "This period is read-only for history and reports." },
];

const normalizeTab = (workflow, tab) => {
  const config = academicWorkflowConfig[workflow];
  if (!config) return "";
  return config.tabs.some((item) => item.id === tab)
    ? tab
    : config.defaultTab;
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
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = normalizeTab(
    workflow,
    searchParams.get("view") || searchParams.get("tab"),
  );
  const Icon = config.icon;

  const selectTab = (tabId) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", tabId);
    next.delete("tab");
    setSearchParams(next, { replace: true });
  };

  const selectWorkflow = (nextWorkflow) => {
    if (!nextWorkflow || nextWorkflow === workflow) return;
    navigate(`/admin/academic/${nextWorkflow}`);
  };

  return (
    <DashboardLayout
      role="admin"
      title={config.title}
      description={config.description}
      actions={actions}
    >
      <section className="grid gap-4 xl:grid-cols-[14.25rem_minmax(0,1fr)]">
        <Card className="h-fit overflow-hidden p-3 max-xl:hidden xl:sticky xl:top-24">
          <Link
            to="/admin/academic"
            className="mb-3 flex min-h-10 items-center gap-2 rounded-xl px-3 text-sm font-semibold text-primary transition hover:bg-primary-subtle/40"
          >
            <ArrowLeft className="h-4 w-4" />
            Academic Hub
          </Link>

          <div className="space-y-1">
            {academicWorkflowOrder.map((key) => {
              const item = academicWorkflowConfig[key];
              const ItemIcon = item.icon;
              const active = key === workflow;

              return (
                <Link
                  key={key}
                  to={`/admin/academic/${key}`}
                  className={cn(
                    "flex min-h-10 items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-semibold transition",
                    active
                      ? "bg-primary text-white shadow-sm"
                      : "text-text-muted hover:bg-surface-muted hover:text-text",
                  )}
                >
                  <ItemIcon className="h-4 w-4 shrink-0" />
                  <span className="min-w-0 flex-1 truncate">{item.shortTitle}</span>
                  {active ? <ChevronRight className="h-4 w-4" /> : null}
                </Link>
              );
            })}
          </div>
        </Card>

        <div className="min-w-0 space-y-4">
          <Card className="p-3 xl:hidden">
            <Link
              to="/admin/academic"
              className="mb-3 inline-flex min-h-9 items-center gap-2 rounded-lg px-2 text-sm font-semibold text-primary"
            >
              <ArrowLeft className="h-4 w-4" />
              Academic Hub
            </Link>
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-text-soft">
                Workspace
              </span>
              <select
                value={workflow}
                onChange={(event) => selectWorkflow(event.target.value)}
                className="input-base"
              >
                {academicWorkflowOrder.map((key) => {
                  const item = academicWorkflowConfig[key];
                  return (
                    <option key={key} value={key}>
                      {item.title}
                    </option>
                  );
                })}
              </select>
            </label>
          </Card>

          <Card className="overflow-hidden p-4 sm:p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <div
                  className={cn(
                    "flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl",
                    academicToneStyles[config.tone] || academicToneStyles.primary,
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-xl font-semibold text-text sm:text-2xl">
                    {config.title}
                  </h2>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-text-muted">
                    {config.description}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <AcademicStatusBadge
                      label="Session"
                      status={currentSession?.status || (currentSession ? "ready" : "not configured")}
                      helper={currentSession?.name || ""}
                    />
                    <AcademicStatusBadge
                      label="Term"
                      status={currentTerm?.status || (currentTerm ? "ready" : "not configured")}
                      helper={currentTerm?.display_name || currentTerm?.name || ""}
                    />
                    {loading ? <Badge variant="default">Refreshing</Badge> : null}
                  </div>
                </div>
              </div>
            </div>
            {["sessions", "terms"].includes(workflow) ? (
              <div className="mt-4">
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
          </Card>

          {config.tabs.length > 1 ? (
            <div className="pb-1">
              <div className="grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:inline-flex sm:min-w-0">
                {config.tabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => selectTab(tab.id)}
                    className={cn(
                      "min-h-11 rounded-xl px-3 py-2 text-sm font-semibold transition sm:flex-none sm:px-4",
                      activeTab === tab.id
                        ? "bg-surface text-primary shadow-sm"
                        : "text-text-muted hover:bg-surface/60 hover:text-text",
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {children(activeTab)}
        </div>
      </section>
    </DashboardLayout>
  );
}

export default AcademicWorkflowShell;
