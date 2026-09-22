# Bloom filters in practice

## 1 What I built

This C++17 project studies an insertion-only Bloom filter. Choose parameters for the error target and total query cost: seven hashes gave about 0.82% false positives at 10 bits per key, while one hash gave higher exact throughput on tested miss-heavy workloads. Full scanning improved the seven-hash pipeline for all-absent queries but lost to early exit at 50% absent.

The filter accepts unsigned 64-bit keys and stores bit markers, not the keys, in packed 64-bit words. Parameters are bit count m, hash count k and seed. insert adds markers; contains returns definitely absent or possibly present. Deletion, resizing, persistence and concurrent mutation are outside scope.

Each position uses a separately salted SplitMix64 finalizer reduced modulo m. Constants follow Vigna [3]. Hashing is deterministic and non-cryptographic; distinct salts do not prove independence. The experiments test controlled inputs, not a universal hash guarantee.

| Location | Purpose |
| --- | --- |
| include/bloom.hpp | Packed storage, hashing and membership |
| src/study.cpp | Data generation, baselines and measurements |
| tests/test_bloom.cpp | Deterministic and randomized checks |
| src/pipeline_exit.cpp | Paired exact-pipeline follow-up |
| scripts/analyze*.py | Validation, summaries and plots |

## 1.1 Correctness and the difficult step

The key invariant is that every bit required by an inserted key remains set. Initially all words are zero. Insertion visits the key’s k positions and uses bitwise OR to set each bit. OR preserves every previously set bit. Membership recomputes the same positions using the same m, k and seed. Therefore, every inserted key passes every check. This argument does not require the hashes to be independent.

The word index is position / 64 and the bit offset is position % 64. UINT64_C(1) makes the mask unsigned and 64 bits wide; the offset is always between 0 and 63. This matters at word boundaries and for high bits. Storage rounds up to complete words without using an overflow-prone bits + 63 expression.

The deterministic demo inserts 10, 20 and 30 into m = 64, k = 3, seed = 7. Key 10 uses positions 30, 14 and 16. The uninserted key 37 is reported present, demonstrating a legitimate false positive. A separate mutation demo replaces |= with = and makes an inserted key fail. This mutation is deliberately broken demonstration code, not a defect found in the main implementation.

The final test suite passes 464,427 checks in both optimized and AddressSanitizer/UndefinedBehaviorSanitizer builds. It covers empty filters, invalid parameters, duplicate insertions, keys 0 and UINT64_MAX, word boundaries, saturation, full-scan agreement and exact-pipeline equivalence on each key. The accuracy study additionally checks 11,560,000 inserted-key memberships with zero false negatives. Tests support the argument above; they do not replace it.

## 2 Empirical study

### 2.1 Questions and initial hypotheses

The initial study had three questions. H1: at fixed bits per key, false-positive rates should follow the usual theoretical curve and have an interior minimum in k. H2: exceeding design capacity should increase false positives even though the implementation remains correct. H3: an exact pipeline with a Bloom prefilter should benefit mainly when queries are absent and the saved lookup cost exceeds the filter cost.

For n distinct insertions into m bits, the probability that a bit remains unset under independent uniform hashing is (1 − 1/m)^(kn). The commonly used false-positive approximation is p ≈ (1 − exp(−kn/m))^k [1, 2]. It additionally approximates dependencies between queried bits. It is not an exact formula for this implementation.

Writing b = m/n, minimizing this approximation gives k* ≈ b ln 2. At b = 10, k* ≈ 6.93, suggesting seven hashes. This minimizes the false-positive approximation at fixed storage, not wall-clock time or total system cost.

| Experiment | Controlled design |
| --- | --- |
| Hash sweep | n = 20,000; b ∈ {4, 8, 10, 16}; k = 1…16 |
| Capacity | m = 200,000; k = 7; n = 5,000…60,000 |
| Exact lookup | n ∈ {20,000, 200,000}; b = 10; k ∈ {1, 3, 7, 11} |
| Query mix | Absent fractions 0%, 50%, 90%, 100% |

