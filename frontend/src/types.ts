import type { Geometry } from "geojson";

export interface Field {
  id: string;
  name: string;
  geometry: Geometry;
  area_ha: number;
  created_at: string;
  updated_at: string;
}

export interface Job {
  payload?: { field_id?: string; date_from?: string; date_to?: string; history_years?: number; max_cloud_cover?: number };
  id: string;
  kind: string;
  state: "queued" | "running" | "completed" | "failed";
  progress: number;
  stage: string;
  message: string;
  result_ref?: string | null;
  error?: string | null;
}

export interface SystemState {
  version: string;
  files: {
    train: boolean;
    test: boolean;
    report: boolean;
    submission: boolean;
  };
  fields: number;
  analyses: number;
  analysis_resolution_m: number;
}

export interface Analysis {
  id: string;
  title: string;
  field: Field;
  center: [number, number];
  period: { from: string; to: string; history_years: number };
  sources: Record<string, unknown>;
  quality: Record<string, number | boolean>;
  state: {
    condition: string;
    min_zscore: number | null;
    latest_ndvi: number;
    latest_expected: number | null;
  };
  series: Array<{
    date: string;
    source: string | null;
    observed: number | null;
    restored: number;
    expected: number | null;
    lower: number | null;
    upper: number | null;
    zscore: number | null;
    status: string;
    temperature_c?: number | null;
    precipitation_mm?: number | null;
  }>;
  events: Array<Record<string, unknown>>;
  spatial_events: Array<{
    id: string;
    area_ha: number;
    min_zscore: number;
    mean_zscore: number;
    geometry: Geometry;
    date?: string;
  }>;
  layers: Array<{ key: string; label: string; tile_url: string }>;
}
