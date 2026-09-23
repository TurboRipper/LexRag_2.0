"""Local, CPU-only legal retrieval demonstrator. No remote services at runtime."""
import csv
import hashlib
import math
import os
import re
import time
import threading
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from flask import Flask, jsonify, render_template, request, send_from_directory
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity

BASE = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE), static_folder=None)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
MAX_JUDGMENTS = int(os.getenv('LEXRAG_MAX_JUDGMENTS', '300'))
MAX_CHUNKS = int(os.getenv('LEXRAG_MAX_CHUNKS', '6000'))
TOP_K = 5
MIN_SIMILARITY = 0.04  # Development threshold; calibrate with held-out labels.


def tokens(text):
    return re.findall(r'[a-zA-Z0-9]+', str(text).lower())


class BM25:
    def __init__(self, docs):
        words = [tokens(x) for x in docs]
        self.lengths = np.array([len(x) for x in words])
        self.avg = max(float(self.lengths.mean()), 1.0)
        self.tf = [Counter(x) for x in words]
        df = Counter()
        for x in words:
            df.update(set(x))
        n = len(words)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query):
        out = np.zeros(len(self.tf))
        for i, tf in enumerate(self.tf):
            for term in set(tokens(query)):
                f = tf.get(term, 0)
                if f:
                    out[i] += self.idf.get(term, 0) * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * self.lengths[i] / self.avg))
        return out


def value(row, names):
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        v = lower.get(name.lower())
        if v is not None and str(v).strip():
            return str(v).strip()
    return ''


def load_rows():
    configured = os.getenv('LEXRAG_DATASET')
    path = Path(configured) if configured else BASE / 'in_sikkim_judgments.parquet'
    if not path.is_absolute():
        path = BASE / path
    if not path.is_file():
        raise RuntimeError(f'Dataset not found: {path.name}. Copy the Parquet file beside app.py or set LEXRAG_DATASET.')
    if MAX_JUDGMENTS < 1 or MAX_CHUNKS < 1:
        raise ValueError('Dataset limits must be positive integers.')
    rows = []
    selected_cases = set()
    def include(row):
        case_key = value(row, ['case_id', 'id', 'document_id']) or hashlib.sha256(value(row, ['text', 'judgment_text', 'content']).encode()).hexdigest()
        if case_key not in selected_cases and len(selected_cases) >= MAX_JUDGMENTS:
            return
        selected_cases.add(case_key)
        rows.append(row)
    if path.suffix.lower() == '.parquet':
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=min(128, MAX_JUDGMENTS)):
            for row in batch.to_pylist():
                include(row)
        total = parquet.metadata.num_rows
    elif path.suffix.lower() == '.csv':
        csv.field_size_limit(2_147_483_647)
        total = 0
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                total += 1
                include(row)
    else:
        raise ValueError('Use a .parquet or .csv dataset.')
    return rows, path.name, total


def chunks(text, size=180, overlap=35):
    words = text.split()
    return [' '.join(words[i:i + size]) for i in range(0, len(words), size - overlap)
            if len(words[i:i + size]) >= 20]


def court_metadata(row):
    # Never infer the issuing court from mentions of cited courts in the judgment.
    name = value(row, ['court', 'court_name', 'courtname'])
    s = name.lower().replace('_', ' ')
    if 'supreme' in s:
        return name, 1.0
    if 'high' in s:
        return name, 0.8
    if 'district' in s or 'sessions' in s:
        return name, 0.6
    if 'tribunal' in s:
        return name, 0.5
    return name or 'Unknown issuing court', 0.0


def decision_date(row):
    raw = value(row, ['decision_date', 'judgment_date', 'date_of_judgment', 'date'])
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw[:10], fmt).date().isoformat()
        except ValueError:
            pass
    return ''


