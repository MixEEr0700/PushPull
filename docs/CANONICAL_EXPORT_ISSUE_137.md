# #137 first working stage — production canonical export

Base main 584f9fb after #136, governed by #123 and #137's explicit split permission. This PR delivers a **working production UI export**, not another planner. **Restored records: 0.** New canonical restore is NOT implemented or advertised as usable. Issue #137 must remain open for that second stage.

## Actual UI and implementation

`Dane → Zapisz kopię → Telefon / dysk — PPC1` downloads a real `.ppc1` file. The two primary backup actions, Matrix, workouts and all original controls remain. Existing `Telefon / dysk` JSON export stays as-is because its existing restore is available; making an unrestorable canonical format the only/default phone backup would remove a working recovery path. The new option warns **before downloading** and in its final status that canonical restore is not yet available. Existing JSON/PPC1 source-only imports, Drive/manual/automatic behavior and technical backup tools are not replaced.

The event reserves synchronously before any await and runs outside the existing write/action queue. A module worker owns native IDB capture, source validation, hashes/index proofs, codec, decompression and exact encode→decode readback. Main thread sends only durable local buffer strings and observed revision; it never serializes the full history or calls ensureFull/auditExport. Navigation/cancel kills the worker; stale results cannot download or report success. Double click cannot reserve another export. Status means download requested, not a physically saved phone file. No success on timeout/read error or source change.

`canonical-export-worker.mjs` uses the existing selective `journal-runtime.reader`, `transact/request`, canonical constructor/codec, and `same`. It opens existing v2 readonly (aborts creation if absent), requires the known store inventory, hashes the root and every required row/object through the established persistent indexes, checks all live IDs/counts/positions, rejects duplicate metadata/snapshot fields and unbound metadata. It enumerates all live sessions/results/snapshots in order, batches 32 verified lookups, and checks root/marker/allocation stability after capture and after file readback. It does NOT load the legacy anchor object, archive raw objects, checkpoint payloads, old physical projections or rescue JSON. No v1 migration, rescue capture or source write is invoked by this new path.

Auxiliary meta and local buffers are checked again before publishing. Draft changes without a journal revision also refuse. Cross-tab buffer storage events invalidate the operation; same-tab buffer/revision values are compared again. Known local editor persistence errors refuse. Note-input receipts allow checking durable text without parsing note JSON on the main thread or treating flush/reload as a snapshot. No winner is selected among draft versions. Unpersisted editor memory in other tabs cannot be certified; this export covers the identified persistent canonical sources, not an all-tab memory freeze. Cross-IDB/localStorage atomicity is not claimed: repeated observations/event guards are stability evidence, not an exclusion protocol for every adversarial process schedule.

## Capture → file → restore/readback map

| Actual source | New canonical content | Verification | New restore |
|---|---|---|---|
| Active journalMetadata/source data/catalog | Complete logical data/catalog/extensions: history, plan versions, rotation, exercise IDs, instructions, notes, supported settings | Source/index hashes, full canonical semantic validation and exact codec equality | NOT implemented |
| journalSessions / journalResults | Every actual session/result and its series, L/P, drop/other performance semantics, order | Counts, positions, IDs and row/object hashes + domain validation | NOT implemented |
| journalSnapshots | Every logical snapshot and its original parameters/model | All fields, unique keys, ordered IDs, semantic references; existing canonical interning retained | NOT implemented |
| meta workout-draft:* | Every raw persisted draft record as key/value including conflicts, tokens, parent/revision/context and unfinished values | Before/after exact auxiliary equality | NOT implemented; context/CAS rebinding required |
| Workout/note local buffers and retired-note tokens | Exact sorted key/raw pairs, including malformed/unfinished strings | Synchronous inventory, storage-event guard and scalar value equality | NOT implemented |
| meta canonical-preferences-v1.value (optional) | preferences, default empty if absent | Exact auxiliary equality and portable validation | NOT implemented |
| meta drive-sync-v1.clientId | Client configuration only, no authentication request | Existing UI configure test and exact auxiliary equality | NOT implemented; no source device/token/outbox replay |
| meta state/training-model-v1/protocol marker; old v1 projection tables | Classified technical material / redundant projection, not copied | Marker/root verified; unknown stores/meta refuse instead of silently omitting | Regenerate later, not raw replay |
| Legacy local anchor/backups, archive/checkpoint raw, derived indexes/caches and Drive operational authority | Explicitly excluded under revised #123 | Never read as export payload; no archive nesting | Not applicable |

