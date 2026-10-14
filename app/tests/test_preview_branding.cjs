const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/attendee-branding.js'),'utf8');
test('late saved theme cannot overwrite a newer published theme',async()=>{
 let resolve;const pending=new Promise(r=>resolve=r),style={setProperty(){}};
 const classes={add(){},toggle(){},contains(){return false;}};
 const root={dataset:{},isConnected:true,closest(){return true;},style:{},classList:classes,parentElement:{style,classList:classes}};
 const window={WelcomeDisplay:{applyFont(){},loadFont(){},fonts:{default:['Default','default'],new:['New','new'],old:['Old','old']},backgroundImage(){return '';}}};
 vm.runInNewContext(source,{window,fetch:()=>pending,setTimeout(){}});
 const p=window.RegFirePreviewBranding.connect(root,'flow');
 window.RegFirePreviewBranding.publish('flow',{intro_font:'new'});
 resolve({ok:true,json:async()=>({registration:{appearance:{intro_font:'old'}}})});await p;
 assert.equal(root.style.fontFamily,'new');
});
