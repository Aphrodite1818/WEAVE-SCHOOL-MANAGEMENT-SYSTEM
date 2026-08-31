import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useId } from "react";
import InteractiveChartShell from "./InteractiveChartShell";
import { formatChartLabel } from "../../utils/academicDashboard";

const normalizeItems = (data, valueKey) => {
  if (!Array.isArray(data)) return [];

  return data
    .filter((item) => Number.isFinite(Number(item?.[valueKey])))
    .map((item) => ({ ...item, [valueKey]: Number(item[valueKey]) }));
};

const withTrendLine = (items, valueKey) =>
  items.map((item, index) => {
    const previous = items[index - 1]?.[valueKey];
    const current = item[valueKey];
    const next = items[index + 1]?.[valueKey];
    const values = [previous, current, next].filter((value) => Number.isFinite(Number(value)));
    const trend = values.reduce((sum, value) => sum + Number(value), 0) / Math.max(values.length, 1);

    return { ...item, __trend: Number(trend.toFixed(2)) };
  });

const chartSummary = (items, valueKey, labelKey) => {
  const latest = items[items.length - 1];
  const peak = items.reduce(
    (highest, item) => (Number(item[valueKey]) > Number(highest?.[valueKey] ?? -Infinity) ? item : highest),
    null,
  );

  return {
    latestValue: latest ? latest[valueKey] : 0,
    latestLabel: latest ? formatChartLabel(latest[labelKey]) : "Latest",
    peakValue: peak ? peak[valueKey] : 0,
    peakLabel: peak ? formatChartLabel(peak[labelKey]) : "Peak",
  };
};

function TrendTooltip({ active, payload, label, tooltipLabelKey }) {
  if (!active || !payload?.length) return null;

  const primary = payload.find((entry) => entry.dataKey !== "__trend");
  const trend = payload.find((entry) => entry.dataKey === "__trend");
  const tooltipLabel = primary?.payload?.[tooltipLabelKey] || formatChartLabel(label);

  return (
    <div className="rounded-2xl border border-border bg-surface/95 px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold text-text">{tooltipLabel}</p>
      {primary ? (
        <p className="mt-1 flex items-center gap-2 text-text-muted">
          <span className="h-2 w-2 rounded-full bg-primary" />
          Value: <span className="font-semibold text-text">{primary.value}</span>
        </p>
      ) : null}
      {trend ? (
        <p className="mt-1 flex items-center gap-2 text-text-muted">
          <span className="h-2 w-2 rounded-full bg-text-faint" />
          Trend: <span className="font-semibold text-text-soft">{trend.value}</span>
        </p>
      ) : null}
    </div>
  );
}

function AnalyticsLineChart({
  data = [],
  title,
  description,
  emptyMessage = "No trend data available yet.",
  labelKey = "label",
  tooltipLabelKey = "fullLabel",
  valueKey = "value",
}) {
  const gradientId = `analytics-line-${useId().replaceAll(":", "")}`;
  const items = normalizeItems(data, valueKey);
  const chartItems = withTrendLine(items, valueKey);
  const summary = chartSummary(items, valueKey, labelKey);

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
      <div className="chart-interactive-scroll mt-5 min-h-0 flex-1 rounded-[1.5rem] border border-border/60 bg-surface-muted/15 px-1 py-3 sm:px-2">
        <div className="flex min-w-max items-start justify-between gap-6 px-4 pb-1 pt-1 sm:px-5">
          <div className="min-w-[7rem]">
            <p className="text-2xl font-semibold text-primary sm:text-3xl">{summary.latestValue}</p>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-text-muted sm:text-[11px]">
              {summary.latestLabel}
            </p>
          </div>
          <div className="min-w-[7rem]">
            <p className="text-2xl font-semibold text-text sm:text-3xl">{summary.peakValue}</p>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-text-muted sm:text-[11px]">
              Peak {summary.peakLabel}
            </p>
          </div>
        </div>
        <div style={{ minWidth: chartMinWidth, height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartItems} margin={{ left: 0, right: expanded ? 28 : 14, top: 14, bottom: 18 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity={0.28} />
                  <stop offset="58%" stopColor="#2563eb" stopOpacity={0.09} />
                  <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="1 6"
                vertical={false}
                stroke="rgba(148, 163, 184, 0.24)"
              />
              <XAxis
                dataKey={labelKey}
                tickLine={false}
                axisLine={false}
                tickMargin={12}
                tickFormatter={formatChartLabel}
                height={expanded ? 60 : 54}
                interval={0}
                tick={{ fill: "#64748b", fontSize: expanded ? 13 : 11, fontWeight: 600 }}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={42}
                tick={{ fill: "#64748b", fontSize: expanded ? 12 : 10, fontWeight: 600 }}
              />
              <Tooltip
                cursor={{ stroke: "rgba(100, 116, 139, 0.24)", strokeDasharray: "4 4" }}
                content={<TrendTooltip tooltipLabelKey={tooltipLabelKey} />}
              />
              <Area
                type="monotone"
                dataKey={valueKey}
                stroke="none"
                fill={`url(#${gradientId})`}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="__trend"
                stroke="rgba(100, 116, 139, 0.42)"
                strokeWidth={expanded ? 2 : 1.5}
                strokeDasharray="2 4"
                dot={false}
                activeDot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey={valueKey}
                stroke="#2563eb"
                strokeWidth={expanded ? 4 : 3}
                dot={{ r: expanded ? 4.5 : 3.5, fill: "#ffffff", stroke: "#2563eb", strokeWidth: 2 }}
                activeDot={{ r: expanded ? 8 : 6, fill: "#2563eb", stroke: "#dbeafe", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </AreaChart>
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
