# Issue #118 — isolated semantic PPC1 preview

Base main `22fdc47` after PR #115. Read PR #113/#115 contracts, project plan, AGENTS and future #109. No automatic backup, production exporter/importer, restore, Google Drive, main UI, IndexedDB protocol, service worker or legacy format changes. No private database was accessed. Work specification remains unavailable; no contents assumed.

## Narrow entry point

Test-only module API, deliberately not a new backup UI or an addition to the main restore flow:

```js
const {createCompactPreview} = await import('./model/compact-backup-preview.mjs');
const preview = createCompactPreview();
const report = await preview.preview(syntheticPpc1Blob, {
  signal,
  getRevision: async () => authoritativeRootToken // optional, read-only caller probe
});
const fresh = await preview.read(); // rechecks a published report's source token
preview.cancel();
```

No storage APIs are referenced by this module. Caller probes must be read-only and authoritative (e.g. actual IndexedDB v2 sealed root, including epoch/revision), not an in-memory revision that can miss another tab. Tokens can be bounded nonempty strings or nonnegative safe integers; an integer alone cannot protect against reset/ABA without an epoch-aware caller. With no probe, report explicitly says revisionChecked=false and warns it is not bound to current database state. No current-database access is inferred or initiated by default.

Only the latest operation can publish. Starting another preview or cancelling aborts pending probes, clears previous results and invalidates late replies. Supplied AbortSignal covers active preview. read() rechecks before returning a published report, invalidates on changed/unavailable source and is cancellable with cancel(). No partial summary/model is published. A returned report is a point-in-time immutable value; external code must use read() before display and invalidate views on source events. It is not a CAS authorization for a future restore.

## Exact semantic scope

Uses existing openCompactBackup via readCompactModel: complete manifest/chunk/graph validation and bounded decompression before semantic inspection. Accepts only a complete structured v2 source `{format:'pushpull-backup',version:2,data,catalog,archives}` with optional object-valued settings/metadata. Other writer-compatible arbitrary graphs, missing sections, future formats and extra root representations are refused, not partially interpreted. The writer's generic losslessness does not certify a graph as a valid application snapshot.

Existing validateStructuredSource validates legacy source/catalog, active session, native models, session snapshots, owners, plan/result references and global IDs, including validatePerformance's projection and L/P/drop rules. No full legacy v3 document is manufactured. Plan packets are checked through existing storedPlanModel with fallback definitions of the target version removed so corrupt packet metadata cannot hide behind an intact snapshot/current model. Additional read-only continuity FK checks cover the stored historical decision records without replaying import/activation against today's state. Unsupported execution versions and incomplete executable definitions are rejected. Uses the same reserved-property restriction as production data loading, with memoization over shared graph nodes. Existing production validators remain unchanged.

Reports contain only fixed text/anonymous counts: sessions/results/snapshots, catalog plans/versions, native plan versions, archive counts, active-version presence and settings presence. Error messages never include parser excerpts, IDs, names or callback credentials. All successful reports say **canRestore=false**. Opaque archive raw (including null, empty, invalid JSON and Unicode) is preserved and transport-verified, not recursively interpreted. Settings and extension values have portable-JSON/integrity checks, not an invented settings schema. Warnings explicitly state this boundary; no report claims full semantic certification of opaque contents, authenticity or restore readiness. PPC1 is not encrypted; no decryption/authentication mechanism is added.

## Resource and safety limits

Unchanged PPC1 budgets passed to the existing mapper/reader; only lowered overrides accepted. Preview also checks total elapsed time around semantic stages and source probes. Native IO/crypto and synchronous existing validators cannot be physically preempted; cancellation suppresses results but does not undo or mutate anything. Stalled probes are raced with abort; their underlying read can finish later. No production worker or hard RSS cap is claimed. Complete reconstructed model and validation projections can occupy significant memory. 64 MiB old-space tests do not bound native Blob/crypto/Chromium RSS and are not Pixel 9 acceptance.

## Verification

Node fixtures: complete native V2/TEST plans, original notes/instructions, L/P, drops, catalog, all source archives and settings. Positive full counts/source immutability, transport corruption, rehashed but semantically invalid files, session/snapshot/result/catalog/plan/continuity errors, unsupported model/version, large opaque archive, lower resource budget, cancellation, superseding operations, source failure and revision changes during/after validation. Reports never expose source content.

Chromium: isolated native IndexedDB v2 fixture, all-store and localStorage equality before/after successful/offline/corrupt/limited/cancelled preview; throwing guards on all IDB and localStorage write methods; real sealed-root probes; actual second-handle commit with BroadcastChannel disabled (only intentional fixture commit changes records), cancelled late response and main two backup buttons unchanged. Additional offline run uses 64 MiB V8 old-space. These modules are not in production precache; offline test exercises explicitly loaded isolated modules. Existing full CI covers production PWA/offline/update/restore regression. Exact local/CI results in PR; no real Google/Pixel result or performance improvement claimed.

Next step: separately approved restore design and isolated application of a validated supported snapshot, retaining existing CAS, preimage, readback and strict complete. This PR provides no restore method, no production write path and no #109 implementation.
