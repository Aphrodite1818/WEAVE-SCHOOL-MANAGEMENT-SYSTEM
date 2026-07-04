import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatChartLabel } from "../../utils/academicDashboard";

const DEFAULT_COLORS = ["#0f766e", "#0ea5e9", "#f59e0b", "#ef4444", "#8b5cf6"];
const normalizeItems = (data, valueKey) =>
  Array.isArray(data)
    ? data.filter((item) => Number.isFinite(Number(item?.[valueKey])) && Number(item?.[valueKey]) >= 0)
    : [];

function AnalyticsDonutChart({
  data = [],
  title,
  emptyMessage = "No chart data available yet.",
  labelKey = "label",
  valueKey = "value",
}) {
  const items = normalizeItems(data, valueKey);
  const total = items.reduce((sum, item) => sum + Number(item?.[valueKey] || 0), 0);

  return (
    <div className="dashboard-chart-card">
      <div>
        <h3 className="text-base font-semibold text-text">{title}</h3>
      </div>

      {items.length === 0 ? (
        <div className="dashboard-chart-empty">
          {emptyMessage}
        </div>
      ) : (
        <div className="mt-5 flex min-h-0 flex-1 flex-col gap-4">
          <div className="mx-auto h-48 w-full max-w-[220px] shrink-0">
            {total > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={items}
                    dataKey={valueKey}
                    nameKey={labelKey}
                    cx="50%"
                    cy="50%"
                    innerRadius={58}
                    outerRadius={88}
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

          <div className="min-w-0 space-y-3">
            {items.map((item, index) => (
              <div
                key={`${item?.[labelKey]}-${index}`}
                className="flex min-w-0 items-center justify-between gap-3 rounded-2xl border border-border bg-surface-muted/40 px-3 py-2.5"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    className="h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: DEFAULT_COLORS[index % DEFAULT_COLORS.length] }}
                  />
                  <span className="truncate text-sm font-medium text-text">
                    {formatChartLabel(item?.[labelKey])}
                  </span>
                </div>
                <span className="shrink-0 text-sm font-semibold text-text">{item?.[valueKey] ?? 0}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default AnalyticsDonutChart;
