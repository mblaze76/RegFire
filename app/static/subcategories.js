/* Nested choices inherit their root registration type's rate and eligibility. */
(()=>{
 const paths=new Map();
 function render(target,type){
  if(!type?.subcategories?.length)return;
  const key=target.id+':'+type.id,path=paths.get(key)||[];
  const group=document.createElement('div');group.className='subcategory-choices';target.append(group);
  function draw(){
   group.replaceChildren();let parent=type,depth=0;
   while(parent.subcategories?.length){
    const options=parent.subcategories,label=document.createElement('label'),select=document.createElement('select');
    label.append(document.createTextNode('Choose '+(parent.name||'category')+' subcategory *'));
    select.required=true;select.name='subcategory-'+depth;select.append(new Option('Choose an option',''));
    for(const child of options)select.append(new Option(child.name||'Unnamed subcategory',child.id));
    const chosen=options.find(child=>child.id===path[depth]);select.value=chosen?.id||'';
    const level=depth;select.onchange=()=>{path.splice(level,path.length-level,...(select.value?[select.value]:[]));paths.set(key,path);draw();};
    label.append(select);group.append(label);
    if(!chosen){path.splice(depth);break;}parent=chosen;depth++;
   }
  }
  draw();
 }
 window.RegFireSubcategories={render,clear(){paths.clear();}};
})();
