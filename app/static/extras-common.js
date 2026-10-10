(()=>{
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const money=(n,c)=>new Intl.NumberFormat(undefined,{style:'currency',currency:c}).format(n/(c==='JPY'?1:100));
 function mount(root,{saved=false}={}){
  let page=null,choices=new Map(),seq=0;
  function draw(){
   root.replaceChildren();root.classList.add('extras-browser');root.append(el('p','MAKE IT YOURS','eyebrow'),el('h2','Extra options'),el('p','Add something extra to your event experience.'));
   const cards=el('div',undefined,'extras-cards'),summary=el('div',undefined,'extras-summary');summary.setAttribute('role','status');
   if(!page.items.length)cards.append(el('p','No extra options are available yet.','session-empty'));
   for(const item of page.items){
    const card=el('article',undefined,'extras-card');card.append(el('small',item.kind==='physical'?'Physical item':'Service / experience'),el('h3',item.name),el('p',item.description),el('strong',money(item.price_minor,page.currency)));
    const choice=choices.get(item.id)||{quantity:0,variant_id:null};let variant;
    if(item.variants.length){const label=el('label','Choose a variant / size');variant=el('select');variant.append(new Option('Choose an option',''),...item.variants.map(v=>new Option(v.label+(v.inventory===0?' — Sold out':''),v.id)));variant.value=choice.variant_id||'';label.append(variant);card.append(label);}
    const stock=()=>item.variants.length?item.variants.find(v=>v.id===(variant?.value||choice.variant_id))?.inventory:item.inventory;
    const availability=el('p','','field-note'),label=el('label','Quantity'),qty=el('input');qty.type='number';qty.min=0;qty.step=1;qty.value=choice.quantity;label.append(qty);card.append(availability,label);
    const update=(calculate=true)=>{const n=stock();qty.max=String(Math.min(item.allow_multiple?99:1,n??99));qty.disabled=n===0||!!(variant&&!variant.value);availability.textContent=n===0?'Sold out':variant&&!variant.value?'Choose an option to see availability.':n==null?'Available':n+' available';if(qty.disabled||Number(qty.value)>Number(qty.max))qty.value='0';choice.quantity=Number(qty.value);choice.variant_id=variant?.value||null;choices.set(item.id,choice);if(calculate)total(summary);};
    qty.oninput=update;if(variant)variant.onchange=update;update(false);cards.append(card);
   }
   root.append(cards,summary,el('p','Preview selections do not reserve inventory or complete a purchase.','session-note'));total(summary);
  }
  async function total(target){
   const ticket=++seq,selections=[...choices].filter(([,c])=>c.quantity>0).map(([id,c])=>({item_id:id,...c}));
   if([...choices.values()].some(c=>!Number.isInteger(c.quantity)||c.quantity<0)){target.textContent='Choose whole-number quantities.';return;}
   let amount=0;
   if(saved){try{const r=await fetch('/api/events/'+page.event_id+'/extra-options/quote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selections})}),q=await r.json();if(ticket!==seq)return;if(!r.ok)throw Error(q.error);amount=q.item_subtotal_minor;}catch(e){if(ticket===seq)target.textContent=e.message||'Could not check current inventory.';return;}}
   else for(const [id,c] of choices){const item=page.items.find(i=>i.id===id);if(item)amount+=item.price_minor*c.quantity;}
   if(ticket!==seq)return;target.replaceChildren(el('strong','Extra options subtotal: '+money(amount,page.currency)),el('p','Registration fees and any applicable tax are handled in the final order summary when checkout is available.'));
  }
  return {update(next){if(page?.event_id!==next.event_id)choices=new Map();page=next;const ids=new Set(page.items.map(i=>i.id));for(const id of choices.keys())if(!ids.has(id))choices.delete(id);draw();}};
 }
 window.ExtraOptionsBrowser={mount,money};
})();