def prepare(rows):
    docs, meta, seen = [], [], set()
    for row in rows:
        text = value(row, ['text_original', 'text', 'judgment_text', 'judgment', 'content', 'body'])
        if not text:
            continue
        fingerprint = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
        identity = (value(row, ['case_id', 'id', 'document_id']), fingerprint)
        if identity in seen:
            continue
        seen.add(identity)
        name, authority = court_metadata(row)
        title = value(row, ['title', 'case_title', 'case_name', 'name']) or 'Untitled judgment'
        source_id = value(row, ['case_id', 'id', 'document_id', 'doc_id'])
        source_chunk = value(row, ['chunk_id'])
        parts = [text] if source_chunk else chunks(text)[:30]
        for number, part in enumerate(parts, 1):
            docs.append(part)
            meta.append({'case_id': source_id or fingerprint, 'source_id': source_id,
                         'source_chunk_id': source_chunk, 'page_start': row.get('page_start'),
                         'page_end': row.get('page_end'), 'section_type': row.get('section_type', ''),
                         'citation_id': f'{source_chunk or fingerprint}:{number}', 'chunk': number,
                         'title': title, 'court': name, 'authority': authority,
                         'authority_basis': 'structured court metadata' if authority else 'unknown',
                         'decision_date': decision_date(row)})
            if len(docs) >= MAX_CHUNKS:
                return docs, meta
    return docs, meta


INIT_ERROR = None
ROWS, DOCS, META, SOURCE, TOTAL_ROWS = [], [], [], 'Unavailable', None
try:
    ROWS, SOURCE, TOTAL_ROWS = load_rows()
    DOCS, META = prepare(ROWS)
    if not DOCS:
        raise ValueError('No usable judgment text. Expected text, judgment_text, judgment, content or body column.')
    VECTORIZER = TfidfVectorizer(stop_words='english', ngram_range=(1, 2), max_features=24000, sublinear_tf=True)
    MATRIX = VECTORIZER.fit_transform(DOCS)
    BM = BM25(DOCS)
except Exception as exc:
    INIT_ERROR = str(exc)



NEURAL = None
NEURAL_ERROR = None
NEURAL_LOCK = threading.Lock()


def models_present():
    return (BASE/'models/manifest.json').is_file() and all(
        (BASE/'models'/name/'model.safetensors').is_file() for name in ('encoder','reranker','nli'))


def get_neural():
    global NEURAL, NEURAL_ERROR
    with NEURAL_LOCK:
        if NEURAL is None:
            if not models_present():
                raise RuntimeError('Research models are not installed. Run setup_research_windows.cmd first.')
            try:
                from research_models import NeuralEngine
                NEURAL = NeuralEngine(BASE,DOCS)
                NEURAL_ERROR = None
            except Exception as exc:
                NEURAL_ERROR = str(exc)
                raise RuntimeError('Research models could not load. Check the server log and local model installation.') from exc
    return NEURAL


def retrieve_research(question, as_of=None, variant='full', excluded=()):
    engine = get_neural()
    bm = BM.scores(question)
    dense, window_scores = engine.dense_scores(question)
    valid = np.array([i for i,m in enumerate(META)
                      if m['citation_id'] not in excluded
                      and (not as_of or (m['decision_date'] and m['decision_date'] <= as_of))],dtype=int)
    if not len(valid):
        return []
    sparse_order = valid[np.argsort(-bm[valid],kind='stable')]
    sparse_order = np.array([i for i in sparse_order if bm[i]>0],dtype=int)[:40]
    dense_order = valid[np.argsort(-dense[valid],kind='stable')]
    dense_order = np.array([i for i in dense_order if dense[i]>=0.25],dtype=int)[:40]
    rrf = np.zeros(len(DOCS))
    for order in (sparse_order,dense_order):
        for rank,i in enumerate(order,1):rrf[i]+=1/(60+rank)
    candidates=np.array(sorted(set(sparse_order)|set(dense_order)),dtype=int)
    if not len(candidates):return []
    candidates=candidates[np.argsort(-rrf[candidates],kind='stable')][:24]
    cross = engine.rerank(question,candidates,window_scores) if variant in {'reranked','full'} else {}
    similarity=cosine_similarity(VECTORIZER.transform([question]),MATRIX)[0]
    result=[]
    for i in candidates:
        if cross and cross[int(i)] < -2.0:continue
        base=float(1/(1+np.exp(-np.clip(cross[int(i)],-60,60)))) if cross else float(rrf[i]/(2/61))
        score=base*(1+0.15*META[i]['authority']) if variant=='full' else base
        result.append({'text':DOCS[i],**META[i],'bm25':float(bm[i]),'tfidf':float(similarity[i]),
                       'dense':float(dense[i]),'reranker_logit':cross.get(int(i)),
                       'relevance':float(rrf[i]/(2/61)),'final':score})
    return sorted(result,key=lambda r:-r['final'])[:TOP_K]


