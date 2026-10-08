const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../../static/welcome.js'),'utf8');
const upload=source.slice(source.indexOf('async function uploadImage('),source.indexOf('\nasync function load('));
async function run(names,existing=[],fail='',switchEvent=false){
 const rendered=[],calls=[],messages=[];const ctx={event:{id:'event-a'},page:{sponsor_asset_ids:[...existing],sponsor_urls:existing.map(()=> '')},serial:1,busy:false,controls(){},say(t){messages.push(t)},changed(){},render(){rendered.push([...ctx.page.sponsor_asset_ids])},fetch:async(url,{body})=>{calls.push(body.name);if(switchEvent){ctx.serial++;ctx.event={id:'event-b'};}return {ok:body.name!==fail,json:async()=>({id:body.name,error:'Invalid image'})}}};
 vm.createContext(ctx);vm.runInContext(upload,ctx);await ctx.uploadImage({files:names.map(name=>({name,type:'image/png'})),value:'files'},'sponsor');return {ctx,rendered,calls,messages};
}
(async()=>{
 let r=await run(['wide','square','tall']);assert.deepEqual([...r.ctx.page.sponsor_asset_ids],['wide','square','tall']);assert.equal(r.rendered.at(-1).length,3);assert.equal(r.ctx.busy,false);
 r=await run(['b','c'],['a']);assert.equal(r.ctx.page.sponsor_asset_ids.length,3);
 r=await run(['b','c','d','e'],['a']);assert.equal(r.calls.length,0);assert.equal(r.ctx.page.sponsor_asset_ids.length,1);
 r=await run(['a','bad','c'],[],'bad');assert.deepEqual([...r.ctx.page.sponsor_asset_ids],['a','c']);assert.match(r.messages.at(-1),/bad: Invalid image/);
 r=await run(['a','b'],[],'',true);assert.equal(r.ctx.page.sponsor_asset_ids.length,0);assert.equal(r.calls.length,1);
 console.log('5 sponsor batch upload regression scenarios passed');
})().catch(e=>{console.error(e);process.exitCode=1});
