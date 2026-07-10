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

function XAxisTick({ x, y, payload, isMobileChart }) {
  const label = shortLabel(payload?.value, isMobileChart ? 11 : 16);

  return (
    <g transform={`translate(${x},${y})`}>
      <text
        x={0}
        y={0}
        dy={isMobileChart ? 16 : 14}
        textAnchor={isMobileChart ? "end" : "middle"}
        transform={isMobileChart ? "rotate(-35)" : undefined}
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
  const hasLongLabels = items.some((item) => formatChartLabel(item?.[labelKey]).length > 10);
  const useHorizontalBars = isMobileChart && (items.length >= 4 || hasLongLabels);
  const chartHeight = useHorizontalBars ? Math.max(280, items.length * 48) : isMobileChart ? 300 : 280;
  const yAxisWidth = 138;
  const verticalChartMinWidth = !useHorizontalBars
    ? Math.max(isMobileChart ? 340 : 520, items.length * (isMobileChart ? 88 : 118))
    : "100%";

  return (
    <div className="dashboard-chart-card flex min-h-[22rem] flex-col overflow-hidden p-4 sm:p-5">
      <div>
        <h3 className="text-base font-semibold text-text">{title}</h3>
        {description ? <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p> : null}
      </div>

      {items.length === 0 ? (
        <div className="dashboard-chart-empty mt-5 flex min-h-[14rem] items-center justify-center rounded-2xl border border-dashed border-border bg-surface-muted/25 px-4 py-5 text-center text-sm text-text-muted">
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
        <div className="mt-5 min-h-0 flex-1 overflow-x-auto overflow-y-hidden rounded-2xl border border-border/50 bg-surface-muted/10 px-1 py-3 sm:px-2">
          <div style={{ minWidth: verticalChartMinWidth, height: chartHeight }}>
            <ResponsiveContainer width="100%" height="100%">
              {useHorizontalBars ? (
                <BarChart data={items} layout="vertical" margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(148, 163, 184, 0.25)" />
                  <XAxis
                    type="number"
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    width={36}
                    tick={{ fontSize: 13 }}
                  />
                  <YAxis
                    type="category"
                    dataKey={labelKey}
                    tickLine={false}
                    axisLine={false}
                    tickMargin={10}
                    width={yAxisWidth}
                    tickFormatter={(value) => shortLabel(value, 18)}
                    tick={{ fontSize: 13, fontWeight: 500 }}
                  />
                  <Tooltip labelFormatter={formatChartLabel} />
                  <Bar dataKey={valueKey} radius={[0, 10, 10, 0]} barSize={20}>
                    {items.map((item, index) => (
                      <Cell key={`${item?.[labelKey]}-${index}`} fill={CHART_BAR_COLORS[index % CHART_BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              ) : (
                <BarChart data={items} margin={{ left: 0, right: 12, top: 8, bottom: isMobileChart ? 36 : 24 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(148, 163, 184, 0.25)" />
                  <XAxis
                    dataKey={labelKey}
                    tickLine={false}
                    axisLine={false}
                    tickMargin={10}
                    tick={<XAxisTick isMobileChart={isMobileChart} />}
                    interval={0}
                    minTickGap={0}
                    height={isMobileChart ? 88 : 64}
                  />
                  <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={36} tick={{ fontSize: isMobileChart ? 13 : 12 }} />
                  <Tooltip labelFormatter={formatChartLabel} />
                  <Bar dataKey={valueKey} radius={[10, 10, 0, 0]} maxBarSize={isMobileChart ? 48 : 56}>
                    {items.map((item, index) => (
                      <Cell key={`${item?.[labelKey]}-${index}`} fill={CHART_BAR_COLORS[index % CHART_BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

export default AnalyticsBarChart;
