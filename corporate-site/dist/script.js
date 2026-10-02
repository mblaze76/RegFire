const menu = document.querySelector('.menu');
const navigation = document.querySelector('nav');
menu.addEventListener('click', () => {const open = menu.getAttribute('aria-expanded') !== 'true';menu.setAttribute('aria-expanded', String(open)); menu.setAttribute('aria-label',open ? 'Close navigation' : 'Open navigation');navigation.classList.toggle('open',open);});
navigation.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{navigation.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');}));
document.addEventListener('keydown', e=>{if(e.key==='Escape' && navigation.classList.contains('open')){navigation.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');menu.focus();}});

document.querySelector('.client-login').addEventListener('click',()=>document.querySelector('#client-access').showModal());
