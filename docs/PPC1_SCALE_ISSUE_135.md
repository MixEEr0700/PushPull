# #135 — canonical document admission budget

Base main 5af1342 after #134, #123. Isolated codec only: no production export/restore, Drive, UI, schema, private database, migration or old backup recovery.

## Reproduction / cause

For the exact #133 4000-session canonical input, transport succeeds (17 bounded chunks, roughly 4.25 MB decoded). The borrowed `boundedBackupJson` treats the entire document as metadata and refuses after **100000 lexical tokens** (`v4: token limit`). Existing fallback then fails the old graph's **10000 nodes** (`compact graph: node limit`). This is not a SHA, gzip, chunk-size or semantic-history failure. A dedicated test confirms the old parser refuses the same text while the corrected codec exactly roundtrips it.

## Small correction and safety model

Only the canonical JSON payload now uses a separate preflight `parseCanonicalJSON`; existing metadata/v4/graph parsers retain their limits. Container, version, manifest, chunk sizes, stored/decoded SHA-256, decompression caps and source validators are unchanged. No new encoding version or expanded capture guard.

The new parser keeps depth 32 (or a lower requested value), numeric-token length <128, duplicate-key/lossless-number checks and strict JSON syntax. Before native JSON.parse:

`charged = 3 * decodedUTF8Bytes + 64 * lexicalTokens <= 64 MiB`.

This reuses the existing capture admission scale of 64 MiB rather than blindly enlarging the old manifest token count. The 3-byte reserve covers the owned UTF-8 input plus worst-case UTF-16 text; 64 bytes/token adds eight pointer-sized allocation credits for parsed containers/entries, key bookkeeping and strict duplicate detection. It is a conservative **admission heuristic**, not an experimentally established V8 heap upper bound. Strings are charged through decoded bytes, dense short values through token credit. Worst-case domain cardinality cannot grow independently of that fixed aggregate budget. At most 22369621 declared decoded bytes fit even with zero tokens; real documents fit less once tokens are counted. Payloads above that preallocation bound refuse before the aggregate Uint8Array allocation. These are new stricter document-specific guards; the legacy 512 MiB transport ceiling is not a promise of canonical document capacity.

Preflight enforces cancellation/deadline while scanning (including inside long strings); strict parse is bounded but synchronous/non-preemptible, as are existing semantic validators. They must run in a worker when production integration is added. No production main-thread path is enabled by this PR; browser functional tests do not prove UI responsiveness. Actual process peak memory is **not measured** and may exceed the admission charge due to input/model/writer/validation coexistence. No arbitrary totalDecodedBytes or 64 MiB increase.

Memory refusals do not trigger a fallback that could bypass the guard. The old graph is retained only for the existing deeper-model nesting fallback and old graph files remain readable. Read/write success still requires container and semantic validation plus exact caller tests; no partial file or data truncation.

## Actual synthetic results

Same command/data as #133: `node tests/canonical-comparison.mjs`. All successful variants compare every field. Raw results (0/4/40/400/4000, repeated and unique snapshots, JSON/gzip/old/new PPC1, bytes/write/read/preparation and manifest breakdown): `docs/benchmarks/PPC1_135.jsonl`.

4000 sessions, one result each:

| Snapshots | JSON B / write / read ms | gzip(JSON) B / write / read ms | Canonical PPC1 B / write / read ms | Preparation ms |
|---|---|---|---|---:|
| Repeated | 4241690 / 39.27 / 47.47 | 75933 / 63.53 / 53.70 | 80932 / 362.27 / 372.91 | 245.47 |
| Unique | 4264140 / 34.58 / 32.16 | 96033 / 68.71 / 66.07 | 101867 / 353.11 / 357.23 | 257.27 |

Old graph still refuses these inputs, but the canonical path now succeeds without graph fallback. One cold sample per profile, not median/p95 or Pixel evidence. JSON/gzip baselines perform fewer integrity/domain checks; preparation is separate, no disk commit measured. gzip remains smaller; the PPC1 integrity envelope is not claimed to outperform raw gzip compression.

## Verification

Targeted Node: 11 cases PASS across focused runs: retained canonical/old graph regressions (6), explicit 4000 reproduction, 0/4/40/400/6000 repeated/unique exact histories, malformed/duplicate/numeric/depth/budget/cancel guards, valid-hash dense payload/inflate attacks, and deeper graph-compatible fallback. The dense test was sized from the actual charge: 1.1 million short values exceed 64 MiB before native JSON.parse. The forged gzip test has valid stored/decoded/manifest hashes; one case fails parser memory admission, another declares only 32 decoded bytes and fails the unchanged decompression-size guard. Corruption/truncation/low decoded caps still refuse.

Chromium: existing targeted 40-session test PASS; new **6000-session unique snapshot** exact roundtrip offline PASS with all source IDB records/localStorage unchanged. Build/SW hash check PASS. Full final CI recorded in PR; no duplicate full local suite. 6000 coverage is a functional bounded fixture test, not a timing/capacity guarantee for all 6000-session native models. Large field sizes, depth or density can refuse earlier. No actual restore, clean-profile durable restart/readback, production integration, physical Android, quota-on-write or peak-heap measurement. No full production recoverability claim.
