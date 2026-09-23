"""Transparent, paired verification ablations for the review demo."""
import hashlib
import json
import time
from datetime import datetime, timezone


def corpus_hash(docs):
    return hashlib.sha256(json.dumps(docs, ensure_ascii=False).encode()).hexdigest()


def prefix_evidence(evidence, limit=1000):
    """First 1,000 source characters in retrieval order; preserve source offsets.

    Each source segment is verified separately, using the same window/token rules
    as other variants. This is a prefix-budget ablation, not a paper reproduction.
    """
    selected = []
    for item in evidence:
        if limit <= 0:
            break
        text = item['text'][:limit]
        if text:
            selected.append({**item, 'text': text})
            limit -= len(text)
    return selected


def timed_check(engine, claim, evidence):
    start = time.perf_counter()
    result = engine.verify(claim, evidence)
    return result, time.perf_counter() - start


def compare(question, claim, engine, retrieve):
    start = time.perf_counter()
    initial = retrieve(question)
    retrieval_seconds = time.perf_counter() - start
    prefix = prefix_evidence(initial)
    first, prefix_seconds = timed_check(engine, claim, prefix)
    second, window_seconds = timed_check(engine, claim, initial)
    combined = list(initial)
    third = second
    retry_seconds = 0.0
    retried = second['label'] != 'Model-supported'
    if retried:
        start = time.perf_counter()
        known = {item['citation_id'] for item in combined}
        for item in retrieve(claim):
            if item['citation_id'] not in known:
                combined.append(item)
                known.add(item['citation_id'])
        if len(combined) > len(initial):
            third = engine.verify(claim, combined)
        retry_seconds = time.perf_counter() - start

    variants = []
    for key, name, check, evidence, seconds, rounds, added in [
        ('prefix', 'A · Prefix only', first, prefix, prefix_seconds, 1, 0),
        ('windows', 'B · Evidence windows', second, initial, window_seconds, 1, 0),
        ('retry', 'C · Windows + re-search', third, combined, window_seconds + retry_seconds,
         2 if retried else 1, len(combined) - len(initial)),
    ]:
        variants.append({
            'id': key, 'name': name, 'check': check,
            'eligible_characters': sum(len(item['text']) for item in evidence),
            'passages': len(evidence), 'retrieval_rounds': rounds, 'added_passages': added,
            'strategy_seconds': round(seconds, 4),
            'estimated_pipeline_seconds': round(retrieval_seconds + seconds, 4),
            'evidence_ids': [item['citation_id'] for item in evidence],
        })
    return {
        'question': question, 'claim': claim, 'variants': variants,
        'initial_retrieval_seconds': round(retrieval_seconds, 4),
        'retry_seconds': round(retry_seconds, 4),
        'retry_attempted': retried,
        'initial_evidence': initial,
        'additional_evidence': combined[len(initial):],
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'models': engine.manifest,
        'controls': {
            'same_claim_and_nli_model': True, 'same_initial_retrieval': True,
            'threshold': 0.8, 'prefix_characters': 1000, 'maximum_windows_per_check': 48,
            'window_tokens': 190, 'window_overlap_tokens': 40,
            'independent_gold_labels': False, 'equal_compute_budget': False,
        },
        'scope': 'Live ablation on one claim, not an accuracy benchmark or reproduction of another project. '
                 'A uses the first 1,000 source characters, scored per source segment with the same NLI model. '
                 'B and C have larger evidence budgets. NLI scores are uncalibrated. '
                 'Initial retrieval is shared; C reuses B and adds measured retry work. '
                 'Pipeline times are component sums, not independent end-to-end benchmark runs.',
    }
