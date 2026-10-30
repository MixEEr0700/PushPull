import {test} from 'node:test';
import assert from 'node:assert/strict';
import {localSource,captureCompleteContract,CAPTURE_LIMITS} from '../model/complete-backup-capture.mjs';
test('only inventoried PushPull namespaces qualify, no unrelated origin values',()=>{
 for(const key of ['pushpull_skeleton_v1','pushpull_indexeddb_owner','pushpull_skeleton_v1_backup_old','pushpull_workout_draft_v1:a','pushpull-note-ui-v1:retired:a'])assert.equal(localSource(key),true);
 for(const key of ['other-app','pushpull_future','pushpull_skeleton_v10','pushpull_indexeddb_owner_other'])assert.equal(localSource(key),false);
});
test('capture budgets only allow stricter limits and abort before database access',async()=>{
 for(const [key,value] of Object.entries(CAPTURE_LIMITS))await assert.rejects(captureCompleteContract({limits:{[key]:value+1}}),/limits may only be lowered/);
 await assert.rejects(captureCompleteContract({limits:{unknown:1}}),/limits may only be lowered/);
 let opened=0;const events=new EventTarget(),c=new AbortController();c.abort();
 await assert.rejects(captureCompleteContract({indexedDB:{open(){opened++;}},storage:{},events,signal:c.signal}),{name:'AbortError'});assert.equal(opened,0);
});
