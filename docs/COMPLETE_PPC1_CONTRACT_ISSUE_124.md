# #124 — persistent PPC1 contract revision 1 (isolated)

Base `4f5817d` after #122. Implements the contract/inventory stage of #123, **not production completeness**. No private device capture, migration, export/import switch, UI, SW, Drive, #109 or #120 changes. No transactional architecture change. Scope is explicitly supplied persistent snapshots; live editor memory and other tabs are NOT certified.

## Inventory and coverage

Database `pushpull` v2 is declared by `indexeddb.js` and `model/journal-idb.mjs`; `journal-protocol.mjs` declares journal stores. The test derives declared legacy TABLES + meta/backups + journal STORES and checks exact coverage (new stores fail the test). All fields/unknown extensions of every supplied record remain in the ledger, with original ordering. Omission of a store, record count or observed local key fails validation. This is not proof a caller actually enumerated every source: live enumeration/stability belongs to the next integration.

Common map for EVERY table row below: capture is caller-supplied snapshot, PPC1 field is `indexedDB.stores.<store>`, isolated write/read performs exact field comparison. **Production capture/restore/readback of this new envelope: NOT integrated.** Original #122 source-only importer is not an implementation of these rows.

| Store | Role / actual data | Current #122 restore |
|---|---|---|
| meta | Separate truth: workout-draft:* (context, unfinished value, token, parent, sequence, revision), drive-sync-v1 (config/selected account/account heads/outbox/manual flags/CAS token/device ID). Technical evidence: state, training-model-v1, journal-protocol-v2 marker; all unknown meta retained | Keeps local drafts/Drive metadata; does not restore incoming auxiliary records |
| plans | Retained v1 plan rows | Reconstructed source projection, not raw replay |
| planVersions | Retained v1 immutable parameter versions | Source catalog, not raw replay |
| exercises | Retained v1 identity/parameters | Source data, not raw replay |
| sessions | Retained v1 sessions/date/rotation | Source data, not raw replay |
| entries | Retained v1 results/corrections | Source data, not raw replay |
| sets | Retained v1 actual series | Source data, not raw replay |
| notes | Retained v1 notes | Source data, not raw replay |
| changes | Retained v1 technique changes | Source data, not raw replay |
| backups | Retained v1 raw archives/preimages | Logical archives merged; no raw physical replay |
| journalObjects | Source values, deduplicated immutable graph; also retained old objects and legacy anchor | Rebuilds new protocol graph from incoming source |
| journalMetadata | Current non-table source data/catalog/plan model/unknown fields, rotation/settings stored inside data | Source fields preserved |
| journalSessions | Current sessions and active session metadata | Source fields preserved |
| journalResults | Current complete results/performance/L/P/drop/corrections | Source fields preserved |
| journalSnapshots | Current immutable snapshots, plans/instructions/notes captured therein | Source fields preserved |
| journalArchives | Current ordered raw archives + metadata | Source archives preserved plus prior archives/preimage |
| journalIndex | Derived persistent indexes with integrity links | Rebuilt, not raw replay |
| journalState | Active epoch/revision/root/counts/allocation/runtime links, CAS authority | Fresh commit root, not old epoch replay |
| journalCheckpoints | Retained conversion/previous-store rescue evidence | Not fully restored by source-only import |

Active source truth is the verified journal graph, not stale v1 tables or an arbitrary localStorage history. The contract requires active v2 state and a matching active meta marker. Legacy/conversion-pending-only databases require a separately specified capture policy; they are not silently interpreted as complete v2.

| localStorage source | Role | Capture → PPC1 → current restore → readback |
|---|---|---|
| pushpull_skeleton_v1 | Original legacy text/anchor and possible conflicting evidence | Exact raw string → localStorage entries → #122 leaves local anchor, does not apply incoming value → synthetic equality only |
| pushpull_skeleton_v1_backup_* | Earlier raw rescue backups | Exact raw → entries → not restored → synthetic equality |
| pushpull_indexeddb_owner | Device routing marker | Exact raw → entries → backend establishes current ownership, not incoming replay → synthetic equality |
| pushpull_workout_draft_v1:* | Uncommitted/failed-write buffers, all versions/conflicts and corrupt JSON | Exact key/raw → entries → not imported → synthetic equality |
| pushpull-note-ui-v1:* | Note buffers with base/text/context/token, including retired:<token> tombstones | Exact key/raw → entries → not imported → synthetic equality |

