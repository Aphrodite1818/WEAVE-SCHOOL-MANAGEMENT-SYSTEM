import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatChartLabel } from "../../utils/academicDashboard";

const normalizeItems = (data, valueKey) =>
  Array.isArray(data)
    ? data.filter((item) => Number.isFinite(Number(item?.[valueKey])) && Number(item?.[valueKey]) >= 0)
    : [];

function AnalyticsBarChart({
  data = [],
  title,
  emptyMessage = "No chart data available yet.",
  labelKey = "label",
  valueKey = "value",
}) {
  const items = normalizeItems(data, valueKey);
  const hasVisibleValues = items.some((item) => Number(item?.[valueKey]) > 0);

  return (
    <div className="dashboard-chart-card">
      <div>
        <h3 className="text-base font-semibold text-text">{title}</h3>
      </div>

      {items.length === 0 ? (
        <div className="dashboard-chart-empty">
          {emptyMessage}
        </div>
      ) : !hasVisibleValues ? (
        <div className="mt-5 flex min-h-0 flex-1 flex-col justify-center space-y-4 rounded-2xl border border-border bg-surface-muted/30 px-4 py-5">
          {items.map((item, index) => (
            <div key={`${item?.[labelKey]}-${index}`} className="space-y-2">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="font-medium text-text">{formatChartLabel(item?.[labelKey])}</span>
                <span className="font-semibold text-text-muted">{Number(item?.[valueKey])}</span>
              </div>
              <div className="h-2 rounded-full bg-surface-subtle">
                <div className="h-2 rounded-full bg-primary/20" style={{ width: "100%" }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-5 min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={items} margin={{ left: 0, right: 12, top: 8, bottom: 24 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(148, 163, 184, 0.25)" />
              <XAxis dataKey={labelKey} tickLine={false} axisLine={false} tickMargin={10} tickFormatter={formatChartLabel} angle={-30} textAnchor="end" height={84} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={36} />
              <Tooltip />
              <Bar dataKey={valueKey} fill="#0f766e" radius={[10, 10, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default AnalyticsBarChart;
