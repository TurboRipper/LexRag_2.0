"""Evaluate independently reviewed case-level qrels; never creates gold labels."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def retrieval_metrics(ranked, relevant, k=5):
    ranked=list(dict.fromkeys(ranked))[:k]
    gold=set(relevant)
    if not gold:
        return {'recall_at_5':None,'precision_at_5':None,'mrr':None,'ndcg_at_5':None,
                'returned_evidence':bool(ranked)}
    hits=[int(x in gold) for x in ranked]
    dcg=sum(hit/math.log2(i+2) for i,hit in enumerate(hits))
    ideal=sum(1/math.log2(i+2) for i in range(min(k,len(gold))))
    return {'recall_at_5':sum(hits)/len(gold),'precision_at_5':sum(hits)/k,
            'mrr':next((1/(i+1) for i,hit in enumerate(hits) if hit),0),
            'ndcg_at_5':dcg/ideal,'returned_evidence':bool(ranked)}


def load_labels(path):
    rows=[json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if not rows:raise ValueError('No evaluation questions supplied.')
    ids=set()
    for r in rows:
        if r.get('reviewed') is not True:raise ValueError('Every query must have independently reviewed labels (reviewed: true).')
        if not isinstance(r.get('id'),str) or r['id'] in ids:raise ValueError('Use unique string query IDs.')
        ids.add(r['id'])
        if not isinstance(r.get('question'),str) or not r['question'].strip():raise ValueError('Missing question.')
        gold=r.get('relevant_case_ids')
        if not isinstance(gold,list) or any(not isinstance(x,str) for x in gold):raise ValueError('Supply relevant_case_ids as a list of strings.')
        if not isinstance(r.get('answerable'),bool) or r['answerable']!=bool(gold):raise ValueError('Answerability and gold case IDs disagree.')
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('labels',help='Reviewed JSONL questions and case-level relevance labels')
    parser.add_argument('--output',default='output/evaluation.json')
    args=parser.parse_args()
    labels=load_labels(args.labels)
    import app
    if app.INIT_ERROR:raise RuntimeError(app.INIT_ERROR)
    corpus={m['case_id'] for m in app.META}
    missing={g for r in labels for g in r['relevant_case_ids'] if g not in corpus}
    if missing:raise ValueError(f'Gold cases missing from indexed corpus: {sorted(missing)[:10]}. Expand indexing before evaluation.')
    results=[]
    for r in labels:
        for variant in ('lexical','dense_hybrid','reranked','full'):
            evidence=app.retrieve(r['question'],'normal_rag') if variant=='lexical' else app.retrieve_research(r['question'],variant=variant)
            ranked=[e['case_id'] for e in evidence]
            results.append({'query_id':r['id'],'variant':variant,'ranked_cases':list(dict.fromkeys(ranked)),
                            **retrieval_metrics(ranked,r['relevant_case_ids'])})
    means={}
    for variant in ('lexical','dense_hybrid','reranked','full'):
        subset=[x for x in results if x['variant']==variant]
        means[variant]={}
        for key in ('recall_at_5','precision_at_5','mrr','ndcg_at_5'):
            values=[x[key] for x in subset if x[key] is not None]
            means[variant][key]=sum(values)/len(values) if values else None
        unanswerable=[x for x in subset if x['recall_at_5'] is None]
        means[variant]['unanswerable_queries_returning_evidence']=sum(x['returned_evidence'] for x in unanswerable)
        means[variant]['unanswerable_query_count']=len(unanswerable)
    report={'query_count':len(labels),'indexed_cases':len(corpus),'indexed_chunks':len(app.DOCS),
            'labels_sha256':hashlib.sha256(Path(args.labels).read_bytes()).hexdigest(),
            'corpus_sha256':hashlib.sha256(json.dumps(list(zip(app.DOCS,app.META)),sort_keys=True).encode()).hexdigest(),
            'models':app.get_neural().manifest,'means':means,'per_query':results,
            'scope':'Case-level binary labels, deduplicated top-5 chunk results. Not a claim-verification or legal-correctness score. No confidence intervals; include them in a publication study.'}
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'Saved {output}')


if __name__=='__main__':main()
