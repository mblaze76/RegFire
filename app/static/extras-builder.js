(()=>{
 const root=document.getElementById('extras-view');if(!root)return;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 let event=null,page=null,dirty=false,busy=false,epoch=0,preview,channel;const editor=crypto.randomUUID();let seq=0;
 root.innerHTML='<div class="builder-heading"><p class="eyebrow">EVENT EXPERIENCE</p><h2>Extra options</h2><p>Offer merchandise, services, and experiences for this registration flow.</p></div><p id="extras-status" role="status"></p><button id="extras-reload" class="secondary" type="button">Reload saved options</button><div class="extras-layout"><div class="extras-editor"><section><h3>Options settings</h3><label>Currency<select id="extras-currency"><option>USD</option><option>EUR</option><option>GBP</option><option>CAD</option><option>AUD</option><option>JPY</option></select></label><p class="field-note">Prices and inventory are configured here. Checkout and inventory reservations are not connected yet.</p></section><section><h3>Your extra options</h3><div id="extras-items"></div><button id="extras-add" class="secondary" type="button">Add an extra option</button></section><div class="savebar"><button id="extras-save" class="primary" type="button">Save and finish</button></div></div><div class="extras-preview-panel"><h3>Attendee preview</h3><a id="extras-open" target="_blank" rel="noopener">Open live preview ↗</a><div id="extras-preview"></div><footer id="extras-footer" class="registration-footer" hidden></footer></div></div>';
 const $=id=>document.getElementById(id),message=(s,error=false)=>{$('extras-status').textContent=s;$('extras-status').className=error?'session-error':'';};
 const request=async(body)=>{const r=await fetch('/api/events/'+event.id+'/extra-options',body?{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:undefined),data=await r.json();if(!r.ok)throw Error(data.error||'Could not load extra options.');return data;};
 function update(){if(!page)return;preview.update(page);channel?.postMessage({kind:'extras',editor,seq:++seq,page});}
 function change(){dirty=true;message('Unsaved extra options');update();}
 function field(parent,title,value,onchange,{type='text',min,max,step,placeholder}={}){const label=el('label',title),input=el('input');input.type=type;input.value=value??'';for(const [k,v]of Object.entries({min,max,step,placeholder}))if(v!==undefined)input[k]=v;input.oninput=()=>{onchange(input.value);change();};label.append(input);parent.append(label);return input;}
 function check(parent,title,value,onchange){const label=el('label',undefined,'check-label'),input=el('input');input.type='checkbox';input.checked=value;input.onchange=()=>{onchange(input.checked);change();};label.append(input,document.createTextNode(title));parent.append(label);return input;}
 function draw(){
  const list=$('extras-items');list.replaceChildren();$('extras-currency').value=page.currency;
  if(!page.items.length)list.append(el('p','Add your first item, service, or experience.','field-note'));
  for(const item of page.items){
   const card=el('article',undefined,'extras-item-editor'),title=el('h4',item.name||'New extra option');card.append(title);const grid=el('div',undefined,'extras-form-grid');card.append(grid);
   field(grid,'Item name',item.name,v=>{item.name=v;title.textContent=v||'New extra option';});
   const kindLabel=el('label','Item type'),kind=el('select');kind.append(new Option('Physical item','physical'),new Option('Service / experience','service'));kind.value=item.kind;kind.onchange=()=>{item.kind=kind.value;if(item.kind!=='physical')item.taxable=false;change();draw();};kindLabel.append(kind);grid.append(kindLabel);
   field(grid,'Description',item.description,v=>item.description=v);
   field(grid,'Price',item.price_minor/(page.currency==='JPY'?1:100),v=>item.price_minor=Math.round(Number(v)*(page.currency==='JPY'?1:100)),{type:'number',min:0,step:page.currency==='JPY'?1:.01});
   if(!item.variants.length)field(grid,'Inventory',item.inventory,v=>item.inventory=v===''?null:Number(v),{type:'number',min:0,max:1000000,step:1,placeholder:'Unlimited'});
   check(card,'Allow multiple quantities',item.allow_multiple,v=>item.allow_multiple=v);
   if(item.kind==='physical')check(card,'Apply tax at checkout',item.taxable,v=>item.taxable=v);
   const variants=el('div',undefined,'extras-variants');variants.append(el('h5','Variants / sizes'),el('p','Leave inventory blank for unlimited; zero means sold out.','field-note'));
   for(const v of item.variants){const row=el('div',undefined,'extras-variant-row');field(row,'Variant / size',v.label,x=>v.label=x);field(row,'Variant inventory',v.inventory,x=>v.inventory=x===''?null:Number(x),{type:'number',min:0,max:1000000,step:1,placeholder:'Unlimited'});const remove=el('button','Remove variant','secondary');remove.type='button';remove.onclick=()=>{item.variants=item.variants.filter(x=>x.id!==v.id);change();draw();};row.append(remove);variants.append(row);}
   const add=el('button','Add variant / size','secondary');add.type='button';add.onclick=()=>{item.inventory=null;item.variants.push({id:crypto.randomUUID(),label:'',inventory:null});change();draw();};variants.append(add);card.append(variants);
   const remove=el('button','Remove option','secondary');remove.type='button';remove.onclick=async()=>{if(!await confirmAction('Remove '+(item.name||'this option')+' from the draft?'))return;page.items=page.items.filter(i=>i.id!==item.id);change();draw();};card.append(remove);list.append(card);
  }
  update();
 }
 function lock(value){busy=value;root.querySelectorAll('input,select,button').forEach(e=>e.disabled=value);}
 async function load(next){const ticket=++epoch;event=next;page=null;dirty=false;lock(true);message('Loading extra options…');channel?.close();try{const data=await request();if(ticket!==epoch)return;page=data;preview=window.ExtraOptionsBrowser.mount($('extras-preview'));channel=new BroadcastChannel('regfire-extras:'+editor+':'+event.id);channel.onmessage=e=>{if(e.data?.kind==='request')update();};$('extras-open').href='/extras#event='+event.id+'&editor='+editor;window.RegistrationFooter.connect($('extras-footer'),event.id);draw();message('Saved options · '+page.items.length+' items');}catch(e){if(ticket===epoch)message(e.message,true);}finally{if(ticket===epoch)lock(false);}}
 async function save(){if(busy||!page)return false;lock(true);try{page=await request(page);dirty=false;draw();message('Extra options saved.');return true;}catch(e){message(e.message,true);return false;}finally{lock(false);}}
 $('extras-add').onclick=()=>{if(!page)return;page.items.push({id:crypto.randomUUID(),name:'',description:'',kind:'physical',price_minor:0,inventory:null,variants:[],allow_multiple:false,taxable:false});change();draw();$('extras-items').lastElementChild?.querySelector('input')?.focus();};
 $('extras-currency').onchange=()=>{page.currency=$('extras-currency').value;change();draw();};$('extras-save').onclick=()=>window.saveSetupNext();$('extras-reload').onclick=async()=>{if(dirty&&!await confirmAction('Discard unsaved extra options and reload?'))return;load(event);};
 window.ExtrasBuilder={load,save,get dirty(){return dirty;},get busy(){return busy;},clear(){epoch++;channel?.close();channel=null;event=page=null;dirty=busy=false;}};
})();
