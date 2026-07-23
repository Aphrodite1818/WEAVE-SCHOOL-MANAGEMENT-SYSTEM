import { ArrowLeft, ChevronRight } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Card from "../../components/ui/Card";
import { cn } from "../../utils/cn";
import {
  academicToneStyles,
  academicWorkflowConfig,
  academicWorkflowOrder,
} from "./academicWorkflowConfig";

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
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = normalizeTab(workflow, searchParams.get("tab"));
  const Icon = config.icon;

  const selectTab = (tabId) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tabId);
    setSearchParams(next, { replace: true });
  };

  return (
    <DashboardLayout
      role="admin"
      title={config.title}
      description={config.description}
      actions={actions}
    >
      <section className="grid gap-4 xl:grid-cols-[15.5rem_minmax(0,1fr)]">
        <Card className="h-fit overflow-hidden p-3 xl:sticky xl:top-24">
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
                    "flex min-h-11 items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
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
                    <Badge variant={currentSession ? "success" : "warning"}>
                      Session: {currentSession?.name || "Not configured"}
                    </Badge>
                    <Badge variant={currentTerm ? "primary" : "warning"}>
                      Term: {currentTerm?.display_name || currentTerm?.name || "Not configured"}
                    </Badge>
                    {loading ? <Badge variant="default">Refreshing</Badge> : null}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <div className="overflow-x-auto pb-1">
            <div className="inline-flex min-w-full gap-2 rounded-2xl border border-border/70 bg-surface-muted/30 p-1 sm:min-w-0">
              {config.tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => selectTab(tab.id)}
                  className={cn(
                    "min-h-11 flex-1 whitespace-nowrap rounded-xl px-4 py-2 text-sm font-semibold transition sm:flex-none",
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

          {children(activeTab)}
        </div>
      </section>
    </DashboardLayout>
  );
}

export default AcademicWorkflowShell;
