import { type MutableRefObject, useEffect, useRef } from "react";
import type { Feature, FeatureCollection, Geometry, Position } from "geojson";
import {
  type GeoJSONSource,
  type IControl,
  Map,
  type MapMouseEvent,
  Marker,
  NavigationControl,
  setWorkerUrl,
  type StyleSpecification,
} from "maplibre-gl";
import type { Analysis, Field } from "../types";
import { absoluteTileTemplate } from "../lib/visualization";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

// Vite должен собрать worker вместе с его imports, иначе GeoJSON слои молча не появятся.
setWorkerUrl(workerUrl);

const style: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#07120e" },
    },
    {
      id: "osm",
      type: "raster",
      source: "osm",
      paint: {
        "raster-opacity": 0.65,
        "raster-saturation": -0.85,
        "raster-brightness-max": 0.58,
      },
    },
  ],
};

export function MapPane({
  fields,
  selected,
  analysis,
  activeLayer,
  onField,
  onDraw,
  onViewport,
  opacity = 0.7,
  showFields = true,
  focusToken = 0,
  searchLocation = null,
}: {
  opacity?: number;
  showFields?: boolean;
  focusToken?: number;
  searchLocation?: [number, number] | null;
  fields: Field[];
  selected: Field | null;
  analysis: Analysis | null;
  activeLayer: string;
  onField: (id: string) => void;
  onDraw: (geometry: Geometry) => void;
  onViewport: (bbox: [number, number, number, number]) => void;
}) {
  const node = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const analysisRef = useRef<string | null>(null);
  const markerRef = useRef<Marker | null>(null);

  const latest = useRef({
    fields,
    analysis,
    activeLayer,
    onField,
    onDraw,
    onViewport,
  });
  latest.current = {
    fields,
    analysis,
    activeLayer,
    onField,
    onDraw,
    onViewport,
  };

  useEffect(() => {
    if (!node.current) return;
    const map = new Map({
      container: node.current,
      style,
      center: [39.0, 45.0],
      zoom: 5.2,
      pitch: 28,
    });
    mapRef.current = map;
    // Раскладка меняется без window.resize: canvas должен следовать размеру панели.
    const resize = new ResizeObserver(() => map.resize());
    resize.observe(node.current);
    map.addControl(new NavigationControl(), "bottom-right");
    const draw = installDrawControl(map, (geometry) =>
      latest.current.onDraw(geometry),
    );

    const viewport = () => {
      const bounds = map.getBounds();
      latest.current.onViewport([
        bounds.getWest(),
        bounds.getSouth(),
        bounds.getEast(),
        bounds.getNorth(),
      ]);
    };
    map.on("moveend", viewport);
    map.on("style.load", () => {
      syncFields(map, latest.current.fields, (id) =>
        latest.current.onField(id),
      );
      syncAnalysis(
        map,
        latest.current.analysis,
        latest.current.activeLayer,
        analysisRef,
      );
      viewport();
    });
    return () => {
      markerRef.current?.remove();
      resize.disconnect();
      draw.cleanup();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    // Загрузка тайлов не должна блокировать обновление уже созданного GeoJSON source.
    if (!map?.getSource("fields")) return;
    syncFields(map, fields, onField);
    syncAnalysis(map, analysis, activeLayer, analysisRef);
  }, [fields, analysis, activeLayer, onField]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected) return;
    const geometry = selected.geometry;
    if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") return;
    const positions =
      geometry.type === "Polygon"
        ? geometry.coordinates.flat()
        : geometry.coordinates.flat(2);
    const lng = positions.map((point) => point[0]);
    const lat = positions.map((point) => point[1]);
    map.fitBounds(
      [
        [Math.min(...lng), Math.min(...lat)],
        [Math.max(...lng), Math.max(...lat)],
      ],
      {
        padding: 65,
        maxZoom: 16,
      },
    );
  }, [selected, focusToken]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !searchLocation) return;
    markerRef.current?.remove();
    markerRef.current = new Marker({ color: "#62dfb6" })
      .setLngLat(searchLocation)
      .addTo(map);
    map.flyTo({ center: searchLocation, zoom: 14, essential: true });
  }, [searchLocation]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const update = () => {
      for (const layer of ["fields-fill", "fields-line"]) {
        if (map.getLayer(layer))
          map.setLayoutProperty(
            layer,
            "visibility",
            showFields ? "visible" : "none",
          );
      }
      for (const key of ["ndvi", "zscore", "quality"]) {
        if (map.getLayer(`raster-${key}`))
          map.setPaintProperty(`raster-${key}`, "raster-opacity", opacity);
      }
      if (map.getLayer("osm"))
        map.setPaintProperty(
          "osm",
          "raster-opacity",
          activeLayer === "none" ? 0.65 : 0.35,
        );
    };
    if (map.getSource("fields")) update();
    map.on("style.load", update);
    return () => {
      map.off("style.load", update);
    };
  }, [opacity, showFields, analysis, activeLayer]);

  return <div ref={node} className="map" />;
}

