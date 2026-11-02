# #139 — working canonical restore into a clean installation

Base main fdbd201 after #138, #123/#137/#139. Real production export and file-picker restore are now connected. This supersedes #137's export-only limitation. No old user database migration/recovery, no automatic reset, no new Drive sync/automation, no Matrix redesign.

## Production path

`Dane → Przywróć kopię → Z pliku` recognizes the versioned canonical PPC1 payload in the existing worker preview. SHA/limits/semantic validation precedes the preview, including session/result/plan summaries and draft/buffer counts. The existing separate confirm button plus native confirmation is required. Cancel/invalid file does not reserve or mutate the target. Heavy parsing, protocol construction, hashing, native journal restore and full readback run in a module worker; the main thread handles localStorage (unavailable in workers), final checks, and restart. Existing JSON and source-only PPC1 restore paths remain intact. Local export labels no longer claim canonical restore is unavailable; it is limited to a clean installation.

After complete verification the app reloads. A temporary sessionStorage receipt displays human-readable counts/time; inability to store this UI receipt does not turn data success into a partial restore. It is not canonical user data. No success receipt is created on a pending operation. The mandatory test reloads **again**, exports through the production button and compares every canonical field to the original downloaded file, so it does not trust the receipt or a live JS model.

## Clean-target policy and CAS

A clean installation is the app's freshly initialized v2 profile, not literally nonexistent IDB: pristine default data/catalog, revision 1, zero sessions/results/snapshots/archives, null legacy anchor, no drafts/preferences/client configuration/accounts/unknown meta or local buffers. The default catalog is derived using the same app catalogFor/fresh input, not hardcoded source IDs. This is deliberately strict; a used or imported profile is refused, never wiped. The worker checks compact state counts first to avoid loading history/rescue payloads in a used target. Only after these checks does it read the known-empty target's native graph for the existing bulk-writer CAS.

A local reservation and then a native **strict** claim transaction verify the complete target journal rows and meta snapshot; concurrent changes cause refusal. Preferences, draft absence, account state and marker are checked from that actual meta snapshot too. Only the claim transaction creates `canonical-restore-pending` with a fresh operation ID. The main thread first reserves `pushpull_canonical_restore_pending` after verifying the local target again. Foreign state is never cleared or restored over; best-effort cleanup removes only this operation's local flag if no claim committed. No legacy rollback/reset is attempted.

## Durable fail-closed gate

The startup gate reads flags before PushPullDB.open and checks again after it, before draft/Drive/UI initialization. Unknown gate status blocks visibly. While pending, normal app events/render, workout buffer writes/clears and all v2 readwrite transactions are fenced. The journal transaction helper includes meta in the native transaction scope and checks pending ownership **inside that same transaction** before running writer work. Restore-owned transactions require the matching ID; there is no global lock claim based on a BroadcastChannel or a check outside a transaction. Existing open tabs retain their old model until reload and cannot commit over the new root; a pending startup cannot initialize a partial model as a normal application.

Phases:

1. Validate immutable file in worker; verify pristine target and its complete native CAS snapshot.
2. Reserve local flag; strict native claim marker/readback. From here any interruption is pending.
3. Existing `replaceSource` recovery bulk writer: fresh epoch/root, regenerated indexes/runtime/allocation, target revision +1, native equalRows/root CAS, readback, **strict transaction complete**, independent post-complete audit. Existing small preimage of the known-empty default target is retained by that helper; there is no old-history rescue, archive import or nested backup chain.
4. Restore all draft rows, preferences and portable client config in a guarded strict meta transaction with exact readback. Capture expected meta for final activation CAS.
5. Main thread writes only missing local buffer keys; quota/conflict/error sends failure. Verify every raw key/value; no overwriting or compensating deletion of a foreign edit.
6. Existing production capture/codec reads the target while owned-pending, and compares **the entire canonical object** to the file. Activation checks exact root and the full expected meta snapshot inside a strict transaction before removing the DB marker.
7. The local flag still blocks all startup/normal main-thread writers. Main thread verifies the complete local buffer inventory, owner/legacy anchor, storage-event conflict flag and operation ownership once more; only then removes its local flag and reports success/reloads.

A crash or failure after claim keeps durable gates and imported/staged data inactive. Restart shows a blocking explanation, not the workout UI or a success. The supported retry is explicitly another fresh profile using the unchanged original PPC1 file. This PR never silently deletes pending data, retries over a used target, or implements an old-preimage rescue tool. Cross-IDB/localStorage atomicity is **not** claimed: activation is gated on both stores. Guarantees apply to cooperating current-version app writers and browser storage API completion; these gates are not an authentication boundary against arbitrary same-origin scripts or user DevTools deletion of authority records. Deliberately clearing site data/permissions or physical storage failure is outside a browser's absolute atomicity guarantee.