## 2.2 Reproducible measurement

Accuracy uses eight seeded filters and 200,000 absent queries per configuration. Keys are the bijective mix64 transform of consecutive counters. Disjoint counter ranges guarantee absent queries. Seeds change the ranges and hash salts; comparisons within a seed reuse keys. The 560 accuracy rows contain 112 million absent-query evaluations, not 112 million independent datasets.

Timing uses four seeds, seven measured repetitions and 200,000 queries per repetition. Present queries sample inserted keys with replacement; absent queries are distinct. The mixture is shuffled. The three methods are an exact std::unordered_set, the approximate Bloom filter alone, and Bloom followed by the same exact set when needed. Only the first and third provide equivalent exact answers.

Generation, allocation, construction, validation and printing are outside lookup timing. Each method is warmed up; execution order is shuffled per repetition. Returned counts are checked and consumed by an observable accumulator. The exact set is reserved at maximum load factor 1.0 and uses mix64. This is one standard-library baseline, not all hash tables.

For each seed, timing is summarized by the median of seven repetitions. Plots show the mean of these seed medians and a two-sided Student t 95% interval across four seeds. Speedup is paired within seed before summarizing. Accuracy intervals use eight seed-level rates [4]. Repeated loops are not treated as independent trials. These descriptive intervals do not cover all machine or workload uncertainty.

## 2.3 Accuracy and hash count

![Figure 1. Left: eight-seed mean false-positive rates with 95% intervals and theoretical lines. Right: fixed-size filter loaded beyond design capacity. Some error bars are smaller than the markers.](../figures/accuracy.png)

| Bits per key | Measured best k | FPR at that k |
| --- | --- | --- |
| 4 | 3 | 14.712% |
| 8 | 6 | 2.144% |
| 10 | 7 | 0.821% |
| 16 | 12 | 0.043% |

At 10 bits per key, k = 7 gives 0.821 ± 0.016 percentage points, close to the theoretical 0.819%. Increasing k to 16 raises the measured rate to 2.714%. More positions must match, but inserting each key also sets more bits. Beyond the minimum, the increased occupancy outweighs the benefit of extra checks.

At 16 bits per key, the smallest sample mean occurs at k = 12 rather than the rounded theoretical choice of 11. Nearby intervals overlap. This is not strong evidence that the theoretical optimum is wrong; selecting the smallest noisy estimate can move the apparent optimum. The curve and its uncertainty matter more than a single winning integer.

## 2.4 Capacity and storage

| Inserted / design capacity | Measured false-positive rate |
| --- | --- |
| 0.5× | 0.019% |
| 1× | 0.821% |
| 1.5× | 4.875% |
| 2× | 13.841% |
| 3× | 40.182% |

With m = 200,000 and k = 7, doubling the intended 20,000-key capacity raises false positives from 0.821% to 13.841%; tripling it raises them to 40.182%. Inserted keys still pass. This is saturation, not a correctness failure: design capacity is an accuracy budget rather than a hard insertion limit.

At one quarter of capacity, only three false positives appear across 1.6 million absent-query evaluations. This is insufficient for a precise tail estimate. A near-zero observation does not prove that false positives are impossible.

| Structure at n = 200,000 | Requested storage |
| --- | --- |
| Bloom bit array | 250,000 bytes |
| Exact set nodes and buckets | 6,400,024 bytes |
| Bloom plus exact set | 6,650,024 bytes |

Bloom-only storage is about 25.6 times smaller but gives approximate answers. The exact pipeline adds 250,000 bytes, about 3.9%. A counting allocator records requested set-node and bucket bytes; Bloom storage counts word payload. Object headers, allocator metadata and input vectors are excluded. These are structure-storage figures, not resident-memory measurements.

## 2.5 Exact lookup performance

![Figure 2. Exact set time divided by filtered-set time. Values above 1 favour the prefilter. Error bars are 95% intervals across four paired seed-level ratios.](../figures/speedup.png)