def verify_with_retry(question,claims,as_of=None,retry=True,excluded=()):
    engine=get_neural()
    initial=retrieve_research(question,as_of,excluded=excluded)
    checks=[]
    for claim in claims:
        first=engine.verify(claim,initial)
        evidence=list(initial)
        attempted=retry and first['label']!='Model-supported'
        if attempted:
            ids={e['citation_id'] for e in evidence}
            additions=retrieve_research(claim,as_of,excluded=excluded)
            evidence.extend(e for e in additions if e['citation_id'] not in ids)
        final=engine.verify(claim,evidence) if len(evidence)>len(initial) else first
        final.update({'initial_label':first['label'],'retrieval_rounds':2 if attempted else 1,
                      'added_chunks':len(evidence)-len(initial),'evidence_ids':[e['citation_id'] for e in evidence]})
        checks.append(final)
    accepted=[c for c in checks if c['label']=='Model-supported']
    return {'checks':checks,'accepted_claims':[c['claim'] for c in accepted],
            'decision':'All claims model-supported' if len(accepted)==len(checks) else
                       'Partially supported; review omitted claims' if accepted else 'Abstain: support not established',
            'note':'This checks your supplied statements, not copied answer sentences. NLI scores are uncalibrated model outputs. Mixed signals may reflect different cases or contexts; they do not establish a conflict in law. Decisions apply only to the checked evidence windows.',
            'excluded_citations':list(excluded)}


def retrieve(question, mode, top_k=TOP_K, as_of=None):
    bm = BM.scores(question)
    similarity = cosine_similarity(VECTORIZER.transform([question]), MATRIX)[0]
    query_terms = set(tokens(question)) - ENGLISH_STOP_WORDS
    coverage = [len(query_terms & set(tf)) / max(len(query_terms), 1) for tf in BM.tf]
    eligible = np.array([i for i, m in enumerate(META)
                         if bm[i] > 0 and similarity[i] >= MIN_SIMILARITY and coverage[i] >= 0.5
                         and (not as_of or (m['decision_date'] and m['decision_date'] <= as_of))], dtype=int)
    if not len(eligible):
        return []
    # RRF gives each retriever an equal vote without query-wise min-max scores.
    rrf = np.zeros(len(DOCS))
    for scores in (bm, similarity):
        order = eligible[np.argsort(-scores[eligible], kind='stable')]
        for rank, i in enumerate(order, 1):
            rrf[i] += 1.0 / (60 + rank)
    relevance = rrf / (2.0 / 61.0)
    # Authority only reranks the top 50 already relevant candidates.
    candidates = eligible[np.argsort(-relevance[eligible], kind='stable')][:50]
    final = relevance.copy()
    if mode == 'lex_rag':
        final[candidates] *= 1.0 + 0.15 * np.array([META[i]['authority'] for i in candidates])
    ordered = candidates[np.argsort(-final[candidates], kind='stable')][:top_k]
    return [{'text': DOCS[i], 'bm25': float(bm[i]), 'tfidf': float(similarity[i]),
             'relevance': float(relevance[i]), 'final': float(final[i]), **META[i]} for i in ordered]


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) >= 35]


def answer_for(question, results, neural=False):
    pool = []
    seen = set()
    for item in results:
        for sentence in sentences(item['text']):
            if sentence not in seen:
                pool.append((sentence, item))
                seen.add(sentence)
    if not pool:
        return []
    if neural:
        pool=pool[:120]
        engine=get_neural()
        sims=engine.encode([s for s,_ in pool]) @ engine.encode([question])[0]
    else:
        sims = cosine_similarity(VECTORIZER.transform([question]), VECTORIZER.transform([s for s, _ in pool]))[0]
    chosen = []
    for i in np.argsort(-sims, kind='stable'):
        if sims[i] < (0.25 if neural else MIN_SIMILARITY):
            continue
        sentence, item = pool[i]
        chosen.append({'claim': sentence, 'evidence': sentence, 'citation_id': item['citation_id'],
                       'case_id': item['case_id'], 'label': 'Exact source extract', 'score': 1.0})
        if len(chosen) == 4:
            break
    return chosen