## Data/identity policy

- Logical source data/catalog, sessions, actual series/performance/L/P/drop fields, versions, snapshots, instructions, user notes, rotation and all supported extensions are preserved exactly by the canonical source and existing domain validators.
- Draft records and raw workout/note buffers, including conflicts and retired-note tokens, are restored exactly. Draft IDs/tokens/ancestry are **logical branch/version identities**, not credentials or imported journal authority. They remain to preserve buffer references and explicit resume/discard CAS semantics. No winner/date/global sequence is selected. The test resumes a compatible imported draft in the real editor after full equality verification.
- Journal epoch/root/global CAS and derived records are newly generated. Logical model ownerId remains because it binds exercise/note provenance IDs; it is not the physical Drive device identity.
- Preferences are restored as the typed canonical preference value. No unknown physical ledger or source legacy marker is activated.
- Drive gets only the canonical client ID with `mode:manual`, disabled, selected null, accounts empty and **fresh deviceId/token**. A source fixture deliberately contains heads/outbox/selected account; they are not in the canonical file and are not replayed. No OAuth/network upload occurs. Other Drive code remains unchanged.
- Legacy JSON export/import and source-only PPC1 continue to use their existing paths. `storage.js` exposes its exact existing validator to module workers; no independently weakened restore validator is substituted.

## Actual evidence

Targeted Node: **2 cases PASS** (export lifecycle/conflicts; native transaction pending ownership, metadata scope, strict durability and local gate checks). Targeted Chromium: **7 canonical restore cases PASS across focused runs**, plus a targeted existing source-only PPC1 offline/preimage/strict-complete/mobile/restart regression and existing export UI regression PASS. An early cancel test had a test synchronization race (flipped dialog response before the queued confirmation); it now waits for the actual dialog event before changing the response, retaining exact no-mutation assertions.

Mandatory full UI test:

- Fresh source activates a V2 plan, starts a real session, saves a result/series and user note; captures a real unfinished form. Synthetic second draft branch and buffered conflict are added to actual stores, with preferences, raw unfinished note and existing client-config form. Source operational account/head/outbox fixture is deliberately excluded by the established exporter.
- Production PPC1 download → independent clean browser context → readonly preview → explicit confirm → native restore → automatic reload → manual reload → production re-export → exact deep comparison of **all canonical values** (not counts alone), including catalogs, original model/snapshots, draft fields, buffer raw strings, preferences and client config.
- Source versus destination physical epoch/root and Drive device/token differ as required; accounts/selection empty. Native draft can be resumed with its recovered kg value. No test-only restore API bypasses the production confirm path.
- **Actually restored: 1 session, 1 result record (all its series), 1 native snapshot, 2 persisted draft branches, 4 exact local buffers, saved user note, full model/catalog/plan versions, preferences and client configuration.** Logical categories are reported separately, not a misleading sum of physical/deduplicated records.
- Final local positive sample: **20854 B**, worker **521 ms**, click-to-verified-reload notice about **0.891 s** (Python monotonic clock). One synthetic cold sample, not Pixel or median/p95; file bytes vary with UUIDs/timestamps. Includes full worker parsing, source/auxiliary writes and readback; UI time includes restart/notification polling.
- Offline restore/re-export via real service worker, mobile 360/390/412 no overflow.

Fault coverage: cancel preview/decline confirmation and corrupt/truncated file leave target unchanged; a target with a real session refuses without overwrite; quota after the third local-key attempt keeps partial buffers and both gates, no success, with exact no-writer-mutation after reload; quota/abort at journal state put roll back the native journal transaction but preserve pending claim; killed worker after strict claim blocks boot and a different fresh profile successfully retries; already-open second tab cannot start a session while pending and reloads complete data afterward; foreign meta change before claim causes CAS failure and preserves every foreign value with no imported records. Low-level write gate also refuses non-owner transaction work in its strict native scope.

No full local suite was duplicated. Final full CI on final SHA is recorded in PR. Pixel 9 acceptance, large native multi-year restore/peak heap/p95 measurements, real hardware power loss, actual disk exhaustion and hostile raw script mutation are **not verified**. No migration/reset of the user's old phone data, no Drive sync/automation, no claim that these synthetic results constitute physical Android acceptance.
