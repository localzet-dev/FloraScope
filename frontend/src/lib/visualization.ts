import type { Geometry } from "geojson";
export type Metric = "ndvi" | "zscore" | "weather";
export type Trace = "observed" | "restored" | "expected";
export type TimeWindow = [string, string] | null;
export interface PlotPoint {
  date: string;
  observed: number | null;
  restored: number | null;
  expected: number | null;
  zscore: number | null;
  temperature?: number | null;
  precipitation?: number | null;
  predicted?: number | null;
  source?: string | null;
}
export interface VegetationEvent {
  kind?: unknown;
  severity?: unknown;
  start?: unknown;
  end?: unknown;
  interpretation?: unknown;
  confidence?: unknown;
  evidence?: unknown;
  evidence_json?: unknown;
  [key: string]: unknown;
}
export const traceLabels: Record<Trace, string> = {
  observed: "Наблюдения",
  restored: "Восстановление",
  expected: "Историческая норма",
};
export const traceColors: Record<Trace, string> = {
  observed: "#62dfb6",
  restored: "#eabd71",
  expected: "#879cf4",
};

export function absoluteTileTemplate(template: string, origin: string): string {
  if (/^https?:\/\//i.test(template)) return template;
  const slash = template.startsWith("/") ? "" : "/";
  // URL() кодирует фигурные скобки. MapLibre должен получить {z}/{x}/{y}
  // буквально, иначе отправит серверу %7Bz%7D и каждый тайл ответит 422.
  return `${origin}${slash}${template}`;
}
export const metricLabel = (value: number | null | undefined, digits = 3) =>
  value == null || !Number.isFinite(value) ? "—" : value.toFixed(digits);
export const shortDate = (date: string) =>
  new Date(date + "T12:00:00").toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
  });
export function eventTitle(event: VegetationEvent): string {
  return event.kind === "PHENOLOGY_SHIFT"
    ? "Сдвиг сезонной фазы"
    : event.kind === "NEGATIVE_DEVIATION"
      ? "Устойчивое снижение NDVI"
      : "Изменение растительности";
}
export function eventWindow(
  event: VegetationEvent,
  points: PlotPoint[],
): TimeWindow {
  if (!points.length || !event.start || !event.end) return null;
  const first = points[0].date,
    last = points[points.length - 1].date;
  if (String(event.end) < first || String(event.start) > last) return null;
  const padded = (day: string, offset: number) =>
    new Date(Date.parse(day) + offset * 86400000).toISOString().slice(0, 10);
  const start = padded(String(event.start), -7),
    end = padded(String(event.end), 7);
  return [start < first ? first : start, end > last ? last : end];
}
export function parsePolygons(
  raw: unknown,
): Array<{ name: string; geometry: Geometry }> {
  const value = raw as {
    type?: string;
    features?: unknown[];
    geometry?: Geometry;
    properties?: { name?: string };
  };
  if (!value || typeof value !== "object")
    throw new Error("В файле нет GeoJSON.");
  if (value.type === "FeatureCollection") {
    if (!Array.isArray(value.features) || !value.features.length)
      throw new Error("Коллекция не содержит объектов.");
    return value.features.flatMap(parsePolygons);
  }
  const geometry = (
    value.type === "Feature" ? value.geometry : value
  ) as Geometry;
  if (!geometry || !["Polygon", "MultiPolygon"].includes(geometry.type))
    throw new Error(
      "Нужен Polygon или MultiPolygon. Точки и линии не являются территорией.",
    );
  return [{ name: value.properties?.name || "Новая территория", geometry }];
}
export function evidenceEntries(
  event: VegetationEvent,
): Array<[string, string]> {
  let evidence = event.evidence;
  if (!evidence && typeof event.evidence_json === "string") {
    try {
      evidence = JSON.parse(event.evidence_json);
    } catch {
      return [];
    }
  }
  if (!evidence || typeof evidence !== "object") return [];
  const names: Record<string, string> = {
    ndvi_min_z: "Минимальное отклонение NDVI",
    observed_points: "Реальных наблюдений",
    water_z: "Отклонение водного индекса",
    precip_z: "Отклонение осадков",
    temp_z: "Отклонение температуры",
    lag_days: "Сдвиг, дней",
    shape_corr: "Сходство формы со сдвигом",
    unshifted_corr: "Сходство без сдвига",
    history_years: "Исторических сезонов",
    ndmi_deviation: "Отклонение NDMI",
  };
  return Object.entries(evidence)
    .filter(([, v]) => v != null && ["number", "string"].includes(typeof v))
    .map(([key, v]) => [
      names[key] ?? key.replaceAll("_", " "),
      typeof v === "number"
        ? metricLabel(v, Number.isInteger(v) ? 0 : 2)
        : String(v),
    ]);
}
