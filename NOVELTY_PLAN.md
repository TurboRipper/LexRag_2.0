> Implementation update: local dense retrieval, cross-encoder reranking, window-based NLI for independently supplied claims, and one additional verification-guided retrieval round are now implemented. See RESEARCH_METHODS.md for current behavior. The plan below records the original research proposal; its "Current portable version" column describes the pre-upgrade baseline. Generative answer production and verifier-driven regeneration are still not implemented, and publication novelty remains unproven.

# LEX-RAG: a defensible research contribution

## Proposed project title

**Evidence-Sufficiency-Aware Legal Retrieval with Claim-Level Verification and Selective Answering for Indian Judgments**

This is a research proposal, not a verified claim that the combination is original or that the implementation already achieves it. A literature review and controlled experiments are still required.

## Why the original implementation was not sufficient

The original code combined BM25 and TF-IDF with a fixed court-weight bonus, then extracted sentences and checked their lexical similarity to the same source. It did not use dense embeddings, an LLM or NLI. Scoring a copied sentence against its source makes high apparent support nearly automatic. It also inferred court hierarchy from mentions in the text, potentially confusing a cited Supreme Court decision with the issuing court.

Authority-aware ranking, agentic verification and Indian-law RAG already appear in the supplied literature. Do not claim any one of them, or merely joining them, as a new invention.

Relevant prior work:

- Singh, *Precedent-Aware Multi-Agent Retrieval-Augmented Generation in Case Law Analysis*: authority-aware precedent ranking and citation verification. Publisher PDF: https://ijisrt.com/assets/upload/files/IJISRT25DEC1556.pdf
- Pipitone and Houir Alami, *LegalBench-RAG*: evaluates retrieval against annotated legal evidence. Paper: https://arxiv.org/abs/2408.10343 ; authors' repository: https://github.com/ZeroEntropy-AI/legalbenchrag
- Park et al., *LRAGE*: component-level RAG evaluation. Paper: https://arxiv.org/abs/2504.01840
- The supplied `IJISRT26MAY1714.pdf` describes LegalMind with a DeBERTa NLI verifier; `2605.14665v2.pdf` describes graph-constrained verification and conflicts. These are close comparisons, not evidence that verification is new.

## Narrow research question

Does a policy that conditions authority ranking and answer acceptance on sufficient, traceable evidence reduce unsupported claims at a comparable answer coverage, particularly when relevant evidence is missing, temporally unavailable, contradicted or from another jurisdiction?

The potential contribution should be the **tested evidence-sufficiency policy and a reproducible Indian-law stress-test set**, rather than a new name for an existing RAG pipeline. Legal authority and semantic entailment are separate dimensions; one must not compensate for absence of the other.

## Implemented foundation versus remaining work

| Component | Current portable version | Research extension |
|---|---|---|
| Corpus provenance | Preserved case/chunk IDs, dates and pages | Audit OCR and source metadata; add validated mixed-court cases |
| Retrieval | BM25 + TF-IDF RRF; lexical relevance gate | BM25 + locally cached dense embeddings; reranker; calibrated sufficiency threshold |
| Authority | Small explicit court-metadata bonus within relevant candidates | Reviewed jurisdiction, hierarchy and subsequent-treatment features; no invented bindingness labels |
| Temporal scope | Optional decision cutoff; unknown dates excluded | Validate amendment and precedent-treatment dates; distinguish issue date from continued validity |
| Answering | Source-linked extracts; heuristic abstention | Same generator for all ablations; atomic claim decomposition |
| Verification | Exact source traceability only | NLI entailment/contradiction plus citation existence; domain-calibrated thresholds |
| Evaluation | Regression tests and runtime diagnostics | Independently labeled retrieval/claim data; accuracy/coverage tradeoff and confidence intervals |

Do not rename the current extractor as an LLM, TF-IDF as dense retrieval, or source matching as NLI. A CPU-only extractive demonstrator is useful for both laptops; the research model can be a separately measured configuration once laptop RAM and approved model access are known.

## Suggested study

1. Start with 60-100 legally reviewed questions, including unanswerable questions, and a documented jurisdiction/date scope. Mark relevant case IDs and minimal evidence spans. Have two annotators review at least a subset and resolve disagreements. Do not fabricate gold labels or use model-generated labels as legal ground truth.
2. Split by case, not by chunk; keep overlapping chunks and related query variants in the same split. Tune thresholds on development data only. Freeze the evaluation corpus, random seeds, model versions and configurations before testing.
3. Compare: BM25; hybrid RRF; hybrid plus authority; hybrid plus NLI; hybrid plus authority and NLI; full method with calibrated abstention. Keep generator, retrieval budget and prompts constant. Test the portable extractor separately from generative variants.
4. Build paired stress tests: remove an essential evidence span; exclude a necessary decision with a cutoff; insert a topically similar but unsupported passage; add an expert-verified conflicting proposition; substitute authority metadata only in explicitly labeled synthetic diagnostic tests. Preserve an untouched original test set.
5. Measure retrieval Recall@5, MRR and nDCG using independent relevance labels. Measure human-supported claim rate, contradiction-detection precision/recall, citation correctness, answer coverage, risk at matched coverage, latency and peak RAM. Always report denominators, abstentions and confidence intervals. Do not assign perfect accuracy to an answer with no claims.
6. Assess evidence sensitivity: does the method abstain, revise or flag uncertainty when required evidence is removed? Track whether residual passages still support an answer; removal alone does not prove an answer is unsupported. Compare performance before/after perturbation and against abstention-enabled baselines.

A simple acceptance policy to test: answer only when all material claims have a valid source citation and sufficiently calibrated entailment, with no unresolved material contradiction; otherwise return the supported subset with explicit uncertainty or abstain. This is a candidate policy, not a legal guarantee or established novel algorithm.

## What this dataset can and cannot show

The supplied corpus has 2,219 distinct case IDs and 11,389 rows, almost all labeled High Court of Sikkim. A uniform court-hierarchy feature cannot prove a ranking gain. Add reviewed Supreme Court and other High Court material before evaluating hierarchy/jurisdiction effects. Unknown metadata should remain unknown; citations in the judgment body do not identify the issuing court. Suspicious bench-strength values require audit before use.

Sikkim data can still support retrieval, OCR-quality, source-traceability, temporal filtering and evidence-sensitivity experiments. If mixed-court data is unavailable, narrow the contribution to selective, evidence-grounded retrieval over this corpus and remove claims about demonstrated authority gains.

## Suitable review statement

"The project investigates whether evidence-sufficiency checks and calibrated abstention improve the reliability of legal answers under missing or conflicting evidence. The portable prototype implements local retrieval, metadata-aware reranking and source-linked extraction. The proposed research extension adds claim-level NLI and evaluates the combined policy against controlled ablations and a legally reviewed Indian-judgment stress-test set."

Avoid statements such as "first-ever", "hallucination-free", or numerical performance improvements until supported by a broader literature review and completed experiments.
