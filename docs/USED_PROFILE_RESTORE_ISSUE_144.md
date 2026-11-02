# #144 — replace a used canonical profile, with recoverable preimage

Base: main 0781ebe after #143. Existing canonical PPC1 reader/writer, validation, native replaceSource, root CAS, strict complete and fail-closed gates are reused. No private device database or real Google account was read. No Drive file is deleted. Older JSON/source-only PPC1 import paths remain unchanged.

## Production behavior

File and selected Drive point both enter the existing inline restore preview. A worker compares complete current/incoming canonical histories and summaries (sessions/results/plans), note additions/removals/changes, drafts/buffers and preference counts. Confirmation explicitly replaces, never merges. Preview captures a complete read-only current PPC1; confirm checks revision and the same canonical contents again, including drafts/local buffers that do not advance journal revision. Navigation/cancellation before confirmation makes no source writes.

Before claiming the source, the worker produces the current canonical PPC1, checks auxiliary values against its physical metadata snapshot, verifies codec/domain equality and stores an independent immutable recovery point. New database `pushpull-canonical-rescue`, version 1, stores a canonical file plus journal/metadata evidence and separate SHA-256 digests. Existing source schema/stores and formats do not change. Add/readback/strict transaction completion is followed by a separate read, file and evidence digest checks, and canonical semantic decode. Quota/error/refusal here leaves source records and localStorage unchanged; a refused claim can leave a harmless extra recovery point. Source journal/metadata CAS still has to match after this work.

The rescue evidence retains original journal records/checkpoints and Drive metadata, including obsolete queue evidence. This evidence is **not** reactivated as source epoch, auth or Drive authority. Existing legacy stores are untouched. Logical restore/rollback reconstructs the canonical model, not byte-identical operational ledgers. Old technical archives are evidence, not merged training history or newly exported canonical payloads, consistent with #123.

A local reservation and strict native pending marker fence startup/writers. The marker carries the owned journal state; the bulk writer updates that witness in the same strict transaction as its new root. Recovery refuses a foreign root. If only the final local marker remains after native activation, the current full canonical fingerprint must match the intended incoming snapshot retained with the point. Recovery is unavailable without the matching pending identity; normal point restore always creates a fresh safety point. The bulk source replacement regenerates epoch/root with existing all-row CAS, opaque checkpoint, exact readback and independent native audit. Auxiliary replacement checks the expected full metadata snapshot after the source transaction, removes old draft rows, restores incoming drafts/preferences and creates disconnected/manual Drive configuration with fresh device/token and no accounts/queues/checkpoint claims. The legacy Drive metadata writer also checks the native pending marker inside its transaction. The running Drive controller pauses credentials/retry before commit; other old queue callbacks cannot acknowledge against the changed token. Captured HTTP may already have appended a remote file, but no restored point is treated as a newly verified cloud backup.

Main thread replaces only the exact previously captured local buffer inventory, after the durable rescue and claim, checking ownership/storage events. It never guesses a winning draft. Worker re-exports and compares the entire activated canonical object. Root/full-meta CAS removes the native marker only after this verification; main final buffer/anchor/owner checks remove the local marker. A failed/uncertain operation never produces a success receipt.

## Actual rollback, including restart

`Dane → Opcje zaawansowane → Punkty cofnięcia PPC1` lists points by an index (without loading all payloads), with download and preview/restore. Restoring a point through normal UI first saves a new point of the current valid state. Points are append-only; no deletion/retention or overwrite of the only copy.

On interrupted/partial restore startup returns before normal writers, draft initialization or Drive queue execution. The blocked screen offers **Cofnij przerwane przywracanie** with explicit confirmation and **Pobierz punkt ratunkowy PPC1**. Recovery requires that operation's durable native/local pending identity and a verified matching point. It reuses guarded bulk replacement and full canonical readback, regenerating epoch/CAS rather than reviving old writers. No attempt to export a partially restored current model is necessary. Failure during rollback keeps the original point and pending gate; retry is deterministic from that same point. A download is available if the device cannot complete rollback. Heavy rescue verification is in the existing worker, not a main-thread parse/hash.

Drive credentials/accounts/old outboxes are intentionally disconnected after both restore and rollback. After explicit new login the next backup follows the normal flow and a fresh lineage; no source cloud head/token is copied.

## Verified synthetic evidence

Targeted Node: 3 PASS (existing canonical codec/corruption and native pending ownership). New Chromium cases, PASS across focused runs:

1. Used target with two finished sessions, preferences and raw note buffer → real local PPC1 with another history, result/series, plan/snapshot/user note, two draft branches and four raw buffers → restart → production re-export exact equality → actual point UI rollback → restart → equality to target's original canonical file. Cancel leaves all native records unchanged. Epoch differs; old pending upload metadata is not reactivated.
2. Partial local buffer quota failure → blocked restart → verified recovery-file download even when the native source database is unavailable → rollback → exact equality to original used profile.
3. Simulated OAuth/real production Google HTTP transport: two uploads (base/delta), select earlier point on same used profile, preview/confirm/restart, exact comparison, then point rollback to later state. Upload count remains two.
4. Recovery database quota refuses before any source record/localStorage change.
5. Two cards: pending claim blocks other card and legacy Drive state writes; kill worker/reload after strict claim, then rollback and full equality.
6. Native journal abort leaves original journal rows intact; restart/rollback restores every canonical value.
7. Concurrent newer revision after preview refuses without overwriting it.
8. Missing base / corrupted Drive delta refuse without changing the used target.
9. Corrupt rescue file or evidence SHA refuses preview/activation and leaves current records/localStorage unchanged.

11. A final local activation error after removal of the native marker still supports verified rollback using the incoming canonical fingerprint.
12. A foreign root introduced after claim is retained; recovery refuses to silently erase it.
10. A codec-valid file with a draft key incompatible with the native meta keypath refuses before source mutation or rescue creation; format readers remain unchanged.

Updated inherited clean/cancel/corrupt test now also proves a used target can restore, instead of asserting the obsolete clean-only restriction. Export wording test follows the new supported behavior; integrity assertions remain. Build/worker hashes/diff/syntax checks pass. Final CI result is in PR; no duplicate full local regression.

## Boundaries

Canonical native v2 data must be fully readable/valid to make the preimage. Unknown source settings, conflicting legacy localStorage anchor or inability to create/verify the point causes refusal, never reset or guessed recovery. Legacy formats retain their existing paths. Rescue file and serialized evidence each have a 128 MiB cap; this is not a peak-heap guarantee. Listing caps at 1000 points, with no automatic deletion. Extra disk space is needed for the point and journal checkpoint. Independent database + localStorage atomicity is not claimed: durable gates control activation. Browser strict completion is tested, not physical hardware power loss or disk corruption survival. Same-origin hostile scripts/DevTools destruction are not an authentication boundary. No real Drive/Pixel 9 acceptance, large-device memory/p95 measurement or quota exhaustion on physical storage. Google behavior above uses simulated API/OAuth with actual app transport and browser stores.