| n = 200,000 | k = 1 speedup | k = 7 speedup |
| --- | --- | --- |
| 0% absent | 0.736 ± 0.061 | 0.385 ± 0.014 |
| 50% absent | 0.947 ± 0.010 | 0.727 ± 0.010 |
| 90% absent | 1.557 ± 0.069 | 0.680 ± 0.009 |
| 100% absent | 2.709 ± 0.062 | 0.905 ± 0.440 |

The accuracy-optimal k = 7 did not reliably accelerate these in-memory lookups. For n = 20,000 and all-absent queries, its speedup is 0.713 ± 0.021, meaning a slowdown. In contrast, k = 1 gives 2.871 ± 0.357. Although one hash admits more false positives, it is cheaper and still rejects most absent keys.

For n = 200,000 and all-absent queries, the k = 7 interval spans 1. The run is inconclusive about a speed advantage there. All-present workloads consistently penalize the prefilter because every query pays for both structures. A prefilter should be selected for the query mix and backend cost, not for low false-positive rate alone.

## 2.6 A follow-up on early exit

![Figure 3. Follow-up ablation at k = 7. The early-exit and full-scan variants return identical results on every checked query. Bars show means of seed medians, with 95% intervals.](../figures/early_exit.png)

The main run unexpectedly measured absent Bloom queries as slower than present queries. This motivated a separate, post-hoc experiment rather than a change to the original benchmark. It compares the core early-exit query with a diagnostic full scan over a reconstructed packed layout, using the same positions and contents. Each configuration has four seeds and seven timed repetitions. Source-level bit-probe counts are collected outside timing.

At n = 200,000, an absent early-exit query checks about 1.996 positions on average but takes 41.69 ± 1.96 ns. The full scan checks all seven positions and takes 23.58 ± 0.50 ns. The smaller dataset shows the same direction. Fewer logical probes therefore do not imply lower elapsed time for this compiled implementation.

The result is consistent with differences in branching and generated machine code. It does not isolate branch prediction: no branch counters or assembly analysis were collected, and the diagnostic layout has a different allocation address. Section 2.7 now tests both versions inside exact pipelines using one shared Bloom object. The original measurements are retained separately; no timing values from the two runs are pooled.

## 2.7 Full scanning in the exact pipeline

![Figure 4. Separately dated paired experiment. Values above 1 indicate faster exact lookup than the set alone. Error bars are 95% intervals across four seed-level ratios.](../figures/pipeline_exit.png)

The follow-up uses contains and contains_full_scan on the same Bloom object and the same exact set. Both variants have identical positions, contents and backend-call counts. The full scan accumulates every bit test with &= and has no source-level early return. Each query is checked against the exact set before timing.

The design uses two set sizes, k = 1 or 7, four absent fractions, four seeds, seven repetitions and 200,000 queries per repetition (1,344 timing rows). Generation and validation are outside timing. Methods are warmed up and randomly ordered. Ratios are paired within seed after taking repetition medians. k = 1 is a control where both variants check one position.

| n = 200,000; k = 7 | Set / early time | Set / full time |
| --- | --- | --- |
| 50% absent | 0.732 ± 0.006 | 0.629 ± 0.004 |
| 90% absent | 0.676 ± 0.016 | 1.011 ± 0.028 |
| 100% absent | 0.707 ± 0.041 | 1.282 ± 0.098 |

## 2.7.1 Results and scope

For 200,000 keys and all-absent queries, full scanning speeds up the exact pipeline by 1.812 ± 0.034 times relative to early exit. Relative to the set alone, full scanning gives 1.282 ± 0.098 times speedup; early exit gives 0.707 ± 0.041. Thus the original component-level observation can translate into an end-to-end benefit.

The benefit depends on workload. At 50% absent queries, the full/early speed ratio is 0.859 ± 0.006: full scanning is slower. At 90% absent queries, its speedup over the direct set is 1.011 ± 0.028; the interval spans 1. Neither result supports a universal full-scan recommendation.

