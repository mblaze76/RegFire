/* A text-only sample badge. Attendee values stay in the preview and are never broadcast. */
(()=>{
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 function mount(container){
  const root=el('section',undefined,'sample-badge-preview'),caption=el('h3','Your sample badge'),badge=el('div',undefined,'sample-badge'),event=el('div','','sample-badge-event'),body=el('div',undefined,'sample-badge-body'),name=el('strong','','sample-badge-name'),company=el('p','','sample-badge-company'),city=el('p','','sample-badge-city'),category=el('div','','sample-badge-category');
  root.setAttribute('aria-label','Live sample badge');body.append(name,company,city);badge.append(event,body,category);root.append(caption,badge,el('p','Preview only — updates as you type.','field-note'));container.append(root);
  return {root,update({eventName,fields,values,categoryName,appearance={}}){
   const value=re=>{const f=fields.find(f=>re.test(f.id.replaceAll('-',' ')+' '+f.label));return f&&typeof values[f.id]==='string'?values[f.id].trim():'';};
   const first=value(/first.?name|given.?name/i),last=value(/last.?name|surname|family.?name/i),address=fields.find(f=>f.type==='address'),a=address&&values[address.id]||{};
   event.textContent=eventName||'Event name';name.textContent=[first||'First name',last||'Last name'].join(' ');company.textContent=value(/company|organization|organisation|employer/i)||'Company name';city.textContent=[a.city||value(/\bcity\b/i)||'City',a.region||value(/\bstate\b|province|region/i)||'State'].join(', ');category.textContent=categoryName||'Registration category';
   const color=/^#[0-9a-f]{6}$/i.test(appearance.button_color||'')?appearance.button_color:'#a84415';badge.style.setProperty('--badge-accent',color);
  }};
 }
 function read(container,fields,prefix){const out={};for(const f of fields){const find=id=>container.querySelector('#'+CSS.escape(id));if(f.type==='address'){out[f.id]={};for(const k of ['line1','line2','city','region','postal','country'])out[f.id][k]=find(prefix+f.id+'-'+k)?.value||'';}else if(f.type==='radio')out[f.id]=container.querySelector('input[name="'+CSS.escape(prefix+f.id)+'"]:checked')?.value||'';else{const input=find(prefix+f.id);out[f.id]=f.type==='checkbox'?!!input?.checked:input?.value||'';}}return out;}
 window.BadgePreview={mount,read};
})();
