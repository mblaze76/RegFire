/* Background eligibility for registration previews; field values are never saved. */
(()=>{
 function attach({form,result,price,getContext}){
  const button=form.querySelector('button[type=submit],button:not([type])');let ticket=0,timer=null,rateReady=false,rateText='—',eligibility=null,pending=false,stopped=false;
  function paint(){button.disabled=pending||!rateReady||!eligibility?.can_continue;form.setAttribute('aria-busy',String(pending));if(price)price.textContent=pending||!eligibility?'—':eligibility.status==='pending'?'Price pending':eligibility.can_continue?rateText:'—';}
  async function check(){clearTimeout(timer);const id=++ticket;pending=true;eligibility=null;result.textContent='';paint();
   try{const context=getContext();if(!context)return false;const values={};form.querySelectorAll('[data-membership-field]').forEach(input=>values[input.dataset.membershipField]=input.value);const response=await fetch('/api/events/'+context.event_id+'/membership/check-fields',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({registration_page:context.page,regtype_id:context.regtype_id,subcategory_path:context.subcategory_path||[],values})});const data=await response.json();if(id!==ticket||stopped)return false;if(!response.ok)throw Error();eligibility=data;if(!data.can_continue&&!data.needs_details&&!data.needs_subcategory)result.textContent='We could not confirm eligibility for this registration type. Check your details or contact the organizer.';return !!data.can_continue;
   }catch{if(id===ticket&&!stopped){eligibility=null;result.textContent='We could not check eligibility right now. Please try again shortly or contact the organizer.';}return false;
   }finally{if(id===ticket&&!stopped){pending=false;paint();}}
  }
  function refresh(){stopped=false;clearTimeout(timer);ticket++;eligibility=null;pending=true;result.textContent='';paint();timer=setTimeout(check,450);}
  form.addEventListener('input',e=>{if(e.target.matches('[data-membership-field]'))refresh();});
  // Retry stays on the same form, with no separate membership screen.
  const retry=document.createElement('button');retry.type='button';retry.className='secondary';retry.textContent='Retry eligibility check';retry.hidden=true;result.after(retry);retry.onclick=()=>check();
  const originalPaint=paint;paint=()=>{originalPaint();retry.hidden=pending||!!eligibility?.can_continue||!result.textContent;};
  return {refresh,check,setPricing(ready,text=rateText){rateReady=ready;rateText=text;paint();},clear(){stopped=true;clearTimeout(timer);ticket++;eligibility=null;pending=false;rateReady=false;paint();}};
 }
 window.BackgroundMembership={attach};
})();
