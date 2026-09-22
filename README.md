# Bloom filters in practice

41052 Advanced Algorithms — Programming Assignment 1, **Track A: Implementation and Empirical Study**.

This project implements a packed, seeded Bloom filter for 64-bit integer keys and compares accuracy, capacity, requested storage, and lookup time against an exact hash set. The report follows the supplied Word template.

## Main findings

- At 10 bits/key, seven hashes produced **0.821%** false positives. Doubling the design insertion count raised this to **13.841%**.
- The lowest false-positive rate did not give the fastest exact pipeline. With 200,000 keys and all-absent queries, a one-hash prefilter gave a **2.71×** paired mean speedup over the exact set. Seven hashes gave an inconclusive **0.90 ± 0.44×**.
- A follow-up ablation found that an absent early-exit lookup checked about two positions but took **41.69 ns**, while a seven-position full scan took **23.58 ns**. These are observations for this implementation/compiler, not universal performance claims.
- An approximate filter used 250,000 bytes for 200,000 keys versus 6,400,024 requested bytes for the exact set. Keeping both for exact answers **adds** storage.

All numbers come from archived runs, not estimated or fabricated results. The full report discusses uncertainty and limitations.

## Build and verify

Requirements: C++17 compiler (Clang or GCC) and Make. No third-party C++ library is needed.

```sh
make all
make test
make sanitize
./build/bloom_demo --what-breaks
```

`make test` performs 464,427 checks and the mutation demonstration. Sanitizers cover the core test suite; sanitizer binaries are never used for timing. `make sanitize` requires compiler support for AddressSanitizer and UndefinedBehaviorSanitizer.

The deterministic demo shows that uninserted key 37 can return true and that replacing `|=` with `=` loses an inserted key. The intentionally broken mutation is isolated in the demo.

## Reproduce experiments

The study refuses to overwrite an existing output directory. Pick a new run name each time.

```sh
# Small end-to-end smoke run (not the data used in the report)
./build/study --out results/my-smoke-run --quick

# Full study
./build/study --out results/my-full-run

# Follow-up early-exit/full-scan experiment
./build/early_exit results/my-early-exit.csv
```

Timing is hardware/load dependent. Expect the accuracy curves to be reproducible under the recorded build, but do not expect identical nanoseconds. `std::shuffle` and library implementation details can differ across C++ standard libraries.

For analysis, use Python 3.10 or later in a local virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/analyze.py results/full-20260910 \
  --ablation results/early-exit-20260910.csv --out figures

# Analyze a new run without overwriting the archived report figures
.venv/bin/python scripts/analyze.py results/my-full-run \
  --ablation results/my-early-exit.csv --out results/my-analysis
```

The analysis validates row completeness, uniqueness, count semantics and exact-pipeline outcomes before producing charts. Accuracy intervals use eight seed-level rates; timing uses seven repetitions summarized within each of four seeds. Repeated queries are not independent statistical trials. Quick mode has two seeds and three timing repetitions and is not suitable for substantive performance conclusions.

## Files

| File or directory | Contents |
|---|---|
| `include/bloom.hpp` | Core insertion-only filter and theoretical approximation |
| `src/study.cpp` | Main accuracy, capacity, timing and allocator instrumentation |
| `src/early_exit.cpp` | Follow-up diagnostic ablation with identical logical bit layouts |
| `src/demo.cpp` | Worked example and deliberate what-breaks mutation |
| `tests/test_bloom.cpp` | Known-answer, boundary, randomized and per-key oracle checks |
| `results/full-20260910/` | Raw accuracy, timing and memory CSVs used in the report |
| `results/early-exit-20260910.csv` | Raw ablation measurements |
| `results/environment.json` | Machine/compiler/flags and original source fingerprints |
| `results/manifest.sha256` | Fingerprints of evidence and deliverables |
| `figures/` | Regenerable PNG charts, summaries and derived break-even model |
The final report is submitted separately as a PDF using the supplied Word template.

## API and guarantees

```cpp
bloom::BloomFilter filter(200000, 7, 1); // m bits, k hashes, seed
filter.insert(42);
bool possible = filter.contains(42);
```

All inserted keys stay positive as long as the filter parameters/state are unchanged. Absent keys can be false positives. Insert and query cost O(k) logical work; absent queries can stop early. Storage is `8 * ceil(m/64)` bytes of bit-array payload. Duplicate insertions do not change the filter after the first insertion. The implementation deliberately has no deletion, resizing, concurrent mutation or cryptographic guarantee. Invalid zero sizes, zero hashes and hash counts above 64 are rejected.

## Provenance and submission

Core code and experiment automation were produced with extensive OpenAI Codex assistance. The final report contains the required AI use section. The author must record the required walkthrough and review the reflection before submitting.

The GitHub repository is private. Give the marker access, or use an allowed source archive submission, before the deadline. The original assignment documents, virtual environment, compiled binaries and credentials are not included.

The hash finalizer is adapted from Sebastiano Vigna's public-domain `splitmix64.c`: <https://prng.di.unimi.it/splitmix64.c>. The mixer has not been proven to provide independent hash positions for this application.

## September 22 revision: exact-pipeline query variants

`contains_full_scan` is an experimental alternative to `contains`: both read the
same packed storage and hash mapping. `src/pipeline_exit.cpp` compares the direct
set with both exact pipelines on identical queries. This is a separately dated
run; do not combine its timings with the earlier run.

```sh
make all test sanitize
./build/pipeline_exit results/my-pipeline-run.csv
.venv/bin/python scripts/analyze_pipeline.py results/my-pipeline-run.csv --out figures/my-pipeline-run
```

The executable refuses to overwrite an existing CSV. It checks per-key answer
equivalence before timing and validates all timed positive counts. Analysis checks
all 1,344 unique configurations/repetitions, matching backend-call counts and
positive counts. Summaries use four seed medians (seven repetitions each), paired
ratios and descriptive Student t 95% intervals. The recorded input is
`results/pipeline-exit-20260922.csv`; its summaries are `figures/pipeline_summary.*`.

At n=200,000 and k=7, full scanning improves exact lookup for all-absent queries
but loses to early exit at 50% absent. The k=1 pipeline remains faster in the
all-absent comparison. No branch-prediction or universal optimality claim follows
from these timings.
