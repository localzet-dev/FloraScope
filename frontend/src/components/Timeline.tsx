import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { LineChart } from "lucide-react";
import {
  type Metric,
  type PlotPoint,
  type TimeWindow,
  type Trace,
  type VegetationEvent,
  traceColors,
  traceLabels,
} from "../lib/visualization";

export function Timeline({
  points,
  events = [],
  metric = "ndvi",
  visible = ["observed", "restored", "expected"],
  range = null,
  showEvents = true,
  onPoint,
}: {
  points: PlotPoint[];
  events?: VegetationEvent[];
  metric?: Metric;
  visible?: Trace[];
  range?: TimeWindow;
  showEvents?: boolean;
  onPoint?: (point: PlotPoint) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const latest = useRef({ points, onPoint });
  latest.current = { points, onPoint };
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chartRef.current = chart;
    chart.on("click", (p) => {
      const point = latest.current.points[p.dataIndex];
      if (point) latest.current.onPoint?.(point);
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);
  useEffect(() => {
    const pairs = (key: keyof PlotPoint) =>
      points.map((p) => [p.date, p[key] ?? null]);
    const eventAreas = events
      .filter((e) => e.start && e.end)
      .map((e) => [
        {
          xAxis: String(e.start),
          itemStyle: {
            color:
              e.kind === "PHENOLOGY_SHIFT"
                ? "rgba(135,156,244,.10)"
                : "rgba(246,138,111,.10)",
          },
        },
        { xAxis: String(e.end) },
      ]);
    const lines: echarts.SeriesOption[] =
      metric === "ndvi"
        ? visible.map((key) => ({
            name: traceLabels[key],
            type: key === "observed" ? "scatter" : "line",
            data: pairs(key),
            symbol: key === "observed" ? "circle" : "none",
            symbolSize: 7,
            itemStyle: { color: traceColors[key] },
            lineStyle: {
              color: traceColors[key],
              width: 2,
              type: key === "expected" ? "dashed" : "solid",
            },
            connectNulls: false,
          }))
        : metric === "zscore"
          ? [
              {
                name: "Отклонение от нормы, σ",
                type: "line",
                data: pairs("zscore"),
                showSymbol: false,
                itemStyle: { color: "#ad9cf5" },
                lineStyle: { width: 2 },
                markLine: {
                  symbol: "none",
                  silent: true,
                  label: { formatter: "{b}", color: "#96a3b1" },
                  data: [
                    { yAxis: -2, name: "−2σ", lineStyle: { color: "#ed977d" } },
                    {
                      yAxis: 0,
                      name: "Норма",
                      lineStyle: { color: "#50606f" },
                    },
                  ],
                },
              },
            ]
          : [
              {
                name: "Температура, °C",
                type: "line",
                data: pairs("temperature"),
                showSymbol: false,
                itemStyle: { color: "#eabd71" },
              },
              {
                name: "Осадки, мм",
                type: "bar",
                yAxisIndex: 1,
                data: pairs("precipitation"),
                itemStyle: { color: "#6aa9e6" },
                barMaxWidth: 9,
              },
            ];
    if (showEvents && eventAreas.length)
      lines.push({
        name: "Периоды событий",
        type: "line",
        // Подсветка событий не должна менять масштаб значений скрытым рядом.
        data: points.map((point) => [point.date, null]),
        showSymbol: false,
        silent: true,
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
        markArea: { silent: true, data: eventAreas as any },
      });
    chartRef.current?.setOption(
      {
        backgroundColor: "transparent",
        animationDuration: 250,
        textStyle: { fontFamily: "Inter, Segoe UI, sans-serif" },
        tooltip: {
          trigger: "axis",
          renderMode: "richText",
          backgroundColor: "#1b2835",
          borderColor: "#344554",
          textStyle: { color: "#dfe8f1" },
          valueFormatter: (v: any) =>
            v == null ? "Нет данных" : Number(v).toFixed(3),
        },
        grid: {
          left: 52,
          right: metric === "weather" ? 48 : 24,
          top: 24,
          bottom: 55,
        },
        xAxis: {
          type: "time",
          axisLine: { lineStyle: { color: "#2b3946" } },
          axisLabel: {
            color: "#8493a4",
            hideOverlap: true,
            formatter: (value: number) =>
              new Date(value).toLocaleDateString("ru-RU", {
                day: "numeric",
                month: "short",
              }),
          },
          splitLine: { show: false },
        },
        yAxis: [
          {
            type: "value",
            scale: true,
            axisLabel: { color: "#8493a4" },
            splitLine: { lineStyle: { color: "#24323e", type: "dashed" } },
          },
          ...(metric === "weather"
            ? [
                {
                  type: "value",
                  axisLabel: { color: "#6aa9e6" },
                  splitLine: { show: false },
                },
              ]
            : []),
        ],
        dataZoom: [
          {
            type: "inside",
            filterMode: "none",
            ...(range
              ? {
                  startValue: Date.parse(range[0]),
                  endValue: Date.parse(range[1]),
                }
              : { start: 0, end: 100 }),
          },
          {
            type: "slider",
            height: 14,
            bottom: 6,
            borderColor: "transparent",
            backgroundColor: "#18232d",
            fillerColor: "rgba(98,223,182,.10)",
            handleStyle: { color: "#62dfb6", borderColor: "#62dfb6" },
            textStyle: { color: "#8493a4" },
            showDetail: false,
          },
        ],
        series: lines,
      },
      { notMerge: true },
    );
  }, [points, metric, visible, range, events, showEvents]);
  return (
    <div className="chart-canvas-wrap">
      <div className="chart-canvas" ref={ref} />
      {!points.length && (
        <div className="chart-empty">
          <LineChart size={28} />
          <b>Здесь появится динамика</b>
          <span>Выберите сохранённый анализ или запустите новый.</span>
        </div>
      )}
    </div>
  );
}
