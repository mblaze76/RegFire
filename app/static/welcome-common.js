(()=>{
const fonts={default:['App default','Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'],arial:['Arial','Arial,Helvetica,sans-serif'],georgia:['Georgia','Georgia,serif'],trebuchet:['Trebuchet MS','"Trebuchet MS",sans-serif'],verdana:['Verdana','Verdana,sans-serif']};
Object.assign(fonts,window.WelcomeGoogleFonts||{});
const loadedFonts=new Map();
function loadFont(id){
 if(!id?.startsWith('google-')||!fonts[id])return Promise.resolve(true);
 if(loadedFonts.has(id))return loadedFonts.get(id);
 const promise=new Promise(resolve=>{const link=document.createElement('link');link.rel='stylesheet';let settled=false;const finish=value=>{if(!settled){settled=true;clearTimeout(timeout);resolve(value);}};const timeout=setTimeout(()=>finish(false),12000);link.onload=()=>document.fonts.load('400 18px '+JSON.stringify(fonts[id][0]),fonts[id][0]).then(faces=>finish(faces.length>0),()=>finish(false));link.onerror=()=>finish(false);link.href='https://fonts.googleapis.com/css2?family='+encodeURIComponent(fonts[id][0])+'&display=swap';document.head.append(link);});loadedFonts.set(id,promise);return promise;
}
function heading(node,page){if(!node)return;node.textContent=page.title||'Welcome to online registration';node.style.fontFamily=(fonts[page.title_font]||fonts.default)[1];node.style.color=page.title_color||(page.background_asset_id&&Number(page.background_fade??80)<50?'#ffffff':'#24242a');loadFont(page.title_font).then(()=>node.dispatchEvent(new Event('welcome-heading-change')));node.dispatchEvent(new Event('welcome-heading-change'));}
function body(node,page){loadFont(page.about_font);node.textContent=page.about;node.style.color=/^#[0-9a-f]{6}$/i.test(page.about_color||'')?page.about_color:'#24242a';node.style.fontFamily=(fonts[page.about_font]||fonts.default)[1];}
function buttons(node,page,flows,newTab=false){node.replaceChildren();for(const button of page.buttons||[]){const flow=flows.find(f=>f.id===button.flow_id);if(!flow)continue;const link=document.createElement('a');link.className='primary';link.textContent=button.label;link.href='/preview#event='+encodeURIComponent(flow.id)+'&view=welcome';if(newTab){link.target='_blank';link.rel='noopener';}node.append(link);}}
function backgroundImage(page,eventID){const mode=page.background_mode||(page.background_asset_id?'image':'color');if(mode==='image')return /^[a-f0-9-]{36}$/.test(page.background_asset_id||'')?'url("/api/events/'+eventID+'/assets/'+page.background_asset_id+'")':'none';const color=/^#[0-9a-f]{6}$/i.test(page.background_color||'')?page.background_color:'#ffffff';return 'linear-gradient('+color+','+color+')';}
function background(node,page,eventID){const id=page.background_asset_id,valid=page.background_mode==='color'||/^[a-f0-9-]{36}$/.test(id||'');node.classList.toggle('welcome-has-artwork',valid);node.classList.toggle('welcome-vivid-artwork',valid&&Number(page.background_fade??80)<50);node.style.setProperty('--welcome-background',valid?backgroundImage(page,eventID):'none');node.style.setProperty('--welcome-opacity',String(1-Math.max(0,Math.min(100,Number(page.background_fade??80)))/100));const hex=/^#[0-9a-f]{6}$/i.test(page.about_color||'')?page.about_color:'#24242a';const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));node.style.setProperty('--welcome-text-scrim',rgb[0]*.299+rgb[1]*.587+rgb[2]*.114>150?'#171719c9':'#ffffffc9');}
function searchResults(input,select){
 const results=document.createElement('div');results.className='font-search-results font-face-results';results.hidden=true;results.id=input.id+'-results';results.setAttribute('aria-label','Matching fonts');input.setAttribute('aria-controls',results.id);input.parentElement.after(results);
 select.hidden=true;select.tabIndex=-1;const current=document.createElement('span');current.className='font-current';select.after(current);
 let timer,limit=12,revision=0;
 const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;const button=entry.target;observer.unobserve(button);const id=button.dataset.fontId,label=fonts[id][0],caption=button.querySelector('small');if(!id.startsWith('google-')){caption.textContent=id==='default'?'App default':'System font';return;}caption.textContent='Loading preview…';loadFont(id).then(ok=>{if(button.isConnected)caption.textContent=ok?'Google Fonts':'Preview unavailable · fallback shown';});}},{root:results,threshold:0.01});
 function update(reset=true){
  clearTimeout(timer);revision++;observer.disconnect();if(reset)limit=12;
  current.textContent=(fonts[select.value]||fonts.default)[0];current.style.fontFamily=(fonts[select.value]||fonts.default)[1];loadFont(select.value);
  const query=input.value.trim().toLowerCase();results.replaceChildren();results.hidden=!query;if(!query)return;
  const matches=Object.entries(fonts).filter(([, [label]])=>label.toLowerCase().includes(query)).sort((a,b)=>Number(!a[1][0].toLowerCase().startsWith(query))-Number(!b[1][0].toLowerCase().startsWith(query))||Number(a[0].startsWith('google-'))-Number(b[0].startsWith('google-'))||a[1][0].localeCompare(b[1][0]));
  if(!matches.length){const note=document.createElement('p');note.setAttribute('role','status');note.textContent='No matching fonts. Try another name.';results.append(note);return;}
  const version=revision;
  for(const [id,[label,family]] of matches.slice(0,limit)){const button=document.createElement('button');button.type='button';button.dataset.fontId=id;button.setAttribute('aria-label',label);button.setAttribute('aria-pressed',String(select.value===id));const name=document.createElement('span'),caption=document.createElement('small');name.textContent=label;name.style.fontFamily=family;caption.textContent=id.startsWith('google-')?'Preview pending':'System font';button.append(name,caption);button.onclick=()=>{if(![...select.options].some(o=>o.value===id))select.add(new Option(label,id));select.value=id;select.dispatchEvent(new Event('change',{bubbles:true}));update();input.focus();};results.append(button);}
  if(matches.length>limit){const more=document.createElement('button');more.type='button';more.className='font-more';more.textContent='Show more ('+(matches.length-limit)+' remaining)';more.onclick=()=>{const previous=limit;limit+=12;update(false);results.querySelectorAll('[data-font-id]')[previous]?.focus();};results.append(more);}
  timer=setTimeout(()=>{if(version===revision)results.querySelectorAll('[data-font-id]').forEach(button=>observer.observe(button));},200);
 }
 input.addEventListener('input',()=>update());
 input.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){const first=results.querySelector('button');if(first){e.preventDefault();first.focus();}}if(e.key==='Escape'){input.value='';input.dispatchEvent(new Event('input',{bubbles:true}));}});
 results.addEventListener('keydown',e=>{const buttons=[...results.querySelectorAll('button')],i=buttons.indexOf(document.activeElement);if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();buttons[Math.max(0,Math.min(buttons.length-1,i+(e.key==='ArrowDown'?1:-1)))]?.focus();}if(e.key==='Escape'){results.hidden=true;input.focus();}});
 select.addEventListener('change',()=>update());
 // Organizer renders restore the value after replacing its options.
 new MutationObserver(()=>{current.textContent=(fonts[select.value]||fonts.default)[0];current.style.fontFamily=(fonts[select.value]||fonts.default)[1];}).observe(select,{childList:true});
 return update;
}
window.WelcomeDisplay={backgroundImage,fonts,loadFont,heading,body,buttons,background,searchResults};
})();