All current source.data fields are retained. New unknown durable store/meta/local namespaces refuse until their canonical mapping is defined. This is not an automatic migrator for arbitrary old test state. The preferences meta key is a typed capture binding, not a new settings UI. The worker never writes client config or operational Drive state.

## Tests and measured evidence

Targeted Node: **1 orchestration case PASS**, covering sorted read-only buffer enumeration, unrelated-key exclusion, cancellation/termination, late result, revision/buffer changes, unknown data and worker errors. Inherited codec/domain/security Node tests are unchanged and included in final CI.

Targeted Chromium: **7 cases PASS across focused runs**:

1. Fresh UI starts a training session, saves a result; real existing Google configuration form saves synthetic client ID. Synthetic auxiliary draft/conflict/preferences/raw note values are stored in actual browser stores. Actual PPC1 button downloads a file; decoded source and auxiliary fields match exactly; all source IDB/localStorage unchanged; widths 360/390/412 have no horizontal overflow.
2. Immediate double click sends one worker request. Held worker work does not block navigation (<1500 ms test threshold); cancellation produces no late download.
3. Fresh profile activates V2 through existing UI, starts a session, saves native result/series and user note, then exports offline via controlled service worker. Exact logical data equality, one real session/result/snapshot, all source records unchanged.
4. A gated SHA in the real worker allows changing auxiliary preferences during capture; worker refuses, no file and no extra source mutations. The test gate queues bootstrap messages explicitly; no production hook was added.
5. Separate synthetic real-store source setup at 400/4000 sessions/results with unique snapshot-like preferences; actual app reload and production export button; entire data/catalog/preferences compared, not just counts. This setup is isolated test data creation, not a migration of user state.
6. Worker-side synthetic read quota/abort failures refuse with no file/mutation. These are read fault injections; no actual disk quota exhaustion or restore-write failure is claimed.

7. Existing malformed preferences (`value:null`) refuse rather than defaulting to empty settings; no download/source mutation. Client config types are checked as well.

Local worker measurements (single cold samples, synthetic; not Pixel, median/p95, peak memory or click-to-download timings):

| Scenario | Sessions / results / native snapshots | File bytes | Worker capture+encode+readback ms |
|---|---|---:|---:|
| Real new V2 UI session and saved note, final targeted run | 1 / 1 / 1 | 19825 | 177 |
| Synthetic source with unique preference snapshots | 400 / 400 / 0 | 11091 | 596 |
| Synthetic source with unique preference snapshots | 4000 / 4000 / 0 | 79048 | 4508 |

The two scale samples precede final extra invariant checks (metadata reachability/ID schema); the same benchmark test is part of final CI. Timing varies with generated IDs/timestamps and host load. A 4.5-second worker operation is not a blocked interface: separate gated-navigation test checks availability. It is also NOT an Android responsiveness acceptance result. Large localStorage reads/structured-clone buffers remain synchronous browser APIs; no universal zero-blocking/heap guarantee. Existing codec parse/transport caps remain; local buffers use the established 64 MiB/10000-entry admission scale, and a 60-second UI watchdog terminates unresponsive work. Limits are not raised.

Build allowlist includes five new runtime modules and SW was hash-refreshed, no deployment. Full final CI is recorded in PR. No duplicate full local regression. Pixel 9 acceptance and actual restore/restart/readback remain untested.

## Concrete restore blocker / next required implementation

Current `journal-database.commit` / `journal-idb.replaceSource` commits the journal plus protocol marker, but does not apply incoming draft/preference records and localStorage. `app.js` immediately opens the database, drafts and Drive; that startup has no durable pending-restore gate. A naive sequence `commit(source); put drafts; setItem buffers` could crash after strict journal complete and then start a partially restored app. Fresh profiles also initialize app state before a file is chosen, so emptiness requires an explicit logical-empty CAS policy rather than assuming the database is absent.

The necessary follow-up is a small fail-closed pending-operation record checked **before startup writers**, with checks for already-open writer tabs, a guarded empty-target executor reusing strict CAS/readback, and activation only after journal + auxiliary + local verification. Interrupted new restore must remain inactive and require a deliberate retry into a clean target; old preimage recovery is not required. This needs actual fault-injected restart tests and destination identity/draft-token rebinding, not a fabricated success flag. No such executor/gate is smuggled into this export PR. There is no new restore preview/confirmation path, no clean-profile restore roundtrip and no claim that all requested #137 acceptance criteria are complete.

Final correctness fix: preference/client type validation prevents silent normalization of existing malformed auxiliary records. Only the new counterexample was rerun locally; the fixed final SHA supersedes the initial CI, with final outcome recorded in PR.
