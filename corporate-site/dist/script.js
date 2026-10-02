const menu = document.querySelector('.menu');
const navigation = document.querySelector('nav');
menu.addEventListener('click', () => {const open = menu.getAttribute('aria-expanded') !== 'true';menu.setAttribute('aria-expanded', String(open)); menu.setAttribute('aria-label',open ? 'Close navigation' : 'Open navigation');navigation.classList.toggle('open',open);});
navigation.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{navigation.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');}));
document.addEventListener('keydown', e=>{if(e.key==='Escape' && navigation.classList.contains('open')){navigation.classList.remove('open');menu.setAttribute('aria-expanded','false');menu.setAttribute('aria-label','Open navigation');menu.focus();}});

document.querySelector('.client-login').addEventListener('click',()=>document.querySelector('#client-access').showModal());

const heroVideo=document.querySelector('#hero-teaser');
const soundButton=document.querySelector('#hero-sound');
const playButton=document.querySelector('#hero-play');
const productVideo=document.querySelector('#product-demo');
function updateVideoControls(){playButton.textContent=heroVideo.ended?'Replay':heroVideo.paused?'Play':'Pause';playButton.setAttribute('aria-label',playButton.textContent+' teaser');soundButton.textContent=heroVideo.muted?'Play with sound':'Mute sound';soundButton.setAttribute('aria-pressed',String(!heroVideo.muted));}
heroVideo.muted=true;
heroVideo.play().catch(updateVideoControls);
['play','pause','ended','volumechange'].forEach(event=>heroVideo.addEventListener(event,updateVideoControls));
soundButton.addEventListener('click',()=>{if(heroVideo.muted){heroVideo.currentTime=0;heroVideo.muted=false;productVideo.pause();heroVideo.play().catch(updateVideoControls);}else heroVideo.muted=true;updateVideoControls();});
playButton.addEventListener('click',()=>{if(heroVideo.paused||heroVideo.ended){productVideo.pause();heroVideo.play().catch(updateVideoControls);}else heroVideo.pause();});
productVideo.addEventListener('play',()=>heroVideo.pause());
updateVideoControls();
