(()=>{
const fonts={default:['App default','Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'],arial:['Arial','Arial,Helvetica,sans-serif'],georgia:['Georgia','Georgia,serif'],trebuchet:['Trebuchet MS','"Trebuchet MS",sans-serif'],verdana:['Verdana','Verdana,sans-serif']};
Object.assign(fonts,window.WelcomeGoogleFonts||{});
const loadedFonts=new Set();
function loadFont(id){if(!id?.startsWith("google-")||!fonts[id]||loadedFonts.has(id))return;const link=document.createElement("link");link.rel="stylesheet";link.href="https://fonts.googleapis.com/css2?family="+encodeURIComponent(fonts[id][0])+"&display=swap";document.head.append(link);loadedFonts.add(id);}
function body(node,page){loadFont(page.about_font);node.textContent=page.about;node.style.color=/^#[0-9a-f]{6}$/i.test(page.about_color||'')?page.about_color:'#24242a';node.style.fontFamily=(fonts[page.about_font]||fonts.default)[1];}
function buttons(node,page,flows,newTab=false){node.replaceChildren();for(const button of page.buttons||[]){const flow=flows.find(f=>f.id===button.flow_id);if(!flow)continue;const link=document.createElement('a');link.className='primary';link.textContent=button.label;link.href='/preview#event='+encodeURIComponent(flow.id)+'&view=welcome';if(newTab){link.target='_blank';link.rel='noopener';}node.append(link);}}
function background(node,page,eventID){const id=page.background_asset_id,valid=/^[a-f0-9-]{36}$/.test(id||'');node.classList.toggle('welcome-has-artwork',valid);node.classList.toggle('welcome-vivid-artwork',valid&&Number(page.background_fade??80)<50);node.style.setProperty('--welcome-background',valid?'url("/api/events/'+eventID+'/assets/'+id+'")':'none');node.style.setProperty('--welcome-opacity',String(1-Math.max(0,Math.min(100,Number(page.background_fade??80)))/100));const hex=/^#[0-9a-f]{6}$/i.test(page.about_color||'')?page.about_color:'#24242a';const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));node.style.setProperty('--welcome-text-scrim',rgb[0]*.299+rgb[1]*.587+rgb[2]*.114>150?'#171719c9':'#ffffffc9');}
function searchResults(input,select){
 const results=document.createElement('div');results.className='font-search-results';results.hidden=true;results.setAttribute('aria-label','Matching fonts');input.parentElement.after(results);
 function update(){
  const query=input.value.trim().toLowerCase();results.replaceChildren();results.hidden=!query;if(!query)return;
  const matches=Object.entries(fonts).filter(([, [label]])=>label.toLowerCase().includes(query));
  if(!matches.length){const note=document.createElement('p');note.setAttribute('role','status');note.textContent='No matching fonts. Try another name.';results.append(note);return;}
  for(const [id,[label]] of matches){const button=document.createElement('button');button.type='button';button.textContent=label;button.setAttribute('aria-pressed',String(select.value===id));button.onclick=()=>{if(![...select.options].some(o=>o.value===id))select.add(new Option(label,id));select.value=id;select.dispatchEvent(new Event('change',{bubbles:true}));update();input.focus();};results.append(button);}
 }
 input.addEventListener('input',update);
 input.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){const first=results.querySelector('button');if(first){e.preventDefault();first.focus();}}if(e.key==='Escape'){input.value='';input.dispatchEvent(new Event('input',{bubbles:true}));}});
 results.addEventListener('keydown',e=>{const buttons=[...results.querySelectorAll('button')],i=buttons.indexOf(document.activeElement);if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();buttons[Math.max(0,Math.min(buttons.length-1,i+(e.key==='ArrowDown'?1:-1)))]?.focus();}if(e.key==='Escape'){results.hidden=true;input.focus();}});
 select.addEventListener('change',update);
 return update;
}
window.WelcomeDisplay={fonts,loadFont,body,buttons,background,searchResults};
})();
