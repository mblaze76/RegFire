const menu = document.querySelector('.menu');
const navigation = document.querySelector('nav');
menu.addEventListener('click', () => {const open = menu.getAttribute('aria-expanded') !== 'true';menu.setAttribute('aria-expanded', String(open)); menu.setAttribute('aria-label',open ? 'Close navigation' : 'Open navigation');navigation.classList.toggle('open',open);});
navigation.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{navigation.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');}));
document.addEventListener('keydown', e=>{if(e.key==='Escape' && navigation.classList.contains('open')){navigation.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');menu.focus();}});

document.querySelector('.client-login')?.addEventListener('click',()=>document.querySelector('#client-access').showModal());

const heroVideo=document.querySelector('#hero-teaser');
const soundButton=document.querySelector('#hero-sound');
const playButton=document.querySelector('#hero-play');
const productVideo=document.querySelector('#product-demo');
if(heroVideo && soundButton && playButton && productVideo){
let blocked=false;
const preferenceKey='regfire-teaser-preference';
let preference='sound';try{preference=localStorage.getItem(preferenceKey)||'sound';}catch{}
const remember=value=>{preference=value;try{localStorage.setItem(preferenceKey,value);}catch{}};
function updateVideoControls(){playButton.textContent=heroVideo.ended?'Replay':heroVideo.paused?'Play':'Pause';playButton.setAttribute('aria-label',playButton.textContent+' teaser');soundButton.textContent=blocked||heroVideo.muted||heroVideo.paused?'Play with sound':'Mute sound';soundButton.setAttribute('aria-pressed',String(!heroVideo.muted&&!heroVideo.paused));}
function startTeaser(){productVideo.pause();blocked=false;return heroVideo.play().then(updateVideoControls).catch(()=>{blocked=true;updateVideoControls();});}
heroVideo.removeAttribute('autoplay');
heroVideo.muted=preference==='muted';
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
if(!reducedMotion.matches&&preference!=='paused')startTeaser();
else heroVideo.pause();
reducedMotion.addEventListener('change',event=>{if(event.matches)heroVideo.pause();});
['play','pause','ended','volumechange'].forEach(event=>heroVideo.addEventListener(event,updateVideoControls));
soundButton.addEventListener('click',()=>{if(blocked||heroVideo.muted||heroVideo.paused){heroVideo.currentTime=0;heroVideo.muted=false;remember('sound');startTeaser();}else{heroVideo.muted=true;remember('muted');}updateVideoControls();});
playButton.addEventListener('click',()=>{if(heroVideo.paused||heroVideo.ended){remember(heroVideo.muted?'muted':'sound');startTeaser();}else{remember('paused');heroVideo.pause();}});
productVideo.addEventListener('play',()=>heroVideo.pause());
updateVideoControls();

}
document.querySelector('.skip').addEventListener('click',()=>document.querySelector('#main').focus({preventScroll:true}));
