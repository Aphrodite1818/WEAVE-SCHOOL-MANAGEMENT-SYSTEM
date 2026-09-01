import { ArrowRight, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import AcademicOrbitNavigator from "../../features/academic-admin/AcademicOrbitNavigator";
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
  const [selectedKey, setSelectedKey] = useState("sessions");

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

  useEffect(() => {
    if (!rows.length) return;
    if (!rows.some((row) => row.key === selectedKey)) setSelectedKey(rows[0].key);
  }, [rows, selectedKey]);

  const selectedRow = rows.find((row) => row.key === selectedKey) || rows[0] || null;

  return (
    <DashboardLayout
      role="admin"
      title="Academic Hub"
      description="Manage academic structure, operations, and lifecycle from one workspace."
    >
      <section className="space-y-4">
        <div className="flex flex-col gap-3 border-b border-border/70 pb-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full lg:max-w-xl">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search academic entities..."
              className="min-h-11 w-full rounded-lg border border-border bg-surface pl-10 pr-4 text-sm text-text outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
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

        {metricsError ? <p className="text-sm text-warning">{metricsError}</p> : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.55fr)]">
          <Card className="overflow-hidden rounded-xl shadow-none">
            <div className="border-b border-border/70 px-4 py-4 sm:px-5">
              <h2 className="text-base font-semibold text-text">Academic entities</h2>
              <p className="mt-1 text-sm text-text-muted">
                Select an entity to inspect its current scope, lifecycle, and available workspace.
              </p>
            </div>

            <div className="hidden overflow-x-auto lg:block">
              <table className="w-full min-w-[58rem] border-collapse text-left">
                <thead className="bg-surface-muted/55 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                  <tr>
                    <th className="px-5 py-3">Entity</th>
                    <th className="px-4 py-3">Count / Scope</th>
                    <th className="px-4 py-3">Current state</th>
                    <th className="px-4 py-3">Lifecycle</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/70">
                  {rows.map((row) => {
                    const Icon = row.icon;
                    const selected = row.key === selectedRow?.key;
                    return (
                      <tr
                        key={row.key}
                        onClick={() => setSelectedKey(row.key)}
                        className={cn(
                          "cursor-pointer bg-surface transition hover:bg-surface-muted/30",
                          selected && "bg-primary-soft/30",
                        )}
                      >
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-3">
                            <span
                              className={cn(
                                "grid h-9 w-9 shrink-0 place-items-center rounded-lg",
                                academicToneStyles[row.tone] || academicToneStyles.primary,
                              )}
                            >
                              <Icon className="h-4 w-4" />
                            </span>
                            <div>
                              <p className="font-semibold text-text">{row.shortTitle}</p>
                              <p className="mt-0.5 max-w-sm text-xs text-text-muted">
                                {row.description}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-text-soft">{row.scope}</td>
                        <td className="px-4 py-3">
                          <Badge variant={statusVariant(row.state)}>{row.state}</Badge>
                        </td>
                        <td className="px-4 py-3 text-sm text-text-muted">{row.lifecycle}</td>
                        <td className="px-5 py-3 text-right">
                          <Button
                            size="small"
                            variant="outline"
                            onClick={(event) => {
                              event.stopPropagation();
                              navigate(`/admin/academic/${row.key}`);
                            }}
                          >
                            Open
                          </Button>
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
                  <button
                    key={row.key}
                    type="button"
                    onClick={() => navigate(`/admin/academic/${row.key}`)}
                    className="flex w-full items-start gap-3 px-4 py-4 text-left transition hover:bg-surface-muted/25"
                  >
                    <span
                      className={cn(
                        "grid h-10 w-10 shrink-0 place-items-center rounded-lg",
                        academicToneStyles[row.tone] || academicToneStyles.primary,
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
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

            {!rows.length ? (
              <p className="px-5 py-10 text-center text-sm text-text-muted">
                No academic entity matches your search.
              </p>
            ) : null}
          </Card>

          {selectedRow ? (
            <aside className="hidden xl:block xl:sticky xl:top-4 xl:self-start">
              <Card className="overflow-hidden rounded-xl p-0 shadow-none">
                <div className="border-b border-border/70 px-5 py-5">
                  <div className="flex items-start gap-3">
                    <span
                      className={cn(
                        "grid h-11 w-11 shrink-0 place-items-center rounded-xl",
                        academicToneStyles[selectedRow.tone] || academicToneStyles.primary,
                      )}
                    >
                      <selectedRow.icon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <h2 className="text-lg font-semibold text-text">{selectedRow.title}</h2>
                      <p className="mt-1 text-sm leading-6 text-text-muted">
                        {selectedRow.description}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="divide-y divide-border/70">
                  <section className="px-5 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
                      Current scope
                    </p>
                    <p className="mt-2 text-sm font-semibold text-text">{selectedRow.scope}</p>
                    <div className="mt-3">
                      <Badge variant={statusVariant(selectedRow.state)}>{selectedRow.state}</Badge>
                    </div>
                  </section>

                  <section className="px-5 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
                      Lifecycle
                    </p>
                    <p className="mt-2 text-sm leading-6 text-text-muted">
                      {selectedRow.lifecycle}
                    </p>
                  </section>

                  <section className="px-5 py-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
                      Academic context
                    </p>
                    <dl className="mt-3 space-y-3 text-sm">
                      <div className="flex items-start justify-between gap-4">
                        <dt className="text-text-muted">Session</dt>
                        <dd className="text-right font-semibold text-text">
                          {analytics?.stats?.active_academic_session || "Not configured"}
                        </dd>
                      </div>
                      <div className="flex items-start justify-between gap-4">
                        <dt className="text-text-muted">Term</dt>
                        <dd className="text-right font-semibold text-text">
                          {analytics?.stats?.active_academic_term || "Not configured"}
                        </dd>
                      </div>
                    </dl>
                  </section>

                  <section className="px-5 py-4">
                    <Button
                      className="w-full"
                      onClick={() => navigate(`/admin/academic/${selectedRow.key}`)}
                    >
                      Open {selectedRow.shortTitle}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </section>
                </div>
              </Card>
            </aside>
          ) : null}
        </div>
      </section>
      <AcademicOrbitNavigator />
    </DashboardLayout>
  );
}

export default AcademicHubOverviewPage;
