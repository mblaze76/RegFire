/* Only page definitions travel over this event-and-editor-specific channel. */
(() => {
 let session;try{session=sessionStorage.getItem('regfire-preview-editor')||crypto.randomUUID();sessionStorage.setItem('regfire-preview-editor',session);}catch{session=crypto.randomUUID();}
 const channels=new Map(),audience=new Map(),epoch=Date.now(),saved=new Map();let seq=0,inflight=false,lastFetch=0;
 const channel=id=>{if(!channels.has(id)){const c=new BroadcastChannel('regfire-preview:'+session+':'+id);c.onmessage=e=>{if(e.data?.kind==='request'&&e.data.event_id===id&&e.data.session===session){audience.set(id,Date.now());tick();}};channels.set(id,c);}return channels.get(id);};
 function send(id,data){channel(id).postMessage({protocol:1,session,event_id:id,epoch,seq:++seq,...data});}
 function syncEmbedded(event){const frame=document.getElementById('demo-embedded-preview');if(!frame)return;const visible=event&&!document.getElementById('demographics-view').hidden&&!document.getElementById('demo-content').hidden;
  if(!visible){if(frame.dataset.event){frame.src='about:blank';delete frame.dataset.event;}return;}
  if(frame.dataset.event!==event.id){channel(event.id);frame.dataset.event=event.id;frame.src='/preview#event='+encodeURIComponent(event.id)+'&editor='+encodeURIComponent(session)+'&view=demographics&embedded=1';}}
 async function tick(force=false){if(inflight)return;const event=window.liveEvent?.();syncEmbedded(event);if(event)channel(event.id);for(const id of channels.keys())if(id!==event?.id)send(id,{kind:'paused',message:'Organizer is viewing a different event. Return to this event to reconnect.'});if(!event||!channels.has(event.id)||Date.now()-(audience.get(event.id)||0)>10000)return;inflight=true;
  try{const reg=window.RegistrationBuilder?.snapshot(),demo=window.DemographicsBuilder?.snapshot();if(force||Date.now()-lastFetch>5000||!saved.has(event.id)){const [r,d]=await Promise.all([api('/api/events/'+event.id+'/registration-page'),api('/api/events/'+event.id+'/demographics')]);saved.set(event.id,{registration:r,demographics:d});lastFetch=Date.now();}if(window.liveEvent?.()?.id!==event.id)return;
   const base=saved.get(event.id),currentReg=reg?.event_id===event.id?reg:null,currentDemo=demo?.event_id===event.id?demo:null;
   send(event.id,{kind:'snapshot',model:{event:{id:event.id,name:event.name,timezone:event.timezone,start:event.start,end:event.end},registration:currentReg?.page||base.registration,demographics:currentDemo?.page||base.demographics,at:currentReg?.at||'',regtype:currentReg?.regtype||currentDemo?.regtype||null,error:currentReg?.error||null}});
  }catch(e){send(event.id,{kind:'paused',message:'Could not synchronize the organizer. Keep both windows open and retry.'});}finally{inflight=false;}}
 function open(click){const mode=click.currentTarget.closest('#demographics-view')?'demographics':'registration';const event=window.liveEvent?.();if(!event)return;const status=document.getElementById('live-open-message');if(!window.BroadcastChannel){status.textContent='This browser does not support live preview channels. Use a current browser or the preview on this page.';return;}
  channel(event.id);const url='/preview#event='+encodeURIComponent(event.id)+'&editor='+encodeURIComponent(session)+'&view='+mode;const popup=window.open(url,'regfire-preview-'+event.id+'-'+mode,'popup,width=1050,height=850');status.replaceChildren(document.createTextNode(popup?(mode==='demographics'?'Demographics website preview opened. ':'Registration website preview opened. ')+'Move its window to your second monitor, then use Full screen there. If it opened as a tab, drag that tab into its own window. ':'The browser blocked the preview window. Allow popups for this local site or '));{const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener';a.textContent=popup?' Open preview in a new tab':'open the live preview in a new tab';status.append(a);}tick(true);
 }
 document.querySelectorAll('.open-live-preview').forEach(b=>b.onclick=open);
 setInterval(()=>tick(),500);
 // A preview reload can reconnect even after the editor itself was reloaded.
 const route=new URLSearchParams(location.hash.slice(1));if(/^[a-f0-9-]{36}$/.test(route.get('event')||''))channel(route.get('event'));
 window.addEventListener('hashchange',()=>{const id=new URLSearchParams(location.hash.slice(1)).get('event');if(/^[a-f0-9-]{36}$/.test(id||''))channel(id);});
 window.addEventListener('pagehide',()=>{for(const id of channels.keys())send(id,{kind:'paused',message:'Organizer closed or reloading. Showing the last received draft; reopen the same organizer tab to reconnect.'});});
})();

/* One preview header and full-view interaction for every setup preview.
   Expand the existing pane in place: moving an iframe would reload its draft. */
(()=>{'use strict';
 const specs=[
  ['#welcome-preview','.preview-panel','Welcome preview','#welcome-open-site'],
  ['#preview-form','.preview-column','Attendee preview','#builder-view .open-live-preview'],
  ['#demo-embedded-preview','.preview-column','Demographics preview','#demographics-view .open-live-preview'],
  ['#sessions-preview','.sessions-preview-panel','Sessions preview','#sessions-open'],
  ['#extras-preview','.extras-preview-panel','Additional options preview','#extras-open'],
  ['#confirmation-preview','.confirmation-preview-column','Confirmation preview','#confirmation-open'],
  ['.payment-preview-panel','.payment-preview-panel','Payment preview',null]
 ];
 let active=null;
 const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
 function close(){if(!active)return;const a=active;active=null;a.pane.classList.remove('setup-preview-expanded');a.button.textContent='Expand preview';a.button.setAttribute('aria-expanded','false');for(const [n,value]of a.inert)n.inert=value;document.body.style.overflow=a.overflow;for(const [k,v]of Object.entries(a.attrs))v===null?a.pane.removeAttribute(k):a.pane.setAttribute(k,v);for(const cleanup of a.frames)cleanup();a.button.focus();}
 function expand(pane,button){if(active?.pane===pane){close();return;}close();const attrs={role:pane.getAttribute('role'),'aria-modal':pane.getAttribute('aria-modal'),'aria-label':pane.getAttribute('aria-label')};active={pane,button,attrs,inert:[],frames:[],overflow:document.body.style.overflow};pane.classList.add('setup-preview-expanded');pane.setAttribute('role','dialog');pane.setAttribute('aria-modal','true');pane.setAttribute('aria-label',pane.dataset.previewTitle+' full view');button.textContent='Return to setup';button.setAttribute('aria-expanded','true');document.body.style.overflow='hidden';let n=pane;while(n.parentElement&&n.parentElement!==document.documentElement){for(const sibling of n.parentElement.children)if(sibling!==n){active.inert.push([sibling,sibling.inert]);sibling.inert=true;}n=n.parentElement;}for(const frame of pane.querySelectorAll('iframe')){let doc;const fn=e=>{if(e.key==='Escape'){e.preventDefault();close();}};const bind=()=>{try{doc?.removeEventListener('keydown',fn,true);doc=frame.contentDocument;doc?.addEventListener('keydown',fn,true);}catch{}};frame.addEventListener('load',bind);bind();active.frames.push(()=>{frame.removeEventListener('load',bind);try{doc?.removeEventListener('keydown',fn,true);}catch{}});}button.focus();}
 function mount(pane,title,link){if(pane.dataset.previewPane)return;pane.dataset.previewPane='1';pane.dataset.previewTitle=title;pane.classList.add('setup-preview-pane');const bar=el('div'),heading=el('h3',title),actions=el('div'),button=el('button','Expand preview');bar.className='setup-preview-header';actions.className='setup-preview-actions';button.type='button';button.className='secondary setup-preview-expand';button.setAttribute('aria-expanded','false');button.onclick=()=>expand(pane,button);
  const previous=pane.querySelector(':scope > .preview-heading,:scope > .sessions-preview-heading,:scope > .confirmation-preview-bar');
  if(link){link.textContent='Open in new window ↗';link.classList.add('setup-preview-window');actions.append(link);}
  if(previous)previous.remove();else pane.querySelector(':scope > h3')?.remove();actions.append(button);bar.append(heading,actions);pane.prepend(bar);
 }
 function refresh(){for(const [target,ancestor,title,link]of specs){const node=document.querySelector(target);if(node)mount(node.closest(ancestor),title,link?document.querySelector(link):null);}const review=document.getElementById('review-setup-view'),link=document.getElementById('review-setup-preview');if(review&&link&&!review.querySelector('.review-preview-panel')){const editor=review.querySelector('section'),layout=el('div'),pane=el('aside'),frame=el('iframe');layout.className='setup-preview-layout';pane.className='review-preview-panel';frame.title='Verify your details preview';frame.className='setup-review-frame';editor.before(layout);layout.append(editor,pane);pane.append(frame);mount(pane,'Verify your details preview',link);const update=()=>{const src=link.getAttribute('href');if(src&&frame.getAttribute('src')!==src)frame.src=src;};new MutationObserver(update).observe(link,{attributes:true,attributeFilter:['href']});update();}}
 document.addEventListener('keydown',e=>{if(!active)return;if(e.key==='Escape'){e.preventDefault();close();return;}if(e.key==='Tab'){const nodes=[...active.pane.querySelectorAll('button,a[href],input,select,textarea,iframe,[tabindex]')].filter(n=>!n.disabled&&n.tabIndex>=0&&n.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}});
 window.addEventListener('hashchange',close);new MutationObserver(()=>{if(active&&!active.pane.isConnected)close();refresh();}).observe(document.querySelector('main')||document.body,{childList:true,subtree:true});window.RegFirePreviewPane={refresh,close};refresh();
})();
