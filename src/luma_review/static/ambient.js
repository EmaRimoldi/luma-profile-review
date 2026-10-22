/* A quiet particle field, with reduced-motion and page-visibility support. */
(() => {
  'use strict';
  const canvas=document.getElementById('ambient');if(!canvas)return;
  const ctx=canvas.getContext('2d');if(!ctx)return;
  const preference=matchMedia('(prefers-reduced-motion: reduce)');
  let width=0,height=0,frame=0,previous=0,paused=preference.matches;
  const particles=Array.from({length:125},(_,i)=>({x:(i*.61803398875)%1,y:(i*.41421356237)%1,phase:i*.8,r:.45+(i%5)*.15}));
  function size(){width=innerWidth;height=innerHeight;const scale=Math.min(devicePixelRatio||1,1.5);canvas.width=width*scale;canvas.height=height*scale;canvas.style.width=width+'px';canvas.style.height=height+'px';ctx.setTransform(scale,0,0,scale,0,0);draw(0);}
  function draw(time){ctx.clearRect(0,0,width,height);for(const p of particles){const drift=paused?0:time*.000045;const x=(p.x*width+Math.sin(drift+p.phase)*16+width)%width,y=(p.y*height+Math.cos(drift*.6+p.phase)*12+height)%height;ctx.fillStyle='rgba(107,84,132,'+(p.x>.2&&p.x<.82?.09:.22)+')';ctx.beginPath();ctx.arc(x,y,p.r,0,Math.PI*2);ctx.fill();}}
  function tick(time){if(paused||document.hidden){frame=0;return;}if(time-previous>40){draw(time);previous=time;}frame=requestAnimationFrame(tick);}
  function resume(){if(!paused&&!document.hidden&&!frame)frame=requestAnimationFrame(tick);}
  rootToggle();function rootToggle(){window.PeopleMotion={toggle(){paused=!paused;cancelAnimationFrame(frame);frame=0;draw(0);resume();return paused;},get paused(){return paused;}};}
  preference.addEventListener('change',e=>{paused=e.matches;cancelAnimationFrame(frame);frame=0;draw(0);resume();document.dispatchEvent(new Event('people-motion-change'));});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;}else resume();});
  addEventListener('resize',size);size();resume();
})();
