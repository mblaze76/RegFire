/* Organizer definitions only. Preview inputs never leave the browser. */
(() => {
  const $ = id => document.getElementById(id);
  const types = {text:'Short text', email:'Email', tel:'Phone', textarea:'Long text', select:'Dropdown', radio:'Single choice', checkbox:'Checkbox', address:'Address block'};
  const addressParts = [['line1','Address line 1'],['line2','Address line 2'],['city','City'],['region','State / province / region'],['postal','Postal code'],['country','Country']];
  const digits = currency => currency === 'JPY' ? 0 : 2;
  let page = null, event = null, changed = false, busy = false, generation = 0, previewType = null, pricingTicket = 0, pricingTimer = null;
  const node = (tag, className, text) => { const n=document.createElement(tag); if(className)n.className=className; if(text!==undefined)n.textContent=text; return n; };
  function label(text, control) { const n=node('label','',text); n.append(control); return n; }
  function button(text, action, name, disabled=false) { const n=node('button','small-button',text); n.type='button'; if(name)n.setAttribute('aria-label',name); n.disabled=disabled; n.onclick=action; return n; }
  function input(value, max) { const n=node('input'); n.value=value; n.maxLength=max; return n; }
  function minorToText(value,currency) { const count=digits(currency); return count ? Math.floor(value/100)+'.'+String(value%100).padStart(2,'0') : String(value); }
  function parsePrice(value,currency) {
    const d=digits(currency), pattern=d ? /^\d+(?:\.\d{1,2})?$/ : /^\d+$/;
    if(!pattern.test(value.trim()))throw new Error(currency === 'JPY' ? 'JPY prices must be whole yen.' : 'Prices must be nonnegative numbers with at most two decimal places.');
    const [whole,fraction='']=value.trim().split('.');
    const minor=Number(whole)*(d?100:1)+(d?Number(fraction.padEnd(2,'0')):0);
    if(!Number.isSafeInteger(minor)||minor>99999999)throw new Error('Price exceeds the supported maximum of 99,999,999 minor units.');
    return minor;
  }
  function money(value) {
    return new Intl.NumberFormat(undefined,{style:'currency',currency:page.currency,currencyDisplay:'code'}).format(value/(digits(page.currency)?100:1));
  }
  function serializePage() {
    return {promo_codes:page.promo_codes||[],title:page.title,intro:page.intro,currency:page.currency,appearance:{...page.appearance},fields:page.fields.map(f=>({...f,options:['select','radio'].includes(f.type)?f.options:[]})),regtypes:page.regtypes.map(r=>({id:r.id,name:r.name,show_on_welcome:r.show_on_welcome!==false,price_minor:parsePrice(r.price_text,page.currency),use_default:r.use_default,rates:r.rates.map(rate=>({id:rate.id,name:rate.name,price_minor:parsePrice(rate.price_text,page.currency),start:rate.start,end:rate.end}))}))};
  }
  function updatePricing() {
    const ticket=++pricingTicket;
    clearTimeout(pricingTimer);
    $('preview-price').textContent='Checking…';$('preview-rate').textContent='';
    $('preview-form').querySelector('button[type=submit]').disabled=true;
    pricingTimer=setTimeout(async ()=>{
      if(!page||ticket!==pricingTicket)return;
      try {
        const result=await api('/api/events/'+event.id+'/pricing-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({page:serializePage(),at:$('preview-at').value})});
        if(ticket!==pricingTicket||!page)return;
        const rate=result.regtypes[previewType];
        $('preview-price').textContent=rate?.price_minor!==null&&rate?money(rate.price_minor):'No active rate';
        $('preview-rate').textContent=rate?rate.name+' · '+(rate.message||'Active for this preview time. Starts inclusive; ends exclusive.'):'Choose a RegType.';
        $('preview-rate').className='rate-result'+(rate?.status==='unavailable'?' error':'');
        $('preview-timezone').textContent='Event timezone: '+result.timezone+'. Checked at '+result.at+'. Blank uses current time.';
        $('preview-form').querySelector('button[type=submit]').disabled=!rate||rate.status==='unavailable';
      }catch(error){
        if(ticket!==pricingTicket||!page)return;
        $('preview-price').textContent='Check rate settings';$('preview-rate').textContent=error.message;$('preview-rate').className='rate-result error';
      }
    },200);
  }
  function say(text,error=false) { $('page-feedback').textContent=text; $('page-feedback').className=error?'error':''; }
  function dirty() { changed=true; $('page-save-state').textContent='Unsaved changes'; say('Save this page draft to keep your changes.'); }
  function cloneFromServer(data) { return {...data,appearance:{logo_asset_id:null,background_asset_id:null,background_fade:80,...(data.appearance||{})},fields:data.fields.map(f=>({...f,options:[...f.options],visible_to:f.visible_to===null?null:[...f.visible_to]})),regtypes:data.regtypes.map(r=>({...r,use_default:r.use_default??true,price_text:minorToText(r.price_minor,data.currency),rates:(r.rates||[]).map(rate=>({...rate,price_text:minorToText(rate.price_minor,data.currency)}))}))}; }
  async function load(ev) {
    const ticket=++generation; event=ev; page=null; changed=false; previewType=null;
    $('builder-content').hidden=true; $('builder-load-error').hidden=true; $('builder-loading').hidden=false;
    $('builder-event-name').textContent=ev?.name || '';
    $('preview-at').value='';
    $('rate-timezone').textContent='Rate times use '+(ev?.timezone||'the event timezone')+'. Starts include the selected minute; ends expire at the selected minute. Blank boundaries are open-ended.';
    if(!ev) return;
    try {
      const data=await api('/api/events/'+ev.id+'/registration-page');
      if(ticket!==generation)return;
      page=cloneFromServer(data); $('page-title').value=page.title; $('page-intro').value=page.intro; $('page-currency').value=page.currency;
      $('page-save-state').textContent=page.updated?'Saved page draft':'Unsaved starter';
      say(page.updated?'Last saved '+new Date(page.updated).toLocaleString():'Starter fields are ready to customize. Save to keep this page.');
      renderPromos(); renderTypes(); renderFields(); renderPreview(); $('builder-content').hidden=false;
    } catch(error) { if(ticket===generation) { $('builder-load-message').textContent=error.message; $('builder-load-error').hidden=false; } }
    finally { if(ticket===generation)$('builder-loading').hidden=true; }
  }
  function move(array,index,delta,render) { [array[index],array[index+delta]]=[array[index+delta],array[index]]; dirty(); render(); renderPreview(); }
  function controls(array,index,kind,render,remove) {
    const bar=node('div','order-controls');
    bar.append(button('↑',()=>move(array,index,-1,render),'Move '+kind+' '+(index+1)+' up',index===0),button('↓',()=>move(array,index,1,render),'Move '+kind+' '+(index+1)+' down',index===array.length-1),button('Remove',remove,'Remove '+kind+' '+(index+1),array.length===1));
    return bar;
  }
  let pendingPromos=[];
  function renderPromos(){const target=$('promo-editor');target.replaceChildren();(page.promo_codes||[]).forEach((promo,index)=>{const card=node('div','regtype-card'),row=node('div','regtype-inputs');const code=input(promo.code,80);code.oninput=()=>{promo.code=code.value.trim().toUpperCase();dirty();};const kind=node('select');for(const [value,title] of [['free','Free registration'],['percent','Percentage off'],['fixed','Fixed amount off']])kind.append(new Option(title,value));kind.value=promo.type;kind.onchange=()=>{promo.type=kind.value;if(promo.type==='free')promo.amount=0;dirty();renderPromos();};row.append(label('Promo code',code),label('Discount',kind));if(promo.type!=='free'){const amount=input(String(promo.amount??''),12);amount.type='number';amount.min='0';amount.step='0.01';if(promo.type==='percent')amount.max='100';amount.oninput=()=>{promo.amount=amount.value===''?null:Number(amount.value);dirty();};row.append(label(promo.type==='percent'?'Percentage off':'Amount off ('+page.currency+')',amount));}const allotment=input(promo.allotment==null?'':String(promo.allotment),10);allotment.type='number';allotment.min='0';allotment.max='2147483647';allotment.step='1';allotment.placeholder='Unlimited';allotment.oninput=()=>{promo.allotment=allotment.value===''?null:Number(allotment.value);dirty();};row.append(label('Allotment (maximum uses)',allotment));const enabled=node('input');enabled.type='checkbox';enabled.checked=promo.enabled!==false;enabled.onchange=()=>{promo.enabled=enabled.checked;dirty();};const enabledLabel=node('label','check-label');enabledLabel.append(enabled,document.createTextNode('Enabled'));card.append(row,enabledLabel,button('Remove code',async()=>{if(!await confirmAction('Remove promo code '+(promo.code||'without a name')+'?'))return;page.promo_codes.splice(index,1);dirty();renderPromos();}));target.append(card);});}
  $('add-promo').onclick=()=>{page.promo_codes??=[];if(page.promo_codes.length>=1000)return;page.promo_codes.push({code:'',type:'free',amount:0,enabled:true,allotment:null});dirty();renderPromos();};
  $('import-promos').onchange=async()=>{pendingPromos=[];$('confirm-promo-import').hidden=true;const file=$('import-promos').files[0];if(!file)return;try{if(file.size>200000)throw Error('Use a CSV smaller than 200 KB.');const rows=(await file.text()).replace(/^\uFEFF/,'').trim().split(/\r?\n/).filter(x=>x.trim());const header=rows.shift()?.trim().toLowerCase();if(!['code,type,amount','code,type,amount,allotment'].includes(header))throw Error('CSV header must be code,type,amount or code,type,amount,allotment.');const hasAllotment=header.endsWith(',allotment');const seen=new Set((page.promo_codes||[]).map(p=>p.code.toUpperCase()));for(const [index,line] of rows.entries()){const cells=line.split(',').map(x=>x.trim().replace(/^"|"$/g,''));if(cells.length!==(hasAllotment?4:3))throw Error('Check CSV row '+(index+2)+'.');const [raw,type,value]=cells,code=raw.toUpperCase(),amount=type==='free'?0:Number(value);if(!code||code.length>80||seen.has(code)||!['free','percent','fixed'].includes(type)||!Number.isFinite(amount)||(type!=='free'&&amount<=0)||(type==='percent'&&amount>100)||(type==='fixed'&&(amount>999999||Math.round(amount*100)!==amount*100)))throw Error('Invalid or duplicate code on row '+(index+2)+'.');const limit=hasAllotment?cells[3]:'';if(limit!==''&&(!/^\d+$/.test(limit)||Number(limit)>2147483647))throw Error('Allotment must be a whole number of 0 or more on row '+(index+2)+'.');const allotment=limit===''?null:Number(limit);seen.add(code);pendingPromos.push({code,type,amount,enabled:true,allotment});}if(!pendingPromos.length||seen.size>1000)throw Error('Import must contain codes, with no more than 1000 total.');$('promo-import-result').textContent=pendingPromos.length+' valid codes ready: '+pendingPromos.slice(0,10).map(p=>p.code).join(', ')+(pendingPromos.length>10?'…':'');$('confirm-promo-import').hidden=false;}catch(e){pendingPromos=[];$('promo-import-result').textContent=e.message;}};
  $('confirm-promo-import').onclick=()=>{const existing=new Set((page.promo_codes||[]).map(p=>p.code.toUpperCase()));if(pendingPromos.some(p=>existing.has(p.code))||(page.promo_codes||[]).length+pendingPromos.length>1000){$('promo-import-result').textContent='Codes changed. Select the CSV again to check duplicates.';return;}page.promo_codes=[...(page.promo_codes||[]),...pendingPromos];pendingPromos=[];dirty();renderPromos();$('confirm-promo-import').hidden=true;$('promo-import-result').textContent='Codes added. Save page draft to keep them.';$('import-promos').value='';};
  function renderTypes() {
    const container=$('regtypes-editor'); container.replaceChildren();
    page.regtypes.forEach((r,index)=>{
      for(let i=1;i<r.rates.length;i++){if(r.rates[i].start!==r.rates[i-1].end){r.rates[i].start=r.rates[i-1].end;dirty();}}
      const card=node('div','regtype-card'); const heading=node('div','item-heading'); heading.append(node('strong','', 'Subcategory '+(index+1)),controls(page.regtypes,index,'RegType',()=>{renderTypes();renderFields();},async ()=>{
        if(page.fields.some(f=>f.visible_to?.includes(r.id))) {say('This RegType controls field visibility. Set those fields to all types or other RegTypes before removing it.',true);$('page-feedback').scrollIntoView({block:'nearest'});return;}
        if(!await confirmAction('Remove '+(r.name||'this RegType')+' from this page draft?'))return;
        page.regtypes.splice(index,1);dirty();renderTypes();renderFields();renderPreview();
      }));
      const row=node('div','regtype-inputs'); const name=input(r.name,80); name.required=true;
      name.oninput=()=>{r.name=name.value;dirty();renderFields();renderPreview();};
      const price=input(r.price_text,14); price.inputMode='decimal'; price.required=true;
      price.oninput=()=>{r.price_text=price.value;dirty();renderPreview();};
      row.append(label('Attendee subcategory name',name),label('Default price ('+page.currency+')',price));card.append(heading,row);
      const fallback=node('input');fallback.type='checkbox';fallback.checked=r.use_default;
      fallback.onchange=()=>{r.use_default=fallback.checked;dirty();renderPreview();};
      const fallbackLabel=node('label','check-label');fallbackLabel.append(fallback,document.createTextNode('Use default rate outside dated periods'));card.append(fallbackLabel);
      card.append(node('p','field-note','A matching dated period takes priority. With the default disabled, gaps and expired periods offer no price. The default never expires while enabled.'));
      const rateList=node('div','rate-list');
      r.rates.forEach((rate,rateIndex)=>{
        const rateCard=node('div','rate-card');
        const rateHeading=node('div','item-heading');rateHeading.append(node('strong','','Rate period '+(rateIndex+1)),button('Remove',async ()=>{if(!await confirmAction('Remove '+(rate.name||'this rate period')+'? The enabled default may apply in its place.'))return;r.rates.splice(rateIndex,1);if(rateIndex>0&&r.rates[rateIndex])r.rates[rateIndex].start=r.rates[rateIndex-1].end;dirty();renderTypes();renderPreview();},'Remove rate period '+(rateIndex+1)));
        const rateRow=node('div','regtype-inputs');const rateName=input(rate.name,80);rateName.oninput=()=>{rate.name=rateName.value;dirty();renderPreview();};
        const ratePrice=input(rate.price_text,14);ratePrice.inputMode='decimal';ratePrice.oninput=()=>{rate.price_text=ratePrice.value;dirty();renderPreview();};
        rateRow.append(label('Rate name',rateName),label('Rate price ('+page.currency+')',ratePrice));
        const dates=node('div','rate-dates');
        for(const [key,title] of [['start','Starts (inclusive)'],['end','Ends (exclusive)']]){const control=node('input');control.type='datetime-local';control.value=rate[key];if(key==='start'&&rateIndex>0){control.readOnly=true;control.title='Starts when the previous rate period ends';}control.onchange=()=>{rate[key]=control.value;if(key==='end'&&r.rates[rateIndex+1]){r.rates[rateIndex+1].start=control.value;renderTypes();}dirty();renderPreview();};dates.append(label(title,control));}
        rateCard.append(rateHeading,rateRow,dates);if(rateIndex>0)rateCard.append(node('p','field-note','Starts automatically when the previous rate ends, with no gap.'));rateList.append(rateCard);
      });
      const addRate=button('＋ Add rate period',()=>{if(r.rates.length&&!r.rates.at(-1).end){say('Set the previous rate period’s end time before adding another.',true);return;}r.rates.push({id:crypto.randomUUID(),name:'',price_text:r.price_text,start:r.rates.at(-1)?.end||'',end:''});dirty();renderTypes();renderPreview();},'Add rate period for '+(r.name||'unnamed RegType'),r.rates.length>=20);addRate.className='secondary';
      card.append(rateList,addRate);container.append(card);
    });
    $('add-regtype').disabled=page.regtypes.length>=30;
  }
  let fieldDrag=null, dragFrame=null;
  function clearDropFeedback(){document.querySelectorAll('.drop-before,.drop-after').forEach(n=>n.classList.remove('drop-before','drop-after'));}
  function dragTarget(y,x){
    clearDropFeedback();
    const target=document.elementFromPoint(x,y)?.closest('.field-card');
    if(!target||target.dataset.fieldId===fieldDrag?.id){if(fieldDrag)fieldDrag.target=null;return;}
    const rect=target.getBoundingClientRect();const after=y>rect.top+rect.height/2;
    fieldDrag.target=target.dataset.fieldId;fieldDrag.after=after;target.classList.add(after?'drop-after':'drop-before');
    $('field-drag-status').textContent='Release to place the field '+(after?'after':'before')+' '+(page.fields.find(f=>f.id===fieldDrag.target)?.label||'this field')+'.';
  }
  function scrollDrag(){
    if(!fieldDrag?.active)return;
    const edge=70,y=fieldDrag.y;
    const amount=y<edge?-12:y>window.innerHeight-edge?12:0;
    if(amount){window.scrollBy(0,amount);dragTarget(fieldDrag.y,fieldDrag.x);}
    dragFrame=requestAnimationFrame(scrollDrag);
  }
  function dragHandle(field,index){
    const handle=button('⠿',()=>{},'Drag field '+(index+1)+' to reorder');handle.className='drag-handle';handle.title='Drag to reorder. You can also use the up and down buttons.';
    handle.onpointerdown=e=>{
      if(e.button!==0||busy)return;
      fieldDrag={id:field.id,startY:e.clientY,x:e.clientX,y:e.clientY,active:false,target:null};handle.setPointerCapture(e.pointerId);
    };
    handle.onpointermove=e=>{
      if(!fieldDrag)return;fieldDrag.x=e.clientX;fieldDrag.y=e.clientY;
      if(!fieldDrag.active&&Math.abs(e.clientY-fieldDrag.startY)>6){fieldDrag.active=true;handle.closest('.field-card').classList.add('dragging');document.body.classList.add('field-dragging');scrollDrag();}
      if(fieldDrag.active){e.preventDefault();dragTarget(e.clientY,e.clientX);}
    };
    function finish(cancelled){
      if(!fieldDrag)return;
      const drag=fieldDrag;fieldDrag=null;cancelAnimationFrame(dragFrame);clearDropFeedback();document.body.classList.remove('field-dragging');document.querySelector('.field-card.dragging')?.classList.remove('dragging');
      if(!cancelled&&drag.active&&drag.target){
        const from=page.fields.findIndex(f=>f.id===drag.id);const item=page.fields.splice(from,1)[0];const target=page.fields.findIndex(f=>f.id===drag.target);const to=target+(drag.after?1:0);page.fields.splice(to,0,item);
        dirty();renderFields();renderPreview();$('field-drag-status').textContent='Moved '+(item.label||'field')+' to position '+(to+1)+'.';
      }else $('field-drag-status').textContent='Field order unchanged.';
    }
    handle.onpointerup=()=>finish(false);handle.onpointercancel=()=>finish(true);
    return handle;
  }
  function renderFields() {
    const container=$('fields-editor');container.replaceChildren();
    page.fields.forEach((f,index)=>{
      const card=node('div','field-card');card.dataset.fieldId=f.id;
      const heading=node('div','item-heading');heading.append(dragHandle(f,index),node('strong','', 'Field '+(index+1)),controls(page.fields,index,'field',renderFields,async ()=>{
        if(!await confirmAction('Remove '+(f.label||'this field')+' from this page draft?'))return;
        page.fields.splice(index,1);dirty();renderFields();renderPreview();
      }));
      const row=node('div','field-basics');const title=input(f.label,120);title.required=true;
      title.oninput=()=>{f.label=title.value;dirty();renderPreview();};
      const type=node('select');Object.entries(types).forEach(([value,name])=>{const option=node('option','',name);option.value=value;type.append(option);});type.value=f.type;
      type.onchange=()=>{f.type=type.value;if(['select','radio'].includes(f.type)&&f.options.length<2)f.options=['Option 1','Option 2'];dirty();renderFields();renderPreview();};
      row.append(label('Field label',title),label('Field type',type));
      const required=node('input');required.type='checkbox';required.checked=f.required;required.onchange=()=>{f.required=required.checked;dirty();renderPreview();};
      const req=node('label','check-label');req.append(required,document.createTextNode('Required when visible'));
      card.append(heading,row,req);
      if(f.type==='address') card.append(node('p','field-note','Address line 1, city, state / province / region, postal code and country follow this required setting. Address line 2 is always optional.'));
      if(f.type==='tel'){const consent=node('input');consent.type='checkbox';consent.checked=f.sms_consent??(f.id==='cell-phone'||/cell|mobile/i.test(f.label));consent.onchange=()=>{f.sms_consent=consent.checked;dirty();renderPreview();};const consentLabel=node('label','check-label');consentLabel.append(consent,document.createTextNode('Show text-message consent checkbox'));card.append(consentLabel);}
      if(f.type==='tel') card.append(node('p','field-note','Accepts international formats, including +, spaces and extensions.'));
      if(['select','radio'].includes(f.type)){
        const choices=node('textarea');choices.rows=3;choices.value=f.options.join('\n');choices.oninput=()=>{f.options=choices.value.split('\n');dirty();renderPreview();};
        card.append(label('Choices — one per line (2–30)',choices));
      }
      const visibility=node('select');for(const [value,name] of [['all','All RegTypes'],['selected','Selected RegTypes']]){const option=node('option','',name);option.value=value;visibility.append(option);}
      visibility.value=f.visible_to===null?'all':'selected';visibility.onchange=()=>{f.visible_to=visibility.value==='all'?null:[];dirty();renderFields();renderPreview();};
      card.append(label('Show this field to',visibility));
      if(f.visible_to!==null){
        const group=node('fieldset','visibility-options');group.append(node('legend','','Visible for'));
        page.regtypes.forEach(r=>{const check=node('input');check.type='checkbox';check.checked=f.visible_to.includes(r.id);check.onchange=()=>{f.visible_to=check.checked?[...f.visible_to,r.id]:f.visible_to.filter(id=>id!==r.id);dirty();renderPreview();};const l=node('label','check-label');l.append(check,document.createTextNode(r.name||'Unnamed RegType'));group.append(l);});
        if(!f.visible_to.length)group.append(node('p','field-note error','Select at least one RegType before saving.'));
        card.append(group);
      }
      container.append(card);
    });
    $('add-field').disabled=page.fields.length>=50;
  }
  function previewInput(type,required,id) {
    const control=node(type==='textarea'?'textarea':'input');if(type!=='textarea')control.type=type;else control.rows=3;
    control.required=required; control.id=id;
    if(type==='tel'){control.placeholder='+1 212 555 0123';control.autocomplete='tel';}
    return control;
  }
  function renderPreview() {
    if(!page)return;
    updateAppearance();
    $('preview-event').textContent=event.name;$('preview-title').textContent=page.title||'Your page title';$('preview-intro').textContent=page.intro;
    const selector=$('preview-regtype');selector.replaceChildren();
    for(const r of page.regtypes){const option=node('option','',r.name||'Unnamed RegType');option.value=r.id;selector.append(option);}
    if(!page.regtypes.some(r=>r.id===previewType))previewType=page.regtypes[0]?.id;
    selector.value=previewType||'';
    updatePricing();
    const container=$('preview-fields');container.replaceChildren();$('preview-feedback').textContent='';
    page.fields.filter(f=>f.visible_to===null||f.visible_to.includes(previewType)).forEach(f=>{
      const title=(f.label||'Untitled field')+(f.required?' *':'');const id='preview-'+f.id;
      if(f.type==='address'){
        const group=node('fieldset','preview-address');group.append(node('legend','',f.label||'Address'));
        for(const [key,name] of addressParts){const required=f.required&&key!=='line2';const control=previewInput('text',required,id+'-'+key);control.autocomplete='off';group.append(label(name+(required?' *':'')+(key==='line2'?' (optional)':''),control));}container.append(group);
        window.AddressLookup.attach(group.querySelector('#'+CSS.escape(id+'-line1')),address=>{for(const [key] of addressParts)if(key!=='line2')group.querySelector('#'+CSS.escape(id+'-'+key)).value=address[key]||'';});
      } else if(f.type==='select'){
        const control=node('select');control.required=f.required;control.id=id;const placeholder=node('option','','Choose an option');placeholder.value='';control.append(placeholder);
        for(const choice of f.options){const option=node('option','',choice);option.value=choice;control.append(option);}container.append(label(title,control));
      } else if(f.type==='radio'){
        const group=node('fieldset','preview-choices');group.append(node('legend','',title));
        f.options.forEach((choice,i)=>{const radio=previewInput('radio',f.required,id+'-'+i);radio.name=id;radio.value=choice;const l=node('label','check-label');l.append(radio,document.createTextNode(choice));group.append(l);});container.append(group);
      } else if(f.type==='checkbox'){
        const checkbox=previewInput('checkbox',f.required,id);const l=node('label','check-label');l.append(checkbox,document.createTextNode(title));container.append(l);
      } else {const input=previewInput(f.type,f.required,id);container.append(label(title,input));if(f.type==='email')window.EmailValidation.attach(input,container);if(f.type==='tel'&&(f.sms_consent??(f.id==='cell-phone'||/cell|mobile/i.test(f.label))))window.PhoneConsent.attach(input,container,event.name);}
    });
  }
  function assetURL(id){return '/api/events/'+event.id+'/assets/'+id;}
  function introFonts(){
    const select=$('page-intro-font'),current=page?.appearance?.intro_font||'default',query=$('page-intro-font-search').value.trim().toLowerCase();
    select.replaceChildren();let count=0;
    for(const [id,[label]] of Object.entries(window.WelcomeDisplay.fonts)){const match=label.toLowerCase().includes(query);if(match||id===current){select.add(new Option(label,id));if(match)count++;}}
    select.value=current;$('page-intro-font-count').textContent=query?count+' matching fonts. Current selection is retained.':'100 popular Google Fonts plus 5 original choices.';
  }
  $('page-intro-font-search').oninput=introFonts;
  $('page-intro-font').onchange=()=>{if(!page)return;page.appearance.intro_font=$('page-intro-font').value;dirty();updateAppearance();};
  function updateAppearance(){
    if(page){introFonts();const font=page.appearance.intro_font||'default';window.WelcomeDisplay.loadFont(font);$('preview-intro').style.fontFamily=(window.WelcomeDisplay.fonts[font]||window.WelcomeDisplay.fonts.default)[1];}

    if(!page)return;for(const [key,id,target,fallback] of [["title_color","page-title-color","preview-title","#24242a"],["intro_color","page-intro-color","preview-intro","#555c68"]]){const color=page.appearance[key]||fallback;$(id).value=color;$(target).style.color=color;}
    const footer=page.appearance.footer||{};$("footer-enabled").checked=!!footer.enabled;for(const key of ['heading', 'message', 'email', 'phone', 'links', 'facebook','instagram','linkedin','youtube','x'])$("footer-"+key).value=footer[key]||"";window.RegistrationFooter.render($("preview-footer"),footer);
    if(!page)return;
    for(const kind of ['logo','background']){
      const id=page.appearance[kind+'_asset_id'];const image=$(kind+'-thumbnail');
      image.hidden=!id;if(id)image.src=assetURL(id);else image.removeAttribute('src');
      $('remove-'+kind).disabled=!id;
    }
    $('preview-logo').src=page.appearance.logo_asset_id?assetURL(page.appearance.logo_asset_id):'/regfire-logo.png';
    $('preview-logo').alt=page.appearance.logo_asset_id?'Show logo':'RegFire';
    const surface=document.querySelector('.preview-surface');
    surface.classList.toggle('artwork-contrast',!!page.appearance.background_asset_id && Number(page.appearance.background_fade??80)<50);
    surface.style.setProperty('--page-background',page.appearance.background_asset_id?'url("'+assetURL(page.appearance.background_asset_id)+'")':'none');
    surface.style.setProperty('--page-image-opacity',String(1-page.appearance.background_fade/100));
    $('background-fade').value=page.appearance.background_fade;$('fade-value').value=page.appearance.background_fade+'%';
  }
  for(const kind of ['logo','background']){
    $('upload-'+kind).onchange=async ()=>{
      const control=$('upload-'+kind),file=control.files[0];if(!file||!page||busy)return;
      if(file.size>8*1024*1024){say('Choose an image no larger than 8 MB.',true);control.value='';return;}
      busy=true;const controls=[...$('builder-form').elements];controls.forEach(c=>c.disabled=true);say('Checking and storing image…');
      try{
        const asset=await api('/api/events/'+event.id+'/assets/'+kind,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file});
        page.appearance[kind+'_asset_id']=asset.id;dirty();say('Image ready. Save the page draft to keep this selection.');
      }catch(error){say(error.message,true);}
      finally{busy=false;controls.forEach(c=>c.disabled=false);control.value='';renderTypes();renderFields();updateAppearance();}
    };
    $('remove-'+kind).onclick=()=>{page.appearance[kind+'_asset_id']=null;dirty();updateAppearance();};
  }
  for(const key of ['enabled', 'heading', 'message', 'email', 'phone', 'links', 'facebook','instagram','linkedin','youtube','x'])for(const eventName of ["input","change"])$("footer-"+key).addEventListener(eventName,()=>{if(!page)return;page.appearance.footer={...(page.appearance.footer||{}),[key]:key==="enabled"?$("footer-enabled").checked:$("footer-"+key).value};dirty();window.RegistrationFooter.render($("preview-footer"),page.appearance.footer);});
  $('background-fade').oninput=()=>{if(page){page.appearance.background_fade=Number($('background-fade').value);dirty();updateAppearance();}};
  for(const [id,key] of [['page-title-color','title_color'],['page-intro-color','intro_color']])$(id).oninput=()=>{if(!page)return;page.appearance[key]=$(id).value;dirty();updateAppearance();};
  $('page-title').oninput=()=>{page.title=$('page-title').value;dirty();renderPreview();};
  $('page-intro').oninput=()=>{page.intro=$('page-intro').value;dirty();renderPreview();};
  $('page-currency').onchange=async ()=>{
    const next=$('page-currency').value;
    if(!await confirmAction('Change the currency to '+next+' and keep the entered numeric amounts? No exchange-rate conversion will be applied.')){$('page-currency').value=page.currency;return;}
    page.currency=next;dirty();renderTypes();renderPreview();
  };
  $('add-regtype').onclick=()=>{if(page.regtypes.length>=30)return;page.regtypes.push({id:crypto.randomUUID(),name:'',price_text:digits(page.currency)?'0.00':'0',use_default:true,rates:[]});dirty();renderTypes();renderFields();renderPreview();$('regtypes-editor').lastElementChild.querySelector('input').focus();};
  $('add-field').onclick=()=>{if(page.fields.length>=50)return;page.fields.push({id:crypto.randomUUID(),label:'',type:'text',required:false,options:[],visible_to:null});dirty();renderFields();renderPreview();$('fields-editor').lastElementChild.querySelector('input').focus();};
  $('preview-regtype').onchange=()=>{previewType=$('preview-regtype').value;renderPreview();};
  $('preview-at').onchange=()=>{if(page)updatePricing();};
  $('preview-now').onclick=()=>{$('preview-at').value='';if(page)updatePricing();};
  function nextMinute(){setTimeout(()=>{if(page&&!document.hidden&&!$('preview-at').value)updatePricing();nextMinute();},60000-(Date.now()%60000)+20);}
  nextMinute();
  document.addEventListener('visibilitychange',()=>{if(page&&!document.hidden&&!$('preview-at').value)updatePricing();});
  $('preview-form').onsubmit=e=>{e.preventDefault();$('preview-feedback').textContent='Preview check complete. No registration or payment was submitted.';};
  $('builder-retry').onclick=()=>load(event);
  $('builder-form').onsubmit=async e=>{
    e.preventDefault();if(busy||!page)return;
    let body;
    try {
      body=serializePage();
    }catch(error){say(error.message,true);return;}
    busy=true;const controls=[...$('builder-form').elements];controls.forEach(c=>c.disabled=true);say('Saving page draft…');
    try {
      const saved=await api('/api/events/'+event.id+'/registration-page',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      page=cloneFromServer(saved);changed=false;$('page-title').value=page.title;$('page-intro').value=page.intro;
      $('page-save-state').textContent='Saved page draft';say('Saved on this computer · '+new Date(saved.updated).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}));
    }catch(error){say(error.message,true);}
    finally {busy=false;controls.forEach(c=>c.disabled=false);renderTypes();renderFields();renderPreview();}
  };
  window.RegistrationBuilder={load,snapshot(){if(!page)return null;let model,error=null;try{model=serializePage();}catch(e){error=e.message;model={...structuredClone(page),regtypes:page.regtypes.map(r=>({...r,price_minor:null}))};}return {event_id:event.id,page:model,at:$('preview-at').value,regtype:previewType,error};},clear(){generation++;pricingTicket++;clearTimeout(pricingTimer);page=null;changed=false;},get dirty(){return changed;},get busy(){return busy;}};
  window.DraftAutosave.register({ready:()=>!!(page&&changed&&!busy),snapshot:()=>(serializePage()),lock:value=>busy=value,clean:()=>{changed=false;},status:(state,message,error)=>{$('page-save-state').textContent=state;say(message,error);},save:data=>api('/api/events/'+event.id+'/registration-page',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})});
})();
