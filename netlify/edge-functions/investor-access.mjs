const encoder = new TextEncoder();
const cookieName = '__Host-regfire-investor';
const privateHeaders = {'Cache-Control':'private, no-store','Netlify-CDN-Cache-Control':'no-store','X-Robots-Tag':'noindex, noarchive','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'};
function equal(a,b){if(a.length!==b.length)return false;let n=0;for(let i=0;i<a.length;i++)n|=a.charCodeAt(i)^b.charCodeAt(i);return n===0;}
async function digest(value){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(value))),b=>b.toString(16).padStart(2,'0')).join('');}
async function signature(value,secret){const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,encoder.encode(value))),b=>b.toString(16).padStart(2,'0')).join('');}
function reply(body,status=200,extra={}){return new Response(body,{status,headers:{...privateHeaders,...extra}});}
function gate(error=false){return reply(`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Investor access | RegFire</title><style>body{margin:0;background:#101011;color:#f5f3ef;font:18px/1.6 system-ui}main{max-width:480px;margin:10vh auto;padding:24px}h1{line-height:1.2}input,button{box-sizing:border-box;width:100%;min-height:48px;font:inherit;border-radius:6px;padding:12px}input{background:#242426;color:white;border:1px solid #aaa}button{margin-top:20px;background:#c41e18;color:white;border:0;cursor:pointer}a{color:#fff}label{display:block;margin:22px 0 8px}.error{color:#ffb6aa}:focus-visible{outline:3px solid #f4b648;outline-offset:4px}</style><main><p>REGFIRE / INVESTORS</p><h1>Please enter your password.</h1><p>Enter the password shared with you to view our investor materials.</p><form action="/investors/unlock" method="post"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" maxlength="256" required>${error?'<p class="error" role="alert">That password was not recognized. Please try again.</p>':''}<button>View investor materials</button></form><p><a href="/">Back to homepage</a></p></main></html>`,error?401:200,{'Content-Type':'text/html; charset=utf-8','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"});}
export default async function access(request,context){
 const url=new URL(request.url);let path;try{path=decodeURIComponent(url.pathname).toLowerCase();}catch{return reply('Invalid path',400);}
 if(path.startsWith('/.netlify/images')&&/investor/i.test(url.search))return reply('Not available',403);
 const protectedPath=path==='/investors'||path.startsWith('/investors/')||/regfire_(investor|business_plan)/i.test(path);
 if(!protectedPath)return;
 const secret=Netlify.env.get('REGFIRE_INVESTOR_PASSWORD_HASH')||'';
 if(!/^[a-f0-9]{64}$/.test(secret))return reply('Investor access is temporarily unavailable.',503);
 if(url.protocol!=='https:')return Response.redirect('https://'+url.host+url.pathname+url.search,308);
 if(path==='/investors/unlock'&&request.method==='POST'){
  if(request.headers.get('origin')!==url.origin)return reply('Request denied',403);
  if(!request.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded'))return reply('Unsupported form',415);
  const reader=request.body?.getReader();let chunks=[],length=0;if(reader){while(true){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>2048){await reader.cancel();return reply('Request too large',413);}chunks.push(value);}}
  const bytes=new Uint8Array(length);let pos=0;for(const chunk of chunks){bytes.set(chunk,pos);pos+=chunk.length;}
  const password=new URLSearchParams(new TextDecoder().decode(bytes)).get('password')||'';
  if(!equal(await digest(password),secret))return gate(true);
  const expiry=String(Math.floor(Date.now()/1000)+3600);const sig=await signature(url.host+':'+expiry,secret);
  return reply(null,303,{'Location':'/investors/','Set-Cookie':`${cookieName}=${expiry}.${sig}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=3600`});
 }
 if(!['GET','HEAD'].includes(request.method))return reply('Method not allowed',405,{'Allow':'GET, HEAD'});
 const cookie=(request.headers.get('cookie')||'').split(';').map(v=>v.trim()).find(v=>v.startsWith(cookieName+'='))?.slice(cookieName.length+1)||'';
 const [expiry,sig]=cookie.split('.');const now=Math.floor(Date.now()/1000);
 const valid=/^\d+$/.test(expiry||'')&&Number(expiry)>now&&Number(expiry)<=now+3600&&equal(sig||'',await signature(url.host+':'+expiry,secret));
 if(!valid){if(path==='/investors'||path==='/investors/'||path==='/investors/index.html')return gate();return reply('Sign in to view investor materials.',401);}
 const response=await context.next();const headers=new Headers(response.headers);for(const [k,v]of Object.entries(privateHeaders))headers.set(k,v);headers.set('Vary','Cookie');return new Response(response.body,{status:response.status,headers});
}
export const config={path:'/*'};
