const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../../static/app.js'),'utf8');
const init=source.slice(source.indexOf('async function init()'),source.indexOf('function setLocation()'));
async function scenario(hash,items,fail=false){
 let finish;const gate=new Promise(r=>finish=r),calls=[];
 const ctx={URLSearchParams,Intl,events:[],initializing:true,activeView:'event',location:{hash},document:{createElement:()=>({}),modelContext:null},field:()=>({append(){}}),formatFields(){},renderList(){},updateNav(){},loaded(){calls.push('loaded')},loading(t){calls.push(t)},api:async p=>{if(p==='/api/timezones')return [];if(fail)throw Error('offline');return items},openDraft:async e=>{calls.push(e.id);await gate}};
 vm.createContext(ctx);vm.runInContext(init,ctx);const pending=ctx.init();await new Promise(r=>setImmediate(r));return {ctx,calls,finish,pending};
}
(async()=>{
 let s=await scenario('',[{id:'saved'}]);assert.deepEqual(s.calls,['saved']);assert.equal(s.ctx.initializing,true);s.finish();await s.pending;assert.equal(s.ctx.initializing,false);
 s=await scenario('#event=missing',[{id:'saved'}]);await s.pending;assert.match(s.calls[0],/requested event was not found/);assert.equal(s.ctx.initializing,true);
 s=await scenario('',[],true);await s.pending;assert.match(s.calls[0],/Could not load saved events/);assert.ok(!s.calls.includes('loaded'));
 s=await scenario('',[]);await s.pending;assert.deepEqual(s.calls,['loaded']);assert.equal(s.ctx.initializing,false);
 console.log('4 initial-load regression scenarios passed');
})().catch(e=>{console.error(e);process.exitCode=1});
