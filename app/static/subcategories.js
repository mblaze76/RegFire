/* Nested choices inherit their root registration type's rate. */
(()=>{
 const paths=new Map();
 function render(target,type,onchange){
  if(!type?.subcategories?.length){if(type)paths.delete(target.id+':'+type.id);return;}
  const key=target.id+':'+type.id,path=paths.get(key)||[];
  const group=document.createElement('div');group.className='subcategory-choices';target.append(group);
  function draw(){
   group.replaceChildren();let parent=type,depth=0;
   while(parent.subcategories?.length){
    const options=parent.subcategories,label=document.createElement('label'),select=document.createElement('select');
    label.append(document.createTextNode('Choose '+(parent.name||'category')+' subcategory *'));
    select.required=true;if(target.dataset.form)select.setAttribute('form',target.dataset.form);select.name='subcategory-'+depth;select.append(new Option('Choose an option',''));
    for(const child of options)select.append(new Option(child.name||'Unnamed subcategory',child.id));
    const chosen=options.find(child=>child.id===path[depth]);select.value=chosen?.id||'';
    const level=depth;select.onchange=()=>{path.splice(level,path.length-level,...(select.value?[select.value]:[]));paths.set(key,path);draw();onchange?.();};
    label.append(select);group.append(label);
    if(!chosen){path.splice(depth);break;}parent=chosen;depth++;
   }
  }
  draw();
 }
 function categories(target,types,selected,onchange){
  const focusID=target.contains(document.activeElement)?document.activeElement.value:null;
  target.replaceChildren();
  for(const type of types){
   const label=document.createElement('label'),input=document.createElement('input');label.className='check-label';input.type='radio';input.name=target.id+'-category';input.value=type.id;input.required=true;input.checked=type.id===selected;
   if(target.id==='live-category-options')input.setAttribute('form','live-contact');
   input.onchange=()=>{if(input.checked)onchange(type.id);};const caption=document.createElement('span'),rate=document.createElement('span');caption.textContent=type.name||'Unnamed category';rate.className='category-rate';rate.dataset.categoryRate=type.id;rate.textContent='Checking rate…';label.append(input,caption,rate);target.append(label);
   if(focusID===type.id)input.focus({preventScroll:true});
  }
 }
 function rates(target,values,currency,message='Checking rate…'){
  for(const label of target.querySelectorAll('[data-category-rate]')){
   const rate=values?.[label.dataset.categoryRate];
   label.textContent=!values?message:rate?.price_minor!=null?new Intl.NumberFormat(undefined,{style:'currency',currency,currencyDisplay:'code'}).format(rate.price_minor/(currency==='JPY'?1:100))+' · '+rate.name:'No active rate';
  }
 }
 window.RegFireSubcategories={render,categories,rates,path(targetID,typeID){return [...(paths.get(targetID+':'+typeID)||[])];},clear(){paths.clear();}};
})();
