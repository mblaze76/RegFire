const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('optional address capability denial is not an expired attendee session; protected denial still is',async()=>{
 const events=[];const context={URL,URLSearchParams,Headers,CustomEvent:class{constructor(type){this.type=type}},location:{pathname:'/register',hash:'#event=flow',href:'https://example.test/register',origin:'https://example.test'},document:{body:{classList:{add(){}}},getElementById(){return null},addEventListener(){},dispatchEvent(e){events.push(e.type)}},window:{fetch:async url=>({ok:true,status:String(url).includes('/api/public/status')?200:String(url).includes('/me')?200:401,json:async()=>String(url).includes('/api/public/status')?{enabled:true}:{user:null}})}};
 vm.runInNewContext(fs.readFileSync('static/auth-client.js','utf8'),context);
 await context.window.fetch('/api/address-config');assert.deepEqual(events,[]);
 await context.window.fetch('/api/events/flow/checkout/save');assert.deepEqual(events,['regfire-session-expired']);
});
