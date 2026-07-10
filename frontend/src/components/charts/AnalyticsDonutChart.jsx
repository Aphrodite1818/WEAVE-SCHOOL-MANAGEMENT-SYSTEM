import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import InteractiveChartShell from "./InteractiveChartShell";
import { formatChartLabel } from "../../utils/academicDashboard";
import { cn } from "../../utils/cn";

const DEFAULT_COLORS = ["#0f766e", "#0ea5e9", "#f59e0b", "#ef4444", "#8b5cf6", "#3452DB"];
const normalizeItems = (data, valueKey) =>
  Array.isArray(data)
    ? data.filter((item) => Number.isFinite(Number(item?.[valueKey])) && Number(item?.[valueKey]) >= 0)
    : [];

function AnalyticsDonutChart({
  data = [],
  title,
  description,
  emptyMessage = "No chart data available yet.",
  labelKey = "label",
  valueKey = "value",
}) {
  const items = normalizeItems(data, valueKey);
  const total = items.reduce((sum, item) => sum + Number(item?.[valueKey] || 0), 0);

  const renderChartBody = (expanded = false) => {
    if (items.length === 0) {
      return (
        <div className="dashboard-chart-empty mt-5 flex min-h-[14rem] items-center justify-center rounded-2xl border border-dashed border-border bg-surface-muted/25 px-4 py-5 text-center text-sm text-text-muted">
          {emptyMessage}
        </div>
      );
    }

    const chartBoxSize = expanded ? "h-[22rem] max-w-[26rem]" : "h-48 max-w-[220px]";
    const innerRadius = expanded ? 92 : 58;
    const outerRadius = expanded ? 140 : 88;

    return (
      <div
        className={cn(
          "chart-interactive-scroll mt-5 flex min-h-0 flex-1 flex-col gap-4 rounded-2xl border border-border/50 bg-surface-muted/10 p-3",
          expanded ? "xl:flex-row xl:items-center" : "",
        )}
      >
        <div className={`mx-auto w-full shrink-0 ${chartBoxSize}`}>
          {total > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={items}
                  dataKey={valueKey}
                  nameKey={labelKey}
                  cx="50%"
                  cy="50%"
                  innerRadius={innerRadius}
                  outerRadius={outerRadius}
                  paddingAngle={2}
                >
                  {items.map((item, index) => (
                    <Cell key={`${item?.[labelKey]}-${index}`} fill={DEFAULT_COLORS[index % DEFAULT_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="flex h-44 w-44 flex-col items-center justify-center rounded-full border-[18px] border-surface-subtle bg-background text-center">
                <span className="text-3xl font-semibold text-text">0</span>
                <span className="mt-1 max-w-20 text-xs font-medium uppercase tracking-wide text-text-muted">
                  Awaiting data
                </span>
              </div>
            </div>
          )}
        </div>

        <div
          className={cn(
            "grid min-w-0 flex-1 gap-3",
            expanded ? "sm:grid-cols-2 xl:min-w-[24rem]" : "sm:grid-cols-2",
          )}
        >
          {items.map((item, index) => (
            <div
              key={`${item?.[labelKey]}-${index}`}
              className="flex min-w-0 items-center justify-between gap-3 rounded-2xl border border-border bg-surface px-3 py-2.5"
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <span
                  className="h-3 w-3 shrink-0 rounded-full"
                  style={{ backgroundColor: DEFAULT_COLORS[index % DEFAULT_COLORS.length] }}
                />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-text" title={formatChartLabel(item?.[labelKey])}>
                  {formatChartLabel(item?.[labelKey])}
                </span>
              </div>
              <span className="shrink-0 text-sm font-semibold text-text">{item?.[valueKey] ?? 0}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <InteractiveChartShell
      title={title}
      description={description}
      expandedChildren={renderChartBody(true)}
    >
      {renderChartBody(false)}
    </InteractiveChartShell>
  );
}

export default AnalyticsDonutChart;
