(()=>{
 const opened=new Map();
 function minimize(container,title,key,description='Expand to edit settings.'){
  if(container.querySelector(':scope > details.setup-card'))return;
  const card=document.createElement('details'),summary=document.createElement('summary'),strong=document.createElement('strong'),note=document.createElement('span'),body=document.createElement('div');
  card.className='setup-card';strong.textContent=title;note.textContent=description;summary.append(strong,note);
  const focused=container.contains(document.activeElement);
  const heading=container.querySelector(':scope > .item-heading');
  for(const child of [...container.childNodes])if(child!==heading)body.append(child);
  card.append(summary,body);container.append(card);card.open=focused||(opened.get(key)??!title);
  card.addEventListener('toggle',()=>opened.set(key,card.open));
  const input=body.querySelector('input:not([type=checkbox]):not([type=radio])');
  if(input&&container.dataset.collapseKey){const update=()=>{strong.textContent=input.value.trim()||'New item';};input.addEventListener('input',update);update();}
 }
 const builder=document.querySelector('.registration-editor-column')||document.getElementById('builder-form');
 builder?.addEventListener('invalid',event=>{const section=event.target.closest('#builder-form > section');if(section?.hidden){const index=[...section.parentElement.children].filter(e=>e.tagName==='SECTION').indexOf(section);window.showView?.(index<3||section.id==='promo-settings'?'setup':'registration',true);}for(let parent=event.target.parentElement;parent&&parent!==builder;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;},true);
 // A newly added item is focused by the editor; keep its controls discoverable.
 builder?.addEventListener('focusin',event=>{if(event.target.closest('summary'))return;for(let parent=event.target.parentElement;parent&&parent!==builder;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;});
 for(const [id,selector] of [['builder-view','#builder-form > section, #website-membership-settings'],['demographics-view','#demo-editor > section'],['sessions-view','.sessions-editor > section']]){
  const root=document.getElementById(id);if(!root)continue;
  const nav=document.createElement('nav');nav.className='setup-navigation page-section-shortcuts';nav.setAttribute('aria-label','Page section shortcuts');
  root.querySelector('.page-heading,.builder-heading')?.after(nav);
  let signature='',pending=false;
  function refresh(){
   pending=false;
   if(id==='builder-view'){
    root.querySelectorAll('[data-collapse-key]').forEach(card=>{const input=card.querySelector('input:not([type=checkbox]):not([type=radio])');minimize(card,input?.value||'',card.dataset.collapseKey,card.classList.contains('regtype-card')?'Pricing, membership lookup and nested choices.':card.classList.contains('field-card')?'Field type, membership mapping and visibility.':'Membership lookup and nested choices.');});
    root.querySelectorAll(selector).forEach((section,index)=>minimize(section,section.querySelector('h3')?.textContent.trim()||'Settings','section-'+index));
   }
   const sections=Array.from(root.querySelectorAll(selector)).filter(section=>!section.hidden);
   const labels=sections.map(section=>section.querySelector('h3')?.textContent.trim()||'');
   const next=labels.join('|');if(next===signature)return;signature=next;nav.replaceChildren();
   sections.forEach((section,index)=>{if(!labels[index])return;const button=document.createElement('button');button.type='button';button.textContent=labels[index];
    button.onclick=()=>{const card=section.querySelector(':scope > details.setup-card');if(card)card.open=true;section.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});const heading=section.querySelector('h3');heading.tabIndex=-1;heading.focus({preventScroll:true});};nav.append(button);
   });nav.hidden=!nav.childElementCount;
  }
  const observer=new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(refresh);}});observer.observe(root,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden'],characterData:true});refresh();
 }
})();
