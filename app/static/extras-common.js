(()=>{
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const money=(n,c)=>new Intl.NumberFormat(undefined,{style:'currency',currency:c}).format(n/(c==='JPY'?1:100));
 function mount(root,{saved=false}={}){
  let page=null,choices=new Map(),seq=0;
  function draw(){
   root.replaceChildren();root.classList.add('extras-browser');root.append(el('p','MAKE IT YOURS','eyebrow'),el('h2','Additional options'),el('p','Add something extra to your event experience.'));
   const cards=el('div',undefined,'extras-cards'),summary=el('div',undefined,'extras-summary');summary.setAttribute('role','status');
   if(!page.items.length)cards.append(el('p','No additional options are available yet.','session-empty'));
   for(const item of page.items){
    const card=el('article',undefined,'extras-card');if(item.image_asset_id){const image=el('img',undefined,'extras-option-image');image.src='/api/events/'+page.event_id+'/assets/'+item.image_asset_id;image.alt=item.name;image.loading='lazy';card.append(image);}card.append(el('small',item.kind==='physical'?'Physical item':'Service / experience'),el('h3',item.name),el('p',item.description),el('strong',money(item.price_minor,page.currency)));
    const controls=el('div',undefined,'extras-choice-controls');const choice={quantity:0,variant_id:null};let variant;
    if(item.variants.length){const label=el('label','Choose a variant / size','extras-variant-control');variant=el('select');variant.append(new Option('Choose an option',''),...item.variants.map(v=>new Option(v.label+(v.inventory===0?' — Sold out':''),v.id)));variant.value=choice.variant_id||'';label.append(variant);controls.append(label);}
    const stock=()=>item.variants.length?item.variants.find(v=>v.id===(variant?.value||choice.variant_id))?.inventory:item.inventory;
    const availability=el('p','','field-note'),label=el('label','Quantity','extras-quantity-control'),qty=el('select');qty.append(new Option('0','0'));qty.value='0';label.append(qty);controls.append(label);card.append(controls,availability);
    const update=(calculate=true)=>{const n=stock();const max=Math.max(0,Math.min(item.allow_multiple?99:1,n??99)),selected=calculate?Number(qty.value):choice.quantity;qty.replaceChildren(...Array.from({length:max+1},(_,i)=>new Option(String(i),String(i))));qty.value=String(Number.isInteger(selected)&&selected<=max?selected:0);qty.max=String(max);qty.disabled=n===0||!!(variant&&!variant.value);availability.textContent=n===0?'Sold out':variant&&!variant.value?'Choose an option to see availability.':n==null?'Available':n+' available';if(qty.disabled||Number(qty.value)>Number(qty.max))qty.value='0';choice.quantity=Number(qty.value);choice.variant_id=variant?.value||null;};
    qty.onchange=update;if(variant)variant.onchange=update;update(false);const add=el('button','Add to registration');add.type='button';add.onclick=()=>{const key=item.id+'|'+(choice.variant_id||''),existing=choices.get(key),quantity=(existing?.quantity||0)+choice.quantity,n=stock(),itemTotal=[...choices.values()].filter(c=>c.item_id===item.id).reduce((sum,c)=>sum+c.quantity,0)+choice.quantity;if(!choice.quantity){availability.textContent='Choose a quantity to add.';return;}if(quantity>99||(n!=null&&quantity>n)||(!item.allow_multiple&&itemTotal>1)){availability.textContent='That quantity exceeds the available limit. Review the items already added below.';return;}choices.set(key,{item_id:item.id,quantity,variant_id:choice.variant_id});draw();};card.append(add);cards.append(card);
   }
   const cart=el('section',undefined,'extras-cart');cart.append(el('h3','Added to your registration'));for(const [key,c] of choices){const item=page.items.find(i=>i.id===c.item_id);if(!item)continue;const row=el('div',undefined,'extras-cart-row'),v=item.variants.find(v=>v.id===c.variant_id);row.append(el('span',item.name+(v?' — '+v.label:'')+' × '+c.quantity),el('strong',money(item.price_minor*c.quantity,page.currency)));const remove=el('button','Remove');remove.type='button';remove.className='secondary';remove.setAttribute('aria-label','Remove '+item.name+(v?' '+v.label:''));remove.onclick=()=>{choices.delete(key);draw();};row.append(remove);cart.append(row);}if(!choices.size)cart.append(el('p','No additional options added yet.'));root.append(cards,cart,summary,el('p','Selections do not reserve inventory. Availability is checked again before payment.','session-note'));total(summary);
  }
  async function total(target){
   const ticket=++seq,selections=[...choices].filter(([,c])=>c.quantity>0).map(([,c])=>({...c}));
   if(saved||window.RegFireJourney?.editor)window.RegFireJourney?.save({extras:selections});
   if([...choices.values()].some(c=>!Number.isInteger(c.quantity)||c.quantity<0)){target.textContent='Choose whole-number quantities.';return;}
   let amount=0;
   if(saved){try{const r=await fetch('/api/events/'+page.event_id+'/extra-options/quote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({selections})}),q=await r.json();if(ticket!==seq)return;if(!r.ok)throw Error(q.error);amount=q.item_subtotal_minor;}catch(e){if(ticket===seq)target.textContent=e.message||'Could not check current inventory.';return;}}
   else for(const [id,c] of choices){const item=page.items.find(i=>i.id===c.item_id);if(item)amount+=item.price_minor*c.quantity;}
   if(ticket!==seq)return;target.replaceChildren(el('strong','Additional options subtotal: '+money(amount,page.currency)),el('p','Registration fees, discounts and applicable tax appear on Verify your details.'));
  }
  return {update(next){if(page?.event_id!==next.event_id)choices=new Map(((saved||window.RegFireJourney?.editor)?window.RegFireJourney?.read().extras||[]:[]).map(c=>[c.item_id+'|'+(c.variant_id||''),{item_id:c.item_id,quantity:c.quantity,variant_id:c.variant_id}]));page=next;window.RegFirePreviewBranding?.connect(root,page.event_id);const ids=new Set(page.items.map(i=>i.id));for(const [key,c] of choices)if(!ids.has(c.item_id))choices.delete(key);draw();}};
 }
 window.ExtraOptionsBrowser={mount,money};
})();