function syncFields(map: Map, fields: Field[], onField: (id: string) => void) {
  const collection: FeatureCollection = {
    type: "FeatureCollection",
    features: fields.map(
      (field): Feature => ({
        type: "Feature",
        geometry: field.geometry,
        properties: { id: field.id, name: field.name, area_ha: field.area_ha },
      }),
    ),
  };
  const source = map.getSource("fields") as GeoJSONSource | undefined;
  if (source) {
    source.setData(collection);
    return;
  }
  map.addSource("fields", { type: "geojson", data: collection });
  map.addLayer({
    id: "fields-fill",
    type: "fill",
    source: "fields",
    paint: { "fill-color": "#68d49d", "fill-opacity": 0.1 },
  });
  map.addLayer({
    id: "fields-line",
    type: "line",
    source: "fields",
    paint: { "line-color": "#9ae8c2", "line-width": 2 },
  });
  map.on("click", "fields-fill", (event) => {
    const id = event.features?.[0]?.properties?.id;
    if (id) onField(String(id));
  });
}

function syncAnalysis(
  map: Map,
  analysis: Analysis | null,
  activeLayer: string,
  analysisRef: MutableRefObject<string | null>,
) {
  if (analysisRef.current !== analysis?.id) {
    for (const key of ["ndvi", "zscore", "quality"]) {
      if (map.getLayer(`raster-${key}`)) map.removeLayer(`raster-${key}`);
      if (map.getSource(`raster-${key}`)) map.removeSource(`raster-${key}`);
    }
    analysisRef.current = analysis?.id ?? null;
    for (const layer of analysis?.layers ?? []) {
      map.addSource(`raster-${layer.key}`, {
        type: "raster",
        tiles: [absoluteTileTemplate(layer.tile_url, window.location.origin)],
        tileSize: 256,
      });
      map.addLayer(
        {
          id: `raster-${layer.key}`,
          type: "raster",
          source: `raster-${layer.key}`,
          paint: { "raster-opacity": layer.key === "zscore" ? 0.82 : 0.68 },
        },
        "fields-fill",
      );
    }
  }
  for (const key of ["ndvi", "zscore", "quality"]) {
    if (map.getLayer(`raster-${key}`)) {
      map.setLayoutProperty(
        `raster-${key}`,
        "visibility",
        key === activeLayer ? "visible" : "none",
      );
    }
  }

  const events: FeatureCollection = {
    type: "FeatureCollection",
    features: (analysis?.spatial_events ?? []).map(
      (event): Feature => ({
        type: "Feature",
        geometry: event.geometry,
        properties: event,
      }),
    ),
  };
  const source = map.getSource("events") as GeoJSONSource | undefined;
  if (source) source.setData(events);
  else {
    map.addSource("events", { type: "geojson", data: events });
    map.addLayer({
      id: "events-fill",
      type: "fill",
      source: "events",
      paint: { "fill-color": "#ef7c5d", "fill-opacity": 0.28 },
    });
    map.addLayer({
      id: "events-line",
      type: "line",
      source: "events",
      paint: { "line-color": "#ff9b7f", "line-width": 2 },
    });
  }
}

