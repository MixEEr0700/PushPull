# #133 — JSON payload packaging inside PPC1

Base main 1d40171, #123/#133. Isolated canonical codec only. No production export/restore, Drive, UI, database reads/migration or old test-state rescue.

## Decision and format

The old graph writer makes each unique string an individually indexed/hashed object. Even short property names/IDs require descriptors, object IDs, part lists, SHA-256 pairs and a chunk compression decision. UTF-16 strings and graph JSON are separate representations. Dedup removes repeated objects but does not remove the per-unique-string manifest cost. At 400 sessions with unique snapshots: 974 objects/chunks, 255525-byte manifest, 37705-byte payload, 40-byte header. Manifest dominates.

The optimized canonical writer uses **gzip of canonical JSON**, split into bounded 256 KiB chunks inside the **unchanged** PPC1 container manifest v1. One object ID `canonical-json-v1` explicitly versions the new payload encoding. Each chunk retains stored/decoded SHA-256 and size, compression is only used when smaller. Container header/manifest hash and existing transport reader/decompression checks are unchanged. New canonical reader dispatches by object ID and still reads old graph files; old generic graph APIs and production restore are untouched. An unknown payload fails, never gets guessed from filename.

No graph encoding or per-string dedup is needed on this path: gzip handles local repetition. Existing constructor interning is retained for semantic proof/caller ownership and fallback. If JSON expansion hits the existing token/depth cap, the writer tries the existing graph representation, preserving shared-native-snapshot cases. Cancellation, corruption or other resource failures are not swallowed. If both representations exceed limits, refuse; never silently truncate. No caps raised. Existing 40 copied/shared native snapshot regression still passes.

**Recommendation:** gzip(JSON) is the simpler and generally smaller baseline for this data. PPC1 adds bounded chunk verification/manifest integrity, not superior compression. Keep that small envelope only where its verified-container properties are needed; do not defend graph encoding on compression grounds. Independently compressed chunks can occasionally be smaller than whole-stream gzip (dictionary/stream-boundary effects); no universal ratio is promised.

## Reproducible synthetic evidence

Command: `node tests/canonical-comparison.mjs`. Exactly the same canonical object for JSON, gzip(JSON), old graph PPC1 and optimized PPC1. All successful variants perform exact deep equality. Every session has one synthetic result; snapshots in portable preferences model repeated versus unique immutable content. Native training snapshots/Unicode/conflicting drafts are separately exercised by existing canonical tests. These are synthetic workloads, not a Pixel/database benchmark.

One cold sample per row, no median/p95 inference. Preparation (canonical construction/interning/validation) is reported separately below. Per-format write includes JSON serialization; old/new PPC1 also include their integrity/resource/semantic gates, unlike bare JSON/gzip. Read times include equality assertion. Thus baseline bytes are directly comparable; baseline timings do less validation, explicitly. Codec API has no durable storage commit in this task. Peak memory **not measured**; no heap upper bound/constant-memory or UI responsiveness claim. JSON string + UTF-8 + decoded parse coexist in memory. No new module registered as a service-worker asset; production needs a measured worker/lifecycle integration.

Raw results including payload/header/manifest counts: `docs/benchmarks/PPC1_133.jsonl`.

Cells are **bytes / write ms / read ms**. Refusal is an actual error, not a size estimate.

| Sessions | Snapshots | Prepare ms | JSON | gzip(JSON) | Old PPC1 graph | New PPC1 |
|---:|---|---:|---|---|---|---|
|0|repeated|27.22|11241 / 0.25 / 4.77|1343 / 57.05 / 11.11|43938 / 496.9 / 169.97|1728 / 22.8 / 17.05|
|0|unique|12.43|11241 / 0.21 / 3.33|1343 / 6.8 / 2.82|43938 / 429.07 / 264.24|1728 / 30.76 / 12.65|
|4|repeated|11.3|15413 / 1.7 / 0.29|1606 / 3.29 / 2.81|52581 / 537 / 222.4|1991 / 8.16 / 5.88|
|4|unique|4.67|15417 / 0.32 / 0.48|1627 / 1.21 / 0.55|52613 / 298.87 / 177.45|2012 / 12.26 / 11.99|
|40|repeated|8.83|53148 / 0.37 / 2.98|2485 / 7.54 / 4.56|73834 / 497.75 / 207.6|2870 / 18.6 / 15.58|
|40|unique|7.74|53218 / 0.99 / 0.82|2721 / 6.79 / 2.61|74243 / 398.59 / 199.36|3106 / 37.36 / 27.15|
|400|repeated|56.97|432289 / 5.15 / 8.19|10638 / 21.36 / 34.52|288725 / 1860.07 / 1663.73|11050 / 81.26 / 75.16|
|400|unique|41.71|433739 / 4.66 / 3.19|12917 / 8.11 / 43.33|293270 / 1720.13 / 1164.02|13248 / 84.33 / 79.75|
|4000|repeated|487.16|4241690 / 69.53 / 91.08|75933 / 77.43 / 99.86|REFUSED: compact graph: node limit|REFUSED: compact graph: node limit|
|4000|unique|422.05|4264140 / 65.86 / 102.66|96033 / 111.16 / 103.09|REFUSED: compact graph: node limit|REFUSED: compact graph: node limit|

At 400 unique snapshots, 293270 B → 13248 B (about 95.5% smaller), while gzip(JSON) is still 12917 B. New manifest 579 B + header 40 B, payload 12629 B. For 4000 sessions, plain JSON/gzip roundtrip succeeds but JSON PPC1 hits its 100000-token cap; fallback graph exceeds its node cap. Final public failure reports the fallback node limit. This is a real remaining capacity limitation, not solved by changing a filename or suppressing validation. Limits are unchanged and require separate measured review before supporting larger histories. Initial intermediate measurements of this condition are not substituted for final results.

## Verification and limits

Targeted final Node 6/6 PASS (existing canonical semantics and copied/shared native snapshots; old/new compatibility; exact Unicode/lone-surrogate/NUL/buffer preservation; corrupted header/payload, truncation, decoded/file budgets and cancellation). Chromium 1/1 PASS: real app synthetic 40-session roundtrip and exact IDB/localStorage unchanged. Build/SW asset check PASS. One full final CI recorded in PR. Existing generic graph/reader/security/storage suites inherited unchanged and included in full CI. No production restore, clean-profile durable restart comparison, old-data recovery, real disk quota or physical Android test. No full production recoverability claim.
