/* Public marketing measurement only. No form values, query strings or private paths. */
(()=>{'use strict';
 const pages=new Set(['/','/contact/','/products/regfire/','/products/lead-fire/','/products/ignite/','/products/blaze/','/products/groundswell/']);
 if(location.hostname!=='regfire.events'||!pages.has(location.pathname))return;
 const id='G-6FBJ0NEPKF',key='regfire-analytics-consent';let started=false;
 const choice=()=>{try{return localStorage.getItem(key);}catch{return null;}};
 function start(){if(started)return;started=true;window.dataLayer=window.dataLayer||[];function tag(){window.dataLayer.push(arguments);}window.gtag=tag;
 tag('consent','default',{analytics_storage:'granted',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
 tag('js',new Date());tag('config',id,{send_page_view:false,allow_google_signals:false,allow_ad_personalization_signals:false,page_location:location.origin+location.pathname,page_referrer:document.referrer?new URL(document.referrer).origin:'',ignore_referrer:document.referrer.includes('/investors')});
 tag('event','page_view',{page_location:location.origin+location.pathname,page_title:document.title});
 const script=document.createElement('script');script.async=true;script.src='https://www.googletagmanager.com/gtag/js?id='+id;document.head.append(script);
 document.addEventListener('click',e=>{if(choice()!=='accepted')return;const a=e.target.closest('a');if(!a)return;const u=new URL(a.href,location.href);if(u.origin!==location.origin||!pages.has(u.pathname))return;if(u.pathname.startsWith('/products/'))tag('event','product_interest',{product:u.pathname.split('/')[2]});else if(u.pathname==='/contact/')tag('event','contact_page_click');});
 }
 const box=document.createElement('aside');box.className='analytics-consent';box.setAttribute('aria-label','Optional website analytics');const text=document.createElement('p');text.textContent='Allow optional Google Analytics cookies to help us understand visits to our public website? We do not track registration forms or private investor pages.';box.append(text);
 const actions=document.createElement('div');box.append(actions);
 for(const [label,value]of [['Allow analytics','accepted'],['No thanks','declined']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=()=>{try{localStorage.setItem(key,value);}catch{}window['ga-disable-'+id]=value!=='accepted';if(value==='accepted')start();else{window.gtag?.('consent','update',{analytics_storage:'denied'});for(const name of document.cookie.split(';').map(v=>v.trim().split('=')[0]).filter(n=>n.startsWith('_ga'))){document.cookie=name+'=; Max-Age=0; path=/';document.cookie=name+'=; Max-Age=0; path=/; domain=.regfire.events';}}box.hidden=true;};actions.append(b);}
 document.body.append(box);box.hidden=!!choice();if(choice()==='accepted')start();
 const settings=document.createElement('button');settings.type='button';settings.className='analytics-settings';settings.textContent='Privacy choices';settings.onclick=()=>{box.hidden=false;actions.querySelector('button').focus();};(document.querySelector('footer')||document.body).append(settings);
})();
