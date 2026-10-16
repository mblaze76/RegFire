const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/attendee-journey.js'),'utf8');
async function journey(page,counts={},suffix="",saved=null){
 const window={addEventListener(){}};
 const model={demographics:{questions:Array(counts.demographics||0).fill({})}};
 vm.runInNewContext(source,{window,URLSearchParams,location:{pathname:'/'+page,hash:'#event=11111111-1111-1111-1111-111111111111'+suffix},sessionStorage:{getItem(){return saved;}},document:{readyState:'loading',addEventListener(){},querySelectorAll(){return [];},querySelector(){return null;}},fetch:async url=>({ok:true,json:async()=>url.endsWith('/sessions')?{sessions:Array(counts.sessions||0).fill({})}:url.endsWith('/extra-options')?{items:Array(counts.extras||0).fill({})}:model})});
 await window.RegFireJourney.ready;return window.RegFireJourney;
}
test('empty sessions preview links to surrounding enabled steps',async()=>{
 const j=await journey('sessions');assert.equal(j.adjacent(-1),'registration');assert.equal(j.adjacent(1),'review');assert.ok(!j.url(j.adjacent(-1)).includes('undefined'));
});
test('excluded step uses enabled optional neighbors',async()=>{
 const j=await journey('sessions',{demographics:1,extras:1});assert.equal(j.adjacent(-1),'demographics');assert.equal(j.adjacent(1),'extras');
});
test('included steps retain normal navigation and boundaries',async()=>{
 const j=await journey('sessions',{sessions:1,extras:1});assert.equal(j.adjacent(-1),'registration');assert.equal(j.adjacent(1),'extras');
 const end=await journey('confirmation');assert.equal(end.adjacent(1),undefined);assert.equal(end.adjacent(-1),'payment');
});

test('normal registration starts at Welcome without clearing existing answers',async()=>{
 const j=await journey('register',{},'&mode=registration',JSON.stringify({contacts:{email:'sample@example.test'}}));assert.equal(j.adjacent(-1),undefined);assert.equal(j.adjacent(1),'registration');assert.equal(j.read().contacts.email,'sample@example.test');
});
test('explicit attendee and demographic links keep their destination',async()=>{
 const j=await journey('register',{demographics:1},'&view=registration');assert.equal(j.adjacent(-1),'welcome');assert.equal(j.adjacent(1),'demographics');
 const d=await journey('register',{demographics:1},'&view=demographics');assert.equal(d.adjacent(-1),'registration');assert.equal(d.adjacent(1),'review');
 const p=await journey('preview');assert.equal(p.adjacent(-1),'welcome');
});
