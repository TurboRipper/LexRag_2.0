"""CPU neural retrieval and window-based NLI. Models are never fetched at runtime."""
import hashlib
import json
import os
import threading
from pathlib import Path

import numpy as np


def evidence_windows(text, tokenizer, size=190, overlap=40):
    """Token-bounded windows with exact source character offsets, including the tail."""
    offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                        truncation=False, verbose=False)['offset_mapping']
    if not offsets:
        return []
    result = []
    for start in range(0, len(offsets), size-overlap):
        end = min(start+size, len(offsets))
        a, b = offsets[start][0], offsets[end-1][1]
        if b > a:
            result.append({'text': text[a:b], 'char_start': a, 'char_end': b})
        if end == len(offsets):
            break
    return result


def aggregate_nli(predictions, threshold=0.80):
    """Model decisions only: support and contradiction are retained independently."""
    support = [p for p in predictions if p['entailment'] >= threshold]
    contradiction = [p for p in predictions if p['contradiction'] >= threshold]
    if support and contradiction:
        label = 'Mixed evidence signals'
    elif support:
        label = 'Model-supported'
    elif contradiction:
        label = 'Model-contradicted'
    else:
        label = 'Not established'
    return {'label': label,
            'support': sorted(support, key=lambda p: -p['entailment'])[:2],
            'contradiction': sorted(contradiction, key=lambda p: -p['contradiction'])[:2],
            'best_match': max(predictions, key=lambda p: p['entailment'], default=None)}


class NeuralEngine:
    def __init__(self, base, docs):
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        import torch
        from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer
        self.torch = torch
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        self.lock = threading.RLock()
        self.root = Path(base) / 'models'
        self.manifest = json.loads((self.root/'manifest.json').read_text(encoding='utf-8'))
        self.tokenizers, self.models = {}, {}
        for name in ('encoder','reranker','nli'):
            folder = self.root/name
            self.tokenizers[name] = AutoTokenizer.from_pretrained(folder, local_files_only=True, trust_remote_code=False)
            cls = AutoModel if name == 'encoder' else AutoModelForSequenceClassification
            self.models[name] = cls.from_pretrained(folder, local_files_only=True, trust_remote_code=False,
                                                   use_safetensors=True).eval()
        mapping = {int(k): str(v).lower() for k,v in self.models['nli'].config.id2label.items()}
        if set(mapping.values()) != {'contradiction','entailment','neutral'}:
            # Published label order for this exact model only; fail closed for others.
            if self.manifest['nli']['repo'] != 'cross-encoder/nli-MiniLM2-L6-H768':
                raise ValueError('Unknown NLI label mapping')
            mapping = {0:'contradiction',1:'entailment',2:'neutral'}
        self.nli_labels = mapping
        self.windows, owners = [], []
        for i, text in enumerate(docs):
            for w in evidence_windows(text, self.tokenizers['encoder']):
                self.windows.append(w)
                owners.append(i)
        self.owners = np.asarray(owners,dtype=np.int32)
        self.doc_count = len(docs)
        identity = json.dumps(self.manifest['encoder'],sort_keys=True)+'|windows190-40-v1|'+json.dumps(docs,ensure_ascii=False)
        fingerprint = hashlib.sha256(identity.encode()).hexdigest()
        cache_dir = Path(base)/'cache'
        cache_dir.mkdir(exist_ok=True)
        cache = cache_dir/f'embeddings-{fingerprint}.npy'
        try:
            self.embeddings = np.load(cache,allow_pickle=False)
            if self.embeddings.shape != (len(self.windows),384) or not np.isfinite(self.embeddings).all():
                raise ValueError('Invalid embedding cache')
        except (OSError,ValueError):
            print(f'Encoding {len(self.windows)} evidence windows on CPU...',flush=True)
            self.embeddings = self.encode([w['text'] for w in self.windows])
            temp = cache.with_suffix('.tmp')
            with temp.open('wb') as f:
                np.save(f,self.embeddings,allow_pickle=False)
            temp.replace(cache)
        print(f'Neural index ready: {len(self.windows)} windows.',flush=True)

    def encode(self, texts):
        if not texts:
            return np.empty((0,384),dtype=np.float32)
        outputs = []
        with self.lock, self.torch.inference_mode():
            for i in range(0,len(texts),16):
                batch = self.tokenizers['encoder'](texts[i:i+16],padding=True,truncation=True,max_length=256,return_tensors='pt')
                hidden = self.models['encoder'](**batch).last_hidden_state
                mask = batch['attention_mask'].unsqueeze(-1).expand(hidden.size()).float()
                vectors = (hidden*mask).sum(1)/mask.sum(1).clamp(min=1e-9)
                vectors = self.torch.nn.functional.normalize(vectors,p=2,dim=1)
                outputs.append(vectors.cpu().numpy())
        return np.concatenate(outputs)

    def dense_scores(self, question):
        scores = self.embeddings @ self.encode([question])[0]
        doc_scores = np.full(self.doc_count,-1.0)
        np.maximum.at(doc_scores,self.owners,scores)
        return doc_scores,scores

    def rerank(self, question, indices, window_scores):
        # Score two semantic windows per candidate to avoid only reading the beginning.
        pairs, owners = [], []
        for i in indices:
            locations = np.flatnonzero(self.owners == i)
            for j in locations[np.argsort(-window_scores[locations],kind='stable')[:2]]:
                pairs.append((question,self.windows[j]['text']))
                owners.append(int(i))
        logits = self.predict_pairs('reranker',pairs)
        result = {int(i):-100.0 for i in indices}
        for i, score in zip(owners,logits.reshape(-1)):
            result[i] = max(result[i],float(score))
        return result

    def predict_pairs(self,name,pairs):
        outputs=[]
        if not pairs:
            return np.empty((0,3 if name=='nli' else 1))
        with self.lock,self.torch.inference_mode():
            for i in range(0,len(pairs),8):
                batch=pairs[i:i+8]
                inputs=self.tokenizers[name]([p[0] for p in batch],[p[1] for p in batch],
                    padding=True,truncation='only_first' if name=='nli' else True,
                    max_length=384,return_tensors='pt')
                logits=self.models[name](**inputs).logits
                if name=='nli':logits=self.torch.softmax(logits,dim=-1)
                outputs.append(logits.cpu().numpy())
        return np.concatenate(outputs)

    def verify(self, claim, evidence):
        tok=self.tokenizers['nli']
        if len(tok(claim,add_special_tokens=False)['input_ids'])>140:
            raise ValueError('Each claim must be short: at most 140 model tokens. Split long statements into separate claims.')
        windows=[]
        for item in evidence:
            for w in evidence_windows(item['text'],tok):
                windows.append({**w,'citation_id':item['citation_id'],'case_id':item['case_id']})
        total=len(windows)
        # Rank all windows by claim meaning before applying the explicit CPU budget.
        if total>48:
            similarity=self.encode([w['text'] for w in windows]) @ self.encode([claim])[0]
            windows=[windows[i] for i in np.argsort(-similarity,kind='stable')[:48]]
        scores=self.predict_pairs('nli',[(w['text'],claim) for w in windows])
        predictions=[{**w,**{self.nli_labels[j]:float(prob) for j,prob in enumerate(score)}}
                     for w,score in zip(windows,scores)]
        return {'claim':claim,**aggregate_nli(predictions),'windows_checked':len(windows),
                'windows_available':total,'coverage_complete':len(windows)==total,
                'threshold':0.8,'model':self.manifest['nli'],
                'scope':'Retrieved passages only; model predictions are not legal determinations.'}
