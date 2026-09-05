import type { Geometry } from "geojson";
import type { Analysis, Field, Job, SystemState } from "../types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail ?? body);
    } catch {
      // Иногда nginx/прокси вернёт не JSON. Статуса в таком случае достаточно.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  system: () => request<SystemState>("/api/v1/system"),
  fields: () => request<Field[]>("/api/v1/fields"),
  createField: (name: string, geometry: Geometry) =>
    request<Field>("/api/v1/fields", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, geometry }),
    }),
  updateField: (field: Field) =>
    request<Field>(`/api/v1/fields/${field.id}`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: field.name, geometry: field.geometry }),
    }),
  deleteField: (id: string) =>
    request(`/api/v1/fields/${id}`, { method: "DELETE" }),
  discover: (bbox: [number, number, number, number]) =>
    request<
      Array<{
        source_id: string;
        name: string;
        landuse: string | null;
        geometry: Geometry;
      }>
    >("/api/v1/fields/discover", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ bbox, limit: 30 }),
    }),
  runAnalysis: (payload: Record<string, unknown>) =>
    request<Job>("/api/v1/analyses", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    }),
  analyses: () => request<Array<Record<string, string>>>("/api/v1/analyses"),
  analysis: (id: string) => request<Analysis>(`/api/v1/analyses/${id}`),
  jobEvents: (id: string) =>
    request<
      Array<{ id: number; created_at: string; stage: string; message: string }>
    >(`/api/v1/jobs/${id}/events`),
  jobs: () => request<Job[]>("/api/v1/jobs"),
  job: (id: string) => request<Job>(`/api/v1/jobs/${id}`),
  upload: async (kind: "train" | "test", file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Record<string, unknown>>(`/api/v1/benchmark/files/${kind}`, {
      method: "POST",
      body: form,
    });
  },
  runBenchmark: (fast = true) =>
    request<Job>("/api/v1/benchmark/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ fast }),
    }),
  report: () => request<Record<string, any>>("/api/v1/benchmark/report"),
  validate: () =>
    request<{
      valid: boolean;
      rows: number;
      min_prediction: number;
      max_prediction: number;
    }>("/api/v1/benchmark/validate"),
  polygons: () => request<string[]>("/api/v1/benchmark/polygons"),
  series: (id: string) =>
    request<Array<Record<string, any>>>(
      `/api/v1/benchmark/series/${encodeURIComponent(id)}`,
    ),
  events: () => request<Array<Record<string, any>>>("/api/v1/benchmark/events"),
};
