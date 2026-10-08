/* Attendee-owned LinkedIn consent; fills blank fields only, never logs in to RegFire. */
(()=>{
 const fields={'first-name':'given_name','last-name':'family_name',email:'email'};
 function attach({button,status,target,getFlow}){
  let available=false,popup=null,request=null,flow=null,expiry=null,closed=null;
  button.disabled=true;
  status.textContent='Checking LinkedIn availability…';
  fetch('/api/linkedin/status').then(async response=>{
   const data=await response.json();available=response.ok&&data.available===true;button.disabled=!available;
   status.textContent=available?'Import your name and available email with your permission. Existing entries stay unchanged.':'LinkedIn is not connected yet. You can enter your details below.';
  }).catch(()=>{status.textContent='LinkedIn is unavailable. You can enter your details below.';});
  function finish(){clearTimeout(expiry);clearInterval(closed);request=null;button.disabled=!available;}
  button.onclick=()=>{
   if(!available)return;
   flow=getFlow();if(!flow)return;
   request=crypto.randomUUID();
   popup=window.open('/api/linkedin/start?flow='+encodeURIComponent(flow)+'&request='+encodeURIComponent(request),'regfire-linkedin-'+request,'popup,width=620,height=760');
   if(!popup){status.textContent='Allow the LinkedIn popup, or enter your details below.';finish();return;}
   button.disabled=true;status.textContent='Complete LinkedIn consent in the new window. Your entries will stay here.';
   expiry=setTimeout(()=>{status.textContent='LinkedIn import expired. Try again or enter your details below.';finish();},600000);
   closed=setInterval(()=>{if(popup?.closed){status.textContent='LinkedIn window closed. Your entries are unchanged.';finish();}},1000);
  };
  window.addEventListener('message',event=>{
   const data=event.data;
   if(!request||event.origin!==location.origin||event.source!==popup||data?.type!=='regfire-linkedin-profile'||data.request!==request||data.flow!==flow)return;
   if(getFlow()!==flow){status.textContent='The registration flow changed. Please start LinkedIn import again.';finish();return;}
   let count=0;
   if(data.profile&&typeof data.profile==='object'){
    for(const input of target.querySelectorAll('[data-profile-field]')){
     const value=data.profile[fields[input.dataset.profileField]];
     if(!input.value.trim()&&typeof value==='string'&&value.length<=254){
      input.value=value;input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));count++;
     }
    }
    status.textContent=count?'Filled '+count+' empty fields. Review your details before continuing.':'No empty matching fields were available. Your entries are unchanged.';
   }else status.textContent=data.message||'LinkedIn import was not completed. Your entries are unchanged.';
   finish();
  });
 }
 window.LinkedInImport={attach,field(input,field){if(fields[field.id]&&['text','email'].includes(field.type))input.dataset.profileField=field.id;}};
})();
