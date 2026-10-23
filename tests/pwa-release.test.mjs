import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

test('worker identity is read-only and cannot force activation or touch workout storage',()=>{
 const callbacks=new Map(),replies=[];
 const forbidden=()=>{throw Error('Update identity must not mutate data or activate a worker');};
 runInNewContext(readFileSync('sw.js','utf8'),{
  URL, self:{registration:{scope:'https://pushpull.test/'},addEventListener:(name,fn)=>callbacks.set(name,fn),skipWaiting:forbidden,clients:{claim:forbidden}},
  caches:{open:forbidden,delete:forbidden},indexedDB:{open:forbidden},localStorage:{setItem:forbidden},fetch:forbidden,
 });
 const port={postMessage:value=>replies.push(value)};
 callbacks.get('message')({data:{type:'PUSHPULL_RELEASE'},ports:[port]});
 assert.equal(replies.length,1);assert.equal(replies[0].type,'PUSHPULL_RELEASE');assert.match(replies[0].release,/^[a-f0-9]{24}$/);
 assert.deepEqual(Object.keys(replies[0]).sort(),['release','type']);
 callbacks.get('message')({data:{type:'SKIP_WAITING'},ports:[port]});
 callbacks.get('message')({data:null,ports:[port]});
 callbacks.get('message')({data:{type:'PUSHPULL_RELEASE'},ports:[]});
 assert.equal(replies.length,1);
});