The smaller set also benefits at k = 7 with all-absent queries (full-scan/set speedup 1.217 ± 0.009). However, k = 1 with early exit remains faster in the all-absent workload at n = 200,000 (2.726 ± 0.055 times the set). Lower error and faster execution remain different objectives.

The shared object removes the separate Bloom allocation from the original diagnostic comparison. k = 1 shows much smaller version differences than k = 7 on miss-heavy workloads. This narrows the explanation, but does not isolate branch prediction, vectorization or instruction scheduling. Compiler output and hardware counters were not analysed. Fixed configuration order, background load and four seeds limit generalisation.

## 2.8 Interpretation and limits

Let q be the absent-query fraction and p the false-positive rate. The approximate backend-call fraction is r = (1 − q) + qp. Adding cost L per backend call gives Tset(L) = Tset(0) + L and Tfiltered(L) = Tfiltered(0) + rL. For r < 1, the break-even additional cost is L* = (Tfiltered(0) − Tset(0))/(1 − r).

Using paired measurements at n = 20,000, k = 7 and all-absent queries gives L* between 11.18 and 12.17 ns across seeds. This is a derived threshold under a constant extra-cost assumption. It is not a database or network measurement; real backends can have batching, caching, concurrency and different hit/miss costs.

Both runs used an Apple M2 with 8 GB memory, macOS 14.4.1 and Apple Clang 15, using C++17 and -O3. CPU affinity, power state and background load were uncontrolled. Some intervals are wide. Warm queries, two set sizes and uniform integer keys do not represent cold storage, skew or adversarial inputs. The shared generator/filter mixer also limits independence conclusions.

Construction times are separate single observations, excluded from query speedups. Each set-build time is repeated across k rows in the memory CSV, not independently remeasured. Recommendation: use about seven hashes for a 1% error target at 10 bits per key, but benchmark cheaper settings for exact in-memory throughput. Recheck capacity and workload assumptions.

## 2.9 Choosing a configuration

First decide whether approximate membership is acceptable or exact answers are required. For an approximate filter, choose the bit budget and k to meet an error target. For exact answers, retain the backend and measure total lookup time; the filter adds memory and only saves some backend calls.

| Goal or workload | Recommendation within tested scope |
| --- | --- |
| About 1% false positives at 10 bits/key | Use about 7 hashes at design capacity; monitor occupancy and distinct insertions. |
| High exact throughput with 90–100% absent queries | Test cheaper hashing first. k = 1 outperformed k = 7 in the paired follow-up. |
| All queries present | Prefer direct set lookup in these tests; the filter could not avoid backend calls. |
| k = 7 required, all queries absent | Full scanning improved the exact pipeline in both tested sizes. |
| Mixed queries or another backend | Benchmark both query variants and the direct baseline; full scanning lost to early exit at 50% absent. |

These are conditional decisions for the measured C++17 implementation and integer workloads, not universal best parameters. A slower backend can make stronger filtering worthwhile. Capacity growth, key distribution, compiler or machine changes require new measurements. The study did not compare alternative mixer constants or prove their optimality.

## 3 What I learned

### 3.1 The objective determines the parameter

The most useful lesson is the difference between optimizing a component and optimizing the whole pipeline. Seven hashes gave a false-positive rate of 0.821%, whereas one hash gave 9.502%. However, for 200,000 keys and all-absent queries, the exact pipeline with one hash was about 2.71 times as fast as the direct set. The original seven-hash early-exit pipeline had no clear speed advantage. Reducing false positives has value only in relation to the work avoided.

### 3.2 Fewer operations can still take longer

The early-exit experiment makes this lesson concrete. The absent-query path reduced the mean logical probes from seven to about two, yet the full scan was faster. Counting source-level operations is useful, but it leaves out how a processor executes branches and how a compiler transforms loops. The new shared-storage pipeline comparison strengthens the practical result: full scanning helps at 100% absent queries but loses to early exit at 50%. It still does not identify one hardware cause as proven.

