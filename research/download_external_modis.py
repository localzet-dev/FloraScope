"""Независимые MODIS ряды ORNL DAAC; без добавления в organizer training."""
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parent / 'external';
root.mkdir(exist_ok=True)
manifest = []
for site in ('US-SDU', 'US-Ne1', 'US-GLE'):
    url = f'https://modis.ornl.gov/rst/api/v1/MOD13Q1/AMERIFLUX/{site}/subsetStatistics?band=250m_16_days_NDVI&startDate=A2018001&endDate=A2024361'
    path = root / f'{site}_statistics.json'
    try:
        if not path.exists():
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}),
                                        timeout=45) as response: path.write_bytes(response.read())
        payload = json.loads(path.read_bytes())
        manifest.append({'site': site, 'url': url, 'records': len(payload['statistics']),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'retrieved_utc': datetime.now(timezone.utc).isoformat()})
    except Exception as error:
        manifest.append({'site': site, 'url': url, 'error': str(error)})
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(manifest[-1], flush=True)
