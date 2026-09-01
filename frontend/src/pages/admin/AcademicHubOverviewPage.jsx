import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import {
  buildAcademicHubDirectory,
  filterAcademicHubDirectory,
} from "../../features/academic-admin/academicHubDirectory";
import {
  academicToneStyles,
  academicWorkflowConfig,
  academicWorkflowOrder,
} from "../../features/academic-admin/academicWorkflowConfig";
import { getErrorMessage, isAbortError } from "../../services/api";
import { dashboardService } from "../../services/dashboard.service";
import {
  getCachedDashboardBundle,
  getDashboardSessionCacheKey,
} from "../../services/dashboardSessionCache";
import { cn } from "../../utils/cn";

const ACADEMIC_HUB_CACHE_KEY = getDashboardSessionCacheKey(
  "admin:academic-hub-overview",
);

const statusVariant = (status) => {
  const value = String(status || "").toLowerCase();
  if (["operational", "ready", "available", "open"].includes(value)) return "success";
  if (value.includes("needs")) return "warning";
  return "default";
};

function AcademicHubOverviewPage() {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [metricsError, setMetricsError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();
    getCachedDashboardBundle(ACADEMIC_HUB_CACHE_KEY, () =>
      dashboardService.getTenantAdminAnalytics({ signal: controller.signal }),
    )
      .then((data) => {
        if (mounted) setAnalytics(data);
      })
      .catch((error) => {
        if (mounted && !isAbortError(error)) {
          setMetricsError(getErrorMessage(error, "Live academic counts are unavailable."));
        }
      });
    return () => {
      mounted = false;
      controller.abort();
    };
  }, []);

  const rows = useMemo(() => {
    const configRows = new Map(
      academicWorkflowOrder.map((key) => [key, { key, ...academicWorkflowConfig[key] }]),
    );
    const directory = buildAcademicHubDirectory(analytics?.stats || {}).map((row) => ({
      ...configRows.get(row.key),
      ...row,
    }));
    return filterAcademicHubDirectory(directory, query);
  }, [analytics?.stats, query]);

  return (
    <DashboardLayout
      role="admin"
      title="Academic Hub"
      description="Manage academic structure, operations, and lifecycle from one workspace."
    >
      <section className="space-y-4">
        <Card className="p-3 sm:p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative w-full lg:max-w-xl">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search academic entities and lifecycle states"
                className="min-h-11 w-full rounded-xl border border-border bg-surface pl-10 pr-4 text-sm text-text outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={analytics?.stats?.active_academic_session ? "success" : "warning"}>
                Session: {analytics?.stats?.active_academic_session || "Not configured"}
              </Badge>
              <Badge variant={analytics?.stats?.active_academic_term ? "success" : "warning"}>
                Term: {analytics?.stats?.active_academic_term || "Not configured"}
              </Badge>
            </div>
          </div>
          {metricsError ? <p className="mt-3 text-sm text-warning">{metricsError}</p> : null}
        </Card>

        <Card className="overflow-hidden">
          <div className="border-b border-border/70 px-4 py-4 sm:px-5">
            <h2 className="text-base font-semibold text-text">Academic entities</h2>
            <p className="mt-1 text-sm text-text-muted">
              Open an entity to view its records, supported lifecycle, and purpose-built actions.
            </p>
          </div>

          <div className="hidden overflow-x-auto lg:block">
            <table className="w-full min-w-[62rem] border-collapse text-left">
              <thead className="bg-surface-muted/55 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                <tr>
                  <th className="px-5 py-3">Entity</th>
                  <th className="px-4 py-3">Count / Scope</th>
                  <th className="px-4 py-3">Current state</th>
                  <th className="px-4 py-3">Supported lifecycle</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/70">
                {rows.map((row) => {
                  const Icon = row.icon;
                  return (
                    <tr key={row.key} className="bg-surface transition hover:bg-surface-muted/25">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", academicToneStyles[row.tone] || academicToneStyles.primary)}>
                            <Icon className="h-4 w-4" />
                          </span>
                          <div>
                            <p className="font-semibold text-text">{row.shortTitle}</p>
                            <p className="mt-0.5 max-w-sm text-xs text-text-muted">{row.description}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-text-soft">{row.scope}</td>
                      <td className="px-4 py-3"><Badge variant={statusVariant(row.state)}>{row.state}</Badge></td>
                      <td className="px-4 py-3 text-sm text-text-muted">{row.lifecycle}</td>
                      <td className="px-5 py-3 text-right">
                        <Button size="small" variant="outline" onClick={() => navigate(`/admin/academic/${row.key}`)}>Open</Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="divide-y divide-border/70 lg:hidden">
            {rows.map((row) => {
              const Icon = row.icon;
              return (
                <button key={row.key} type="button" onClick={() => navigate(`/admin/academic/${row.key}`)} className="flex w-full items-start gap-3 px-4 py-4 text-left transition hover:bg-surface-muted/25">
                  <span className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-xl", academicToneStyles[row.tone] || academicToneStyles.primary)}><Icon className="h-4 w-4" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-text">{row.shortTitle}</span>
                      <Badge variant={statusVariant(row.state)}>{row.state}</Badge>
                    </span>
                    <span className="mt-1 block text-sm text-text-muted">{row.scope}</span>
                    <span className="mt-2 block text-xs text-text-muted">{row.lifecycle}</span>
                  </span>
                </button>
              );
            })}
          </div>

          {!rows.length ? <p className="px-5 py-10 text-center text-sm text-text-muted">No academic entity matches your search.</p> : null}
        </Card>
      </section>
    </DashboardLayout>
  );
}

export default AcademicHubOverviewPage;
