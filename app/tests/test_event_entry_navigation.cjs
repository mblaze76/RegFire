const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/live-preview.js','utf8');
function entry(hash){let redirect;try{vm.runInNewContext(source,{URLSearchParams,location:{hash,pathname:'/register',replace:x=>{redirect=x}},document:{getElementById:()=>{throw Error('flow page')}}});}catch(e){if(e.message!=='flow page')throw e;}return redirect;}
test('all ordinary flow entries use shared event Welcome',()=>{for(const flow of ['attendee','exhibitor','press'])for(const tail of ['', '&mode=registration','&view=welcome'])assert.equal(entry('#event='+flow+tail),'/welcome#event='+flow+'&mode=registration');});
test('explicit steps and recovery do not redirect',()=>{for(const tail of ['&view=registration','&view=demographics','&resume=private-token','&view=registration&resume=private-token'])assert.equal(entry('#event=flow'+tail),undefined);});
