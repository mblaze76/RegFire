// Run with node --test tests/test_sessions_preview.cjs; no browser or provider calls.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/sessions-site.js'),'utf8');
const event='11111111-1111-1111-1111-111111111111';
const editor='22222222-2222-2222-2222-222222222222';
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function setup(){
 const nodes={},updates=[];let channel,resolve,reject;
 const pending=new Promise((a,b)=>{resolve=a;reject=b;});
 const document={getElementById:id=>nodes[id]??=( {textContent:'',hidden:false}),addEventListener(){}};
 vm.runInNewContext(source,{URLSearchParams,location:{hash:`#event=${event}&editor=${editor}`},document,
  window:{RegistrationFooter:{connect(){}},SessionBrowser:{mount:()=>({update:p=>updates.push(p)})},RegFireJourney:{url:step=>'/'+step+'#event='+event+'&editor='+editor,ready:new Promise(()=>{})}},
  fetch:()=>pending,BroadcastChannel:class {constructor(){channel=this;}postMessage(){}},setInterval(){},Date});
 return {nodes,updates,resolve:p=>resolve({ok:true,json:async()=>p}),reject,
  live:(seq=1)=>channel.onmessage({data:{kind:'sessions',editor,seq,page:{sessions:[],event_name:'Live'}}})};
}
test('saved agenda appears while organizer is unavailable',async()=>{
 const x=setup();x.resolve({sessions:[],event_name:'Saved',flow_name:'Attendee'});await flush();
 assert.equal(x.updates[0].event_name,'Saved');assert.match(x.nodes['sessions-connection'].textContent,/Saved agenda/);
});
test('late saved response cannot replace live draft',async()=>{
 const x=setup();x.live();x.resolve({sessions:[],event_name:'Old'});await flush();
 assert.equal(x.updates.length,1);assert.equal(x.updates[0].event_name,'Live');
});
test('late saved fetch failure does not obscure healthy live preview',async()=>{
 const x=setup();x.live();x.reject(Error('Offline'));await flush();
 assert.equal(x.nodes['sessions-site-error'].textContent,'');assert.equal(x.nodes['sessions-retry'].hidden,true);
});
test('live recovery clears prior error and ignores stale sequence',async()=>{
 const x=setup();x.reject(Error('Offline'));await flush();assert.equal(x.nodes['sessions-site-error'].textContent,'Offline');
 x.live(2);x.live(1);assert.equal(x.updates.length,1);assert.equal(x.nodes['sessions-site-error'].textContent,'');assert.equal(x.nodes['sessions-retry'].hidden,true);
});

test('loading agenda links preserve preview identity before configuration resolves',()=>{const x=setup();assert.match(x.nodes['sessions-extras'].href,new RegExp('editor='+editor));assert.match(x.nodes['sessions-back'].href,new RegExp('editor='+editor));});
