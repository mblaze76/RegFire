import assert from 'node:assert/strict';
import access from '../netlify/edge-functions/investor-access.mjs';
import {createHash} from 'node:crypto';
const secret=createHash('sha256').update('synthetic-test-password').digest('hex');globalThis.Netlify={env:{get:()=>secret}};
let calls=0;const context={next:async()=>{calls++;return new Response('private-content',{headers:{'Content-Type':'application/pdf'}});}};
for(const path of ['/investors/test.pdf','/investors/test.mp4','/investors/test.vtt','/investors/investors.js']){const r=await access(new Request('https://example.com'+path),context);assert.equal(r.status,401);}
assert.equal(calls,0);
let r=await access(new Request('https://example.com/investors/'),context);assert.equal(r.status,200);assert(!(await r.text()).includes(secret));
const login=p=>new Request('https://example.com/investors/unlock',{method:'POST',headers:{origin:'https://example.com','content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({password:p})});
assert.equal((await access(login('wrong'),context)).status,401);
r=await access(login('synthetic-test-password'),context);assert.equal(r.status,303);const cookie=r.headers.get('set-cookie').split(';')[0];assert(r.headers.get('set-cookie').includes('HttpOnly'));
r=await access(new Request('https://example.com/investors/test.pdf',{headers:{cookie,range:'bytes=0-10'}}),context);assert.equal(await r.text(),'private-content');assert.equal(r.headers.get('Cache-Control'),'private, no-store');
assert.equal((await access(new Request('https://other.example/investors/test.pdf',{headers:{cookie}}),context)).status,401);
assert.equal((await access(new Request('https://example.com/investors/test.pdf',{headers:{cookie:cookie+'tampered'}}),context)).status,401);
assert.equal((await access(new Request('https://example.com/.netlify/images?url=/investors/poster.jpg'),context)).status,403);
assert.equal(await access(new Request('https://example.com/'),context),undefined);
globalThis.Netlify.env.get=()=>'';assert.equal((await access(new Request('https://example.com/investors/test.pdf'),context)).status,503);
console.log('Passed: asset denial, password login, secure cookie, authenticated access, tampered and cross-host cookies, image proxy denial, public homepage, fail closed.');
