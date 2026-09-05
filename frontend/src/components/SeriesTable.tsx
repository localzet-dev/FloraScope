import { useEffect, useMemo, useState } from "react";
import { Pagination, Table } from "@mantine/core";
import {
  metricLabel,
  type TimeWindow,
  type PlotPoint,
} from "../lib/visualization";
export function SeriesTable({
  points: sourcePoints,
  range,
  onPoint,
}: {
  points: PlotPoint[];
  range: TimeWindow;
  onPoint: (point: PlotPoint) => void;
}) {
  const points = useMemo(
    () =>
      range
        ? sourcePoints.filter((p) => p.date >= range[0] && p.date <= range[1])
        : sourcePoints,
    [sourcePoints, range],
  );
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [points]);
  return (
    <div className="series-table">
      <div className="table-scroll">
        <Table highlightOnHover horizontalSpacing="md" verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Дата</Table.Th>
              <Table.Th>Наблюдение</Table.Th>
              <Table.Th>Восстановление</Table.Th>
              <Table.Th>Норма</Table.Th>
              <Table.Th>Отклонение, σ</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {points.slice((page - 1) * 12, page * 12).map((p) => (
              <Table.Tr key={p.date}>
                <Table.Td>
                  <button className="table-date" onClick={() => onPoint(p)}>
                    {p.date}
                  </button>
                </Table.Td>
                <Table.Td>{metricLabel(p.observed)}</Table.Td>
                <Table.Td>{metricLabel(p.restored)}</Table.Td>
                <Table.Td>{metricLabel(p.expected)}</Table.Td>
                <Table.Td>{metricLabel(p.zscore, 2)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </div>
      {!points.length && (
        <p className="muted small">Нет точек для отображения.</p>
      )}
      <div className="table-footer">
        <span>{points.length} строк · «—» означает отсутствие данных</span>
        <Pagination
          size="xs"
          total={Math.max(1, Math.ceil(points.length / 12))}
          value={page}
          onChange={setPage}
          withEdges
        />
      </div>
    </div>
  );
}
