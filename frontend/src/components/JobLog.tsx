import { useEffect, useState } from "react";
import { Alert, Modal } from "@mantine/core";
import { api } from "../lib/api";
import type { Job } from "../types";
export function JobLog({
  job,
  opened,
  onClose,
}: {
  job: Job;
  opened: boolean;
  onClose: () => void;
}) {
  const [events, setEvents] = useState<
    Array<{ id: number; created_at: string; stage: string; message: string }>
  >([]);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!opened) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    setEvents([]);
    const poll = async () => {
      try {
        const next = await api.jobEvents(job.id);
        if (active) {
          setEvents(next);
          setError("");
        }
      } catch (error) {
        if (active) setError(String(error));
      }
      if (active) timer = setTimeout(poll, 2000);
    };
    void poll();
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      active = false;
      clearTimeout(timer);
      clearInterval(clock);
    };
  }, [opened, job.id]);
  const last = events.at(-1);
  const running = ["queued", "running"].includes(job.state);
  return (
    <Modal opened={opened} onClose={onClose} title="Журнал расчёта" size="xl">
      <p className="small muted">{job.message}</p>
      {running && last && (
        <p className="small muted">
          С последнего сообщения:{" "}
          {Math.max(0, Math.floor((now - Date.parse(last.created_at)) / 1000))}{" "}
          с. Обновляем журнал каждые 2 секунды; ожидание сети может идти без
          новых сообщений.
        </p>
      )}
      {error && (
        <Alert color="orange">Не удалось обновить журнал: {error}</Alert>
      )}
      {!events.length && (
        <p className="small muted">
          {running
            ? "Ожидаем сообщения…"
            : "Для этого расчёта подробный журнал не записывался. Выше показан сохранённый итог."}
        </p>
      )}
      <ol className="job-log">
        {events.map((event) => (
          <li
            key={event.id}
            className={
              ["WARNING", "FAILED", "INTERRUPTED"].includes(event.stage)
                ? "job-log-warning"
                : ""
            }
          >
            <time dateTime={event.created_at}>
              {new Date(event.created_at).toLocaleString("ru-RU")}
            </time>
            <span>{event.message}</span>
          </li>
        ))}
      </ol>
    </Modal>
  );
}
