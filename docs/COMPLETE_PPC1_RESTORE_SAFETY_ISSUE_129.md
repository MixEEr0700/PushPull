# #129 — necessary read-only restore planner, NOT a restore implementation

Base `fe55e0f` after #128; governed by #123. Issue #129 explicitly allows only the necessary planner/tests when the complete operation cannot yet be safe. This PR takes that fallback. **Persistent records restored: zero.** No production export, import, UI, Drive, database schema or existing transaction code changes. No private profile accessed.

## Concrete blocker in existing code

`journal-database.mjs:commit` creates an import preimage and calls `journal-idb.mjs:replaceSource`. The latter has strict durability, root/equalRows CAS, transaction readback and post-complete source audit, but its transaction scope is nine journal stores plus meta. It does NOT atomically import the nine legacy physical tables, auxiliary meta records and localStorage. It intentionally preserves local drafts/Drive state. Passing the complete envelope into it would either fail or lose incoming auxiliary fields.

`app.js` opens `PushPullDB` before opening drafts and Drive. `journal-database.mjs:publish` writes the ownership key, and startup can convert/initialize an absent database. There is no pending multi-storage restore gate before these writes. Thus using replaceSource followed by a loop of localStorage.setItem would expose a partially restored installation after quota, crash, tab closure or restart. A rollback loop cannot make cross-storage writes atomic, and could delete a competing tab's data. This is a concrete missing safety mechanism, not a performance or old-history compatibility concern.

## Implemented API

`planCompleteRestore(file,{signal,limits})` uses the unchanged PPC1 reader/complete-contract validator. Full container and logical/physical graph validation precedes any plan. The entire input, including all 19 stores and every local raw string, remains immutable in `evidence`. No fields are discarded. Existing createProtocol/materialize prepare and independently check a new candidate graph from the complete logical source. No storage access is needed for this function. `canCommit` and `productionComplete` are always false; it has no execute/commit method.

`inspectEmptyRestoreTarget({signal})` independently observes a real synthetic destination: an absent database or a v2 schema with all 19 correctly keyed empty stores and no lowercase pushpull* localStorage keys. Unrelated app keys/databases are left alone. Existing rows/keys, unexpected schema, storage errors and cancellation refuse. Native database inventory avoids creating an absent database. Existing schemas are inspected with the existing readonly transact/request helper. The result explicitly has `reserved:false`: a target may change after observation; this is NOT a CAS token, write authorization or guarantee of other-tab exclusion.

## Explicit proposed policy (no activation in this PR)

| Data | Candidate/activation policy | Exact original retained |
|---|---|---|
| source: complete training data, plans, settings/extensions, session results, snapshots, notes, archives | Preserve every logical field, stable ID and ordered value | evidence.source |
| journalObjects, journalMetadata, journalSessions, journalResults, journalSnapshots, journalArchives, journalIndex, journalState | Regenerate protocol records from verified source; fresh epoch/root, revision 0, fresh allocation/index integrity | all corresponding evidence stores |
| journalCheckpoints, old preimages | Inert recovery evidence only, not live conversion checkpoints | evidence store verbatim |
| plans, planVersions, exercises, sessions, entries, sets, notes, changes, backups | Inert historical physical evidence; active semantics come from verified source, never blindly replay stale projections | each evidence store verbatim |
| meta journal-protocol-v2 / state / training-model-v1 | Regenerate, never replay source CAS/protocol authority | original records verbatim |
| meta workout-draft:* | Preserve every draft version/conflict; activation blocked until source context/revision/token ancestry can be safely rebound | original records verbatim |
| meta drive-sync-v1 | Disconnected manual candidate (enabled false, selected null, accounts empty, clientId blank); no source device ID, token, heads or outbox activation. Explicit reconnection/configuration later | entire original record, including settings, retained as inert evidence |
| other/unknown meta | Retain without activation; require explicit future semantics rather than silently accepting arbitrary authority | original records verbatim |
| local owner marker | Regenerate target routing only after activation, do not import source marker | original key/raw |
| local legacy anchor | Retain original as evidence; bind regenerated protocol to target anchor explicitly | original key/raw |
| local rescue backups | Retain as evidence, no automatic import | original key/raw |
| local workout/note buffers + retired tombstones | Preserve exact raw values/conflicts, including malformed/unfinished input; verify/rebind context before activation | original key/raw |

Logical training-model ownerId is provenance referenced by training records, not a Drive device credential; it is retained. Fresh protocol epoch/root and revision cannot equal source physical authority. No claim of exact raw physical equality of an eventually regenerated active graph: future acceptance must compare logical portable data exactly and account for every physical evidence row separately. Retaining evidence in a plan/file is NOT durable destination restoration.

## Required next safety implementation

1. Introduce a versioned, durable pending-restore record and recovery gate **before** normal DB initialization, conversion, drafts, Drive and UI writers. This needs a reviewed startup change; no data writes can bypass the gate. A cooperative barrier must cover other app tabs; Web Locks alone do not constrain old/nonparticipating writers.
2. Prepare/validate complete staged input and destination preimage (including absence of every local key), under a fresh operation identity. Keep source identity/outbox/checkpoints inert. Validate typed draft/meta activation mappings; unresolved unknown authority blocks completeness.
3. Extend the established strict transaction to the required stores, with native all-store emptiness CAS, atomic staging/preimage, full row/key readback and actual complete. Reuse current validators and helpers, rather than invent an unverified raw bulk-put path.
4. Journal each cross-storage phase. Apply local keys using expected-absence/expected-value checks. On quota, abort, crash or a conflicting write, gate startup and resume/compensate only owned unchanged values; never erase a competing edit. Keep recovery material until terminal durable verification. An interrupted state is not a successful import, even if IDB completed.
5. After durable local verification, confirm the regenerated graph/marker and all auxiliary stores/keys, activate the new installation, then test actual application restart. A failure after strict complete must report an indeterminate/pending restore and preserve recovery, not claim rollback.
6. Fault-inject at every phase boundary, including two tabs, quota after N local keys, transaction abort, readback failure and restart. Permute record order and compare source→destination under the above explicit policies. Only then expose the new restore API or integrate production capture/export.

## Actual verification and unverified work

Targeted Node: 3 tests PASS (all-store policy coverage and complete evidence equality; fresh graph with exact logical source; no replay of device/Drive/checkpoints; corrupt/truncated/overbudget/pre-aborted input refusal). Chromium: 3 tests PASS, using actual synthetic stores and capture→PPC1→plan in a separate empty browser context; every source field/evidence preserved, source/target unchanged, absent DB not created, empty 19-store schema read, nonempty IDB/local refusal, simulated quota exception and abort. Reload verifies the target remains unchanged/empty; it is NOT a restored-application restart test. Native quota-on-write, transaction abort during restore, crash recovery, two-writer restore exclusion, offline production restore and randomized write order are untested because no write/restore executor exists.

Build/SW hash check PASS. One full final CI is recorded in PR. Earlier capture/reader/writer/transaction tests remain inherited evidence; no unnecessary full local regression. No production complete export→clean-profile import→application restart→all-state equality test, no restored records, no Pixel 9 test, no 100% recoverability claim. Issue #129 remains open for the safety executor and full acceptance test.
