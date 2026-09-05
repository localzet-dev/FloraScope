"""График фактических проверок, без смешивания разных evaluation datasets."""
import json
import matplotlib
import numpy as np
from pathlib import Path

matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path('/research/results')
frozen = json.loads((root / 'new_test_observed_old_model.json').read_text())['folds']
external = json.loads((root / 'external_modis_check.json').read_text())['folds']
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
for ax, labels, models, baselines, title in [
    (axes[0], [str(r['seed']) for r in frozen], [r['rmse'] for r in frozen], [r['linear_rmse_common'] for r in frozen],
     'Новый organizer test · видимые точки\n1970 скрытых точек на маску, 20 новых AOI'),
    (axes[1], ['US-GLE', 'US-Ne1', 'US-SDU'],
     [np.mean([r['model_rmse'] for r in external if r['site'] == s]) for s in ['US-GLE', 'US-Ne1', 'US-SDU']],
     [np.mean([r['linear_rmse'] for r in external if r['site'] == s]) for s in ['US-GLE', 'US-Ne1', 'US-SDU']],
     'Независимый MODIS-only stress test\nСреднее 3 масок, 14–21 точка на маску')]:
    x = np.arange(len(labels));
    a = ax.bar(x - .18, models, .36, label='FloraScope', color='#27756b');
    b = ax.bar(x + .18, baselines, .36, label='Линейная интерполяция', color='#a1a9b1')
    ax.bar_label(a, fmt='%.3f', fontsize=9);
    ax.bar_label(b, fmt='%.3f', fontsize=9)
    ax.set(xticks=x, xticklabels=labels, ylabel='RMSE · меньше лучше', title=title, ylim=(0, .13));
    ax.grid(axis='y', alpha=.15);
    ax.set_axisbelow(True);
    ax.legend(fontsize=8)
fig.savefig(root / 'data_checks.png', dpi=160)
