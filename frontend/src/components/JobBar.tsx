import { useState } from "react";
import { JobLog } from "./JobLog";
import { ActionIcon, Button, Progress } from "@mantine/core";
import { CheckCircle2, LoaderCircle, TriangleAlert, X } from "lucide-react";
import type { Job } from "../types";
export function JobBar({ job, onClose }: { job: Job; onClose: () => void }) {
  const [opened, setOpened] = useState(false);
  const running = ["queued", "running"].includes(job.state);
  return (
    <>
      <JobLog job={job} opened={opened} onClose={() => setOpened(false)} />
      <div className={`jobbar ${job.state}`} role="status" aria-live="polite">
        {running ? (
          <LoaderCircle className="spin" size={18} />
        ) : job.state === "completed" ? (
          <CheckCircle2 size={18} />
        ) : (
          <TriangleAlert size={18} />
        )}
        <div className="job-copy">
          <b>
            {running
              ? "Обрабатываем данные"
              : job.state === "completed"
                ? "Результат готов"
                : "Обработка остановлена"}
          </b>
          <span>{job.message}</span>
        </div>
        {running && <Progress value={job.progress} w={120} size="xs" />}
        <Button variant="subtle" size="xs" onClick={() => setOpened(true)}>
          Журнал
        </Button>
        <span className="mono">{job.progress}%</span>
        {!running && (
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={onClose}
            aria-label="Закрыть статус"
          >
            <X size={15} />
          </ActionIcon>
        )}
      </div>
    </>
  );
}
