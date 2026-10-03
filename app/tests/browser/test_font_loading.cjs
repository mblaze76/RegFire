const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
async function run(fail){
 const links=[];const context={window:{WelcomeGoogleFonts:{'google-test':['Test Family','"Test Family",serif']}},setTimeout,clearTimeout,Promise,Map,Set,document:{createElement:()=>({}),head:{append(link){links.push(link);queueMicrotask(()=>fail?link.onerror():link.onload());}},fonts:{load:async()=>[{family:'Test Family'}]}}};
 vm.runInNewContext(fs.readFileSync('outputs/regfire/static/welcome-common.js','utf8'),context);
 const load=context.window.WelcomeDisplay.loadFont;
 assert.equal(await load('arial'),true);assert.equal(links.length,0);
 assert.equal(await load('google-test'),!fail);assert.equal(links.length,1);
 assert.equal(await load('google-test'),!fail);assert.equal(links.length,1);
 assert.match(links[0].href,/family=Test%20Family/);
 await load('google-unknown');assert.equal(links.length,1);
}
(async()=>{await run(false);await run(true);console.log('Font loading: system fonts, on-demand caching, missing IDs and remote failure passed.');})();
