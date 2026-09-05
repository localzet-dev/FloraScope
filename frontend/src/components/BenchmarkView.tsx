import { useStoredState } from "../lib/useStoredState";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, FileButton, Modal, Select } from "@mantine/core";
import {
  ArrowDownToLine,
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  FlaskConical,
  Play,
  RefreshCw,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { api } from "../lib/api";
import type { Job, SystemState } from "../types";
import {
  type Metric,
  type PlotPoint,
  type TimeWindow,
  type Trace,
  type VegetationEvent,
  eventWindow,
  metricLabel,
  evidenceEntries,
} from "../lib/visualization";
import { Timeline } from "./Timeline";
import { SeriesTable } from "./SeriesTable";
import { ChartControls } from "./ChartControls";
import { EventCards } from "./EventPanel";
export function BenchmarkView({
  system,
  refreshToken,
  onJob,
  onNotice,
  busy,
}: {
  system: SystemState | null;
  refreshToken: number;
  onJob: (job: Job) => void;
  onNotice: (message: string) => void;
  busy: boolean;
}) {
  const [showEvents, setShowEvents] = useState(true),
    [tabular, setTabular] = useState(false);
  const [report, setReport] = useState<Record<string, any> | null>(null),
    [polygons, setPolygons] = useState<string[]>([]),
    [polygon, setPolygon] = useStoredState("benchmarkPolygon", "");
  const [series, setSeries] = useState<Array<Record<string, any>>>([]),
    [events, setEvents] = useState<VegetationEvent[]>([]),
    [year, setYear] = useStoredState("benchmarkYear", "");
  const [validation, setValidation] = useState<{
      valid: boolean;
      rows: number;
    } | null>(null),
    [validationError, setValidationError] = useState(""),
    [loading, setLoading] = useState(false),
    [uploading, setUploading] = useState("");
  const [confirm, setConfirm] = useState(false),
    [starting, setStarting] = useState(false),
    [seriesError, setSeriesError] = useState("");
  const [metric, setMetric] = useState<Metric>("ndvi"),
    [visible, setVisible] = useState<Trace[]>([
      "observed",
      "restored",
      "expected",
    ]),
    [range, setRange] = useState<TimeWindow>(null),
    [eventIndex, setEventIndex] = useState<number | null>(null),
    [point, setPoint] = useState<PlotPoint | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api.report(),
      api.polygons(),
      api.events(),
      api.validate(),
    ]);
    if (results[0].status === "fulfilled") setReport(results[0].value);
    else setReport(null);
    if (results[1].status === "fulfilled") {
      setPolygons(results[1].value);
      const ids = results[1].value;
      setPolygon((v) => (ids.includes(v) ? v : (ids[0] ?? "")));
    } else onNotice(String(results[1].reason));
    if (results[2].status === "fulfilled") setEvents(results[2].value);
    else setEvents([]);
    if (results[3].status === "fulfilled") {
      setValidation(results[3].value);
      setValidationError("");
    } else {
      setValidation(null);
      setValidationError(String(results[3].reason));
    }
    setLoading(false);
  }, [onNotice]);
  useEffect(() => {
    void refresh();
  }, [refreshToken]);
  useEffect(() => {
    let cancelled = false;
    setSeries([]);
    setPoint(null);
    setRange(null);
    setEventIndex(null);
    setSeriesError("");
    if (polygon)
      api
        .series(polygon)
        .then((data) => {
          if (cancelled) return;
          setSeries(data);
          setYear((current) =>
            data.some((row) => row.date?.startsWith(current)) && current
              ? current
              : (data.at(-1)?.date?.slice(0, 4) ?? ""),
          );
        })
        .catch((error) => {
          if (!cancelled) setSeriesError(String(error));
        });
    return () => {
      cancelled = true;
    };
  }, [polygon, refreshToken]);
  const years = useMemo(
    () =>
      [...new Set(series.map((p) => String(p.date).slice(0, 4)))]
        .sort()
        .reverse(),
    [series],
  );
  const points = useMemo<PlotPoint[]>(
    () =>
      series
        .filter((p) => !year || String(p.date).startsWith(year))
        .map((p) => ({
          date: p.date,
          observed: p.primary_ndvi ?? null,
          restored: p.primary_ndvi_filled ?? null,
          expected: p.climatology_calc ?? null,
          zscore: p.ndvi_zscore_calc ?? null,
          predicted: p.primary_ndvi_pred ?? null,
        })),
    [series, year],
  );
  const selectedEvents = useMemo(
    () =>
      events.filter(
        (e) =>
          String(e.anon_polygon_id) === polygon &&
          (!year || String(e.start).startsWith(year)),
      ),
    [events, polygon, year],
  );
  async function upload(kind: "train" | "test", file: File | null) {
    if (!file) return;
    setUploading(kind);
    try {
      await api.upload(kind, file);
      onNotice(
        `${kind === "train" ? "Обучающий" : "Тестовый"} файл загружен. Чтобы обновить предсказания, запустите обработку.`,
      );
      await refresh();
    } catch (error) {
      onNotice(String(error));
    } finally {
      setUploading("");
    }
  }
  const baselineNames: Record<string, string> = {
    primary_ndvi__interp: "Линейная интерполяция",
    whittaker: "Whittaker",
    sensor_ndvi_median: "Медиана спутников",
    clim_corrected: "Скорректированная норма",
    aoi_climatology: "Историческая норма",
  };
  const baselines = Object.entries(report?.validation?.baselines ?? {}).slice(
    0,
    3,
  ) as Array<[string, number]>;
  const chosen = eventIndex == null ? null : selectedEvents[eventIndex];
  return (
    <section className="benchmark-page">
      <div className="page-heading">
        <div>
          <h1>
            Восстановление NDVI<span className="heading-dot">.</span>
          </h1>
          <p>
            Проверьте динамику, сравните с историей и подготовьте CSV для
            отправки.
          </p>
        </div>
        <Button
          component="a"
          href="/api/v1/benchmark/submission"
          disabled={!validation?.valid}
          leftSection={<ArrowDownToLine size={16} />}
        >
          Скачать submission.csv
        </Button>
      </div>
      <div className="recovery-summary">
        <div className="data-pipeline card">
          <div className="panel-heading">
            <h3>Данные проекта</h3>
            <Badge color="gray" variant="light">
              CSV
            </Badge>
          </div>
          <div className="dataset-row">
            {(["train", "test"] as const).map((kind) => (
              <div className="dataset-card" key={kind}>
                <FileSpreadsheet size={23} />
                <div>
                  <b>
                    {kind === "train" ? "Обучающий набор" : "Тестовый набор"}
                  </b>
                  <small>
                    {system?.files[kind] ? "Файл подключён" : "Загрузите CSV"}
                  </small>
                </div>
                <FileButton
                  onChange={(file) => void upload(kind, file)}
                  accept=".csv"
                >
                  {(props) => (
                    <Button
                      {...props}
                      variant="subtle"
                      size="xs"
                      loading={uploading === kind}
                      disabled={busy || !!uploading}
                      aria-label={`Загрузить ${kind === "train" ? "обучающий" : "тестовый"} CSV`}
                    >
                      <Upload size={15} />
                    </Button>
                  )}
                </FileButton>
              </div>
            ))}
          </div>
          <div className="pipeline-actions">
            <Button
              leftSection={<Play size={14} />}
              variant="light"
              disabled={
                !system?.files.train ||
                !system?.files.test ||
                busy ||
                !!uploading
              }
              onClick={() => setConfirm(true)}
            >
              Обработать данные
            </Button>
            <Button
              variant="subtle"
              color="gray"
              leftSection={<RefreshCw size={14} />}
              loading={loading}
              onClick={() => void refresh()}
            >
              Проверить файлы
            </Button>
          </div>
        </div>
        <div className="validation-card card">
          <span className="eyebrow">КАЧЕСТВО ВОССТАНОВЛЕНИЯ</span>
          <div className="hero-metric">
            {metricLabel(report?.validation?.rmse, 4)}
            <span>RMSE</span>
          </div>
          <p>Ошибка на сохранённой проверочной выборке. Меньше — лучше.</p>
          <div className="key-value">
            <span>Оценка по формуле организаторов</span>
            <b>
              {metricLabel(report?.validation?.organizer_score_estimate, 2)} /
              30
            </b>
          </div>
          <div className="metric-caveat">
            Это CV на train, не оценка скрытых ответов текущего test.
          </div>
        </div>
        <div className="submission-card card">
          <div className="submission-icon">
            <ShieldCheck size={26} />
          </div>
          <span className="eyebrow">ФАЙЛ ДЛЯ ОТПРАВКИ</span>
          <h2>
            {loading
              ? "Проверяем CSV…"
              : validation?.valid
                ? "Формат проверен"
                : "Требуется проверка"}
          </h2>
          <p>
            {validation?.valid
              ? `${validation.rows.toLocaleString("ru-RU")} предсказания · ключи совпадают с текущим тестом`
              : "Подготовьте submission для подключённого теста."}
          </p>
          <Badge color={validation?.valid ? "teal" : "orange"} variant="light">
            {loading
              ? "Проверка"
              : validation?.valid
                ? "Валидатор пройден"
                : "Нет валидного результата"}
          </Badge>
          {validationError && (
            <details className="validation-detail">
              <summary>Подробнее</summary>
              <p>{validationError}</p>
            </details>
          )}
        </div>
      </div>
      <div className="benchmark-workspace">
        <div className="trajectory-panel">
          <div className="panel-heading">
            <div>
              <h3>Растительность во времени</h3>
            </div>
            <div className="series-selectors">
              <Select
                aria-label="Полигон датасета"
                searchable
                value={polygon}
                onChange={(v) => setPolygon(v ?? "")}
                data={polygons}
                placeholder="Выберите AOI"
                w={160}
              />
              <Select
                aria-label="Год наблюдений"
                value={year}
                onChange={(v) => {
                  setYear(v ?? "");
                  setRange(null);
                  setEventIndex(null);
                  setPoint(null);
                }}
                data={years}
                placeholder="Год"
                w={100}
              />
            </div>
          </div>
          <ChartControls
            showEvents={showEvents}
            setShowEvents={setShowEvents}
            tabular={tabular}
            setTabular={setTabular}
            metric={metric}
            setMetric={setMetric}
            visible={visible}
            setVisible={setVisible}
            reset={() => {
              setRange(null);
              setEventIndex(null);
            }}
          />
          {seriesError && <Alert color="orange">{seriesError}</Alert>}
          {tabular ? (
            <SeriesTable points={points} range={range} onPoint={setPoint} />
          ) : (
            <Timeline
              showEvents={showEvents}
              points={points}
              events={selectedEvents}
              metric={metric}
              visible={visible}
              range={range}
              onPoint={setPoint}
            />
          )}
          <div className="chart-footnote">
            <span>
              {points.length} строк · {polygon || "Нет данных"} ·{" "}
              {year || "Период не выбран"}
            </span>
            <span>Сплошная линия включает расчётные значения</span>
          </div>
          {point && (
            <div className="selected-point-strip">
              <b>{point.date}</b>
              <span>
                Наблюдение <strong>{metricLabel(point.observed)}</strong>
              </span>
              <span>
                Восстановление <strong>{metricLabel(point.restored)}</strong>
              </span>
              <span>
                Норма <strong>{metricLabel(point.expected)}</strong>
              </span>
            </div>
          )}
        </div>
        <aside className="benchmark-events card">
          <div className="panel-heading">
            <h3>События сезона</h3>
            <Badge variant="light" color="gray">
              {selectedEvents.length}
            </Badge>
          </div>
          <p className="muted small">
            Выберите событие, чтобы приблизить его на графике.
          </p>
          <EventCards
            events={selectedEvents}
            selected={eventIndex}
            onSelect={(i) => {
              setEventIndex(i);
              setRange(eventWindow(selectedEvents[i], points));
            }}
          />
          {chosen && (
            <div className="evidence">
              <h4>Что поддерживает интерпретацию</h4>
              {evidenceEntries(chosen).map(([k, v]) => (
                <div className="key-value" key={k}>
                  <span>{k}</span>
                  <b>{v}</b>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
      <div className="baseline-panel card">
        <div>
          <span className="eyebrow">КОНТРОЛЬНЫЕ МЕТОДЫ</span>
          <h3>Что даёт модель</h3>
          <p className="muted small">
            Сравнение из сохранённого CV-отчёта.
            <br />
            Одна метрика, несколько способов восстановить пропуски.
          </p>
        </div>
        <div className="baseline-bars">
          {[
            ...baselines,
            ["FloraScope", Number(report?.validation?.rmse)] as [
              string,
              number,
            ],
          ]
            .filter(([, v]) => Number.isFinite(v))
            .map(([key, value]) => (
              <div
                className={`baseline-row ${key === "FloraScope" ? "ours" : ""}`}
                key={key}
              >
                <span>{baselineNames[key] ?? key}</span>
                <div>
                  <i
                    style={{ width: `${Math.min(100, (value / 0.15) * 100)}%` }}
                  />
                </div>
                <b>{value.toFixed(4)}</b>
              </div>
            ))}
        </div>
      </div>
      <Modal
        opened={confirm}
        onClose={() => !starting && setConfirm(false)}
        title="Запустить обработку датасетов?"
        size="md"
      >
        <p>
          Будут выполнены validation, обучение модели и восстановление пропусков
          текущего теста. Это может занять несколько минут.
        </p>
        <Alert color="orange">
          Обученная модель, отчёт и submission будут обновлены. Скачайте текущий
          CSV, если хотите его сохранить.
        </Alert>
        <Button
          mt="lg"
          fullWidth
          loading={starting}
          onClick={async () => {
            setStarting(true);
            try {
              onJob(await api.runBenchmark(true));
              setConfirm(false);
            } catch (e) {
              onNotice(String(e));
            } finally {
              setStarting(false);
            }
          }}
        >
          Запустить полный расчёт
        </Button>
      </Modal>
    </section>
  );
}
