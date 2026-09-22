# Experimental protocol and scope

The main hypotheses were chosen before running the main harness. The early-exit ablation was added after observing the main timing results and is explicitly exploratory.

## Main study

- FPR is false positives divided by queries known not to be in the set, not all queries.
- `n` always means distinct inserted keys. Main hash sweep uses 20,000, not repeated insertions counted as new elements.
- Eight seeds × (four bit budgets × 16 hash counts + six capacity settings) = 560 accuracy rows.
- 200,000 absent queries per row = 112,000,000 query evaluations. Several configurations reuse the same query keys for pairing; this is not a count of unique datasets.
- Capacity fixes m = 200,000 and k = 7 while n varies through 5,000, 10,000, 20,000, 30,000, 40,000 and 60,000.
- Four seeds × two set sizes × four k settings × four absent fractions × seven repetitions × three methods = 2,688 timing rows.
- Inserted keys are `mix64((seed << 40) + i)`. Absent keys use the separate range starting at `(seed << 40) + (1 << 32)`.
- The mixer is bijective because multiplication by odd constants and xor-right-shifts are invertible over 64-bit words. Counter ranges used here do not wrap or overlap.
- Query mixtures use exact counts, are shuffled, and are the same across the three methods and k values within a seed/size/mixture.
- Each method is warmed once; timed execution order is randomized per repetition. Generation, output and construction are excluded. Results are consumed outside the timer to retain the computation.
- Approximate Bloom-only counts may differ from exact-set counts. Filtered-set counts must equal exact counts. The test suite additionally checks this equivalence per key, not merely in aggregate.

## Statistical reporting

Timing medians are computed within each seeded workload, followed by means and t intervals across four seeded workloads (df = 3). FPR means and t intervals are computed across eight filters (df = 7). Speedup ratios are paired within seed first. This avoids reporting 28 timing repetitions as 28 independent trials. There is no multiple-comparison correction: curves and intervals are descriptive, and minimum-over-k findings are exploratory.

For tiny rates, the normal-shaped t interval may extend below zero and is a poor tail estimate. The quarter-capacity result has only three observed events; the report gives counts and explicitly limits precision. No nonzero probability is inferred to be zero from an empty sample. Hash independence is an idealized model, not a theorem about the chosen salted mixer.

## Memory and build time

The custom allocator tracks requested live and peak bytes for every allocation made by the exact set, including rebound node and bucket types. It excludes allocation bookkeeping, structure object sizes, key/query arrays and other process memory. Bloom figures count the packed vector's word payload. Combined exact lookup storage is set plus filter, never filter alone.

Each exact set is constructed once per seed/size and reused across k values. Its build time is repeated in corresponding memory CSV rows. Those duplicate figures are not new observations. Filter construction is separately timed for each k. Build times are archived, but no strong comparative build-time claims are made from single observations.

## Follow-up ablation

Four seeds × two sizes × two query classes × seven repetitions × two methods = 224 rows. k = 7 and m/n = 10. The full-scan diagnostic has a separately allocated packed array reconstructed using the same index mapping. It agrees with the core filter on every query before timing. Bit-probe counts are source-level counts, collected outside timing. Timing is summarized at the seed level as in the main study.

This supports an observation about these compiled variants. It does not isolate branch misprediction or cache effects. No hardware counters were collected. The original main filter was retained so the exploratory optimization is not silently substituted into the previously measured pipeline.

## Limits and possible follow-ups

Only one active desktop machine, two set sizes, one integer key family and one standard-library implementation were measured. CPU placement, power state and background load were not held fixed. Construction/build order for parameter groups is not randomized, and drift between groups remains possible. The broad intervals are retained rather than removed as outliers. Stronger future work would use independent hash families, skewed and string keys, more seeds/machines, controlled power and load, and hardware counters. The break-even backend model adds a constant cost per actual backend call; it is not a measured storage service.

## September 22 exact-pipeline follow-up

Purpose: determine whether the earlier isolated full-scan observation transfers
to exact lookup, removing its separate Bloom-storage allocation. This follow-up
was designed after inspecting the original measurements; it is not a pre-registered
hypothesis and does not replace them.

Both methods query the same BloomFilter instance and exact set. Design: n=20,000
or 200,000; m=10n; k=1 or 7; absent fractions 0, .5, .9, 1; seeds 1–4; 200,000
queries; 7 repetitions; 3 randomly ordered methods after warm-up. Query generation
is identical across k within each seed/n/fraction. Disjoint counter ranges passed
through the bijective mixer guarantee negatives. Each query is checked against
the exact set and both filter variants before timing. Per-query checks and counts
are outside timing; timed totals are checked and consumed in a volatile sink.

Analysis uses seed medians and paired ratios, with four-seed t intervals. k=1
controls for the case of exactly one bit check in both versions. Method order
is randomized within a configuration; configuration order is fixed. CPU affinity,
power and background load are uncontrolled. No hardware counters are collected.
New results are archived separately, with their own environment/source record.
