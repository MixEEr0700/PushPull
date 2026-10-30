# Canonical future backup, #123 / updated #131

Base main d117de5. Owner's latest instruction supersedes old physical-ledger preservation. This is an isolated canonical codec, NOT a migration, live exporter, restore, Drive or UI implementation. Nothing is deleted from any source. Existing complete-contract APIs remain unchanged.

## Required canonical state

Root `format:pushpull-canonical, version:1, source, drafts, buffers, preferences, drive`.

- source contains exactly format/version/data/catalog: the full existing validated logical training model, all session/results/series/L/P/drop/corrections, plan versions and stable IDs, rotation, snapshots, instructions, notes and supported extensions inside data/catalog. All logical snapshot references and counts remain intact.
- drafts: explicit key/value records, every conflicting version, unfinished input and ancestry retained. No winner selected. Tokens here describe draft provenance, not authority to overwrite a target database.
- buffers: exact raw workout/note local buffers including retired tokens and malformed Unicode/JSON. No parsing or normalization; future activation must validate context.
- preferences: portable application preferences/extensions, explicitly provided by future capture. It must not be populated blindly from technical storage.
- drive: clientId only as user configuration. No device identity, OAuth, accounts, heads, CAS or upload outbox. Reconnection belongs to later integration.

All sections are required even when empty. Existing training validators, portable JSON boundary and PPC1 SHA-256/size/decompression checks remain in use. Unknown root/source/Drive sections refuse instead of silently discarding fields. This new logical envelope is deliberately distinct from the old complete physical ledger. It does not accept an old source with archives and silently strip it: callers must supply the new explicitly classified state. There is no old-data converter.

## Regenerable versus excluded

| Category | Treatment |
|---|---|
| Active logical training state, all actual results, session snapshots and versioned plans, notes, drafts, portable preferences | Required; field-for-field codec equality |
| Identical copied snapshot/model subtrees | Interned as one immutable value before encoding; existing PPC1 graph dedup serializes shared content once; different values/order remain distinct |
| IDB indexes, object hash graph, allocation counts, epoch/root/revision, routing marker, derived statistics | Regenerate from verified canonical state in a later restore; no source CAS authority replay |
| Legacy tables duplicating the logical model | Excluded from new contract; no migration or deletion |
| Raw backup archives, nested rescue JSON, checkpoint/preimage chains and old test backup files | Excluded; future training history must live in source, not only in an opaque archive |
| Drive transport state, device identity, heads/outbox/tokens | Excluded operational authority; only client configuration retained |
| CacheStorage/SW bytes | Rebuildable application assets, excluded |

Inert historical evidence from #125 is no longer mandatory for the new system per owner decision. This is NOT proof that current live capture can automatically classify every stored unknown field. Binding drafts/preferences and proving complete capture from the future application remains a separate requirement. New durable features must extend this schema explicitly; arbitrary future source sections refuse.

## Measurements (synthetic Node, single cold sample per size)

Fixture uses legacy-structured synthetic sessions with one result per session; native V2 snapshots/notes/draft conflicts/Unicode are covered separately by semantic roundtrip tests. Timing starts after canonical construction; it measures transport write/read including their validation, not capture, construction, UI response, disk commit, median or p95. No Pixel measurements. Raw JSON is canonical root JSON, not old 200 MB backups.

| Sessions/results | JSON bytes | PPC1 bytes | Write ms | Read ms |
|---:|---:|---:|---:|---:|
|0|11227|43647|188.96|43.59|
|4|12672|51362|107.52|45.59|
|40|25855|72617|126.27|49.58|
|400|159476|287481|387.98|273.08|

PPC1 is larger for these small graphs because its current per-object manifest/hash overhead dominates. No assertion of a universal size win, compressed 200 MB recovery or subsecond Android performance. Existing limits are not raised. A copied-snapshot stress test initially hit the existing property limit; subtree interning fixes redundant traversal without increasing budgets. The test compares bytes for 40 copied vs shared identical native snapshots and verifies logical count 40. Unique genuinely different snapshots are never coalesced.

## Tests and remaining work

Targeted Node 4/4 PASS: full native V2 logical and auxiliary equality, caller input unchanged, Unicode/conflicts, explicit refusal of unknown/technical sections, duplicate keys, corruption, cancellation, lower budget and snapshot dedup. Synthetic benchmark verifies exact equality at 0/4/40/400 sessions/results. Chromium 1/1 PASS: 40-session codec roundtrip and exact source IDB/localStorage unchanged. Build/SW hashes match. Full final CI recorded in PR, no duplicate full local regression.

No production capture integration, clean-profile durable restore/restart comparison, quota-on-write recovery, physical Pixel test or actual worker/UI responsiveness measurement. In-memory canonical construction and graph interning are synchronous; future production capture/codec must be worker-driven and measured before responsiveness claims. No large opaque archive test is applicable to this new envelope: archives are explicitly refused, not encoded or deleted. Existing old-codec archive tests remain inherited. User-approved intentional archive exclusion does not authorize omitting future sessions/results. Production completeness remains unproven until future live capture → file → clean-profile restore → application restart → exact state comparison passes.
