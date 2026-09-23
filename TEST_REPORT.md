# Verification performed after the research upgrade

Environment: local Windows laptop; Python 3.12 virtual environment; PyTorch 2.14.0 CPU; Transformers 4.57.6. `pip check` reports no broken dependencies. Model repository revisions are pinned in models/manifest.json.

## Automated checks

19 unittest regression checks passed. In addition to the original 11 checks, research tests cover:
- Token windows preserve exact source offsets and include the end of long text.
- Supporting evidence beyond character 1,000 can be checked (controlled fake-model fixture).
- Contradictory model evidence is not hidden when another passage supports the claim.
- Retry preserves excluded citations and date cutoff, and can be disabled.
- Evaluation deduplicates case IDs and does not inflate recall through duplicate chunks.
- Unreviewed evaluation labels are rejected.
- Invalid claim-check inputs return validation errors.

JavaScript passed Node syntax checking.

## Live model checks

- Downloaded and loaded all three public model snapshots locally with safetensors.
- Indexed 7,672 semantic windows from the default 1,394 chunks / 300 cases.
- First index build and model load took 150.42 seconds in this run; later requests reuse the saved embeddings.
- A research-mode bail query returned four evidence chunks from three cases, with source-linked extracts. One warm query took about 1.8 seconds; timing is machine/load dependent and is not a benchmark average.
- Simple artificial NLI probes separated an affirmative statement from its direct negation. A neutral probe did not cross the 0.80 support or contradiction threshold. These are operational smoke checks, not a legal NLI accuracy evaluation.
- A claim about witness interference triggered a second evidence search and remained Not established. The UI does not force a positive result.
- In the browser, the statement about giving the Public Prosecutor an opportunity to oppose a bail application was model-supported, with 23/23 evidence windows checked and a displayed source passage. This only verifies that the UI and NLI pipeline function.
- Research-mode off-topic query returned no evidence and abstained.
- Research-mode cutoff of 1900-01-01 returned no evidence and abstained.
- Server status reports research models loaded, and the upgraded UI was visually inspected.

No held-out, legally reviewed evaluation set was supplied. No retrieval improvement, legal-correctness score, hallucination reduction, or publication novelty is claimed. General NLI predictions can be wrong and may confuse different factual contexts. See RESEARCH_METHODS.md for scope and limitations.
