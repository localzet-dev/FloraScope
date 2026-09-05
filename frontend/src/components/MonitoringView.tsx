import { useStoredState } from "../lib/useStoredState";
import {
  type ChangeEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Geometry } from "geojson";
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Checkbox,
  Drawer,
  Loader,
  Modal,
  NumberInput,
  Popover,
  Select,
  SegmentedControl,
  Slider,
  TextInput,
  Tooltip,
} from "@mantine/core";
import {
  ArrowDownToLine,
  CalendarDays,
  ChevronDown,
  Crosshair,
  FolderOpen,
  History,
  Layers,
  MapPinned,
  Maximize2,
  Plus,
  Search,
  Settings2,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api } from "../lib/api";
import type { Analysis, Field, Job } from "../types";
import { EventPanel } from "./EventPanel";
import { MapPane } from "./MapPane";
import { Timeline } from "./Timeline";
import { SeriesTable } from "./SeriesTable";
import { ChartControls } from "./ChartControls";
import {
  eventWindow,
  parsePolygons,
  type Metric,
  type PlotPoint,
  type TimeWindow,
  type Trace,
} from "../lib/visualization";

type Candidate = {
  source_id: string;
  name: string;
  landuse: string | null;
  geometry: Geometry;
};
export function MonitoringView({
  refreshToken,
  onJob,
  onNotice,
  busy,
}: {
  refreshToken: number;
  onJob: (job: Job) => void;
  onNotice: (message: string) => void;
  busy: boolean;
}) {
  const [showEvents, setShowEvents] = useState(true),
    [tabular, setTabular] = useState(false);
  const [fields, setFields] = useState<Field[]>([]),
    [selectedId, setSelectedId] = useStoredState("field", "");
  const [analyses, setAnalyses] = useState<Array<Record<string, string>>>([]),
    [analysisId, setAnalysisId] = useStoredState("analysis", "");
  const [analysis, setAnalysis] = useState<Analysis | null>(null),
    [loading, setLoading] = useState(false),
    [loadError, setLoadError] = useState("");
  const [layout, setLayout] = useStoredState("layout", "overview"),
    [metric, setMetric] = useState<Metric>("ndvi");
  const [visible, setVisible] = useState<Trace[]>([
      "observed",
      "restored",
      "expected",
    ]),
    [range, setRange] = useState<TimeWindow>(null);
  const [point, setPoint] = useState<PlotPoint | null>(null),
    [selectedEvent, setSelectedEvent] = useState<number | null>(null);
  const [activeLayer, setActiveLayer] = useState("none"),
    [opacity, setOpacity] = useState(0.7),
    [showFields, setShowFields] = useState(true),
    [focusToken, setFocusToken] = useState(0);
  const [library, setLibrary] = useState(false),
    [history, setHistory] = useState(false),
    [search, setSearch] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]),
    [discovering, setDiscovering] = useState(false);
  const [viewport, setViewport] = useState<[number, number, number, number]>([
    38, 44, 40, 46,
  ]);
  const [draft, setDraft] = useState<
      Array<{ name: string; geometry: Geometry }>
    >([]),
    [draftIndex, setDraftIndex] = useState("0"),
    [name, setName] = useState(""),
    [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false),
    [runOpen, setRunOpen] = useState(false),
    [submitting, setSubmitting] = useState(false);
  const year = new Date().getFullYear();
  const [dateFrom, setDateFrom] = useStoredState("dateFrom", `${year}-03-01`),
    [dateTo, setDateTo] = useStoredState("dateTo", `${year}-09-01`),
    [historyYears, setHistoryYears] = useStoredState<number | string>(
      "historyYears",
      3,
    ),
    [cloud, setCloud] = useStoredState<number | string>("cloud", 35);
  const fileRef = useRef<HTMLInputElement>(null);
  const refresh = useCallback(async () => {
    try {
      const [nextFields, nextAnalyses] = await Promise.all([
        api.fields(),
        api.analyses(),
      ]);
      setFields(nextFields);
      setAnalyses(nextAnalyses);
      setSelectedId((current) =>
        nextFields.some((f) => f.id === current)
          ? current
          : (nextFields[0]?.id ?? ""),
      );
    } catch (error) {
      onNotice(message(error));
    }
  }, [onNotice]);
  useEffect(() => {
    void refresh();
    if (refreshToken > 0) setAnalysisId("");
  }, [refreshToken, refresh]);
  const selected = fields.find((f) => f.id === selectedId) ?? null;
  const fieldAnalyses = analyses.filter((a) => a.field_id === selectedId);
  const requestedId =
    fieldAnalyses.find((a) => a.id === analysisId)?.id ||
    fieldAnalyses[0]?.id ||
    "";
  useEffect(() => {
    let cancelled = false;
    setAnalysis(null);
    setPoint(null);
    setSelectedEvent(null);
    setRange(null);
    setMetric("ndvi");
    setLoadError("");
    if (!requestedId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .analysis(requestedId)
      .then((result) => {
        if (!cancelled) {
          setAnalysis(result);
          setActiveLayer("none");
        }
      })
      .catch((error) => {
        if (!cancelled) setLoadError(message(error));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestedId, selectedId]);
  const points = useMemo<PlotPoint[]>(
    () =>
      analysis?.series.map((p) => ({
        ...p,
        temperature: p.temperature_c,
        precipitation: p.precipitation_mm,
      })) ?? [],
    [analysis],
  );
  const weather = points.some(
    (p) => p.temperature != null || p.precipitation != null,
  );
  function chooseField(id: string) {
    setSelectedId(id);
    setAnalysisId("");
    setLibrary(false);
  }
  function openDraft(items: Array<{ name: string; geometry: Geometry }>) {
    setDraft(items);
    setDraftIndex("0");
    setName(items[0].name);
    setLibrary(false);
  }
  async function importGeoJson(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      if (file.size > 10 * 1024 * 1024)
        throw new Error(
          "GeoJSON больше 10 МБ. Выберите файл с контурами нужных территорий.",
        );
      openDraft(parsePolygons(JSON.parse(await file.text())));
    } catch (error) {
      onNotice(message(error));
    }
  }
  async function saveField() {
    const item = draft[Number(draftIndex)];
    if (!item || !name.trim()) return;
    setSaving(true);
    try {
      const field = await api.createField(name.trim(), item.geometry);
      await refresh();
      setSelectedId(field.id);
      setAnalysisId("");
      setDraft([]);
    } catch (error) {
      onNotice(message(error));
    } finally {
      setSaving(false);
    }
  }
  async function discover() {
    if (viewport[2] - viewport[0] > 0.5 || viewport[3] - viewport[1] > 0.5) {
      onNotice(
        "Приблизьте карту к нужному району, затем повторите поиск контуров.",
      );
      return;
    }
    setDiscovering(true);
    try {
      const result = await api.discover(viewport);
      setCandidates(result);
      if (!result.length)
        onNotice(
          "В этом окне OSM не нашёл сельскохозяйственных контуров. Можно нарисовать территорию или импортировать GeoJSON.",
        );
    } catch (error) {
      onNotice(message(error));
    } finally {
      setDiscovering(false);
    }
  }
  const days = (Date.parse(dateTo) - Date.parse(dateFrom)) / 86400000;
  const periodError =
    !dateFrom || !dateTo
      ? "Укажите обе даты."
      : dateFrom.slice(0, 4) !== dateTo.slice(0, 4)
        ? "Выберите период внутри одного календарного года."
        : days < 30
          ? "Нужен период не короче 30 дней."
          : null;
  async function run() {
    if (!selected || periodError) return;
    setSubmitting(true);
    try {
      onJob(
        await api.runAnalysis({
          field_id: selected.id,
          date_from: dateFrom,
          date_to: dateTo,
          history_years: Number(historyYears),
          max_cloud_cover: Number(cloud),
        }),
      );
      setRunOpen(false);
    } catch (error) {
      onNotice(message(error));
    } finally {
      setSubmitting(false);
    }
  }
  function selectEvent(index: number) {
    setSelectedEvent(index);
    if (analysis) setRange(eventWindow(analysis.events[index], points));
    setLayout("overview");
  }
  const snapshot = analysis?.period;
  return (
    <section className="monitoring-page">
      <div className="page-heading">
        <div>
          <h1>
            Мониторинг территорий<span className="heading-dot">.</span>
          </h1>
        </div>
        <Button
          leftSection={<Plus size={16} />}
          onClick={() => {
            setLibrary(true);
            setSearch("");
          }}
          variant="light"
        >
          Добавить территорию
        </Button>
      </div>
      <div className="workspace-toolbar">
        <button className="territory-picker" onClick={() => setLibrary(true)}>
          <span className="territory-icon">
            <MapPinned size={19} />
          </span>
          <span>
            <small>ТЕРРИТОРИЯ</small>
            <b>{selected?.name ?? "Выберите территорию"}</b>
          </span>
          <ChevronDown size={16} />
        </button>
        <div className="toolbar-divider" />
        <div className="period-summary">
          <CalendarDays size={16} />
          <span>
            {snapshot
              ? `${snapshot.from} — ${snapshot.to}`
              : "Период не выбран"}
            <small>
              {snapshot
                ? `${snapshot.history_years} года истории · сохранённый результат`
                : "Задайте период в новом анализе"}
            </small>
          </span>
        </div>
        <div className="toolbar-spacer" />
        <Tooltip label="История выбранной территории">
          <ActionIcon
            variant="subtle"
            color="gray"
            size="lg"
            onClick={() => setHistory(true)}
            aria-label="История анализов"
          >
            <History size={18} />
          </ActionIcon>
        </Tooltip>
        <Button
          disabled={!selected || busy}
          loading={submitting}
          leftSection={<Plus size={15} />}
          onClick={() => {
            setRunOpen(true);
          }}
        >
          Новый анализ
        </Button>
      </div>
      <div className="workspace-options">
        <SegmentedControl
          size="xs"
          value={layout}
          onChange={setLayout}
          data={[
            { value: "overview", label: "Обзор" },
            { value: "map", label: "Карта" },
            { value: "timeline", label: "Динамика" },
          ]}
        />
        <div className="workspace-meta">
          <span className="status-dot online" />
          {selected
            ? `${selected.area_ha.toFixed(1)} га`
            : "Нет выбранной территории"}
          <span>·</span>
          {loading
            ? "Загружаем анализ…"
            : analysis
              ? `${analysis.quality.current_observations ?? 0} наблюдений за период`
              : "Готово к исследованию"}
        </div>
      </div>
      {loadError && (
        <Alert color="orange" mb="md" title="Не удалось открыть анализ">
          {loadError}
          <Button variant="subtle" onClick={() => void refresh()}>
            Обновить список
          </Button>
        </Alert>
      )}
      <div className={`analysis-workspace layout-${layout}`}>
        <div className="visualization-stack">
          <div className="map-panel" hidden={layout === "timeline"}>
            <MapPane
              fields={fields}
              selected={selected}
              analysis={analysis}
              activeLayer={activeLayer}
              opacity={opacity}
              showFields={showFields}
              focusToken={focusToken}
              onField={chooseField}
              onDraw={(geometry) =>
                openDraft([{ name: "Новая территория", geometry }])
              }
              onViewport={setViewport}
            />
            <div className="map-top-right">
              <Popover width={285} position="bottom-end" shadow="lg">
                <Popover.Target>
                  <Button
                    variant="default"
                    leftSection={<Layers size={16} />}
                    size="xs"
                  >
                    Слои
                  </Button>
                </Popover.Target>
                <Popover.Dropdown>
                  <h4 className="popover-title">Отображение карты</h4>
                  <Select
                    label="Растровый слой"
                    value={activeLayer}
                    onChange={(v) => setActiveLayer(v ?? "none")}
                    data={[
                      { value: "none", label: "Только подложка" },
                      ...(analysis?.layers ?? []).map((l) => ({
                        value: l.key,
                        label: l.label,
                      })),
                    ]}
                  />
                  {!analysis?.layers.length && (
                    <p className="muted small">
                      В этом анализе растровые слои не получены. Доступны
                      контуры и временной ряд.
                    </p>
                  )}
                  <p className="muted small">
                    Слой относится к сохранённому снимку. Выбор даты на графике
                    не меняет растр.
                  </p>
                  <Checkbox
                    label="Контуры территорий"
                    checked={showFields}
                    onChange={(e) => setShowFields(e.currentTarget.checked)}
                    mt="md"
                  />
                  <div className="slider-label">
                    Непрозрачность растра <b>{Math.round(opacity * 100)}%</b>
                  </div>
                  <Slider
                    min={0}
                    max={1}
                    step={0.05}
                    value={opacity}
                    onChange={setOpacity}
                    disabled={activeLayer === "none"}
                    label={(v) => `${Math.round(v * 100)}%`}
                  />
                </Popover.Dropdown>
              </Popover>
              <Tooltip label="Показать выбранную территорию">
                <ActionIcon
                  variant="default"
                  size={30}
                  onClick={() => setFocusToken((v) => v + 1)}
                  aria-label="Показать выбранную территорию"
                >
                  <Crosshair size={16} />
                </ActionIcon>
              </Tooltip>
            </div>
            {!selected && (
              <div className="map-welcome">
                <MapPinned size={30} />
                <h2>Начните с места на карте</h2>
                <p>
                  Импортируйте контур или нажмите ✎ и отметьте минимум три
                  вершины.
                </p>
                <Button
                  variant="light"
                  onClick={() => fileRef.current?.click()}
                >
                  Импорт GeoJSON
                </Button>
              </div>
            )}
            <div className="map-bottom-left">
              <i className="dot observed" />
              Граница территории
              {activeLayer !== "none" && (
                <span>
                  · {analysis?.layers.find((l) => l.key === activeLayer)?.label}
                </span>
              )}
            </div>
            {loading && (
              <div className="map-loading">
                <Loader size="sm" />
                <span>Открываем сохранённые данные</span>
              </div>
            )}
          </div>
          <div className="trajectory-panel" hidden={layout === "map"}>
            <div className="panel-heading">
              <div>
                <h3>
                  {metric === "ndvi"
                    ? "Динамика растительности"
                    : metric === "zscore"
                      ? "Отклонение от исторической нормы"
                      : "Погодный контекст"}
                </h3>
              </div>
              {range && (
                <Badge color="orange" variant="light">
                  Период события
                </Badge>
              )}
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
              weather={weather}
              reset={() => {
                setRange(null);
                setSelectedEvent(null);
              }}
            />
            {tabular ? (
              <SeriesTable points={points} range={range} onPoint={setPoint} />
            ) : (
              <Timeline
                showEvents={showEvents}
                points={points}
                events={analysis?.events ?? []}
                metric={metric}
                visible={visible}
                range={range}
                onPoint={setPoint}
              />
            )}
            <div className="chart-footnote">
              <span>
                Прокрутка — масштаб · ползунок — период · точка — значения
              </span>
              <span>Пропуски не являются наблюдениями</span>
            </div>
          </div>
        </div>
        <EventPanel
          analysis={analysis}
          selectedEvent={selectedEvent}
          onEvent={selectEvent}
          point={point}
        />
      </div>
      <input
        hidden
        ref={fileRef}
        type="file"
        accept=".json,.geojson"
        onChange={importGeoJson}
      />
      <Drawer
        opened={library}
        onClose={() => setLibrary(false)}
        title="Территории"
        size="md"
      >
        <div className="drawer-intro">
          <p>Выберите участок или добавьте новый контур.</p>
          <Button
            fullWidth
            variant="light"
            leftSection={<Upload size={16} />}
            onClick={() => fileRef.current?.click()}
          >
            Импортировать GeoJSON
          </Button>
          <Button
            fullWidth
            mt="sm"
            variant="default"
            leftSection={<Search size={16} />}
            loading={discovering}
            onClick={discover}
          >
            Найти контуры OSM в окне карты
          </Button>
          <p className="muted small">
            Для рисования закройте эту панель и нажмите ✎ на карте.
          </p>
        </div>
        <TextInput
          placeholder="Название территории"
          aria-label="Поиск территории"
          leftSection={<Search size={16} />}
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          mb="md"
        />
        <div className="library-list">
          {fields
            .filter((f) => f.name.toLowerCase().includes(search.toLowerCase()))
            .map((field) => (
              <button
                key={field.id}
                className={field.id === selectedId ? "is-selected" : ""}
                onClick={() => chooseField(field.id)}
              >
                <MapPinned size={20} />
                <span>
                  <b>{field.name}</b>
                  <small>
                    {field.area_ha.toFixed(1)} га ·{" "}
                    {analyses.filter((a) => a.field_id === field.id).length}{" "}
                    анализов
                  </small>
                </span>
                <ChevronDown size={15} />
              </button>
            ))}
          {!fields.length && (
            <p className="muted">Сохранённых территорий пока нет.</p>
          )}
        </div>
        {candidates.length > 0 && (
          <>
            <h4>Контуры из OSM · {candidates.length}</h4>
            <p className="muted small">
              Импортируйте нужный контур, затем проверьте его на карте.
            </p>
            {candidates.map((c) => (
              <Button
                fullWidth
                variant="subtle"
                justify="space-between"
                key={c.source_id}
                onClick={() =>
                  openDraft([{ name: c.name, geometry: c.geometry }])
                }
                rightSection={<Plus size={15} />}
              >
                {c.name || c.landuse || "Территория"}
              </Button>
            ))}
          </>
        )}
        {selected && (
          <Button
            mt="xl"
            color="red"
            variant="subtle"
            leftSection={<Trash2 size={15} />}
            onClick={() => setDeleteOpen(true)}
          >
            Удалить выбранную территорию
          </Button>
        )}
      </Drawer>
      <Drawer
        opened={history}
        onClose={() => setHistory(false)}
        title="История анализов"
        position="right"
        size="md"
      >
        <h3>{selected?.name ?? "Территория не выбрана"}</h3>
        <p className="muted">
          Открытие результата не запускает новый сбор данных.
        </p>
        {fieldAnalyses.map((item) => (
          <button
            className={`history-card ${requestedId === item.id ? "is-selected" : ""}`}
            key={item.id}
            onClick={() => {
              setAnalysisId(item.id);
              setHistory(false);
            }}
          >
            <History size={19} />
            <span>
              <b>{item.title}</b>
              <small>Сохранён {item.created_at?.slice(0, 10)}</small>
            </span>
            <ArrowDownToLine size={16} />
          </button>
        ))}
        {!fieldAnalyses.length && (
          <div className="small-empty">
            <History size={28} />
            <b>История пока пуста</b>
            <p>Запустите первый анализ этой территории.</p>
          </div>
        )}
      </Drawer>
      <Modal
        opened={draft.length > 0}
        onClose={() => !saving && setDraft([])}
        title="Сохранить территорию"
      >
        <p className="muted">
          Контур будет сохранён локально. Спутниковый сбор запускается отдельно.
        </p>
        {draft.length > 1 && (
          <Select
            label={`В файле ${draft.length} объектов. Выберите контур`}
            value={draftIndex}
            onChange={(v) => {
              setDraftIndex(v ?? "0");
              setName(draft[Number(v)].name);
            }}
            data={draft.map((d, i) => ({
              value: String(i),
              label: `${i + 1}. ${d.name}`,
            }))}
          />
        )}
        <TextInput
          label="Название территории"
          placeholder="Например, Северное поле"
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          mt="md"
          data-autofocus
        />
        <Button
          mt="lg"
          fullWidth
          loading={saving}
          disabled={!name.trim()}
          onClick={saveField}
        >
          Сохранить контур
        </Button>
      </Modal>
      <Modal
        opened={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Удалить территорию?"
        size="sm"
      >
        <p>
          Территория «{selected?.name}» будет удалена из списка. Это действие
          нельзя отменить в интерфейсе.
        </p>
        <Button
          color="red"
          fullWidth
          loading={saving}
          onClick={async () => {
            if (!selected) return;
            setSaving(true);
            try {
              await api.deleteField(selected.id);
              setSelectedId("");
              setAnalysisId("");
              setDeleteOpen(false);
              await refresh();
            } catch (e) {
              onNotice(message(e));
            } finally {
              setSaving(false);
            }
          }}
        >
          Удалить территорию
        </Button>
      </Modal>
      <Modal
        opened={runOpen}
        onClose={() => !submitting && setRunOpen(false)}
        title="Новый спутниковый анализ"
        size="lg"
      >
        <div className="analysis-target">
          <MapPinned size={24} />
          <div>
            <b>{selected?.name}</b>
            <small>{selected?.area_ha.toFixed(1)} га</small>
          </div>
        </div>
        <p className="muted">
          Получим спутниковые и погодные данные, построим динамику и проверим
          отклонения от истории.
        </p>
        <div className="form-grid">
          <TextInput
            type="date"
            label="Начало периода"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.currentTarget.value)}
          />
          <TextInput
            type="date"
            label="Конец периода"
            value={dateTo}
            onChange={(e) => setDateTo(e.currentTarget.value)}
          />
          <NumberInput
            label="История, лет"
            min={2}
            max={8}
            allowDecimal={false}
            value={historyYears}
            onChange={setHistoryYears}
          />
          <NumberInput
            label="Облачность сцены, до %"
            min={0}
            max={100}
            value={cloud}
            onChange={setCloud}
          />
        </div>
        <p className="muted small">
          Облачность — предварительный фильтр. Пригодность измерений
          определяется по пикселям внутри территории.
        </p>
        {periodError && (
          <Alert color="orange" mt="sm">
            {periodError}
          </Alert>
        )}
        <div className="context-note">
          <History size={18} />
          <p>
            Сбор может занять несколько минут и зависит от доступности
            источников. Можно продолжить работу, пока анализ выполняется.
          </p>
        </div>
        <Button
          fullWidth
          mt="lg"
          disabled={
            !!periodError || historyYears === "" || cloud === "" || busy
          }
          loading={submitting}
          onClick={run}
        >
          Запустить анализ
        </Button>
      </Modal>
    </section>
  );
}
function message(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
