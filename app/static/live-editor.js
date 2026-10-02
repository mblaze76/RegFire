/* Only page definitions travel over this event-and-editor-specific channel. */
(() => {
 let session;try{session=sessionStorage.getItem('regfire-preview-editor')||crypto.randomUUID();sessionStorage.setItem('regfire-preview-editor',session);}catch{session=crypto.randomUUID();}
 const channels=new Map(),audience=new Map(),epoch=Date.now(),saved=new Map();let seq=0,inflight=false,lastFetch=0;
 const channel=id=>{if(!channels.has(id)){const c=new BroadcastChannel('regfire-preview:'+session+':'+id);c.onmessage=e=>{if(e.data?.kind==='request'&&e.data.event_id===id&&e.data.session===session){audience.set(id,Date.now());tick();}};channels.set(id,c);}return channels.get(id);};
 function send(id,data){channel(id).postMessage({protocol:1,session,event_id:id,epoch,seq:++seq,...data});}
 function syncEmbedded(event){const frame=document.getElementById('demo-embedded-preview');if(!frame)return;const visible=event&&!document.getElementById('demographics-view').hidden&&!document.getElementById('demo-content').hidden;
  if(!visible){if(frame.dataset.event){frame.src='about:blank';delete frame.dataset.event;}return;}
  if(frame.dataset.event!==event.id){channel(event.id);frame.dataset.event=event.id;frame.src='/preview#event='+encodeURIComponent(event.id)+'&editor='+encodeURIComponent(session)+'&view=demographics&embedded=1';}}
 async function tick(force=false){if(inflight)return;const event=window.liveEvent?.();syncEmbedded(event);for(const id of channels.keys())if(id!==event?.id)send(id,{kind:'paused',message:'Organizer is viewing a different event. Return to this event to reconnect.'});if(!event||!channels.has(event.id)||Date.now()-(audience.get(event.id)||0)>10000)return;inflight=true;
  try{const reg=window.RegistrationBuilder?.snapshot(),demo=window.DemographicsBuilder?.snapshot();if(force||Date.now()-lastFetch>5000||!saved.has(event.id)){const [r,d]=await Promise.all([api('/api/events/'+event.id+'/registration-page'),api('/api/events/'+event.id+'/demographics')]);saved.set(event.id,{registration:r,demographics:d});lastFetch=Date.now();}if(window.liveEvent?.()?.id!==event.id)return;
   const base=saved.get(event.id),currentReg=reg?.event_id===event.id?reg:null,currentDemo=demo?.event_id===event.id?demo:null;
   send(event.id,{kind:'snapshot',model:{event:{id:event.id,name:event.name,timezone:event.timezone,start:event.start,end:event.end},registration:currentReg?.page||base.registration,demographics:currentDemo?.page||base.demographics,at:currentReg?.at||'',regtype:currentReg?.regtype||currentDemo?.regtype||null,error:currentReg?.error||null}});
  }catch(e){send(event.id,{kind:'paused',message:'Could not synchronize the organizer. Keep both windows open and retry.'});}finally{inflight=false;}}
 function open(click){const mode=click.currentTarget.closest('#demographics-view')?'demographics':'welcome';const event=window.liveEvent?.();if(!event)return;const status=document.getElementById('live-open-message');if(!window.BroadcastChannel){status.textContent='This browser does not support live preview channels. Use a current browser or the preview on this page.';return;}
  channel(event.id);const url='/preview#event='+encodeURIComponent(event.id)+'&editor='+encodeURIComponent(session)+'&view='+mode;const popup=window.open(url,'regfire-preview-'+event.id+'-'+mode,'popup,width=1050,height=850');status.replaceChildren(document.createTextNode(popup?(mode==='demographics'?'Demographics website preview opened. ':'Welcome website preview opened. ')+'Move its window to your second monitor, then use Full screen there. If it opened as a tab, drag that tab into its own window. ':'The browser blocked the preview window. Allow popups for this local site or '));{const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener';a.textContent=popup?' Open preview in a new tab':'open the live preview in a new tab';status.append(a);}tick(true);
 }
 document.querySelectorAll('.open-live-preview').forEach(b=>b.onclick=open);
 setInterval(()=>tick(),500);
 // A preview reload can reconnect even after the editor itself was reloaded.
 const route=new URLSearchParams(location.hash.slice(1));if(/^[a-f0-9-]{36}$/.test(route.get('event')||''))channel(route.get('event'));
 window.addEventListener('hashchange',()=>{const id=new URLSearchParams(location.hash.slice(1)).get('event');if(/^[a-f0-9-]{36}$/.test(id||''))channel(id);});
 window.addEventListener('pagehide',()=>{for(const id of channels.keys())send(id,{kind:'paused',message:'Organizer closed or reloading. Showing the last received draft; reopen the same organizer tab to reconnect.'});});
})();