def run_pipeline(question, mode, as_of=None):
    start = time.perf_counter()
    results = retrieve_research(question,as_of) if mode=='research' else retrieve(question, mode, as_of=as_of)
    claims = answer_for(question, results,neural=mode=='research')
    answer = '\n\n'.join(f"{c['claim']} [{c['citation_id']}]" for c in claims)
    if not answer:
        answer = 'Insufficient matching evidence in the indexed corpus. Try a more specific question or expand the dataset.'
    return {'system': 'Hybrid retrieval baseline' if mode == 'normal_rag' else 'LEX-RAG',
            'answer': answer, 'abstained': not bool(claims), 'evidence': results, 'claims': claims,
            'metrics': {'response_time_seconds': round(time.perf_counter() - start, 3),
                        'retrieved_chunks': len(results), 'distinct_cases': len({r['case_id'] for r in results}),
                        'known_court_chunks': sum(r['authority'] > 0 for r in results),
                        'source_linked_extracts': len(claims), 'abstained': not bool(claims)}}


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/review')
def review():
    return render_template('review.html')


@app.post('/api/compare-verification')
def compare_verification():
    if INIT_ERROR:
        return jsonify({'error': INIT_ERROR}), 503
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'error': 'Supply one question and one claim.'}), 400
    question, claim = body.get('question'), body.get('claim')
    if not isinstance(question, str) or not 3 <= len(question.strip()) <= 2000:
        return jsonify({'error': 'Question must contain 3 to 2,000 characters.'}), 400
    if not isinstance(claim, str) or not 5 <= len(claim.strip()) <= 600:
        return jsonify({'error': 'Claim must contain 5 to 600 characters.'}), 400
    from review_compare import compare, corpus_hash
    try:
        started = time.perf_counter()
        engine = get_neural()
        setup_seconds = time.perf_counter() - started
        result = compare(question.strip(), claim.strip(), engine, retrieve_research)
        result.update({'source': SOURCE, 'indexed_chunks': len(DOCS),
                       'indexed_cases': len({m['case_id'] for m in META}),
                       'corpus_sha256': corpus_hash(DOCS),
                       'setup_seconds': round(setup_seconds, 4)})
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 503


@app.get('/api/review-record/<name>')
def review_record(name):
    if name not in {'argument', 'tax', 'later', 'unsupported'}:
        return jsonify({'error': 'No recorded run for this example.'}), 404
    import json
    from review_compare import corpus_hash
    path = BASE / 'output' / 'review' / f'{name}.json'
    if not path.is_file():
        return jsonify({'error': 'Recorded run unavailable. Use the live comparison.'}), 404
    data = json.loads(path.read_text(encoding='utf-8'))
    data['recorded_snapshot'] = True
    data['matches_current_corpus'] = not INIT_ERROR and data.get('corpus_sha256') == corpus_hash(DOCS)
    return jsonify(data)


@app.get('/static/<name>')
def assets(name):
    if name not in {'style.css', 'app.js', 'review.css', 'review.js'}:
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(BASE, name)


@app.get('/api/status')
def status():
    return jsonify({'ready': INIT_ERROR is None, 'error': INIT_ERROR, 'source': SOURCE,
                    'judgments': len({m['case_id'] for m in META}), 'loaded_rows': len(ROWS),
                    'total_rows': TOTAL_ROWS, 'chunks': len(DOCS),
                    'known_court_chunks': sum(m['authority'] > 0 for m in META),
                    'dated_chunks': sum(bool(m['decision_date']) for m in META),
                    'research_available': models_present(), 'research_loaded': NEURAL is not None,
                    'research_error': NEURAL_ERROR,
                    'mode': 'Local extracts; optional dense retrieval, cross-encoder reranking and independent NLI claim checker'})


