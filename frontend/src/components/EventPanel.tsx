import { useEffect, useState } from "react";
import { Accordion, Badge, Tabs } from "@mantine/core";
import {
  ArrowUpRight,
  Check,
  CircleDashed,
  CloudSun,
  Focus,
  Layers,
  Satellite,
  ShieldCheck,
} from "lucide-react";
import type { Analysis } from "../types";
import {
  type PlotPoint,
  type VegetationEvent,
  evidenceEntries,
  eventTitle,
  metricLabel,
  shortDate,
} from "../lib/visualization";
export function EventCards({
  events,
  selected,
  onSelect,
}: {
  events: VegetationEvent[];
  selected: number | null;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="event-list">
      {events.length ? (
        events.map((event, index) => (
          <button
            key={`${event.start}-${index}`}
            className={`event-card ${selected === index ? "is-selected" : ""}`}
            onClick={() => onSelect(index)}
          >
            <div className="event-top">
              <span
                className={`event-signal ${event.kind === "PHENOLOGY_SHIFT" ? "phase" : ""}`}
              />
              <b>{eventTitle(event)}</b>
              <ArrowUpRight size={15} />
            </div>
            <span className="event-dates">
              {String(event.start)} — {String(event.end)}
            </span>
            <p>
              {String(
                event.interpretation ||
                  "Выберите событие, чтобы рассмотреть период.",
              )}
            </p>
            <span className="event-confidence">
              Поддержка данными:{" "}
              {(
                { HIGH: "высокая", MEDIUM: "средняя", LOW: "низкая" } as Record<
                  string,
                  string
                >
              )[String(event.confidence)] ?? "не указана"}
            </span>
          </button>
        ))
      ) : (
        <div className="small-empty">
          <ShieldCheck size={25} />
          <b>События не выделены</b>
          <p>
            На этом периоде алгоритм не выделил устойчивых событий. Это не
            оценка урожайности или здоровья растений.
          </p>
        </div>
      )}
    </div>
  );
}
export function EventPanel({
  analysis,
  selectedEvent,
  onEvent,
  point,
}: {
  analysis: Analysis | null;
  selectedEvent: number | null;
  onEvent: (index: number) => void;
  point: PlotPoint | null;
}) {
  const [tab, setTab] = useState<string | null>("summary");
  useEffect(() => {
    if (selectedEvent != null) setTab("events");
  }, [selectedEvent]);
  useEffect(() => {
    if (point) setTab("summary");
  }, [point]);
  if (!analysis)
    return (
      <aside className="inspector">
        <div className="inspector-heading">
          <Focus size={17} />
          <b>Об анализе</b>
        </div>
        <div className="inspector-placeholder">
          <CircleDashed size={38} />
          <h3>Начните с территории</h3>
          <p>
            Выберите сохранённый результат или задайте период нового анализа.
            Здесь появятся состояние, события и источники.
          </p>
        </div>
      </aside>
    );
  const state = analysis.state.condition;
  const condition =
    state === "NORMAL"
      ? "Без устойчивого снижения"
      : state === "UNKNOWN"
        ? "Недостаточно истории"
        : state === "CRITICAL"
          ? "Сильное отклонение"
          : "Есть отклонения";
  const event = selectedEvent == null ? null : analysis.events[selectedEvent];
  const sourceNames: Record<string, string> = {
    "sentinel-2": "Sentinel-2",
    landsat: "Landsat",
    era5: "Погода · ERA5",
  };
  return (
    <aside className="inspector">
      <div className="inspector-heading">
        <Focus size={17} />
        <b>Результат анализа</b>
      </div>
      <Tabs value={tab} onChange={setTab}>
        <Tabs.List grow>
          <Tabs.Tab value="summary">Сводка</Tabs.Tab>
          <Tabs.Tab value="events">
            События <span className="count">{analysis.events.length}</span>
          </Tabs.Tab>
          <Tabs.Tab value="sources">Данные</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="summary">
          <div className="inspector-content">
            <span className="eyebrow">СОСТОЯНИЕ ЗА ПЕРИОД</span>
            <div
              className={`condition-badge ${state === "NORMAL" ? "normal" : state === "UNKNOWN" ? "unknown" : "warning"}`}
            >
              <span className="status-dot online" />
              {condition}
            </div>
            <p className="muted small">
              {analysis.period.from} — {analysis.period.to}
            </p>
            <div className="metric-grid">
              <Metric
                label="Последний NDVI"
                value={metricLabel(analysis.state.latest_ndvi)}
              />
              <Metric
                label="Историческая норма"
                value={metricLabel(analysis.state.latest_expected)}
              />
              <Metric
                label="Минимум отклонения"
                value={
                  analysis.state.min_zscore == null
                    ? "—"
                    : `${metricLabel(analysis.state.min_zscore, 2)} σ`
                }
              />
              <Metric
                label="Наблюдений в периоде"
                value={String(analysis.quality.current_observations ?? "—")}
              />
            </div>
            <div className="context-note">
              <ShieldCheck size={18} />
              <p>
                Сравнение с историей участка. Интерпретация опирается на
                доступные измерения и не является агрономическим диагнозом.
              </p>
            </div>
            {point ? (
              <div className="point-inspector">
                <span className="eyebrow">
                  ВЫБРАННАЯ ТОЧКА · {shortDate(point.date)}
                </span>
                <div className="key-value">
                  <span>Наблюдение</span>
                  <b>{metricLabel(point.observed)}</b>
                </div>
                <div className="key-value">
                  <span>Восстановление</span>
                  <b>{metricLabel(point.restored)}</b>
                </div>
                <div className="key-value">
                  <span>Норма</span>
                  <b>{metricLabel(point.expected)}</b>
                </div>
                <div className="key-value">
                  <span>Источник</span>
                  <b>{point.source || "Нет наблюдения"}</b>
                </div>
              </div>
            ) : (
              <p className="interaction-hint">
                Нажмите на точку графика, чтобы увидеть её значения и источник.
              </p>
            )}
            <button className="text-link" onClick={() => setTab("sources")}>
              Проверить доступность данных <ArrowUpRight size={14} />
            </button>
          </div>
        </Tabs.Panel>
        <Tabs.Panel value="events">
          <div className="inspector-content">
            <p className="muted small">
              Выберите событие — график приблизит соответствующий период.
            </p>
            <EventCards
              events={analysis.events}
              selected={selectedEvent}
              onSelect={onEvent}
            />
            {event && (
              <div className="evidence">
                <h4>Основания интерпретации</h4>
                {evidenceEntries(event).map(([key, value]) => (
                  <div className="key-value" key={key}>
                    <span>{key}</span>
                    <b>{value}</b>
                  </div>
                ))}
                <p className="muted small">
                  Поддержка данными — инженерная оценка, не вероятность
                  конкретной причины.
                </p>
              </div>
            )}
          </div>
        </Tabs.Panel>
        <Tabs.Panel value="sources">
          <div className="inspector-content">
            <span className="eyebrow">ПОКРЫТИЕ И ОГРАНИЧЕНИЯ</span>
            {Object.entries(analysis.sources).map(([name, raw]) => {
              const source = raw as {
                usable?: number;
                candidate_scenes?: number;
                available?: boolean;
                errors?: string[];
              };
              const ready =
                source.usable !== undefined
                  ? source.usable > 0
                  : source.available;
              return (
                <div className="source-card" key={name}>
                  <div className="source-top">
                    {name === "era5" ? (
                      <CloudSun size={18} />
                    ) : (
                      <Satellite size={18} />
                    )}
                    <b>{sourceNames[name] ?? name}</b>
                    <Badge size="xs" color={ready ? "teal" : "gray"}>
                      {ready ? "Есть данные" : "Недоступен"}
                    </Badge>
                  </div>
                  <p>
                    {source.usable !== undefined
                      ? `${source.usable} пригодных из ${source.candidate_scenes ?? 0} выбранных сцен`
                      : "Погодный контекст для интерпретации событий"}
                  </p>
                  {!!source.errors?.length && (
                    <Accordion variant="default">
                      <Accordion.Item value="errors">
                        <Accordion.Control>
                          Ограничения · {source.errors.length}
                        </Accordion.Control>
                        <Accordion.Panel>
                          <ul className="source-errors">
                            {source.errors.map((error, i) => (
                              <li key={i}>{error}</li>
                            ))}
                          </ul>
                        </Accordion.Panel>
                      </Accordion.Item>
                    </Accordion>
                  )}
                </div>
              );
            })}
            <div className="context-note">
              <Layers size={18} />
              <p>
                NDRE и SWIR рассчитываются на аналитической сетке. Отображение
                карты не увеличивает нативное разрешение спутника.
              </p>
            </div>
          </div>
        </Tabs.Panel>
      </Tabs>
    </aside>
  );
}
function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
