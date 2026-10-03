/* Reusable native picker + precise hex value + RegFire palette. */
(()=>{
 const controls=[];
 for(const input of document.querySelectorAll('input[type=color]')){
  const label=input.closest('label'),name=label?.textContent.trim()||'Color',wrap=document.createElement('div');wrap.className='color-control';
  const hex=document.createElement('input');hex.type='text';hex.maxLength=7;hex.pattern='#[0-9a-fA-F]{6}';hex.placeholder='#RRGGBB';hex.setAttribute('aria-label',name+' hex');hex.autocomplete='off';hex.spellcheck=false;hex.value=input.value;
  const palette=document.createElement('div');palette.className='color-palette';palette.setAttribute('role','group');palette.setAttribute('aria-label',name+' palette');
  function apply(value){input.value=value;hex.value=value;hex.setCustomValidity('');input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));}
  hex.oninput=()=>{if(/^#[0-9a-f]{6}$/i.test(hex.value))apply(hex.value);else hex.setCustomValidity('Use a six-digit color, for example #FF6A00.');};
  input.addEventListener('input',()=>{hex.value=input.value;hex.setCustomValidity('');});
  for(const [title,value] of [['Charcoal','#24242a'],['White','#ffffff'],['Flame orange','#ff6a00'],['Deep red','#a60000'],['Gold','#ffbd18'],['Slate','#555c68']]){const button=document.createElement('button');button.type='button';button.style.background=value;button.setAttribute('aria-label','Use '+title+' for '+name);button.title=title+' '+value;button.onclick=()=>apply(value);palette.append(button);}
  wrap.append(hex,palette);label.after(wrap);controls.push({input,hex});
 }
 function sync(){for(const {input,hex} of controls){hex.disabled=input.disabled;if(document.activeElement!==hex){hex.value=input.value;hex.setCustomValidity('');}}}
 new MutationObserver(sync).observe(document.querySelector('main'),{childList:true,subtree:true});window.ColorControls={sync};sync();
})();
