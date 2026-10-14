const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const read=f=>fs.readFileSync(path.join(__dirname,'../static/',f),'utf8');
const flow='11111111-1111-4111-8111-111111111111',editor='22222222-2222-4222-8222-222222222222';
const flush=()=>new Promise(r=>setImmediate(r));
function preview(file,next='extras'){
 const nodes={},updates=[];let resolve,reject,channel;const pending=new Promise((a,b)=>{resolve=a;reject=b});
 const node=()=>({textContent:'',hidden:false,removeAttribute(){},append(){}});
 const document={getElementById:id=>nodes[id]??=node(),querySelector:()=>node(),createElement:()=>node(),addEventListener(){}};
 const journey={ready:Promise.resolve(),url:s=>'/'+s+'#event='+flow+'&editor='+editor,adjacent:n=>n===1?next:'registration',labels:{extras:'Additional options',review:'Verify your details',registration:'Attendee details'}};
 vm.runInNewContext(read(file),{URLSearchParams,location:{hash:`#event=${flow}&editor=${editor}`,href:'/sessions'},document,window:{RegistrationFooter:{connect(){}},SessionBrowser:{mount:()=>({update:p=>updates.push(p)})},ExtraOptionsBrowser:{mount:()=>({update:p=>updates.push(p)})},RegFireJourney:journey},fetch:()=>pending,BroadcastChannel:class {constructor(){channel=this;}postMessage(){}},setInterval(){},Date});
 return {nodes,updates,resolve:p=>resolve({ok:true,json:async()=>p}),reject,live:()=>channel.onmessage({data:{kind:'extras',editor,seq:1,page:{items:[],event_name:'Live'}}})};
}
for(const next of ['extras','review'])test('bottom Sessions action follows enabled next step '+next,async()=>{const x=preview('sessions-site.js',next);await flush();assert.equal(x.nodes['sessions-continue'].href,'/'+next+'#event='+flow+'&editor='+editor);assert.equal(x.nodes['sessions-continue'].href,x.nodes['sessions-extras'].href);assert.match(x.nodes['sessions-bottom-back'].href,/editor=/);});
test('Additional options loads saved data without its editor broadcaster',async()=>{const x=preview('extras-site.js');x.resolve({items:[],event_name:'Saved',flow_name:'Attendee'});await flush();assert.equal(x.updates[0].event_name,'Saved');});
test('late saved Additional options cannot replace live unsaved data',async()=>{const x=preview('extras-site.js');x.live();x.resolve({items:[],event_name:'Old'});await flush();assert.equal(x.updates.length,1);assert.equal(x.updates[0].event_name,'Live');});
test('late saved Additional options error cannot obscure live data',async()=>{const x=preview('extras-site.js');x.live();x.reject(Error('Offline'));await flush();assert.equal(x.nodes['extras-error'].textContent,'');});
