"use client";

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ChartConfig } from "@/types/api";

interface ChartRendererProps {
  chartConfig: ChartConfig;
  columns: string[];
  rows: unknown[][];
}

const CHART_COLORS = [
  "#2563eb",
  "#16a34a",
  "#d97706",
  "#dc2626",
  "#7c3aed",
  "#0891b2",
];

export default function ChartRenderer({
  chartConfig,
  columns,
  rows,
}: ChartRendererProps) {
  // Convert columns/rows (backend format) → Recharts-compatible object array
  const data = rows.map((row) =>
    Object.fromEntries(columns.map((col, i) => [col, row[i]]))
  );

  const { type, x_key, y_key } = chartConfig;

  if (type === "bar") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={x_key} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey={y_key} fill={CHART_COLORS[0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (type === "line") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={x_key} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey={y_key}
            stroke={CHART_COLORS[0]}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === "pie") {
    return (
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            nameKey={x_key}
            dataKey={y_key}
            cx="50%"
            cy="50%"
            outerRadius={100}
            label
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={CHART_COLORS[index % CHART_COLORS.length]}
              />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  return null;
}