Unknown origin keys are refused, not silently omitted or copied from unrelated applications. Absence is represented by an enumerated localKeys list (empty only if enumeration actually found none). Counts and key lists detect accidental removal from a captured ledger, not dishonest declarations.

Other persistence: CacheStorage in SW is rebuildable application code (not training truth); cache names/release bytes are excluded and regenerated. No production sessionStorage, OPFS, cookies, WebSQL or additional database persistence was found in the repository scan. Browser-managed OAuth credentials are not an exportable application record; Google access token is transport memory, while persisted Drive metadata/CAS tokens are included verbatim as evidence. Do not automatically reconnect/replay an old device's outbox when future restore is integrated. Exported files/Drive remote nodes are outside local origin capture. In-memory form edits and unresponsive tabs need a future durable-capture barrier or explicit refusal of a complete-production claim.

## One envelope, existing PPC1 wire

Root exactly `{format:'pushpull-complete-contract',version:1,capture,source,indexedDB,localStorage}`. Capture exactly `{before,after,scope:'supplied-persistent-snapshot',otherTabs:'unknown',counts,localKeys}`; before/after are equal sealed-root strings. indexedDB exactly `{name:'pushpull',version:2,stores}` with every inventoried store required. Each record has a unique string key (meta.key, other store.id); localStorage is ordered `{key,raw}` entries, preserving invalid JSON/UTF16. Empty stores are explicit. Portable JSON only, <=10000 supplied rows/entries, unchanged PPC1 resource limits; safe refusal on unsupported types/limits rather than incomplete output.

source is the complete structured v2 logical source (all data/catalog/archives and compatible portable extensions). Existing validateCompactSource validates training semantics. Existing materialize independently verifies journal hashes/references and its exact equality to source. Legacy retained rows/meta are preserved as opaque physical evidence; their historical domain semantics are not declared valid. Duplicate logical source+physical ledger is intentional conservative evidence in this isolated stage, NOT a claimed optimal production file size. Future integration may normalize derived stores only with an explicit mapping and exact tests, not by silently dropping them.

API: writeCompleteContract / readCompleteContract / validateCompleteContract / contractCoverage. Uses existing PPC1 generic writer/reader unchanged; new root is deliberately rejected by current production restore (#122), preventing partial application. No DB is opened by this module. Snapshot captured before awaits; input descriptors checked before cloning; result immutable. Coverage returns productionComplete=false. Caller-provided revision assertions are not an atomic cross-storage snapshot, authentication, or proof of all-tab capture.

## Evidence and remaining integration

Targeted Node: exact full fields for all stores/local entries, complete native V2 model, legacy snapshot, notes/draft conflicts/settings/archive evidence, Unicode, unknown retained meta fields, omissions/counts/unknown store/key rejection, source-vs-ledger divergence, corrupt file, abort and size refusal. Chromium synthetic fixture: exact per-store and whole-envelope comparison offline; input unchanged; actual initialized IndexedDB records and localStorage unchanged. No production capture/write is exercised; no complete restore claim.

Earlier main CI and unchanged reader/writer/transaction tests are inherited evidence. Only one final full CI is run for this PR, results recorded in PR. No Pixel 9 test, actual production export → empty profile restore → restart → all-state comparison, or new section restore is complete. Next PR must implement that integration: consistent multi-source capture, source and auxiliary semantic validation, atomic/compensated IDB+localStorage application with CAS/preimage/readback/strict complete, safe treatment of device identity/Drive outbox and failure recovery. No destructive raw replay of old epochs is authorized by this contract.
