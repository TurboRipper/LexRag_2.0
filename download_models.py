"""Download the three public model snapshots once. Runtime loads local files only."""
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.environ['HF_HOME'] = str(BASE / 'models' / '.hf-cache')
os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
MODELS = {
    'encoder': 'sentence-transformers/all-MiniLM-L6-v2',
    'reranker': 'cross-encoder/ms-marco-MiniLM-L6-v2',
    'nli': 'cross-encoder/nli-MiniLM2-L6-H768',
}


def main():
    from huggingface_hub import HfApi, snapshot_download
    root = BASE / 'models'
    root.mkdir(exist_ok=True)
    manifest_file = root / 'manifest.json'
    manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
    for name, repo in MODELS.items():
        revision = manifest.get(name, {}).get('revision') or HfApi(token=False).model_info(repo).sha
        print(f'Downloading {name}: {repo} @ {revision}', flush=True)
        snapshot_download(repo, revision=revision, local_dir=root/name, token=False, max_workers=2,
                          allow_patterns=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json',
                                          'special_tokens_map.json','vocab.txt','vocab.json','merges.txt','README.md'])
        if not (root/name/'model.safetensors').exists():
            raise RuntimeError(f'Missing safetensors weights for {name}')
        manifest[name] = {'repo': repo, 'revision': revision}
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('All models saved locally. Restart LEX-RAG to enable research mode.', flush=True)


if __name__ == '__main__':
    main()
