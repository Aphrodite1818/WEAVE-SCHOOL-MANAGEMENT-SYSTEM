import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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

  return (
    <div className="dashboard-chart-card">
      <div>
        <h3 className="text-base font-semibold text-text">{title}</h3>
        {description && <p className="mt-1 text-sm text-text-muted">{description}</p>}
      </div>

      {items.length === 0 ? (
        <div className="dashboard-chart-empty">
          {emptyMessage}
        </div>
      ) : (
        <div className="mt-5 min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={items} margin={{ left: 0, right: 12, top: 8, bottom: 24 }}>
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
              />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={36} />
              <Tooltip
                labelFormatter={(value, payload) =>
                  payload?.[0]?.payload?.[tooltipLabelKey] || formatChartLabel(value)
                }
              />
              <Line
                type="monotone"
                dataKey={valueKey}
                stroke="#2563eb"
                strokeWidth={3}
                dot={{ r: 4, fill: "#2563eb", strokeWidth: 0 }}
                activeDot={{ r: 6, fill: "#1d4ed8", strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default AnalyticsLineChart;
