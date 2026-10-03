/* Position only: pointer movement never submits or changes a conversation. */
(()=>{
 const mascot=document.querySelector('.spark-launcher'),panel=document.querySelector('.spark-panel');if(!mascot||!panel)return;
 const key='regfire.spark.position.v1',pad=8;let point=null,drag=null,suppress=false;
 try{const value=JSON.parse(localStorage.getItem(key));if(value&&Number.isFinite(value.x)&&Number.isFinite(value.y))point=value;}catch{}
 mascot.title='Drag Spark anywhere. Use arrow keys to move; Home resets the corner.';
 mascot.setAttribute('aria-label','Ask Spark. Drag or use arrow keys to reposition; Home resets.');
 const reset=document.createElement('button');reset.type='button';reset.className='spark-position-reset';reset.textContent='Reset position';reset.title='Return Spark to the bottom right';panel.append(reset);
 const tail=document.createElementNS('http://www.w3.org/2000/svg','svg');tail.classList.add('spark-position-tail');tail.setAttribute('aria-hidden','true');tail.innerHTML='<path fill="#fffdf8" stroke="#e8cda9" stroke-width="1.2"/>';document.body.append(tail);
 function store(){try{if(point)localStorage.setItem(key,JSON.stringify(point));else localStorage.removeItem(key);}catch{}}
 function place(){
  const w=document.documentElement.clientWidth,h=innerHeight,mw=mascot.offsetWidth,mh=mascot.offsetHeight;
  const x=Math.max(pad,Math.min(w-mw-pad,point?point.x*(w-mw):w-mw-24));
  const y=Math.max(pad,Math.min(h-mh-pad,point?point.y*(h-mh):h-mh-18));
  Object.assign(mascot.style,{left:x+'px',top:y+'px',right:'auto',bottom:'auto'});
  tail.style.display=panel.hidden?'none':'block';if(panel.hidden)return;
  const room=Math.max(y,h-y-mh),compact=w<600;
  panel.style.width=Math.min(355,w-pad*2)+'px';panel.style.maxWidth=(w-pad*2)+'px';
  panel.style.maxHeight=Math.max(140,compact?room-24:h-pad*2)+'px';
  let pw=panel.offsetWidth,ph=panel.offsetHeight,px,py;
  if(x>=pw+30){px=x-pw-24;py=y+mh*.5-ph;}
  else if(w-x-mw>=pw+30){px=x+mw+24;py=y+mh*.5-ph;}
  else {px=x+mw/2-pw/2;py=y>h-y-mh?y-ph-22:y+mh+22;}
  px=Math.max(pad,Math.min(w-pw-pad,px));py=Math.max(pad,Math.min(h-ph-pad,py));
  Object.assign(panel.style,{left:px+'px',top:py+'px',right:'auto',bottom:'auto'});
  const mx=x+mw*.5,my=y+mh*.66;
  let ax=Math.max(px+22,Math.min(px+pw-22,mx)),ay=my<py?py:my>py+ph?py+ph:my;
  if(my>=py&&my<=py+ph)ax=mx<px?px:px+pw;
  tail.setAttribute('width',w);tail.setAttribute('height',h);
  const horizontal=ax===px||ax===px+pw;
  tail.firstElementChild.setAttribute('d',horizontal?`M ${ax} ${ay-9} Q ${(ax+mx)/2} ${ay} ${mx} ${my} Q ${(ax+mx)/2} ${ay+9} ${ax} ${ay+9}`:`M ${ax-9} ${ay} Q ${ax} ${(ay+my)/2} ${mx} ${my} Q ${ax+9} ${(ay+my)/2} ${ax+9} ${ay}`);
 }
 function move(x,y){point={x:Math.max(0,Math.min(1,x/Math.max(1,innerWidth-mascot.offsetWidth))),y:Math.max(0,Math.min(1,y/Math.max(1,innerHeight-mascot.offsetHeight)))};place();}
 mascot.addEventListener('pointerdown',e=>{if(e.button!==0||!e.isPrimary)return;const r=mascot.getBoundingClientRect();drag={id:e.pointerId,x:e.clientX,y:e.clientY,left:r.left,top:r.top,moved:false};mascot.setPointerCapture(e.pointerId);});
 mascot.addEventListener('pointermove',e=>{if(!drag||e.pointerId!==drag.id)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(!drag.moved&&Math.hypot(dx,dy)<6)return;drag.moved=true;mascot.classList.add('is-dragging');move(drag.left+dx,drag.top+dy);});
 function finish(e){if(!drag||e.pointerId!==drag.id)return;suppress=drag.moved;if(drag.moved)store();drag=null;mascot.classList.remove('is-dragging');setTimeout(()=>suppress=false,0);}
 mascot.addEventListener('pointerup',finish);mascot.addEventListener('pointercancel',finish);
 mascot.addEventListener('click',e=>{if(suppress){e.preventDefault();e.stopImmediatePropagation();}},true);
 mascot.addEventListener('keydown',e=>{if(e.key==='Home'){e.preventDefault();point=null;store();place();return;}const d={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];if(!d)return;e.preventDefault();const r=mascot.getBoundingClientRect(),step=e.shiftKey?40:12;move(r.left+d[0]*step,r.top+d[1]*step);store();});
 reset.onclick=()=>{point=null;store();place();mascot.focus();};
 new MutationObserver(place).observe(panel,{attributes:true,attributeFilter:['hidden']});new ResizeObserver(place).observe(panel);
 window.addEventListener('resize',place);place();
})();
