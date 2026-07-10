import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import InteractiveChartShell from "./InteractiveChartShell";
import { formatChartLabel } from "../../utils/academicDashboard";

const CHART_BAR_COLORS = [
  "#3452DB",
  "#16A34A",
  "#F59E0B",
  "#7C3AED",
  "#0EA5E9",
  "#F97316",
];

const normalizeItems = (data, valueKey) =>
  Array.isArray(data)
    ? data.filter((item) => Number.isFinite(Number(item?.[valueKey])) && Number(item?.[valueKey]) >= 0)
    : [];

const shortLabel = (value, maxLength = 18) => {
  const label = formatChartLabel(value);
  if (!label || label.length <= maxLength) return label;
  return `${label.slice(0, maxLength - 1)}…`;
};

function useMobileChartLayout() {
  const [isMobileChart, setIsMobileChart] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia("(max-width: 640px)").matches;
  });

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const mediaQuery = window.matchMedia("(max-width: 640px)");
    const handleChange = (event) => setIsMobileChart(event.matches);

    setIsMobileChart(mediaQuery.matches);

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handleChange);
      return () => mediaQuery.removeEventListener("change", handleChange);
    }

    mediaQuery.addListener(handleChange);
    return () => mediaQuery.removeListener(handleChange);
  }, []);

  return isMobileChart;
}

function XAxisTick({ x, y, payload, isMobileChart, expanded }) {
  const label = shortLabel(payload?.value, expanded ? 18 : isMobileChart ? 10 : 16);

  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={0}
        dy={isMobileChart ? 18 : 14}
        textAnchor="end"
        transform={`rotate(${isMobileChart ? -48 : -28})`}
        className="fill-text-muted text-[12px] font-medium sm:text-xs"
      >
        {label}
      </text>
    </g>
  );
}

function AnalyticsBarChart({
  data = [],
  title,
  description,
  emptyMessage = "No chart data available yet.",
  labelKey = "label",
  valueKey = "value",
}) {
  const isMobileChart = useMobileChartLayout();
  const items = normalizeItems(data, valueKey);
  const hasVisibleValues = items.some((item) => Number(item?.[valueKey]) > 0);

  const renderChartBody = (expanded = false) => {
    if (items.length === 0) {
      return (
        <div className="dashboard-chart-empty mt-5 flex min-h-[14rem] items-center justify-center rounded-2xl border border-dashed border-border bg-surface-muted/25 px-4 py-5 text-center text-sm text-text-muted">
          {emptyMessage}
        </div>
      );
    }

    const chartHeight = expanded ? 520 : isMobileChart ? 340 : 300;
    const chartMinWidth = Math.max(
      expanded ? 820 : isMobileChart ? 380 : 560,
      items.length * (expanded ? 132 : isMobileChart ? 76 : 108),
    );
    const xAxisHeight = expanded ? 104 : isMobileChart ? 104 : 76;

    return (
      <div className="chart-interactive-scroll mt-5 min-h-0 flex-1 rounded-2xl border border-border/50 bg-surface-muted/10 px-1 py-3 sm:px-2">
        <div style={{ minWidth: chartMinWidth, height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={items} margin={{ left: 0, right: expanded ? 28 : 14, top: 16, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(148, 163, 184, 0.25)" />
              <XAxis
                dataKey={labelKey}
                tickLine={false}
                axisLine={false}
                tickMargin={12}
                tick={<XAxisTick isMobileChart={isMobileChart} expanded={expanded} />}
                interval={0}
                minTickGap={0}
                height={xAxisHeight}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={isMobileChart ? 34 : 38}
                domain={hasVisibleValues ? [0, "auto"] : [0, 1]}
                tick={{ fontSize: isMobileChart ? 13 : 12 }}
              />
              <Tooltip labelFormatter={formatChartLabel} />
              <Bar dataKey={valueKey} radius={[10, 10, 0, 0]} maxBarSize={expanded ? 62 : isMobileChart ? 44 : 56} minPointSize={hasVisibleValues ? 0 : 3}>
                {items.map((item, index) => (
                  <Cell key={`${item?.[labelKey]}-${index}`} fill={CHART_BAR_COLORS[index % CHART_BAR_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
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
      hint="Swipe sideways or expand this vertical bar chart."
    >
      {renderChartBody(false)}
    </InteractiveChartShell>
  );
}

export default AnalyticsBarChart;
