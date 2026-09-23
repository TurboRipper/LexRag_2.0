# Research methods now implemented in LEX-RAG

This is an adaptation of selected methods and future-work ideas from the uploaded papers. It is not a reproduction of all their systems, and implementing published methods is not by itself a novelty claim.

## Paper-to-code mapping

| Uploaded paper | Relevant method or limitation | What is implemented here |
|---|---|---|
| `2608.06828v1.pdf`, Rhetorical-Role-Aware RAG, sections 3.2-3.3 | Sparse+dense retrieval and cross-encoder reranking | BM25 plus MiniLM semantic retrieval, RRF fusion, then a MiniLM cross-encoder; no trained rhetorical-role classifier is claimed |
| `IJISRT26MAY1714.pdf`, LegalMind, sections IV and X | NLI verification; only the first 1,000 context characters are checked | Actual three-class NLI over overlapping evidence windows drawn from throughout the retrieved text, preserving exact source offsets |
| Same paper, section X | Future iterative feedback and targeted regeneration | A narrower implemented adaptation: an unsupported or conflicting claim triggers one additional claim-focused retrieval round and re-verification. No LLM regeneration is implemented |
| `2504.01840v2.pdf`, LRAGE | Evaluate individual components | `evaluate.py` compares lexical, dense-hybrid, reranked and authority-enhanced retrieval against independently reviewed case-level labels |
| `2408.10343v1.pdf`, LegalBench-RAG | Evaluate retrieval using annotated evidence | A reviewed-label input format and real Recall@5, Precision@5, MRR and nDCG calculations; no fabricated labels or performance results |
| `IJISRT25DEC1556.pdf`, Precedent-Aware Multi-Agent RAG | Legal authority ranking | Retains the explicit-court metadata bonus within relevant candidates. Jurisdictional bindingness, negative treatment and agent planning are not implemented |

## How to use it

1. Start the application and open http://127.0.0.1:5000.
2. Keep **Use research models** checked for neural retrieval. Uncheck it for the previous lightweight comparison.
3. Ask a question. Both answer panels still contain source-linked extracts, not newly generated legal advice.
4. In **Check a statement against the judgments**, enter one short statement per line, up to three. These can be your own statements or candidate answer claims.
5. Click **Check evidence**. Open the supporting or contradicting windows to see the exact source text and offsets.
6. Toggle **Search again** to compare one-pass verification with the feedback retrieval extension.

Meanings of checker outputs:

- **Model-supported**: at least one checked window has entailment >= 0.80 and none has contradiction >= 0.80.
- **Model-contradicted**: at least one checked window has contradiction >= 0.80, without a high-scoring supporting window.
- **Mixed evidence signals**: both exist. Different cases and factual circumstances can cause this; it does not establish conflicting precedent.
- **Not established**: no checked window meets either threshold. This does not prove that no evidence exists elsewhere.

The decision returns only model-supported input statements as `accepted_claims`; otherwise it returns a partial-support or abstention status. It does not silently rewrite claims. Exact extracted sentences are displayed separately and are not counted as a meaningful NLI accuracy experiment.

## Local models and limits

| Task | Model | Important limit |
|---|---|---|
| Semantic search | `sentence-transformers/all-MiniLM-L6-v2` | General-purpose English model; 190-token windows, 40-token overlap, normalized mean pooling |
| Reranking | `cross-encoder/ms-marco-MiniLM-L6-v2` | Scores at most two semantic windows for each of the top 24 candidate chunks; may miss other relevant windows |
| NLI | `cross-encoder/nli-MiniLM2-L6-H768` | Smaller CPU-friendly substitute for LegalMind's DeBERTa model; trained on general NLI, not validated Indian legal entailment |

Model revision hashes are saved in `models/manifest.json`. Downloads use public repositories without an account; inference is local-only, loads safetensors and disables remote model code. The weights occupy about 510 MB (decimal). Models and libraries use additional disk space and memory. The first index build takes longer than normal queries; embeddings are cached by corpus content, windowing configuration and encoder revision.

Research retrieval uses the top 40 BM25 candidates and top 40 semantic candidates (cosine >= 0.25), RRF fusion, top 24 candidates for reranking, and a reranker logit cutoff of -2.0. The full mode adds a 15% times court-weight bonus. These thresholds are provisional; they are not legally calibrated confidence levels.

NLI checks up to 48 overlapping windows per claim. If more exist, it ranks windows from the entire evidence set by claim similarity, checks the best 48, and reports partial coverage. Thus later text is eligible, but exhaustive inspection of every retrieved token is not guaranteed on large results. At most 140 NLI tokens are allowed per claim. The retry adds up to five new chunks, preserves cutoff/exclusions, and stops after one extra round. A supported claim stops without retry; this is a latency tradeoff, not proof that contrary evidence does not exist.

The default corpus remains a 300-case development subset. Your full file has 2,219 distinct case IDs, predominantly Sikkim High Court. A single-court corpus cannot establish general court-hierarchy ranking improvements.

## API examples

`POST /api/research`:

```json
{"question":"What factors are considered when granting bail?","research_mode":true,"as_of":null}
```

`POST /api/verify`:

```json
{"question":"What factors are considered when granting bail?","claims":["The court considers the risk of influencing witnesses."],"retry":true,"as_of":null,"excluded_citations":[]}
```

For a controlled evidence-removal experiment, put valid citation IDs into `excluded_citations`. Both retrieval rounds exclude them. Removing one chunk does not remove the entire case or duplicate evidence in other chunks; annotate whether sufficient evidence truly disappeared before interpreting the outcome.

## Evaluation without invented results

Copy `evaluation_template.jsonl`, replace the question and gold case IDs, and obtain independent legal review. Set `reviewed: true` only after that review. Provide several reviewed rows; use `answerable: false` with no gold IDs only for reviewed unanswerable queries. The template intentionally cannot be evaluated as-is.

```bat
.venv\Scripts\python.exe evaluate.py reviewed_questions.jsonl --output output/evaluation.json
```

Gold cases must be in the loaded index; the script fails if they are missing. It evaluates unique case IDs within the top-five returned chunks, so duplicate chunks from one case do not inflate recall. Precision@5 uses a denominator of five even when fewer cases are returned. Unanswerable queries have null relevance metrics and a separate returned-evidence count. The report saves corpus/label hashes and model revisions.

These retrieval metrics do not measure NLI correctness, generated-answer quality, risk-coverage curves or publication significance. Those need separate human claim labels and statistical analysis. Regression tests use controlled fixtures to verify code behavior; live model smoke tests check operation, not research effectiveness.

## What still needs research

- Legally reviewed retrieval and NLI test sets, held out by case.
- Threshold calibration and uncertainty intervals.
- Robust testing of contradictions across differing facts, dates and jurisdictions.
- Mixed-court data and reliable precedent-treatment metadata for authority claims.
- Generative answers and true verifier-guided regeneration, if that is part of the final research question.
- Larger-corpus and bilingual evaluation.

A potentially useful contribution is the measured effect of whole-evidence window selection plus one-round verification-guided retrieval under missing evidence. It remains a hypothesis until comparative experiments and a broader literature review support it.
