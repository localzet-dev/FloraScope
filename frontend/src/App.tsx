import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Modal, Tooltip } from "@mantine/core";
import {
  BookOpen,
  ChartNoAxesCombined,
  CircleHelp,
  FlaskConical,
  Leaf,
  Map,
} from "lucide-react";
import { useStoredState } from "./lib/useStoredState";
import { readStored, writeStored } from "./lib/storage";
import { api } from "./lib/api";
import type { Job, SystemState } from "./types";
import { BenchmarkView } from "./components/BenchmarkView";
import { JobBar } from "./components/JobBar";
import { MonitoringView } from "./components/MonitoringView";
import { ResearchView } from "./components/ResearchView";

type Tab = "monitoring" | "benchmark" | "research";
const destinations = [
  { id: "monitoring" as const, label: "Мониторинг", icon: Map },
  {
    id: "benchmark" as const,
    label: "Восстановление",
    icon: ChartNoAxesCombined,
  },
  { id: "research" as const, label: "Метод и проверка", icon: FlaskConical },
];
export default function App() {
  const [tab, setTab] = useStoredState<Tab>("tab", "monitoring");
  const [system, setSystem] = useState<SystemState | null>(null);
  const [connectionFailed, setConnectionFailed] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [restoringJob, setRestoringJob] = useState(true);
  const [notice, setNotice] = useState("");
  const [help, setHelp] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);
  const refresh = useCallback(async () => {
    try {
      setSystem(await api.system());
      setConnectionFailed(false);
    } catch {
      setSystem(null);
      setConnectionFailed(true);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    let active = true;
    api
      .jobs()
      .then((jobs) => {
        if (!active) return;
        const latest =
          jobs.find((j) => ["running", "queued"].includes(j.state)) ?? jobs[0];
        if (latest && latest.id !== readStored("dismissedJob", "")) {
          setJob(latest);
          // Для старой версии без сохранённого выбора находим поле по задаче.
          if (!readStored("field", "") && latest.payload?.field_id) {
            writeStored("field", latest.payload.field_id);
            if (latest.payload.date_from) writeStored("dateFrom", latest.payload.date_from);
            if (latest.payload.date_to) writeStored("dateTo", latest.payload.date_to);
            if (latest.payload.history_years != null) writeStored("historyYears", latest.payload.history_years);
            if (latest.payload.max_cloud_cover != null) writeStored("cloud", latest.payload.max_cloud_cover);
          }
        }
      })
      .catch((error) => {
        if (active)
          setNotice(`Не удалось восстановить статус расчёта: ${error}`);
      })
      .finally(() => {
        if (active) setRestoringJob(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.state)) return;
    let active = true;
    let timer: number;
    const poll = async () => {
      try {
        const next = await api.job(job.id);
        if (!active) return;
        setJob(next);
        if (next.state === "completed") {
          setRefreshToken((v) => v + 1);
          void refresh();
        }
        if (next.state === "failed") setNotice(next.error ?? next.message);
      } catch (error) {
        if (active) setNotice(String(error));
      }
      if (active) timer = window.setTimeout(poll, 1800);
    };
    timer = window.setTimeout(poll, 1000);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [job?.id, job?.state, refresh]);
  const busy =
    restoringJob || (!!job && ["running", "queued"].includes(job.state));
  return (
    <div className="app-shell">
      <aside className="app-rail">
        <div className="brand-symbol" aria-label="FloraScope">
          <Leaf size={23} />
        </div>
        <div className="rail-nav">
          {destinations.map(({ id, label, icon: Icon }) => (
            <Tooltip key={id} label={label} position="right">
              <button
                className={`rail-button ${tab === id ? "is-active" : ""}`}
                onClick={() => setTab(id)}
                aria-label={label}
                aria-current={tab === id ? "page" : undefined}
              >
                <Icon size={21} />
              </button>
            </Tooltip>
          ))}
        </div>
        <Tooltip label="Как читать анализ" position="right">
          <button
            className="rail-button rail-help"
            onClick={() => setHelp(true)}
            aria-label="Как читать анализ"
          >
            <CircleHelp size={21} />
          </button>
        </Tooltip>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div className="brand">
            flora<span>scope</span>
          </div>
          <nav className="top-nav" aria-label="Разделы">
            {destinations.map(({ id, label }) => (
              <button
                key={id}
                className={tab === id ? "is-active" : ""}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>
          {connectionFailed && (
            <span className="connection" role="status">
              Нет связи с сервером
            </span>
          )}
        </header>
        {notice && (
          <Alert
            color="orange"
            title="Сообщение"
            withCloseButton
            onClose={() => setNotice("")}
            className="global-notice"
          >
            {notice}
          </Alert>
        )}
        {job && (
          <JobBar
            job={job}
            onClose={() => {
              writeStored("dismissedJob", job.id);
              setJob(null);
            }}
          />
        )}
        <main>
          <div hidden={tab !== "monitoring"}>
            {!restoringJob && <MonitoringView
              refreshToken={refreshToken}
              onJob={setJob}
              onNotice={setNotice}
              busy={busy}
            />}
          </div>
          {tab === "benchmark" && (
            <BenchmarkView
              system={system}
              refreshToken={refreshToken}
              onJob={setJob}
              busy={busy}
              onNotice={(m) => {
                setNotice(m);
                void refresh();
              }}
            />
          )}
          {tab === "research" && <ResearchView />}
        </main>
      </div>
      <Modal
        opened={help}
        onClose={() => setHelp(false)}
        title="Как читать FloraScope"
        size="lg"
      >
        <div className="help-intro">
          <BookOpen size={28} />
          <h2>Обозначения на графике</h2>
        </div>
        <div className="definition">
          <i className="dot observed" />
          <div>
            <b>Наблюдения</b>
            <p>
              Значения из спутниковых данных, прошедшие обработку. Это опорные
              точки анализа.
            </p>
          </div>
        </div>
        <div className="definition">
          <i className="dot restored" />
          <div>
            <b>Восстановление</b>
            <p>
              Расчётные значения между наблюдениями. Они помогают увидеть
              траекторию, но не являются новыми измерениями.
            </p>
          </div>
        </div>
        <div className="definition">
          <i className="dot expected" />
          <div>
            <b>Историческая норма</b>
            <p>
              Ожидание по другим годам этого участка. Отсутствие нормы означает
              недостаток истории.
            </p>
          </div>
        </div>
        <Alert color="blue" mt="md">
          Событие описывает отклонение. Его причина — осторожная интерпретация
          доступных данных, а не диагноз.
        </Alert>
        <Button fullWidth mt="lg" onClick={() => setHelp(false)}>
          Закрыть
        </Button>
      </Modal>
    </div>
  );
}
