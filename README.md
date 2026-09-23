# Run this GitHub version on Windows

1. Install Python 3.12 (64-bit).
2. Download this repository as a ZIP and extract it, or clone it.
3. Run `setup_windows.cmd`.
4. Run `.venv\Scripts\python.exe download_dataset.py` in the project folder.
5. Run `setup_research_windows.cmd` to install the research libraries and download the models.
6. Run `start_windows.cmd`.
7. Open http://127.0.0.1:5000 for research or http://127.0.0.1:5000/review for the review demo.

Internet is required for the first installation and downloads. Inference then runs locally.
The large `data/` CSV and model weights are downloaded rather than stored in Git.
`models/manifest.json` pins the model revisions used for the demo. The four recorded
examples in `output/review/` are included and explicitly labelled as saved runs.
For a laptop without internet, transfer the downloaded data, models and a complete
Windows Python 3.12 dependency wheelhouse separately. Do not copy `.venv` between laptops.

# Research interface

For the second-review presentation, open **http://127.0.0.1:5000/review** or select
**Review demo** in the sidebar. It compares prefix-only verification, evidence
windows, and conditional re-search using the same local model. Real recorded
examples are available as a fallback; keep `output/review` when copying this demo.
See [REVIEW_DEMO_GUIDE.md](REVIEW_DEMO_GUIDE.md) for the five-minute presentation,
observed results, and limitations. These are illustrative ablations, not accuracy
scores or reproductions of published systems.

The question-first interface includes suggested prompts, a conversation view with
clickable source citations, and in-memory question history for the current page
session (refreshing clears it). New research clears the conversation while keeping
that session history. The Clear button clears both. Each question is searched
independently; previous messages are not model context.

Search options contains the optional deeper research models and date cutoff. Basic
search is selected initially for faster startup. The connected CSV has no decision
dates, so the interface disables its date cutoff. Source passages, source traceability,
method comparison, JSON export and the statement checker remain available below the
question box. Answers are source extracts, not generated conversational legal advice.

# Connected Hugging Face dataset

The Windows launcher now selects `ninadn/indian-legal`, training split:
https://huggingface.co/datasets/ninadn/indian-legal/resolve/main/train.csv

Download it once with `.venv\Scripts\python.exe download_dataset.py`, then run
`start_windows.cmd` and open http://127.0.0.1:5000. The downloaded CSV is cached in
`data/indian-legal-train.csv`; its source URL and SHA-256 are saved alongside it.
Subsequent starts work offline. Set `LEXRAG_DATASET` to override the launcher's selection.
Running `app.py` directly retains the original local Sikkim default unless this variable is set.

Retrieval uses the `Text` column, not the reference `Summary`. The existing development
limits still apply: up to 300 distinct texts and 6,000 chunks, with at most 30 chunks
per unchunked judgment. Court, title and decision-date metadata are not supplied by
this CSV. Court authority remains unknown, and applying a date cutoff excludes these
undated records. The Sikkim-specific counts below describe the original bundled corpus.

# LEX-RAG research upgrade

The application now has an optional **research mode** with real semantic retrieval, neural reranking and a separate NLI claim checker. These models are already installed on this laptop. See [RESEARCH_METHODS.md](RESEARCH_METHODS.md) for the uploaded-paper mapping, usage, limits and evaluation commands.

On another laptop, run `setup_windows.cmd` first, then `setup_research_windows.cmd` to install the extra libraries and download three public models (about 510 MB). Basic search works without them. For offline research setup, copy `models` plus a complete research `wheelhouse`, run basic setup, then research setup. Model files must include `models/manifest.json`.

**The answer panels still use extracted sentences.** NLI checks independently supplied statements in the new checker; no generative LLM or automatic answer regeneration is claimed.

The following sections describe the original lightweight mode and general Windows setup. Research mode has different retrieval gates and model costs, documented separately.

# Run LEX-RAG on Windows 11

This repository now runs locally on a CPU, using the supplied Parquet file. No GPU, AI API key, external model download, or internet connection is required after dependency installation. Python dependencies need either internet access during setup or an offline wheelhouse.

## First installation on each laptop

