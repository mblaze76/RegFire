/* Shared email format and confirmation checks for registration previews. */
(() => {
 const normalize=value=>value.trim().toLowerCase();
 function formatError(value){
  if(!value)return '';
  const parts=value.split('@');
  if(parts.length!==2||value.length>254)return 'Enter a valid email address, such as name@example.com.';
  const [local,domain]=parts,labels=domain.split('.');
  if(!local||local.length>64||local.startsWith('.')||local.endsWith('.')||local.includes('..')||/[^a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]/.test(local)||labels.length<2||labels.some(x=>!x||x.length>63||!/^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$/.test(x))||!/^[a-zA-Z]{2,}$/.test(labels.at(-1)))return 'Enter a valid email address, such as name@example.com.';
  return '';
 }
 function attach(input,container,{value='',onchange=()=>{}}={}){
  input.autocomplete='email';input.spellcheck=false;input.autocapitalize='none';
  const confirm=document.createElement('input');confirm.type='email';confirm.id=input.id+'-confirm';confirm.autocomplete='off';confirm.spellcheck=false;confirm.autocapitalize='none';confirm.value=value;
  const label=document.createElement('label');label.textContent='Confirm email'+(input.required?' *':'');label.htmlFor=confirm.id;label.append(confirm);
  const error=document.createElement('p');error.id=input.id+'-email-error';error.className='error';error.setAttribute('aria-live','polite');error.hidden=true;
  input.setAttribute('aria-describedby',error.id);confirm.setAttribute('aria-describedby',error.id);container.append(label,error);
  let touched=false;
  function validate(show=false){const a=normalize(input.value),b=normalize(confirm.value);confirm.required=input.required||!!a;const primary=formatError(a);let secondary=formatError(b);if(!secondary&&b&&a!==b)secondary='Email addresses do not match.';input.setCustomValidity(primary);confirm.setCustomValidity(secondary);const message=primary||secondary||(show&&confirm.required&&!b?'Please confirm your email address.':'');error.textContent=message;error.hidden=!message||!show;input.setAttribute('aria-invalid',String(!!primary));confirm.setAttribute('aria-invalid',String(!!secondary||(show&&confirm.required&&!b)));}
  const clearResult=()=>{for(const id of ['live-contact-result','preview-feedback']){const result=document.getElementById(id);if(result)result.textContent='';}};input.addEventListener('input',()=>{clearResult();validate(touched);});confirm.addEventListener('input',()=>{clearResult();onchange(confirm.value);validate(touched);});
  for(const field of [input,confirm]){field.addEventListener('blur',()=>{touched=true;validate(true);});field.addEventListener('invalid',()=>{touched=true;validate(true);});}
  validate();return confirm;
 }
 window.EmailValidation={attach};
})();

window.PhoneConsent={attach(input,container,eventName,{checked=false,onchange=()=>{}}={}){
 const label=document.createElement('label');label.className='check-label sms-consent';
 const box=document.createElement('input');box.type='checkbox';box.id=input.id+'-sms-consent';box.checked=checked;box.onchange=()=>onchange(box.checked);
 const text=document.createElement('span');text.textContent='By checking this box, I agree to receive automated informational and promotional text messages from '+(eventName||'the event organizer')+' at the mobile number I provided. Consent is optional and is not a condition of registration or purchase. Message frequency varies. Message and data rates may apply. Reply STOP to opt out.';
 label.append(box,text);container.append(label);return box;
}};
