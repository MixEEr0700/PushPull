# #147 — restore string limit, export I/O, settled Drive status

Base main 5f2f18d after #145. No private profile was opened; no migration/deletion of source data or existing rescue points. #146 is deferred to another session.

## Confirmed causes and implementation

Restore serialized the entire native preimage several times: rescue JSON byte-count/hash and a new opaque journal checkpoint containing all previous records, including escaped old checkpoints. Serialization occurred BEFORE the byte limit could refuse. Valid logical PPC1 size is not a bound on that technical representation. A synthetic DAG reproduced native V8 `RangeError: Invalid string length` (536870888-character limit, 1227ms) without requiring a large physical source graph.

New rescue points retain the full original evidence as native structured-clone data, verified by a versioned, bounded Merkle proof. Text is hashed in fixed UTF-16LE chunks so Unicode/lone surrogates remain exact; no aggregate JSON string is constructed. Work is bounded by the existing native journal allocation budget (512MiB), not an arbitrary enlarged stringify buffer; file limit remains 128MiB. This representation change avoids measuring repeated JSON escape overhead as physical evidence. Legacy rescue proofs retain their exact digest with a bounded JSON-expansion preflight before stringify; oversized/corrupt legacy points refuse safely. No existing points are migrated or rewritten.

Canonical restore reuses the separately committed/readback-verified rescue point as its opaque protocol-2 checkpoint reference, bound to operation ID and file/evidence digests. It no longer recursively embeds another complete native preimage. The full original native records remain in the immutable rescue point, verified in tests. Other legacy import checkpoint paths retain their previous behavior. The verified physical snapshot is also bound by exact structural CAS before bulk replacement; a different record set cannot borrow that rescue reference. Journal CAS, owned-state witness, allocation checks, strict complete, native audit and whole-canonical readback remain; rollback reconstructs from the original complete PPC1.

Export instrumentation confirmed one native transaction per required index/object/collection key. Export now opts into the existing reader with per-store microtask batching; bulk-owned collection rows seed its cache. Every record still gets SHA/index verification and final root/marker/count CAS; no cache survives this capture. No archive/checkpoint scan was added. Workers now report read/validation/encoding/verification phases, startup and total time. UI labels the actual phase and reports elapsed total rather than only worker time.

Drive listing and selected-point validation now settle success/error notices; busy=false cannot leave their generic transient notice behind. Selected-point notices also honor operation currency/cancellation. A still-owned generic transient notice is settled to neutral after any operation, including an obsolete request, so reopening another flow cannot expose stale busy text. Explicit cancellation/error notices remain untouched.

## Measurements (synthetic desktop Chromium only)

| Profile | Before total | After total | Native transactions before → after |
| --- | ---: | ---: | ---: |
| 40 sessions/results, 2586B PPC1 | 152ms | 132ms | 261 → 86 |
| 400 sessions/results, 8901B PPC1 | 680ms | 351ms | 2421 → 525 |

After 400: read 213ms, domain validation 32.8ms, encode 35.8ms, verify 35ms, startup 35ms. Single samples, not medians/p95. Fixtures have no V2 snapshots; separate existing real V2 UI restore/export regressions cover correctness. These samples do NOT reproduce or confirm elimination of the reported physical Pixel 9 30s/233KB delay. The phase metrics distinguish device startup/cache/I/O from encoding at acceptance. Reproduce locally with `python scripts/benchmark_backup_147.py`; numeric artifact: `docs/performance/backup-147.json`.

The old giant JSON call threw in 1227ms; bounded proof on the same aliased graph used 4370 charged bytes and 120ms. Default CI tests use the bounded form and do not allocate the 512MB failed string again.

## Actual verification

Targeted Node: 24 PASS across focused runs. Canonical export lifecycle/cancellation and pending gate PASS; evidence proof Unicode/corruption/size limits and legacy compatibility PASS; incremental Drive tests (including list success/failure and obsolete point request) PASS.

Chromium: 5 targeted cases PASS across focused runs. Actual used-profile restore under a forced aggregate-string limit → exact canonical equality → rescue physical evidence equals original records → UI rollback/restart/exact original canonical equality PASS. A synthetic legacy-style rescue digest also loads and restores exactly. Existing partial-local-quota/restart/rollback and concurrent auxiliary-change export refusal PASS. A mismatched physical snapshot also refuses before mutation. No full local suite duplicated; final build/full Node/Chromium/PWA CI result recorded in PR.

## Boundaries

No real Google account or physical Pixel test. Unknown/nonresponding tab memory limitations and existing fail-closed rollback gates remain. Sufficient quota and memory are required for the owned native snapshot/structured clone; bounded proof is not a peak-heap guarantee. Old rescue records remain readable within their original bounded JSON proof budget; oversize/corrupt evidence refuses without changing active data. Hardware power loss and large-device peak memory unverified. Legacy opaque checkpoints are retained as evidence, not silently dropped; no retention/deletion enabled. Final Pixel acceptance must measure the new phases before declaring the reported 30s issue resolved on the phone.
