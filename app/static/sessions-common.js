/* One attendee renderer for embedded previews, live previews and saved agendas. */
(()=>{
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const money=(n,c)=>n===0?'Free':new Intl.NumberFormat(undefined,{style:'currency',currency:c}).format(n/(c==='JPY'?1:100));
 const overlaps=(a,b)=>a.start<b.end&&b.start<a.end;
 function mount(root,{persistent=false}={}){
  let page=null,chosen=new Set(),key='',storageOK=true,query='',day='',track='',cost='',only=false;
  root.classList.add('session-browser');
  const top=el('div',undefined,'session-browser-top'),intro=el('div'),eyebrow=el('p','BUILD YOUR EXPERIENCE','eyebrow'),title=el('h2','Explore sessions'),meta=el('p','', 'session-meta'),count=el('strong','','session-count');intro.append(eyebrow,title,meta);top.append(intro,count);
  const filters=el('div',undefined,'session-filters');
  function control(name,input){const l=el('label',name);l.append(input);filters.append(l);return input;}
  const search=control('Search sessions',el('input'));search.type='search';search.placeholder='Title, speaker or keyword';search.oninput=()=>{query=search.value;draw();};
  const dates=control('Date',el('select')),tracks=control('Track',el('select')),prices=control('Price',el('select'));prices.append(new Option('Any price',''),new Option('Free','free'),new Option('Paid','paid'));
  dates.onchange=()=>{day=dates.value;draw();};tracks.onchange=()=>{track=tracks.value;draw();};prices.onchange=()=>{cost=prices.value;draw();};
  const actions=el('div',undefined,'session-actions'),all=el('button','All sessions','secondary'),mine=el('button','My schedule','secondary'),reset=el('button','Clear filters','secondary');
  for(const b of [all,mine,reset])b.type='button';all.onclick=()=>{only=false;draw();};mine.onclick=()=>{only=true;draw();};reset.onclick=()=>{query=day=track=cost='';search.value=dates.value=tracks.value=prices.value='';only=false;draw();};actions.append(all,mine,reset);
  const note=el('p','','session-note'),warning=el('div',undefined,'session-conflicts'),status=el('p','','session-meta'),cards=el('div',undefined,'session-cards');warning.setAttribute('role','status');status.setAttribute('aria-live','polite');
  root.replaceChildren(top,filters,actions,note,warning,status,cards);
  function persist(){if(!persistent)return;try{localStorage.setItem(key,JSON.stringify([...chosen]));}catch{storageOK=false;}}
  function draw(){
   if(!page)return;
   const rows=page.sessions||[],picked=rows.filter(s=>chosen.has(s.id));
   count.textContent=picked.length+' selected';mine.textContent='My schedule ('+picked.length+')';all.setAttribute('aria-pressed',String(!only));mine.setAttribute('aria-pressed',String(only));
   note.textContent=persistent?(storageOK?'Your schedule is saved in this browser. It does not reserve seats or purchase paid sessions.':'Browser storage is unavailable. This schedule will last only while this page stays open.'):'Interactive preview · selections here are temporary and do not change an attendee’s schedule.';
   warning.replaceChildren();const conflicts=[];for(let i=0;i<picked.length;i++)for(let j=i+1;j<picked.length;j++)if(overlaps(picked[i],picked[j]))conflicts.push(picked[i].title+' overlaps '+picked[j].title);
   warning.hidden=!conflicts.length;if(conflicts.length){warning.append(el('strong','Schedule conflicts'));const list=el('ul');for(const c of conflicts)list.append(el('li',c));warning.append(list,el('p','You can keep both, or remove a session from My schedule.'));}
   const q=query.trim().toLocaleLowerCase(),visible=rows.filter(s=>(!only||chosen.has(s.id))&&(!day||s.start.slice(0,10)===day)&&(!track||s.track===track)&&(!cost||(cost==='free'?s.price_minor===0:s.price_minor>0))&&(!q||[s.title,s.speaker,s.description,s.track,s.location].join(' ').toLocaleLowerCase().includes(q)));
   status.textContent=visible.length+' of '+rows.length+' sessions'+(only?' in My schedule':'');cards.replaceChildren();
   if(!visible.length){cards.append(el('div',!rows.length?'Sessions are coming soon.':only&&!picked.length?'Your schedule is empty. Explore sessions and add your favorites.':'No sessions match these filters. Try another keyword or clear filters.','session-empty'));return;}
   for(const s of visible){const card=el('article',undefined,'session-card');if(chosen.has(s.id))card.classList.add('is-selected');const strip=el('div',undefined,'session-card-meta');strip.append(el('span',s.track||'General','session-pill'),el('strong',money(s.price_minor,page.currency)));const date=s.start.slice(0,10);let formatted=date;try{formatted=new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(date+'T12:00:00Z'));}catch{}
    card.append(strip,el('p',formatted+' · '+s.start.slice(11,16)+'–'+s.end.slice(11,16),'session-time'),el('h3',s.title||'Untitled session'));
    if(s.speaker)card.append(el('p',s.speaker,'session-speaker'));if(s.location)card.append(el('p',s.location,'session-meta'));if(s.description){const d=el('details');d.append(el('summary','Session details'),el('p',s.description));card.append(d);}
    if(chosen.has(s.id)&&picked.some(other=>other.id!==s.id&&overlaps(s,other)))card.append(el('p','Overlaps another selected session','session-overlap'));
    const b=el('button',chosen.has(s.id)?'Remove from schedule':'+ Add to schedule',chosen.has(s.id)?'secondary':'primary');b.type='button';b.setAttribute('aria-label',(chosen.has(s.id)?'Remove ':'Add ')+s.title+(chosen.has(s.id)?' from schedule':' to schedule'));b.setAttribute('aria-pressed',String(chosen.has(s.id)));b.onclick=()=>{chosen.has(s.id)?chosen.delete(s.id):chosen.add(s.id);persist();draw();const replacement=[...cards.querySelectorAll('button')].find(button=>button.getAttribute('aria-label')?.includes(s.title));(replacement||mine).focus({preventScroll:true});};card.append(b);cards.append(card);
   }
  }
  function update(next){page=next;const nextKey='regfire-agenda:'+page.event_id;if(key!==nextKey){key=nextKey;chosen=new Set();if(persistent)try{const saved=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(saved))chosen=new Set(saved.filter(x=>typeof x==='string'));}catch{storageOK=false;}}
   const ids=new Set(page.sessions.map(s=>s.id));chosen=new Set([...chosen].filter(id=>ids.has(id)));meta.textContent=page.event_name+' · All times '+page.timezone.replaceAll('_',' ');
   const fill=(select,values,caption,value)=>{select.replaceChildren(new Option(caption,''),...[...new Set(values.filter(Boolean))].sort().map(v=>new Option(v,v)));select.value=value;return select.value;};day=fill(dates,page.sessions.map(s=>s.start.slice(0,10)),'All dates',day);track=fill(tracks,page.sessions.map(s=>s.track),'All tracks',track);draw();
  }
  return {update};
 }
 window.SessionBrowser={mount,money,overlaps};
})();
