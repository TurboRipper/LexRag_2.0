# Second review: demo and speaking notes

Open http://127.0.0.1:5000/review after starting `start_windows.cmd`.
The research homepage also has a **Review demo** link in the sidebar.

## A five-minute presentation

1. **Problem (30 seconds).** A relevant passage is not always enough evidence to support a claim. A passage may state what a party argued rather than what the court decided; checking only the start of retrieved context can miss relevant evidence.
2. **Architecture (45 seconds).** Existing keyword/semantic retrieval and reranking supply evidence. The demo compares the same NLI model and threshold under a prefix budget, overlapping windows, and a conditional claim-focused second search. These are local strategy ablations, not reproductions of entire published projects.
3. **Live example (90 seconds).** Keep the first example selected and click **Run all three strategies**. Show the labels and support scores, then open the supporting passage in B. A checked only the first 1,000 source characters; B considered windows across the same retrieved passages. C skips a second search because B already found model support.
4. **Counterexample (45 seconds).** Choose **Broad tax claim** and run it. Explain that re-search does not guarantee support. A narrower statement about what the appellant claimed is different from a general rule about tax deductibility.
5. **Contribution and next steps (60 seconds).** Use the literature table. The engineering prototype is implemented. The research contribution under investigation is whether evidence coverage and bounded re-search improve claim verification at an acceptable CPU cost. Independent claim labels, calibration and larger controlled experiments are still needed.
6. **Save (10 seconds).** Click **Download this run** for the full question, claim, decisions, passages, timings, corpus hash and model revisions.

## Recorded fallback

Each of the four presets has **Show recorded example**. This loads actual saved model output from `output/review/`, explicitly marked as recorded with its timestamp. It does not run the models. Keep this folder when copying the project for the review. A corpus-match indication detects a changed index. The first live run may require model loading; recorded output is useful if time is short.

## Results observed during preparation

These four examples are illustrative and unlabelled, not an accuracy test set. All results are included; no success rate is calculated.

| Example | A: prefix | B: windows | C: windows + re-search | Added passages |
|---|---|---|---|---|
| argument | Not established | Model-supported | Model-supported | 0 |
| tax | Not established | Not established | Not established | 0 |
| later | Model-contradicted | Model-contradicted | Model-contradicted | 0 |
| unsupported | Model-contradicted | Model-contradicted | Model-contradicted | 0 |

For the first example:

- Question: Are municipal property taxes deductible from income from property?
- Claim: The appellant claimed a deduction for municipal and urban property taxes.
- Highest support-scoring window: A **0.017**, B **0.951**, C **0.951**.
- Evidence budget: A 1,000 source characters / 3 checked windows; B 5,055 eligible characters / 10 checked windows.
- Strategy work: A 0.199 seconds; B 0.620 seconds. Initial retrieval took 0.939 seconds and is shared. These are one-run local timings, not stable performance estimates.
- C reused B and skipped retry. Do not claim this example demonstrates a retry benefit.
- On the other three examples, retry was attempted but added no new passages and changed no label. This is a current limitation, not evidence of improvement.

The context-sensitive and unrelated examples returned contradiction signals. These signals must be inspected against the text: a general NLI model can confuse absent support, lexical mismatch and genuine contradiction. They are not human-reviewed legal labels.

## What to say to the trainer

> I am using existing models as building blocks. My demo compares evidence strategies while keeping the claim, initial retrieval and NLI model fixed. On this example, a prefix-limited verifier misses support that window-based verification finds. The wider check costs more computation. This demonstrates a concrete evidence-coverage difference, not overall superiority over LegalMind or other projects. I will establish any research improvement using independently reviewed claims and controlled ablations.

If asked **“What is new?”**, answer:

> At this stage I have an implemented extension and a testable research question. Windowing, verification and iterative retrieval already exist. I am investigating their budgeted application to Indian legal claims; the novelty claim depends on a differentiated method or dataset and comparative results.

If asked **“Why not just use a bigger model?”**, answer:

> The comparison holds the verifier model fixed, so it demonstrates that the supplied evidence can change a decision. It does not prove that our model choice is optimal.

If asked **“Is 0.951 equal to 95.1% legal accuracy?”**, answer:

> No. It is an uncalibrated NLI support score for one checked passage. Accuracy requires independent labels over many examples.

If asked **“Did you beat the other papers?”**, answer:

> We have not reproduced and benchmarked their complete systems. The literature table compares methods; the live table compares variants within this implementation.

## Experimental limits to know

- No independent gold labels in these demo examples; no fabricated accuracy percentages.
- A is a first-1,000-source-character ablation, segmented by original passage and checked with our MiniLM model. It is not a full reproduction of LegalMind's DeBERTa verifier.
- B/C have larger evidence/compute budgets than A. Their timing and coverage differences must be reported together.
- NLI checks at most 48 windows per invocation. Overlap and larger evidence pools can also produce false support; more text is not automatically better.
- The indexed corpus is a development subset: 6,000 chunks / 286 text-derived case identifiers. No structured court/date metadata is available in this CSV.
- Answers in the main app are source extracts. The comparison verifies a supplied statement; it does not automatically validate every answer.
- The 24 passing regression tests establish code behavior, not legal effectiveness.

See `CONTRIBUTION_ASSESSMENT.md` for the 20-paper comparison and broader prior art.