### 3.3 Correctness and usefulness are separate

An overloaded Bloom filter can remain correct while becoming much less useful. At triple capacity it still produced no false negatives, but roughly 40% of absent queries passed. This changes how success should be defined: a test suite needs functional invariants, while the evaluation needs an accuracy target and an operating range. Merely showing that insert and contains run successfully would miss the main failure in usefulness.

## 3.4 Evidence changed the way results were judged

The memory comparison also requires an explicit definition of what is being replaced. A 250,000-byte approximate filter and a 6,400,024-byte exact set answer different questions. Once the exact set is retained to verify positives, the filter increases total structure storage. The smaller number is useful only when its weaker guarantee fits the application.

The apparent best hash count at 16 bits per key was another reminder to examine uncertainty. The measured minimum at 12 hashes is not automatically a new algorithmic discovery. Nearby choices have similar rates, and the minimum was selected from many estimates. Reporting the whole curve avoids making the conclusion depend on a noisy winner.

Finally, test counts do not by themselves establish test independence. The first bit-vector oracle reused the filter’s position helper, so it could detect packing errors while sharing a hash-indexing error. Review led to fixed known-answer checks and per-key exact-pipeline checks. This gives stronger evidence, while still leaving the statistical quality of the salted hash family as an assumption rather than a proof.

## 4 AI use

I used OpenAI Codex extensively for topic selection, implementation, tests, experimental design and execution, analysis, documentation and report drafting. It also adapted the Word template and uploaded the repository. The September 22 revision added the full-scan API, equivalence checks, paired pipeline experiment and conditional recommendations with Codex assistance. Most code and report text were AI-generated; I do not claim to have independently written every line or run every command.

The first generated reference test reused BloomFilter::position. It checked packed storage but could share an indexing bug. AI-assisted review added fixed mixer/index vectors and per-key equality between the exact pipeline and the set. The initial version is preserved in commit 93063ae; the correction is visible in the test diff.

The analysis script also assumed SciPy and Matplotlib were installed. Execution failed with ModuleNotFoundError for scipy, then matplotlib. The fix used explicit t critical values for the supported seed counts and installed plotting dependencies locally. Commands, package versions and successful output are recorded. The raw measurements were unchanged.

Codex ran compilation, tests, sanitizers, CSV checks and figure regeneration. During code review, I worked through packed bit indexing, the insertion invariant and the query logic. I relied on the published mixer constants rather than deriving them; the study does not prove hash independence or identify the hardware cause of the timing differences. The deliberate |= mutation is an educational example, not an accidental AI bug.

## References

[1] Bloom, B. H. (1970). Space/time trade-offs in hash coding with allowable errors. Communications of the ACM, 13(7), 422–426. https://doi.org/10.1145/362686.362692

[2] Kirsch, A., Mitzenmacher, M., and Varghese, G. Hash-based techniques for high-speed packet processing. Author manuscript. https://www.eecs.harvard.edu/~michaelm/postscripts/dimacs-chapter-08.pdf

[3] Vigna, S. (2015). splitmix64.c. Public-domain reference implementation. https://prng.di.unimi.it/splitmix64.c

[4] NIST/SEMATECH. e-Handbook of Statistical Methods, section 1.3.6.7.2: Critical values of the Student’s t distribution. https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm

### Reproduction record

Repository: https://github.com/mojitote/41052-a1-bloom-filter-study. Main data: results/full-20260910/. Follow-up data: results/early-exit-20260910.csv. New exact-pipeline data: results/pipeline-exit-20260922.csv; analysis: scripts/analyze_pipeline.py. Original environment: results/environment.json; revision metadata: results/upgrade-environment-20260922.json. Exact commands and dependency setup: README.md. Numerical tables and figure source: figures/ and scripts/analyze.py. All external sources accessed on 10 September 2026.
