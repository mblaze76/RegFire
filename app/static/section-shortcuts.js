(()=>{
 for(const [id,selector] of [['builder-view','#builder-form > section'],['demographics-view','#demo-editor > section'],['sessions-view','.sessions-editor > section']]){
  const root=document.getElementById(id);if(!root)continue;
  const nav=document.createElement('nav');nav.className='setup-navigation page-section-shortcuts';nav.setAttribute('aria-label','Page section shortcuts');
  root.querySelector('.page-heading,.builder-heading')?.after(nav);
  let signature='',pending=false;
  function refresh(){
   pending=false;const sections=Array.from(root.querySelectorAll(selector)).filter(section=>!section.hidden);
   const labels=sections.map(section=>section.querySelector('h3')?.textContent.trim()||'');
   const next=labels.join('|');if(next===signature)return;signature=next;nav.replaceChildren();
   sections.forEach((section,index)=>{if(!labels[index])return;const button=document.createElement('button');button.type='button';button.textContent=labels[index];
    button.onclick=()=>{section.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});const heading=section.querySelector('h3');heading.tabIndex=-1;heading.focus({preventScroll:true});};nav.append(button);
   });nav.hidden=!nav.childElementCount;
  }
  const observer=new MutationObserver(()=>{if(!pending){pending=true;requestAnimationFrame(refresh);}});observer.observe(root,{subtree:true,childList:true,attributes:true,attributeFilter:['hidden'],characterData:true});refresh();
 }
})();