1. Install **Python 3.12, Windows x64**, using a per-user installation or your company's approved Python installation. Official installer: https://www.python.org/downloads/windows/
2. Copy the project folder (or unzip `LEXRAG_Windows.zip`) into a directory where you can write files.
3. Double-click `setup_windows.cmd`. This creates a separate `.venv` and installs the pinned dependencies. No virtual-environment activation or PowerShell execution-policy change is needed.
4. Double-click `start_windows.cmd`. Wait for the index to load, then open **http://127.0.0.1:5000** in Edge or Chrome. Keep the console open; Ctrl+C stops the app.

Run these steps separately on both laptops. Do not copy `.venv` between machines. The release ZIP includes the local dataset, source, setup scripts, tests and research plan, but not Python or installed dependencies. The interface is served by Flask: opening `index.html` directly will not work.

## Company laptop without package-index access

On the internet-connected Windows x64 laptop, after setup, run `prepare_offline_windows.cmd`. Copy the project plus the resulting `wheelhouse` folder to the company laptop, with your organization's approval where required. Use the same Python 3.12 x64 interpreter on both. `setup_windows.cmd` automatically installs from that folder with `--no-index`; it will not fall back to network if an offline package is missing. Use approved internal package mirrors instead if your organization requires them. If Python or execution of local applications is blocked, IT must provide an approved installation; this project does not bypass device controls.

## What the application actually implements

- Reads local Parquet or CSV; no silent download or change of corpus.
- Preserves existing chunk IDs, case IDs, dates and page metadata. Prefers `text_original` over synthetic text headers when available.
- In basic mode, uses BM25 and **TF-IDF** with reciprocal rank fusion (RRF). TF-IDF is lexical retrieval, not dense neural embeddings.
- Requires positive BM25, TF-IDF cosine >= 0.04 and at least 50% non-stopword query-term coverage before ranking. These are provisional heuristics, not calibrated probabilities.
- Reranks only the top 50 qualifying chunks using `RRF * (1 + 0.15 * court_weight)`. Court weights come only from explicit court metadata, never from references to another court inside a judgment.
- Optionally excludes decisions after a specified date, and undated decisions. This is a date filter, not subsequent-treatment or legal-validity checking.
- Returns up to four extracted sentences with chunk citations, or an insufficient-evidence response. The basic answer path does not run an LLM or NLI; research mode adds a separate NLI checker.
- Exports the query, both results, evidence and diagnostics as JSON in the browser.
- Uses a local-only Waitress server with debug mode disabled. CSS and fonts require no external services.

Baseline and proposed method use the same relevance gate, candidate budget, date filter and extraction routine. Only the court-authority bonus differs. Reported counts and latency are diagnostics, not precision, recall or hallucination scores. Exact quotations are not proof of legal correctness.

## Dataset and limits

The supplied file has **11,389 pre-existing chunk rows across 2,219 case IDs**. Of those rows, 11,251 list the High Court of Sikkim; 138 have no court value. This is not 11,389 independent judgments. OCR noise is visible in some texts. `bench_strength` contains questionable values and is deliberately not used as a ranking feature without validation.

Default indexing selects up to 300 distinct case IDs in dataset order and at most 6,000 chunks. This is a deterministic development subset, not a representative evaluation split. Identical text within a case is deduplicated. Very short unchunked documents may be omitted. Most known court weights in this corpus are identical, so baseline and authority-aware rankings will often match.

Optional settings in Command Prompt before launch:

```bat
set LEXRAG_MAX_JUDGMENTS=2219
set LEXRAG_MAX_CHUNKS=12000
set LEXRAG_PORT=5001
start_windows.cmd
```

Open the port printed by the server. Use `LEXRAG_DATASET` to select a different local `.parquet` or `.csv`; relative paths resolve beside `app.py`, regardless of the terminal's working directory. Larger corpora increase memory use and startup time. Remote URLs are not accepted as dataset paths.

## Checks and troubleshooting

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- `Dataset unavailable`: ensure the dataset file is alongside `app.py`; `/api/status` reports the error.
- Port in use: choose `LEXRAG_PORT=5001` and open http://127.0.0.1:5001.
- Empty evidence: try a question relevant to Sikkim judgments, remove the optional cutoff, or index more cases. The lexical coverage gate can reject valid paraphrases.
- Identical comparisons: expected on a single-court dataset, not proof that authority-aware retrieval is ineffective.
- Install fails: inspect the console message, confirm Python 3.12 x64 and package-index access, or use the offline path above.

See `NOVELTY_PLAN.md` for research context and `RESEARCH_METHODS.md` for the implemented upgrade and remaining experiments.
