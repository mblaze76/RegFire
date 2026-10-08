const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../../static/linkedin-import.js'),'utf8');
async function fixture(available=true){
 const listeners={},popup={closed:false},button={},status={},inputs=[
  {value:'Keep my name',dataset:{profileField:'first-name'}},
  {value:'',dataset:{profileField:'last-name'}},
  {value:'',dataset:{profileField:'email'}}];
 inputs.forEach(input=>input.dispatchEvent=()=>{});
 const context={window:{open:()=>popup,addEventListener:(name,fn)=>listeners[name]=fn},location:{origin:'http://localhost'},crypto:{randomUUID:()=> 'test-request'},fetch:async()=>({ok:true,json:async()=>({available})}),setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){},Event:class{}};
 vm.createContext(context);vm.runInContext(source,context);
 context.window.LinkedInImport.attach({button,status,target:{querySelectorAll:()=>inputs},getFlow:()=> 'flow'});
 await new Promise(resolve=>setImmediate(resolve));return {listeners,popup,button,status,inputs};
}
(async()=>{
 let f=await fixture(false);assert.equal(f.button.disabled,true);assert.match(f.status.textContent,/not connected/);
 f=await fixture();assert.equal(f.button.disabled,false);f.button.onclick();
 const data={type:'regfire-linkedin-profile',request:'test-request',flow:'flow',profile:{given_name:'Replace?',family_name:'Example',email:'attendee@example.test'}};
 f.listeners.message({origin:'https://untrusted.example',source:f.popup,data});assert.equal(f.inputs[1].value,'');
 f.listeners.message({origin:'http://localhost',source:{},data});assert.equal(f.inputs[1].value,'');
 f.listeners.message({origin:'http://localhost',source:f.popup,data:{...data,request:'wrong'}});assert.equal(f.inputs[1].value,'');
 f.listeners.message({origin:'http://localhost',source:f.popup,data});assert.deepEqual(f.inputs.map(i=>i.value),['Keep my name','Example','attendee@example.test']);assert.match(f.status.textContent,/Filled 2 empty fields/);
 f.listeners.message({origin:'http://localhost',source:f.popup,data:{...data,profile:{family_name:'Replay'}}});assert.equal(f.inputs[1].value,'Example');
 console.log('LinkedIn unavailable, message binding, replay, and non-overwrite checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