function installDrawControl(map: Map, onDraw: (geometry: Geometry) => void) {
  let drawing = false;
  let coordinates: Position[] = [];
  let control: DrawControl;

  const data = (): FeatureCollection => ({
    type: "FeatureCollection",
    features:
      coordinates.length < 2
        ? []
        : [
            {
              type: "Feature",
              properties: {},
              geometry:
                coordinates.length < 3
                  ? { type: "LineString", coordinates }
                  : {
                      type: "Polygon",
                      coordinates: [[...coordinates, coordinates[0]]],
                    },
            },
          ],
  });
  const refresh = () =>
    (map.getSource("draft") as GeoJSONSource | undefined)?.setData(data());
  const start = () => {
    drawing = true;
    coordinates = [];
    map.getCanvas().style.cursor = "crosshair";
    refresh();
    control.sync();
  };
  const cancel = () => {
    drawing = false;
    coordinates = [];
    map.getCanvas().style.cursor = "";
    refresh();
    control.sync();
  };
  const finish = () => {
    if (coordinates.length >= 3)
      onDraw({
        type: "Polygon",
        coordinates: [[...coordinates, coordinates[0]]],
      });
    cancel();
  };
  control = new DrawControl(
    () => drawing,
    () => coordinates.length,
    start,
    finish,
    cancel,
  );
  map.addControl(control, "top-left");
  const click = (event: MapMouseEvent) => {
    if (!drawing) return;
    coordinates.push([event.lngLat.lng, event.lngLat.lat]);
    refresh();
    control.sync();
  };
  map.on("click", click);
  map.on("style.load", () => {
    map.addSource("draft", {
      type: "geojson",
      data: { type: "FeatureCollection", features: [] },
    });
    map.addLayer({
      id: "draft-fill",
      type: "fill",
      source: "draft",
      paint: { "fill-color": "#7be2ac", "fill-opacity": 0.16 },
    });
    map.addLayer({
      id: "draft-line",
      type: "line",
      source: "draft",
      paint: {
        "line-color": "#a4f2cb",
        "line-width": 2,
        "line-dasharray": [2, 1],
      },
    });
  });
  return {
    cleanup: () => {
      map.off("click", click);
      if (map.hasControl(control)) map.removeControl(control);
    },
  };
}

class DrawControl implements IControl {
  private container?: HTMLDivElement;
  private main?: HTMLButtonElement;
  private cancel?: HTMLButtonElement;

  constructor(
    private isDrawing: () => boolean,
    private points: () => number,
    private start: () => void,
    private finish: () => void,
    private abort: () => void,
  ) {}

  onAdd(): HTMLElement {
    this.container = document.createElement("div");
    this.container.className =
      "maplibregl-ctrl maplibregl-ctrl-group draw-control";
    this.main = document.createElement("button");
    this.cancel = document.createElement("button");
    this.main.type = this.cancel.type = "button";
    this.main.onclick = () => (this.isDrawing() ? this.finish() : this.start());
    this.cancel.onclick = this.abort;
    this.cancel.textContent = "×";
    this.container.append(this.main, this.cancel);
    this.sync();
    return this.container;
  }

  onRemove() {
    this.container?.remove();
  }

  sync() {
    if (!this.main || !this.cancel) return;
    const drawing = this.isDrawing();
    this.main.textContent = drawing ? `✓ ${this.points()}` : "✎";
    this.main.setAttribute(
      "aria-label",
      drawing ? "Завершить рисование территории" : "Нарисовать территорию",
    );
    this.main.title = drawing
      ? "Минимум 3 вершины. Нажмите, чтобы сохранить."
      : "Нарисовать территорию";
    this.cancel.setAttribute("aria-label", "Отменить рисование");
    this.main.disabled = drawing && this.points() < 3;
    this.cancel.style.display = drawing ? "block" : "none";
  }
}
