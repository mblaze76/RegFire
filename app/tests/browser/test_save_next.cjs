const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../../static/app.js'),'utf8');
const fn=source.slice(source.indexOf('window.saveSetupNext=async()=>'));
async function scenario(view,fail='',busy=false){
 const calls=[],elements={};let resolve;
 const ctx={activeView:view,document:{getElementById:id=>elements[id]??={},querySelector:()=>null},showView:(...args)=>calls.push(['next',...args]),window:{RegistrationFlows:{current:()=>({id:'flow'})}}};
 for(const [name,key] of [['RegistrationBuilder','registration'],['MembershipBuilder','membership'],['DemographicsBuilder','demographics'],['SessionsBuilder','sessions']])ctx.window[name]={busy:busy&&key==='registration',save:async()=>{calls.push(key);return fail!==key;}};
 vm.createContext(ctx);vm.runInContext(fn,ctx);await ctx.window.saveSetupNext();return {calls,ctx};
}
(async()=>{
 for(const [view,next,expected] of [['setup','registration',['registration','membership']],['registration','demographics',['registration']],['demographics','sessions',['demographics']],['sessions','flows',['sessions']]]){
  let result=await scenario(view);assert.deepEqual(result.calls.slice(0,-1),expected);assert.equal(result.calls.at(-1)[1],next);assert.equal(result.ctx.window.setupAdvancing,false);
  for(const failure of expected){result=await scenario(view,failure);assert.ok(!result.calls.some(c=>Array.isArray(c)),'Must stay after '+failure+' failure');assert.equal(result.ctx.window.setupAdvancing,false);}
 }
 assert.deepEqual((await scenario('setup','',true)).calls,[]);
 console.log('Save-and-next success, failure, final-step and busy checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