@app.post('/api/research')
def research():
    if INIT_ERROR:
        return jsonify({'error': INIT_ERROR}), 503
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('question'), str):
        return jsonify({'error': 'Supply a text question.'}), 400
    question = body['question'].strip()
    if not 3 <= len(question) <= 2000:
        return jsonify({'error': 'Enter a question between 3 and 2,000 characters.'}), 400
    as_of = body.get('as_of') or None
    if as_of is not None:
        try:
            if not isinstance(as_of, str) or date.fromisoformat(as_of).isoformat() != as_of:
                raise ValueError()
        except (ValueError, TypeError):
            return jsonify({'error': 'Use YYYY-MM-DD for the decision cutoff.'}), 400
    use_research=body.get('research_mode',False)
    if not isinstance(use_research,bool):
        return jsonify({'error':'research_mode must be true or false.'}),400
    try:
        proposed=run_pipeline(question,'research' if use_research else 'lex_rag',as_of)
    except RuntimeError as exc:
        return jsonify({'error':str(exc)}),503
    return jsonify({'question': question, 'as_of': as_of, 'research_mode':use_research,
                    'normal_rag': run_pipeline(question, 'normal_rag', as_of),
                    'lex_rag': proposed,
                    'comparison_note': ('Research mode adds dense retrieval and cross-encoder reranking to the lexical baseline, plus the authority bonus. This is a multi-component comparison; use the evaluation script for ablations. Both answers remain extracts.' if use_research else 'Both systems use the same relevance gate, BM25 + TF-IDF RRF, top-50 candidates, top-5 budget, date filter and extractive answer method. Only the metadata-based authority bonus differs.'),
                    'metric_note': 'Counts and timings are diagnostics, not accuracy scores. Exact extracts demonstrate source traceability, not legal correctness or NLI entailment. A single-court corpus may produce identical rankings. A decision cutoff excludes undated cases and does not establish whether a precedent remains valid.'})


@app.post('/api/verify')
def verify_endpoint():
    if INIT_ERROR:return jsonify({'error':INIT_ERROR}),503
    body=request.get_json(silent=True)
    if not isinstance(body,dict):return jsonify({'error':'Supply a question and a list of claims.'}),400
    question=body.get('question')
    claims=body.get('claims')
    if not isinstance(question,str) or not 3<=len(question.strip())<=2000:
        return jsonify({'error':'Question must contain 3 to 2,000 characters.'}),400
    if not isinstance(claims,list) or not 1<=len(claims)<=3 or any(not isinstance(c,str) or not 5<=len(c.strip())<=600 for c in claims):
        return jsonify({'error':'Supply 1 to 3 short claims, each 5 to 600 characters.'}),400
    as_of=body.get('as_of') or None
    if as_of is not None:
        try:
            if not isinstance(as_of,str) or date.fromisoformat(as_of).isoformat()!=as_of:raise ValueError()
        except (ValueError,TypeError):return jsonify({'error':'Use YYYY-MM-DD for the cutoff.'}),400
    retry=body.get('retry',True)
    excluded=body.get('excluded_citations',[])
    if not isinstance(retry,bool) or not isinstance(excluded,list) or len(excluded)>20 or any(not isinstance(x,str) for x in excluded):
        return jsonify({'error':'Invalid retry or excluded_citations.'}),400
    known={m['citation_id'] for m in META}
    if not set(excluded)<=known:return jsonify({'error':'An excluded citation is not in this index.'}),400
    try:
        result=verify_with_retry(question.strip(),[c.strip() for c in claims],as_of,retry,excluded)
        return jsonify(result)
    except ValueError as exc:return jsonify({'error':str(exc)}),400
    except RuntimeError as exc:return jsonify({'error':str(exc)}),503


if __name__ == '__main__':
    from waitress import serve
    port = int(os.getenv('LEXRAG_PORT', '5000'))
    print(f'LEX-RAG: http://127.0.0.1:{port}', flush=True)
    if INIT_ERROR:
        print(f'Dataset error: {INIT_ERROR}', flush=True)
    serve(app, host='127.0.0.1', port=port, threads=4)
