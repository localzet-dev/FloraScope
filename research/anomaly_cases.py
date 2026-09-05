import argparse
import json
import matplotlib
from pathlib import Path

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
points = pd.read_csv(args.input / 'analysis_points.csv', parse_dates=['date'])
events = pd.read_csv(args.input / 'events.csv')
negative = events.query("kind == 'NEGATIVE_DEVIATION'").sort_values('observations', ascending=False)
phase = events.query("kind == 'PHENOLOGY_SHIFT'")
chosen = [negative.iloc[0]]
if not phase.empty:
    chosen.append(phase.iloc[0])
else:
    chosen.append(negative.loc[negative.anon_polygon_id != chosen[0].anon_polygon_id].iloc[0])
args.output.mkdir(parents=True, exist_ok=True)
records = []
for index, event in enumerate(chosen, 1):
    year = int(str(event.start)[:4])
    season = points.loc[(points.anon_polygon_id == event.anon_polygon_id) & (points.date.dt.year == year)]
    fig, ax = plt.subplots(figsize=(11, 4.2), constrained_layout=True)
    ax.plot(season.date, season.primary_ndvi_filled, label='Восстановленный ряд', color='#366976')
    ax.plot(season.date, season.climatology_calc, label='Историческое ожидание', color='#639c45', linestyle='--')
    ax.scatter(season.date, season.primary_ndvi, label='Наблюдения', color='#16394c', s=15, zorder=3)
    ax.axvspan(pd.Timestamp(event.start), pd.Timestamp(event.end), color='#db8057', alpha=.15)
    ax.set(title=f'{event.anon_polygon_id} · {year} · {event.kind}', ylabel='primary NDVI')
    ax.legend(loc='best', fontsize=9);
    ax.grid(alpha=.15)
    fig.savefig(args.output / f'anomaly_case_{index}.png', dpi=150)
    plt.close(fig)
    records.append({key: None if pd.isna(value) else value for key, value in event.to_dict().items()})
(args.output / 'anomaly_cases.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(records, ensure_ascii=False, indent=2))
