import { ActionIcon, Progress } from "@mantine/core";
import { CheckCircle2, LoaderCircle, TriangleAlert, X } from "lucide-react";
import type { Job } from "../types";
export function JobBar({ job, onClose }: { job: Job; onClose: () => void }) {
  const running = ["queued", "running"].includes(job.state);
  return (
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
  );
}
