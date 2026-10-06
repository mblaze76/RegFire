/* Live Spark chat via the authenticated backend. History lasts only on this page. */
(()=>{
 const launcher=document.createElement('button');launcher.type='button';launcher.className='spark-launcher';launcher.setAttribute('aria-label','Ask Spark');launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-controls','spark-panel');launcher.innerHTML='<img src="/spark-3d.png" alt=""><span>Spark</span>';
 const panel=document.createElement('section');panel.id='spark-panel';panel.className='spark-panel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-labelledby','spark-title');panel.innerHTML=`<h2 id="spark-title" class="spark-accessible-title">Talk with Spark</h2><button type="button" class="spark-motion-toggle" aria-pressed="false" aria-label="Pause Spark dance" title="Pause dance">Ⅱ</button><button class="spark-close" type="button" aria-label="Minimize Spark">×</button><div class="spark-messages" role="log" aria-label="Spark conversation" aria-live="polite"><p class="spark-bubble">Hi, I’m Spark! ✨<br>What can I help you with?</p></div><div class="spark-suggestions"><button type="button">Set up sessions</button><button type="button">Brand my event</button><button type="button">What’s next?</button></div><div class="spark-voice"><button type="button" id="spark-voice-enabled" class="spark-icon" aria-label="Enable voice preview" title="Voice preview" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4Z"/><path d="M16 8q5 4 0 8m3-11q8 7 0 14" fill="none"/></svg></button><label><span class="spark-accessible-title">Voice style</span><select id="spark-voice-choice" aria-label="Voice style" title="Choose voice style"><option>Warm & friendly</option><option>Calm & clear</option><option>Bright & upbeat</option></select></label></div><form class="spark-compose"><label for="spark-input">Ask about your setup</label><div class="spark-compose-row"><input id="spark-input" placeholder="How do I…" maxlength="500" autocomplete="off"><button type="submit" aria-label="Try message" title="Try message">↑</button></div></form>`;
 document.body.append(launcher,panel);const input=panel.querySelector('input[type=text]')||panel.querySelector('#spark-input'),log=panel.querySelector('.spark-messages');
 // Seven genuinely different rendered viewing angles, not a transform of one picture.
 // Keep the static transparent character if canvas or the sprite cannot load.
 const canvas=document.createElement('canvas');canvas.className='spark-turning';canvas.width=240;canvas.height=280;canvas.setAttribute('aria-hidden','true');launcher.prepend(canvas);
 const ctx=canvas.getContext('2d'),sprite=new Image(),motion=matchMedia('(prefers-reduced-motion: reduce)');
 const frames=[3,3,3,3,3,3,3,3,2,1,0,0,0,1,2,3,4,5,6,6,6,5,4,3,3,3,3,3,3,3,3,3];
 let ready=false,raf=0,epoch=0,last=-1;
 function drawFrame(frame){if(!ctx||!ready||last===frame)return;last=frame;ctx.clearRect(0,0,240,280);const cell=sprite.naturalWidth/7;ctx.drawImage(sprite,cell*frame,158,cell,404,12,0,216,280);canvas.dataset.frame=String(frame);}
 function tick(now){raf=0;if(document.hidden||motion.matches||launcher.dataset.paused==='true'){drawFrame(3);return;}if(!epoch)epoch=now;drawFrame(frames[Math.floor((now-epoch)/150)%frames.length]);raf=requestAnimationFrame(tick);}
 function syncMotion(){cancelAnimationFrame(raf);raf=0;epoch=0;drawFrame(3);if(ready&&!document.hidden&&!motion.matches&&launcher.dataset.paused!=='true')raf=requestAnimationFrame(tick);}
 sprite.onload=()=>{ready=!!ctx;if(!ready)return;launcher.classList.add('has-turning');syncMotion();};
 sprite.onerror=()=>{launcher.classList.remove('has-turning');cancelAnimationFrame(raf);};
 if(ctx)sprite.src='/spark-turns.png';motion.addEventListener('change',syncMotion);document.addEventListener('visibilitychange',syncMotion);
 function close(){panel.hidden=true;launcher.classList.remove('is-speaking');launcher.setAttribute('aria-expanded','false');launcher.focus();}
 panel.querySelector('.spark-motion-toggle').onclick=e=>{const paused=launcher.dataset.paused!=='true';launcher.dataset.paused=String(paused);e.currentTarget.setAttribute('aria-pressed',String(paused));e.currentTarget.textContent=paused?'▶':'Ⅱ';e.currentTarget.setAttribute('aria-label',paused?'Resume Spark dance':'Pause Spark dance');e.currentTarget.title=paused?'Resume dance':'Pause dance';syncMotion();};
 launcher.onclick=()=>{if(!panel.hidden){close();return;}panel.hidden=false;launcher.classList.add('is-speaking');launcher.setAttribute('aria-expanded','true');input.focus();};panel.querySelector('.spark-close').onclick=close;panel.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();}});
 function bubble(text,user=false){const p=document.createElement('p');p.className='spark-bubble'+(user?' from-user':'');p.textContent=text;log.append(p);log.scrollTop=log.scrollHeight;return p;}
 const history=[],suggestions=[...panel.querySelectorAll('.spark-suggestions button')],send=panel.querySelector('button[type=submit]');let busy=false;
 send.setAttribute('aria-label','Send message');send.title='Send message';
 const notice=document.createElement('p');notice.className='spark-prototype';notice.textContent='AI replies can be mistaken. Messages go to your configured Ollama model; cloud models send them to Ollama. Chat clears on reload.';panel.append(notice);
 function setBusy(value){busy=value;send.disabled=value;input.disabled=value;for(const button of suggestions)button.disabled=value;log.setAttribute('aria-busy',String(value));}
 async function ask(text,retryNote=null){
  if(busy||!text)return;
  if(retryNote)retryNote.remove();else{bubble(text,true);input.value='';}
  setBusy(true);const pending=bubble('Spark is thinking…'),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),65000);
  try{
   const section=document.querySelector('.event-nav [aria-current="page"]')?.textContent.trim()||'';
   const messages=[...history.slice(-12),{role:'user',content:text}];
   while(messages.length>1&&new TextEncoder().encode(JSON.stringify({messages,section})).length>20000)messages.splice(0,2);
   const response=await fetch('/api/spark/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages,section}),signal:controller.signal});
   const data=await response.json();if(!response.ok)throw new Error(data.error||'Spark could not answer. Please retry.');
   if(typeof data.reply!=='string'||!data.reply.trim())throw new Error('Spark returned no answer. Please retry.');
   pending.textContent=data.reply;history.push({role:'user',content:text},{role:'assistant',content:data.reply});if(history.length>12)history.splice(0,history.length-12);
  }catch(error){
   pending.textContent=error.name==='AbortError'?'Spark took too long to answer. Please retry.':error.message==='Failed to fetch'?'Could not connect to RegFire. Check the server and retry.':error.message;
   const retry=document.createElement('button');retry.type='button';retry.className='secondary';retry.textContent='Retry message';retry.onclick=()=>ask(text,pending);pending.append(document.createElement('br'),retry);
  }finally{clearTimeout(timer);setBusy(false);log.scrollTop=log.scrollHeight;if(!panel.hidden)input.focus();}
 }
 for(const button of suggestions)button.onclick=()=>ask(button.textContent);
 panel.querySelector('form').onsubmit=e=>{e.preventDefault();ask(input.value.trim());};
 panel.querySelector('#spark-voice-enabled').onclick=e=>{const button=e.currentTarget,enabled=button.getAttribute('aria-pressed')!=='true';button.setAttribute('aria-pressed',String(enabled));button.setAttribute('aria-label',enabled?'Disable voice preview':'Enable voice preview');button.title=enabled?'Voice style preview selected; audio is not connected':'Voice preview; audio is not connected';};
})();
