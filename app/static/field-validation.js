/* Accessible focus for browser-validated attendee forms. No answers are saved here. */
(()=>{
 const visible=input=>!input.disabled&&input.type!=='hidden'&&input.getClientRects().length>0;
 function focus(input){if(!input)return;for(let p=input.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;input.scrollIntoView({block:'center',behavior:'auto'});input.focus({preventScroll:true});}
 function attach(form){if(!form||form.dataset.focusValidation)return;form.dataset.focusValidation='true';let scheduled=false;
 function clear(input){const error=document.getElementById(input.dataset.validationError);if(error)error.remove();const ids=(input.getAttribute('aria-describedby')||'').split(' ').filter(id=>id&&id!==input.dataset.validationError);if(ids.length)input.setAttribute('aria-describedby',ids.join(' '));else input.removeAttribute('aria-describedby');input.removeAttribute('aria-invalid');delete input.dataset.validationError;}
 form.addEventListener('invalid',e=>{const input=e.target;if(!visible(input))return;e.preventDefault();clear(input);const error=document.createElement('p');error.id='field-error-'+crypto.randomUUID();error.className='error';error.textContent=input.validationMessage||'Please complete this field.';input.setAttribute('aria-invalid','true');input.dataset.validationError=error.id;input.setAttribute('aria-describedby',[input.getAttribute('aria-describedby'),error.id].filter(Boolean).join(' '));(input.closest('label')||input).insertAdjacentElement('afterend',error);if(!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;focus([...form.elements].find(i=>visible(i)&&i.validity&&!i.validity.valid));});}},true);
 form.addEventListener('input',e=>{if(e.target.validity?.valid)clear(e.target);});form.addEventListener('change',e=>{if(e.target.validity?.valid)clear(e.target);});
 }
 window.RegFireFieldValidation={attach,focus};document.addEventListener('DOMContentLoaded',()=>{for(const id of ['live-contact','preview-form'])attach(document.getElementById(id));});
})();
