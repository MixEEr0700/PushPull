import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {stagePlan} from '../model/plan-import.mjs';import {views} from '../model/v2-plan.mjs';import * as editor from '../model/performance-editor.mjs';import {newPerformance} from '../model/performance.mjs';
const p=JSON.parse(fs.readFileSync('plans/PushPull-01.07.2026.json'));const initial={version:1,exercises:{'PUSH A':[],'PULL A':[],'PUSH B':[],'PULL B':[]},sessions:[],entries:[],changes:{},nextType:'PUSH A',activeId:null};const data=stagePlan(initial,p);const m=data.trainingJournal.model;
test('fresh plan paired and bilateral quick fields accept focus without guessing load convention',()=>{
 for(const u of p.planVersion.units)for(const ex of views(m,p.planVersion.id,u.id,data)){editor.clear();const html=editor.editor(ex,'synthetic',null,null);assert.doesNotMatch(html,/readonly data-quick/);assert.equal(editor.state(ex.id,'synthetic').performance.loadConvention.basis,null)}
});
test('unknown convention historical asymmetric and explicitly combined results remain protected',()=>{
 const ex=views(m,p.planVersion.id,'PULL A',data).find(x=>x.name==='Wiosłowanie jednorącz siedząc');const perf=newPerformance(ex);perf.rows[0].segments[0].kg='15';perf.rows[1].segments[0].kg='16';editor.clear();assert.match(editor.editor(ex,'s',{performance:perf},null),/readonly data-quick/);
 const symmetric=newPerformance(ex);symmetric.loadConvention.basis='combined';editor.clear();assert.match(editor.editor(ex,'s',{performance:symmetric},null),/readonly data-quick/);
});
