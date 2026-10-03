(async()=>{
 const $=id=>document.getElementById(id),route=new URLSearchParams(location.hash.slice(1)),id=route.get('event'),editor=route.get('editor');
 $('welcome-fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{$('welcome-error').textContent='Use your browser full-screen control to expand this preview.';}};
 document.addEventListener('fullscreenchange',()=>{$('welcome-fullscreen').textContent=document.fullscreenElement?'Exit full screen':'Full screen';});
 window.RegistrationFooter.connect(document.getElementById('welcome-shared-footer'),id);
 $('return-login').href='/registrant-login?event='+encodeURIComponent(id||'');let liveModel=null;
 function render(model){const {page,flows}=model;window.WelcomeDisplay.heading(document.querySelector('[data-welcome-heading]'),page);window.WelcomeDisplay.background(document.body,page,id);$('event-name').textContent=model.event_name||'';
 function image(asset,url,alt){const img=document.createElement('img');img.src='/api/events/'+id+'/assets/'+asset;img.alt=alt;if(url){try{const parsed=new URL(url);if(['http:','https:'].includes(parsed.protocol)){const a=document.createElement('a');a.href=parsed.href;a.target='_blank';a.rel='noopener noreferrer';a.append(img);return a;}}catch{}}return img;}
 $('welcome-preview-logo').replaceChildren(...(page.logo_asset_id?[image(page.logo_asset_id,page.logo_url,'Show logo')]:[]));
 $('welcome-preview-sponsors').replaceChildren(...page.sponsor_asset_ids.map((asset,i)=>image(asset,page.sponsor_urls?.[i],'Sponsor '+(i+1)+' logo')));
 window.WelcomeDisplay.body($('welcome-preview-about'),page);
 window.WelcomeDisplay.buttons($('welcome-preview-flows'),page,flows);
 }
 try{
 if(!/^[a-f0-9-]{36}$/.test(id||''))throw Error('Open this welcome page from an event.');
 if(/^[a-f0-9-]{36}$/.test(editor||'')&&window.BroadcastChannel){const channel=new BroadcastChannel('regfire-welcome:'+editor);channel.onmessage=e=>{const model=e.data;if(model?.event_id!==id||!model.page||typeof model.page.about!=='string'||!Array.isArray(model.page.sponsor_asset_ids)||!Array.isArray(model.flows))return;liveModel=model;render(model);$('welcome-error').textContent='Live preview · includes unsaved welcome edits.';};channel.postMessage({request:id});window.addEventListener('pagehide',()=>channel.close());}
 const get=async path=>{const r=await fetch(path),d=await r.json();if(!r.ok)throw Error(d.error||'Could not load event.');return d;};
 const [page,flows,events]=await Promise.all([get('/api/events/'+id+'/welcome-page'),get('/api/events/'+id+'/flows'),get('/api/events')]);
 render(liveModel||{page,flows,event_name:events.find(e=>e.id===id)?.name||''});
 }catch(e){$('welcome-error').textContent=e.message;}
})();
