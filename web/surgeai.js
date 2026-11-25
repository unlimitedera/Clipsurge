/* Copyright (c) 2026 unlimitedera. All Rights Reserved.
   SurgeAI: the animated bot. Every limb is moved by a small animation engine that eases toward the pose it wants,
   so changes of state and activity always blend smoothly.
   Chat states: idle, wave, listening, thinking, talking, happy, sad. While idle he picks random activities:
   drawing, eating, scrolling his phone, reading, drinking coffee, listening to music, napping. */
(function(){
 const INK="#0d1117",LIME="#c6ff3d";
 const clock={off:0};const now=()=>performance.now()/1000+clock.off;
 const defs=document.createElement("div");defs.style.cssText="position:absolute;width:0;height:0;overflow:hidden";
 defs.innerHTML=`<svg width="0" height="0" aria-hidden="true"><defs>
  <linearGradient id="sai-body" x1="0" y1="0" x2="0.8" y2="1"><stop offset="0" stop-color="#e4ff7a"/><stop offset="0.55" stop-color="#c6ff3d"/><stop offset="1" stop-color="#a5e01f"/></linearGradient>
  <linearGradient id="sai-fold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7da514"/><stop offset="1" stop-color="#3f5a08"/></linearGradient>
  <radialGradient id="sai-glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#c6ff3d" stop-opacity=".45"/><stop offset="1" stop-color="#c6ff3d" stop-opacity="0"/></radialGradient>
  <clipPath id="sai-scr"><rect x="54.2" y="74" width="11.6" height="20" rx="1.6"/></clipPath>
 </defs></svg>`;
 document.body.appendChild(defs);

 /* ------------------------------------------------------------ markup */
 window.surgeBot=function(size,state){
  size=size||64;
  const bars=[0,1,2,3,4].map(i=>`<rect x="55.4" y="${75+i*8}" width="${6+(i*5)%5}" height="2.2" rx="1" fill="${["#c6ff3d","#7fd4ff","#ff9ec0","#ffd166","#c6ff3d"][i]}"/><rect x="55.4" y="${78.4+i*8}" width="9" height="1.6" rx=".8" fill="#5a6572"/>`).join("");
  return `<svg class="sai" data-s="${state||"idle"}" viewBox="0 -16 120 168" width="${size}" height="${Math.round(size*168/120)}" role="img" aria-label="SurgeAI">
  <ellipse cx="60" cy="62" rx="62" ry="62" fill="url(#sai-glow)" data-k="glow"/>
  <ellipse data-k="shadow" cx="60" cy="146" rx="26" ry="4.5" fill="#000" opacity=".35"/>
  <g data-k="bot">
   <g data-k="legL"><line x1="46" y1="94" x2="43" y2="128" stroke="#dcf870" stroke-width="5.5" stroke-linecap="round"/><rect x="35" y="126" width="16" height="8" rx="4" fill="${INK}" stroke="${LIME}" stroke-width="1.6"/></g>
   <g data-k="legR"><line x1="74" y1="94" x2="77" y2="128" stroke="#dcf870" stroke-width="5.5" stroke-linecap="round"/><rect x="69" y="126" width="16" height="8" rx="4" fill="${INK}" stroke="${LIME}" stroke-width="1.6"/></g>
   <g data-k="head">
    <path d="M98 65 L69 94 L98 94 Z" fill="url(#sai-fold)" stroke="#5d7d0e" stroke-width="2" stroke-linejoin="round"/>
    <path d="M28 18 H92 Q98 18 98 24 V65 L69 94 H28 Q22 94 22 88 V24 Q22 18 28 18 Z" fill="url(#sai-body)" stroke="#a5e01f" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M30 22 H84 Q58 26 28 52 Z" fill="#fff" opacity=".22"/>
    <path d="M69 94 L98 65" stroke="#fff" stroke-opacity=".5" stroke-width="1.6" stroke-linecap="round"/>
    <g data-k="blush" opacity="0"><ellipse cx="34" cy="62" rx="6" ry="3.4" fill="#ff7b7b" opacity=".5"/><ellipse cx="86" cy="62" rx="6" ry="3.4" fill="#ff7b7b" opacity=".5"/></g>
    <g data-k="look">
     <g data-k="eN"><ellipse data-k="eL" cx="41.5" cy="39.5" rx="5.2" ry="5.6" fill="${INK}"/><ellipse data-k="eR" cx="78.5" cy="39.5" rx="5.2" ry="5.6" fill="${INK}"/></g>
     <g data-k="eH" opacity="0"><path d="M33 42 Q41 33 50 42" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/><path d="M70 42 Q79 33 87 42" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/></g>
     <g data-k="eS" opacity="0"><path d="M33 42 L50 36" stroke="${INK}" stroke-width="4.2" stroke-linecap="round"/><path d="M87 42 L70 36" stroke="${INK}" stroke-width="4.2" stroke-linecap="round"/></g>
     <g data-k="eC" opacity="0"><path d="M33 41 Q41 44.5 50 41" fill="none" stroke="${INK}" stroke-width="3.6" stroke-linecap="round"/><path d="M70 41 Q79 44.5 87 41" fill="none" stroke="${INK}" stroke-width="3.6" stroke-linecap="round"/></g>
    </g>
    <path data-k="mL" d="M50 67 Q60 68.2 70 67" fill="none" stroke="${INK}" stroke-width="3.6" stroke-linecap="round"/>
    <g data-k="mO" opacity="0"><ellipse data-k="mOe" cx="60" cy="68" rx="6" ry="3" fill="${INK}"/><ellipse data-k="mT" cx="60" cy="71" rx="4" ry="2" fill="#ff7b86"/></g>
    <path data-k="mD" d="M47 64 Q60 79 73 64 Z" fill="${INK}" stroke="${INK}" stroke-width="2.5" stroke-linejoin="round" opacity="0"/>
    <path data-k="mK" d="M48 68 q4 -4 8 0 t8 0 t8 0" fill="none" stroke="${INK}" stroke-width="3.4" stroke-linecap="round" opacity="0"/>
    <ellipse data-k="tng" cx="68" cy="71.5" rx="3.2" ry="2.2" fill="#ff7b86" opacity="0"/>
    <g data-k="hp" opacity="0"><path d="M23 40 Q22 2 60 3 Q98 2 97 40" fill="none" stroke="${INK}" stroke-width="5" stroke-linecap="round"/><rect x="13" y="34" width="11" height="22" rx="5" fill="${INK}" stroke="${LIME}" stroke-width="1.6"/><rect x="96" y="34" width="11" height="22" rx="5" fill="${INK}" stroke="${LIME}" stroke-width="1.6"/></g>
   </g>
   <g data-k="pCanvas" opacity="0"><rect x="36" y="72" width="36" height="22" rx="3" fill="#fffdf0" stroke="${INK}" stroke-width="1.5"/><path data-k="doodle" d="" fill="none" stroke="#ff5d73" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></g>
   <g data-k="pBook" opacity="0"><path d="M36 74 L60 78 L60 95 L36 91 Z" fill="#fffdf0" stroke="${INK}" stroke-width="1.4" stroke-linejoin="round"/><path d="M60 78 L84 74 L84 91 L60 95 Z" fill="#f4f0dc" stroke="${INK}" stroke-width="1.4" stroke-linejoin="round"/>
    <path d="M41 80 L56 83 M41 84 L56 87 M41 88 L52 90 M64 83 L79 80 M64 87 L79 84 M64 91 L75 89" stroke="#9aa3ad" stroke-width="1.3" stroke-linecap="round"/><path d="M60 78 V95" stroke="${INK}" stroke-width="1.6"/>
    <g data-k="flap" style="transform-box:view-box;transform-origin:60px 0"><path d="M60 78 L84 74 L84 91 L60 95 Z" fill="#fffdf0" stroke="${INK}" stroke-width="1.4" stroke-linejoin="round"/><path d="M64 83 L79 80 M64 87 L79 84" stroke="#9aa3ad" stroke-width="1.3" stroke-linecap="round"/></g></g>
   <path data-k="armLo" d="" fill="none" stroke="#a5e01f" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
   <path data-k="armRo" d="" fill="none" stroke="#a5e01f" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
   <path data-k="armL" d="" fill="none" stroke="#e6ff8f" stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round"/>
   <path data-k="armR" d="" fill="none" stroke="#e6ff8f" stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round"/>
   <g data-k="pPhone" opacity="0"><rect x="52" y="71" width="16" height="25" rx="3.2" fill="#10151b" stroke="${LIME}" stroke-width="1.3"/><rect x="54.2" y="74" width="11.6" height="20" rx="1.6" fill="#1b2330"/><g clip-path="url(#sai-scr)"><g data-k="feed">${bars}</g></g><rect x="57.5" y="72.2" width="5" height="1.1" rx=".5" fill="#2a3340"/></g>
   <g data-k="pCookie" opacity="0"><circle data-k="ck" cx="0" cy="0" r="6" fill="#dba15a" stroke="#8a5a24" stroke-width="1.2"/><circle cx="-2" cy="-1.5" r="1" fill="#5a3512"/><circle cx="2" cy="1.5" r="1" fill="#5a3512"/><circle cx="1" cy="-3" r=".8" fill="#5a3512"/></g>
   <circle data-k="cr0" r="1.2" fill="#dba15a" opacity="0"/><circle data-k="cr1" r="1" fill="#dba15a" opacity="0"/><circle data-k="cr2" r="1.1" fill="#c8893f" opacity="0"/>
   <g data-k="pCup" opacity="0"><path d="M-5 -6 H5 V4 Q5 7 2 7 H-2 Q-5 7 -5 4 Z" fill="#fffdf0" stroke="${INK}" stroke-width="1.3"/><path d="M5 -3 Q10 -3 10 1 Q10 4 5 3" fill="none" stroke="${INK}" stroke-width="1.3"/><rect x="-4" y="-5" width="8" height="2.2" fill="#7a4a24"/></g>
   <g data-k="steam" opacity="0"><path d="M-2 -10 q-3 -4 0 -7 t0 -7" fill="none" stroke="#fff" stroke-opacity=".7" stroke-width="1.4" stroke-linecap="round"/><path d="M2 -9 q-3 -4 0 -7 t0 -6" fill="none" stroke="#fff" stroke-opacity=".5" stroke-width="1.2" stroke-linecap="round"/></g>
   <g data-k="pPencil" opacity="0"><rect x="-1.3" y="-11" width="2.6" height="12" rx="1" fill="#ffb703" stroke="${INK}" stroke-width=".6"/><path d="M-1.3 1 L0 4.4 L1.3 1 Z" fill="#f3d9a8" stroke="${INK}" stroke-width=".5"/></g>
   <circle data-k="hL" r="4.6" fill="#f4ffc4" stroke="#a5e01f" stroke-width="1.4"/>
   <circle data-k="hR" r="4.6" fill="#f4ffc4" stroke="#a5e01f" stroke-width="1.4"/>
   <g data-k="dots" opacity="0"><circle cx="96" cy="2" r="2.6" fill="${LIME}"/><circle cx="104" cy="-5" r="3.6" fill="${LIME}"/><circle cx="114" cy="-13" r="4.8" fill="${LIME}"/></g>
   <g data-k="spark" opacity="0"><path d="M14 8 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#fff6a8"/><path d="M104 20 l1.6 4 4 1.6 -4 1.6 -1.6 4 -1.6 -4 -4 -1.6 4 -1.6z" fill="#fff6a8"/></g>
   <g data-k="zzz" opacity="0"><text data-k="z0" x="90" y="10" font-family="Arial,sans-serif" font-weight="700" font-size="13" fill="#9ad7ff">Z</text><text data-k="z1" x="90" y="10" font-family="Arial,sans-serif" font-weight="700" font-size="13" fill="#9ad7ff">Z</text><text data-k="z2" x="90" y="10" font-family="Arial,sans-serif" font-weight="700" font-size="13" fill="#9ad7ff">Z</text></g>
   <g data-k="notes" opacity="0"><g data-k="n0"><circle cx="0" cy="0" r="2.6" fill="#7fd4ff"/><path d="M2.4 0 V-9 q3 0 4 3" fill="none" stroke="#7fd4ff" stroke-width="1.6" stroke-linecap="round"/></g><g data-k="n1"><circle cx="0" cy="0" r="2.6" fill="#ff9ec0"/><path d="M2.4 0 V-9 q3 0 4 3" fill="none" stroke="#ff9ec0" stroke-width="1.6" stroke-linecap="round"/></g><g data-k="n2"><circle cx="0" cy="0" r="2.6" fill="${LIME}"/><path d="M2.4 0 V-9 q3 0 4 3" fill="none" stroke="${LIME}" stroke-width="1.6" stroke-linecap="round"/></g></g>
  </g></svg>`};

 /* ------------------------------------------------------------ engine */
 const reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
 const ACTS=["draw","eat","scroll","read","coffee","music","sleep"];
 const DUR={draw:8.5,eat:8,scroll:9,read:8.5,coffee:8.5,music:8.5,sleep:9.5};
 const K={y:6,rot:6,sx:9,sy:9,lookX:7,lookY:7,eyeSX:10,eyeSY:34,eN:12,eH:12,eS:12,eC:12,curv:12,mW:10,open:24,mO:20,mD:14,mK:12,blush:5,tng:10,hp:6,
   pCanvas:7,pBook:7,pPhone:7,pCookie:9,pCup:9,pPencil:9,steam:6,dots:8,spark:10,zzz:6,notes:6,lLegR:10,rLegR:10,hLx:5.6,hLy:5.6,hRx:5.6,hRy:5.6,tilt:7};
 const HANG=()=>({y:0,rot:0,sx:1,sy:1,lookX:0,lookY:0,eyeSX:1,eyeSY:1,eN:1,eH:0,eS:0,eC:0,curv:1.2,mW:10,open:0,mO:0,mD:0,mK:0,blush:0,tng:0,hp:0,
   pCanvas:0,pBook:0,pPhone:0,pCookie:0,pCup:0,pPencil:0,steam:0,dots:0,spark:0,zzz:0,notes:0,lLegR:0,rLegR:0,hLx:13,hLy:87,hRx:107,hRy:87,tilt:0});
 const insts=[];const seen=new WeakSet();
 const q=(r,k)=>r.querySelector(`[data-k=${k}]`);
 const ease=x=>x<0?0:x>1?1:x*x*(3-2*x);
 function setup(svg){
  const els={};svg.querySelectorAll("[data-k]").forEach(e=>els[e.dataset.k]=e);
  const i={svg,els,cur:HANG(),tg:HANG(),state:svg.dataset.s||"idle",st0:now(),act:null,actAt:0,nextAct:now()+1.5+Math.random()*2.5,last:null,blinkAt:now()+2,blink:0,crumbT:-9,bites:0,seed:Math.random()*100,timer:null,init:false};
  svg._sai=i;insts.push(i);return i}
 function scan(){document.querySelectorAll("svg.sai").forEach(s=>{if(!seen.has(s)){seen.add(s);setup(s)}})}
 /* two-bone arm: shoulder S, hand T, elbow bends outward */
 function arm(S,T,side){
  const L=15,dx=T[0]-S[0],dy=T[1]-S[1];let d=Math.hypot(dx,dy);const dd=Math.min(Math.max(d,5),29.6);
  const base=Math.atan2(dy,dx),a=Math.acos((L*L+dd*dd-L*L)/(2*L*dd));
  const ang=side<0?base+a:base-a;const E=[S[0]+L*Math.cos(ang),S[1]+L*Math.sin(ang)];
  const H=d>29.6?[S[0]+dx/d*29.6,S[1]+dy/d*29.6]:T;
  return {E,H,d:`M${S[0]} ${S[1]} L${E[0].toFixed(2)} ${E[1].toFixed(2)} L${H[0].toFixed(2)} ${H[1].toFixed(2)}`}}

 function pose(i,t){
  const g=HANG(),tg=i.tg;Object.assign(tg,g);
  const T=t-i.st0,w=t+i.seed;
  /* neutral: gentle breathing, drifting eyes, swaying hands */
  tg.y=-1.4-1.4*Math.sin(w*1.7);tg.lookX=2.4*Math.sin(w*.55)*(Math.sin(w*.23)>0?1:0.25);tg.lookY=-.4*Math.sin(w*.4);
  tg.hLx=13+1.3*Math.sin(w*1.2);tg.hRx=107-1.3*Math.sin(w*1.2+1);tg.hLy=87+1.2*Math.sin(w*1.7);tg.hRy=87+1.2*Math.sin(w*1.7+.8);
  tg.lLegR=1.2*Math.sin(w*1.2);tg.rLegR=-1.2*Math.sin(w*1.2);
  const S=i.state;
  if(S==="idle"){
   if(!i.act&&t>i.nextAct&&!reduce){let a;do{a=ACTS[(Math.random()*ACTS.length)|0]}while(a===i.last);i.act=a;i.actAt=t;i.last=a;i.bites=0}
   if(i.act&&t-i.actAt>DUR[i.act]){i.act=null;i.nextAct=t+2.4+Math.random()*4}
   if(i.act)activity(i,tg,i.act,t-i.actAt,w)}
  else{ if(i.act){i.act=null;i.nextAct=t+3} state(i,tg,S,t-i.st0,w)}
  /* blinking (only when the eyes are the plain ones) */
  if(t>i.blinkAt){i.blink=t+.13;i.blinkAt=t+2.2+Math.random()*3.8}
  if(t<i.blink)tg.eyeSY*=0.08;
 }
 function state(i,tg,S,s,w){
  if(S==="wave"){tg.eN=0;tg.eH=1;tg.mL=0;tg.mD=1;tg.blush=1;tg.hRx=108+4*Math.sin(s*11);tg.hRy=30+3*Math.sin(s*11+1.2);tg.rot=-2;tg.y-=1}
  else if(S==="listening"){tg.rot=-4+Math.sin(w*2)*.6;tg.eyeSX=1.12;tg.eyeSY=1.5;tg.lookX=0;tg.open=.25;tg.hLx=11;tg.hLy=44+2*Math.sin(w*2);tg.lookY=0}
  else if(S==="thinking"){tg.lookX=3.4;tg.lookY=-3;tg.rot=3.5+1.5*Math.sin(w*1.2);tg.mK=1;tg.dots=1;tg.hRx=76;tg.hRy=79+1.5*Math.sin(w*2.4);tg.hLx=58;tg.hLy=96;tg.rLegR=-9*Math.max(0,Math.sin(w*4.5))}
  else if(S==="talking"){const n=Math.abs(Math.sin(w*9.5))*(0.55+0.45*Math.abs(Math.sin(w*2.7)));tg.open=.12+.9*n;tg.y=-2.5*Math.abs(Math.sin(w*5));tg.lookX=0;tg.lookY=0;
   tg.hLx=13-4*Math.sin(w*3.1);tg.hLy=87-24*Math.max(0,Math.sin(w*3.1));tg.hRx=107+4*Math.sin(w*3.1+2);tg.hRy=87-24*Math.max(0,Math.sin(w*3.1+2));tg.lLegR=5*Math.sin(w*5);tg.rLegR=-5*Math.sin(w*5)}
  else if(S==="happy"){tg.eN=0;tg.eH=1;tg.mD=1;tg.blush=1;tg.spark=1;tg.y=-9*Math.abs(Math.sin(s*5.6));tg.sy=1+.03*Math.cos(s*11);tg.sx=1-.02*Math.cos(s*11);tg.hLx=7+2*Math.sin(s*9);tg.hLy=40;tg.hRx=113-2*Math.sin(s*9);tg.hRy=40}
  else if(S==="sad"){tg.eN=0;tg.eS=1;tg.curv=-6;tg.y=3.5;tg.rot=-2.5;tg.lookX=0;tg.hLx=20;tg.hLy=88;tg.hRx=100;tg.hRy=88}
  tg.mL=S==="wave"||S==="happy"?0:1}
 function activity(i,tg,a,s,w){
  const dur=DUR[a],fin=ease((dur-s)/0.9),fade=ease(s/0.6)*fin;   /* props fade in and out */
  if(a==="draw"){
   tg.pCanvas=fade;tg.pPencil=fade;tg.lookY=2.6;tg.lookX=0;tg.rot=3*Math.sin(s*1.3);tg.hLx=39;tg.hLy=88;
   const dd=dur-2.2,p=Math.min(1,Math.max(0,(s-.8)/dd));const px=u=>[43+u*27,84+3.2*Math.sin(u*13)-u*5];
   const pts=[];for(let k=0;k<=36;k++){const u=p*k/36;pts.push(px(u))}i.doodle=pts.map((c,k)=>(k?"L":"M")+c[0].toFixed(1)+" "+c[1].toFixed(1)).join(" ");
   const hp=p<1?px(p):[80,76];tg.hRx=s<.8?58:hp[0]+(p<1?0:0);tg.hRy=s<.8?78:hp[1];tg.tng=p<1&&s>.8?1:0;tg.open=0;tg.eyeSY=.9;
   if(p>=1){tg.eN=0;tg.eH=1;tg.mD=1;tg.mL=0;tg.blush=.8;tg.lookY=0}}
  else if(a==="eat"){
   const C=2.4,b=Math.min(3,Math.floor((s-.4)/C)),ph=s-.4-b*C;tg.pCookie=s<5? (ease(s/.5)*(b<3?1:0)):0;
   const done=b>=3;tg.hLx=14;tg.hLy=88;
   if(done||s<.4){tg.hRx=86;tg.hRy=80;tg.pCookie=done?0:ease(s/.4);tg.blush=done?1:0;if(done){tg.eN=0;tg.eH=1;tg.mD=1;tg.mL=0}}
   else{
    const up=ease(ph/.55)*(1-ease((ph-1.45)/.6));tg.hRx=86-17*up;tg.hRy=80-10*up;
    const chew=ph>.65&&ph<1.55;tg.open=ph>.45&&ph<.7?.95:chew?.2+.22*Math.abs(Math.sin((ph-.65)*17)):0;
    tg.blush=chew?.8:0;if(chew){tg.eN=0;tg.eH=1;}
    if(ph>.6&&i.bites<=b){i.bites=b+1;i.crumbT=s}
    tg.pCookie=1}
   i.ckR=6.2-1.7*Math.min(3,i.bites);tg.y+=0;tg.rot=2*Math.sin(w)}
  else if(a==="scroll"){
   tg.pPhone=fade;tg.lookY=3.2;tg.eyeSY=.58;tg.rot=4;tg.y+=1.6;tg.hLx=52.5;tg.hLy=93;
   const sp=(s*1.05)%1,sw=sp<.4?ease(sp/.4):1-ease((sp-.4)/.6);tg.hRx=68;tg.hRy=92-9*sw;i.feed=-((s*17)%16);
   tg.mL=1;tg.curv=(Math.sin(s*2.1)>.82)?6:.2;tg.eyeSX=1;if(Math.sin(s*1.3+1)>.93){tg.eyeSY=1.2}}
  else if(a==="read"){
   tg.pBook=fade;tg.hLx=36;tg.hLy=92;tg.hRx=84;tg.hRy=90;tg.lookY=2.2;const m=(s*.8)%1;tg.lookX=-3+6*Math.min(1,m*1.25);tg.rot=1.5*Math.sin(s*.8);tg.curv=0;
   const fp=((s-1.4)%3.2)/.55;i.flip=fp>=0&&fp<=1?fp:-1}
  else if(a==="coffee"){
   const C=3.4,ph=(s-.5)%C,on=s>.5&&s<dur-1.4;tg.pCup=fade;tg.hLx=30;tg.hLy=84;
   const up=on?ease(ph/.7)*(1-ease((ph-1.7)/.7)):0;tg.hRx=84-13*up;tg.hRy=82-12*up;i.cupTilt=-24*up;
   const sip=on&&ph>.7&&ph<1.7;if(sip){tg.eN=0;tg.eH=1;tg.open=.2;tg.mL=0}
   tg.steam=fade*(sip?0:1);tg.blush=s>dur-2?.8:0;if(s>dur-2){tg.eN=0;tg.eH=1;tg.mD=1;tg.mL=0}}
  else if(a==="music"){
   const B=.56,b=s/B,bn=Math.abs(Math.sin(Math.PI*b));tg.hp=fade;tg.notes=fade;tg.eN=0;tg.eH=1;tg.blush=.6;tg.y=-4*bn;tg.rot=4*Math.sin(Math.PI*b);
   tg.hLx=11-3*Math.sin(Math.PI*b);tg.hLy=84-18*Math.max(0,Math.sin(Math.PI*b));tg.hRx=109+3*Math.sin(Math.PI*b);tg.hRy=84-18*Math.max(0,-Math.sin(Math.PI*b));
   tg.lLegR=10*Math.sin(Math.PI*b);tg.rLegR=10*Math.sin(Math.PI*b+Math.PI);tg.open=.1+.32*Math.abs(Math.sin(s*5.2))*(Math.sin(s*.9)>0?1:.3);tg.mL=0;tg.mO=1;tg.sy=1+.025*bn;tg.sx=1-.015*bn}
  else if(a==="sleep"){
   const yawn=ease(s/.5)*(1-ease((s-1.8)/.6)),sl=ease((s-2)/.8)*(1-ease((s-8)/.35)),wk=ease((s-8.1)/.2)*(1-ease((s-9.2)/.5));
   tg.hLx=13+15*yawn;tg.hLy=87-62*yawn;tg.hRx=107-15*yawn;tg.hRy=87-62*yawn;tg.open=yawn*1.1+sl*(.1+.05*Math.sin(s*2.2))+wk*.6;
   tg.eN=0;tg.eC=(yawn>.1||sl>.1)?1:0;tg.eN=(yawn>.1||sl>.1)?0:1;tg.sy=1+.05*yawn+.02*sl*Math.sin(s*2.2);tg.sx=1-.03*yawn;
   tg.y=3.5*sl-9*wk;tg.rot=sl*(-6+4*Math.sin(s*.85))+0;tg.zzz=sl;tg.lookX=0;tg.lookY=0;if(wk>.05){tg.eyeSX=1.25;tg.eyeSY=1.5;tg.eN=1;tg.eC=0}}}

 let last=now();
 function frame(){
  const t=now(),dt=Math.min(.05,t-last);last=t;
  if(!document.hidden)tick(t,dt);
  requestAnimationFrame(frame)}
 function tick(t,dt){
  for(let n=insts.length-1;n>=0;n--){
   const i=insts[n];if(!i.svg.isConnected){insts.splice(n,1);continue}
   if(i.svg.getBoundingClientRect().width===0)continue;
   if(!i.state||i.state!==i.svg.dataset.s){i.state=i.svg.dataset.s||"idle";i.st0=t}
   pose(i,t);const c=i.cur,g=i.tg;
   /* critically damped spring toward the wanted pose: eases in and out, never jumps, whatever the target does */
   const v=i.vel||(i.vel={});
   for(const k in g){if(!i.init){c[k]=g[k];v[k]=0;continue}
    const w=1.35*(K[k]||8),e=Math.exp(-w*dt),d=c[k]-g[k],tmp=(v[k]||0)+w*d;c[k]=g[k]+(d+tmp*dt)*e;v[k]=((v[k]||0)-w*tmp*dt)*e}
   i.init=true;
   draw(i,t)}}
 /* test helper: run the animation forward by a number of seconds without waiting (background tabs do not run animation frames) */
 window.surgeBotSim=function(sec,fps){fps=fps||30;const dt=1/fps;for(let k=0;k<sec*fps;k++){clock.off+=dt;tick(now(),dt)}};
 const set=(e,a,v)=>e&&e.setAttribute(a,v);
 function draw(i,t){
  const E=i.els,c=i.cur;
  set(E.bot,"transform",`translate(60 94) rotate(${c.rot.toFixed(2)}) scale(${c.sx.toFixed(3)} ${c.sy.toFixed(3)}) translate(-60 -94) translate(0 ${c.y.toFixed(2)})`);
  const sh=1-Math.min(.35,Math.max(-.2,-c.y/30));set(E.shadow,"transform",`translate(60 146) scale(${sh.toFixed(3)} 1) translate(-60 -146)`);set(E.shadow,"opacity",(.35*sh).toFixed(2));
  set(E.legL,"transform",`rotate(${c.lLegR.toFixed(2)} 46 94)`);set(E.legR,"transform",`rotate(${c.rLegR.toFixed(2)} 74 94)`);
  set(E.look,"transform",`translate(${c.lookX.toFixed(2)} ${c.lookY.toFixed(2)})`);
  const es=(el,cx)=>set(el,"transform",`translate(${cx} 39.5) scale(${c.eyeSX.toFixed(3)} ${Math.max(.06,c.eyeSY).toFixed(3)}) translate(${-cx} -39.5)`);es(E.eL,41.5);es(E.eR,78.5);
  set(E.eN,"opacity",Math.max(0,c.eN).toFixed(2));set(E.eH,"opacity",Math.max(0,c.eH).toFixed(2));set(E.eS,"opacity",Math.max(0,c.eS).toFixed(2));set(E.eC,"opacity",Math.max(0,c.eC).toFixed(2));
  const op=Math.min(1,Math.max(0,c.open)),lineV=Math.max(0,1-op*4)*(1-c.mD)*(1-c.mK)*(i.state==="idle"&&i.act==="music"?0:1);
  set(E.mL,"d",`M${60-c.mW} 67 Q60 ${(67+c.curv).toFixed(2)} ${60+c.mW} 67`);set(E.mL,"opacity",Math.max(0,Math.min(1,1-op*4-c.mD-c.mK)).toFixed(2));
  set(E.mO,"opacity",(op>.02?1:0)*Math.min(1,op*6));set(E.mOe,"ry",(1.2+op*5.6).toFixed(2));set(E.mOe,"rx",(4+op*3.4).toFixed(2));set(E.mOe,"cy",(67.5+op*1.4).toFixed(2));
  set(E.mT,"opacity",op>.55?((op-.55)*2.4).toFixed(2):0);set(E.mT,"cy",(69.5+op*3).toFixed(2));
  set(E.mD,"opacity",c.mD.toFixed(2));set(E.mK,"opacity",c.mK.toFixed(2));set(E.tng,"opacity",c.tng.toFixed(2));set(E.blush,"opacity",Math.min(1,Math.max(0,c.blush)).toFixed(2));set(E.hp,"opacity",c.hp.toFixed(2));
  /* arms */
  const L=arm([22,60],[c.hLx,c.hLy],-1),R=arm([98,60],[c.hRx,c.hRy],1);
  set(E.armLo,"d",L.d);set(E.armL,"d",L.d);set(E.armRo,"d",R.d);set(E.armR,"d",R.d);
  set(E.hL,"cx",L.H[0].toFixed(2));set(E.hL,"cy",L.H[1].toFixed(2));set(E.hR,"cx",R.H[0].toFixed(2));set(E.hR,"cy",R.H[1].toFixed(2));
  /* props */
  const po=(e,v)=>set(e,"opacity",Math.min(1,Math.max(0,v)).toFixed(2));
  po(E.pCanvas,c.pCanvas);po(E.pBook,c.pBook);po(E.pPhone,c.pPhone);po(E.pCookie,c.pCookie);po(E.pCup,c.pCup);po(E.pPencil,c.pPencil);po(E.steam,c.steam);po(E.dots,c.dots);po(E.spark,c.spark);po(E.zzz,c.zzz);po(E.notes,c.notes);
  if(c.pCanvas>.01)set(E.doodle,"d",i.doodle||"");
  if(c.pPencil>.01)set(E.pPencil,"transform",`translate(${R.H[0].toFixed(2)} ${(R.H[1]+1).toFixed(2)}) rotate(-24)`);
  if(c.pPhone>.01)set(E.feed,"transform",`translate(0 ${(i.feed||0).toFixed(2)})`);
  if(c.pBook>.01){const f=i.flip;if(f>=0){set(E.flap,"transform",`scale(${Math.cos(Math.PI*f).toFixed(3)} 1)`);set(E.flap,"opacity",1)}else set(E.flap,"opacity",0)}
  if(c.pCookie>.01){set(E.pCookie,"transform",`translate(${(R.H[0]+2.5).toFixed(2)} ${(R.H[1]-3.5).toFixed(2)})`);set(E.ck,"r",Math.max(.1,i.ckR||6).toFixed(2))}
  const cs=i.act==="eat"?(now()-i.st0):0;
  ["cr0","cr1","cr2"].forEach((k,n)=>{const e=E[k];if(!e)return;const w2=i.act==="eat"?(t-i.actAt-.4-i.crumbT)+.4-0:99;const u=i.act==="eat"?((t-i.actAt)-i.crumbT-0):99;
   if(i.act==="eat"&&u>=0&&u<.8){set(e,"opacity",(1-u/.8).toFixed(2));set(e,"cx",(66+n*3-3+u*(n-1)*6).toFixed(1));set(e,"cy",(72+u*u*50+u*6).toFixed(1))}else set(e,"opacity",0)});
  if(c.pCup>.01){set(E.pCup,"transform",`translate(${(R.H[0]+2).toFixed(2)} ${(R.H[1]-5).toFixed(2)}) rotate(${(i.cupTilt||0).toFixed(1)})`);set(E.steam,"transform",`translate(${(R.H[0]+2).toFixed(2)} ${(R.H[1]-5).toFixed(2)})`)}
  if(c.zzz>.01)["z0","z1","z2"].forEach((k,n)=>{const u=((t*.5+n/3)%1);set(E[k],"transform",`translate(${(u*14).toFixed(1)} ${(-u*26).toFixed(1)}) scale(${(.6+u*.7).toFixed(2)})`);set(E[k],"opacity",(Math.sin(Math.PI*u)).toFixed(2))});
  if(c.notes>.01)["n0","n1","n2"].forEach((k,n)=>{const u=((t*.7+n/3)%1);set(E[k],"transform",`translate(${(96+n*6+Math.sin(u*6+n)*5).toFixed(1)} ${(34-u*44).toFixed(1)})`);set(E[k],"opacity",Math.sin(Math.PI*u).toFixed(2))});
  if(c.dots>.01)E.dots.querySelectorAll("circle").forEach((d,n)=>{const u=.55+.55*Math.max(0,Math.sin(t*5.2-n*.9));d.setAttribute("transform",`translate(${d.getAttribute("cx")} ${d.getAttribute("cy")}) scale(${u.toFixed(2)}) translate(-${d.getAttribute("cx")} -${d.getAttribute("cy")})`)});
  if(c.spark>.01)E.spark.setAttribute("transform",`rotate(${(Math.sin(t*3)*8).toFixed(1)} 60 20)`)}
 /* a state set from outside; with ms it falls back to idle afterwards. "act:draw" starts an activity at once. */
 window.botState=function(root,s,ms){
  (root.matches&&root.matches(".sai")?[root]:root.querySelectorAll(".sai")).forEach(el=>{
   const i=el._sai||(seen.add(el),setup(el));clearTimeout(i.timer);
   if(s.startsWith("act:")){el.dataset.s="idle";i.state="idle";i.act=s.slice(4);i.actAt=now();i.last=i.act;i.bites=0;return}
   el.dataset.s=s;i.state=s;i.st0=now();if(ms)i.timer=setTimeout(()=>{el.dataset.s="idle";i.state="idle";i.nextAct=now()+3},ms)})};
 scan();setInterval(scan,400);requestAnimationFrame(frame);
})();
