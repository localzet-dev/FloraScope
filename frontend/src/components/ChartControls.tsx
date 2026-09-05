import { ActionIcon, SegmentedControl, Tooltip } from "@mantine/core";
import {
  RotateCcw,
  Table2,
  ChartNoAxesCombined,
  CalendarRange,
} from "lucide-react";
import { type Metric, type Trace, traceLabels } from "../lib/visualization";
export function ChartControls({
  metric,
  setMetric,
  visible,
  setVisible,
  weather = false,
  reset,
  showEvents,
  setShowEvents,
  tabular,
  setTabular,
}: {
  metric: Metric;
  setMetric: (m: Metric) => void;
  visible: Trace[];
  setVisible: (v: Trace[]) => void;
  weather?: boolean;
  reset: () => void;
  showEvents: boolean;
  setShowEvents: (v: boolean) => void;
  tabular: boolean;
  setTabular: (v: boolean) => void;
}) {
  return (
    <div className="chart-controls">
      {tabular ? (
        <span className="muted small">
          NDVI и отклонение · значения за выбранный период
        </span>
      ) : (
        <>
          <SegmentedControl
            size="xs"
            value={metric}
            onChange={(v) => setMetric(v as Metric)}
            data={[
              { value: "ndvi", label: "Растительность" },
              { value: "zscore", label: "Отклонение" },
              ...(weather ? [{ value: "weather", label: "Погода" }] : []),
            ]}
          />
          <div className="trace-controls">
            {metric === "ndvi" &&
              (["observed", "restored", "expected"] as Trace[]).map((key) => (
                <button
                  key={key}
                  className={`trace-toggle ${visible.includes(key) ? "" : "off"}`}
                  aria-pressed={visible.includes(key)}
                  onClick={() =>
                    setVisible(
                      visible.includes(key)
                        ? visible.filter((v) => v !== key)
                        : [...visible, key],
                    )
                  }
                >
                  <i className={`dot ${key}`} />
                  {traceLabels[key]}
                </button>
              ))}
          </div>
          <Tooltip
            label={
              showEvents ? "Скрыть периоды событий" : "Показать периоды событий"
            }
          >
            <ActionIcon
              variant={showEvents ? "light" : "subtle"}
              color="orange"
              onClick={() => setShowEvents(!showEvents)}
              aria-label="Периоды событий"
              aria-pressed={showEvents}
            >
              <CalendarRange size={15} />
            </ActionIcon>
          </Tooltip>
        </>
      )}
      <Tooltip
        label={tabular ? "Показать график" : "Показать таблицу значений"}
      >
        <ActionIcon
          variant={tabular ? "light" : "subtle"}
          color="gray"
          onClick={() => setTabular(!tabular)}
          aria-label={tabular ? "Показать график" : "Показать таблицу значений"}
        >
          {tabular ? <ChartNoAxesCombined size={15} /> : <Table2 size={15} />}
        </ActionIcon>
      </Tooltip>
      <Tooltip label="Показать весь период">
        <ActionIcon
          variant="subtle"
          color="gray"
          onClick={reset}
          aria-label="Показать весь период"
        >
          <RotateCcw size={15} />
        </ActionIcon>
      </Tooltip>
    </div>
  );
}
