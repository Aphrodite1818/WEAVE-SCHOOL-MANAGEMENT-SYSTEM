import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import InteractiveChartShell from "./InteractiveChartShell";
import { formatChartLabel } from "../../utils/academicDashboard";

const normalizeItems = (data, valueKey) =>
  Array.isArray(data)
    ? data.filter((item) => Number.isFinite(Number(item?.[valueKey])))
    : [];

function AnalyticsLineChart({
  data = [],
  title,
  description,
  emptyMessage = "No trend data available yet.",
  labelKey = "label",
  tooltipLabelKey = "fullLabel",
  valueKey = "value",
}) {
  const items = normalizeItems(data, valueKey);

  const renderChartBody = (expanded = false) => {
    if (items.length === 0) {
      return (
        <div className="dashboard-chart-empty mt-5 flex min-h-[14rem] items-center justify-center rounded-2xl border border-dashed border-border bg-surface-muted/25 px-4 py-5 text-center text-sm text-text-muted">
          {emptyMessage}
        </div>
      );
    }

    const chartHeight = expanded ? 500 : 280;
    const chartMinWidth = Math.max(expanded ? 760 : 420, items.length * (expanded ? 112 : 92));

    return (
      <div className="chart-interactive-scroll mt-5 min-h-0 flex-1 rounded-2xl border border-border/50 bg-surface-muted/10 px-1 py-3 sm:px-2">
        <div style={{ minWidth: chartMinWidth, height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={items} margin={{ left: 0, right: expanded ? 28 : 12, top: 8, bottom: 24 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(148, 163, 184, 0.25)" />
              <XAxis
                dataKey={labelKey}
                tickLine={false}
                axisLine={false}
                tickMargin={10}
                tickFormatter={formatChartLabel}
                angle={-30}
                textAnchor="end"
                height={84}
                interval={0}
                tick={{ fontSize: expanded ? 14 : 12 }}
              />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={36} tick={{ fontSize: expanded ? 14 : 12 }} />
              <Tooltip
                labelFormatter={(value, payload) =>
                  payload?.[0]?.payload?.[tooltipLabelKey] || formatChartLabel(value)
                }
              />
              <Line
                type="monotone"
                dataKey={valueKey}
                stroke="#2563eb"
                strokeWidth={expanded ? 4 : 3}
                dot={{ r: expanded ? 5 : 4, fill: "#2563eb", strokeWidth: 0 }}
                activeDot={{ r: expanded ? 8 : 6, fill: "#1d4ed8", strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
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

export default AnalyticsLineChart;
