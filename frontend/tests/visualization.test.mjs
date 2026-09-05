import test from "node:test";
import assert from "node:assert/strict";
import {
  eventWindow,
  parsePolygons,
  metricLabel,
  evidenceEntries,
} from "../src/lib/visualization.ts";
const polygon = {
  type: "Polygon",
  coordinates: [
    [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 0],
    ],
  ],
};
test("GeoJSON collection keeps every contour and its name for explicit selection", () => {
  const result = parsePolygons({
    type: "FeatureCollection",
    features: [
      { type: "Feature", properties: { name: "Первое" }, geometry: polygon },
      { type: "Feature", properties: { name: "Второе" }, geometry: polygon },
    ],
  });
  assert.equal(result.length, 2);
  assert.equal(result[1].name, "Второе");
});
test("points and empty collections cannot silently become territories", () => {
  assert.throws(() => parsePolygons({ type: "Point", coordinates: [0, 0] }));
  assert.throws(() =>
    parsePolygons({ type: "FeatureCollection", features: [] }),
  );
});
test("event focus clamps to real data and excludes non-overlapping events", () => {
  const points = [{ date: "2024-05-01" }, { date: "2024-06-01" }];
  assert.deepEqual(
    eventWindow({ start: "2024-05-02", end: "2024-05-30" }, points),
    ["2024-05-01", "2024-06-01"],
  );
  assert.equal(
    eventWindow({ start: "2023-05-01", end: "2023-06-01" }, points),
    null,
  );
});
test("missing values are never displayed as zero or as a valid number", () => {
  assert.equal(metricLabel(null), "—");
  assert.equal(metricLabel(NaN), "—");
  assert.equal(metricLabel(0), "0.000");
});
test("event evidence supports saved CSV JSON and ignores malformed input", () => {
  assert.deepEqual(
    evidenceEntries({ evidence_json: '{"observed_points":3}' }),
    [["Реальных наблюдений", "3"]],
  );
  assert.deepEqual(evidenceEntries({ evidence_json: "broken" }), []);
});
