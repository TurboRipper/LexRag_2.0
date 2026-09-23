"""Download the configured public Hugging Face training corpus for offline use."""
import csv
import json
import hashlib
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATASET_URL = 'https://huggingface.co/datasets/ninadn/indian-legal/resolve/main/train.csv'
DESTINATION = BASE / 'data' / 'indian-legal-train.csv'


def main():
    DESTINATION.parent.mkdir(exist_ok=True)
    temporary = DESTINATION.with_suffix('.csv.part')
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(DATASET_URL, timeout=120) as response, temporary.open('wb') as output:
            expected = response.headers.get('Content-Length')
            while block := response.read(1024 * 1024):
                output.write(block)
                digest.update(block)
                size += len(block)
            if expected and size != int(expected):
                raise RuntimeError('Incomplete dataset download.')
        csv.field_size_limit(2_147_483_647)
        with temporary.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ['Text', 'Summary']:
                raise ValueError(f'Unexpected dataset columns: {reader.fieldnames}')
            count = sum(1 for row in reader if row.get('Text', '').strip())
        if not count:
            raise ValueError('Dataset has no judgment text.')
        temporary.replace(DESTINATION)
        DESTINATION.with_suffix('.source.json').write_text(json.dumps({
            'url': DATASET_URL, 'sha256': digest.hexdigest(),
            'bytes': size, 'rows_with_text': count,
        }, indent=2), encoding='utf-8')
        print(f'Downloaded {count:,} judgments ({size:,} bytes) to {DESTINATION}', flush=True)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
