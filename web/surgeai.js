/* Copyright (c) 2026 unlimitedera. All Rights Reserved. SurgeAI: the animated bot. States: idle, wave, listening, thinking, talking, happy, sad. */
(function(){
 const defs=document.createElement("div");defs.style.cssText="position:absolute;width:0;height:0;overflow:hidden";
 defs.innerHTML=`<svg width="0" height="0" aria-hidden="true"><defs>
  <linearGradient id="sai-body" x1="0" y1="0" x2="0.8" y2="1"><stop offset="0" stop-color="#e4ff7a"/><stop offset="0.55" stop-color="#c6ff3d"/><stop offset="1" stop-color="#a5e01f"/></linearGradient>
  <linearGradient id="sai-fold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7da514"/><stop offset="1" stop-color="#3f5a08"/></linearGradient>
  <linearGradient id="sai-limb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f0ffb0"/><stop offset="1" stop-color="#cdf55a"/></linearGradient>
  <radialGradient id="sai-glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#c6ff3d" stop-opacity=".45"/><stop offset="1" stop-color="#c6ff3d" stop-opacity="0"/></radialGradient>
 </defs></svg>`;
 document.body.appendChild(defs);
 const INK="#0d1117";
 window.surgeBot=function(size,state){
  size=size||64;
  return `<svg class="sai" data-s="${state||"idle"}" viewBox="0 -16 120 168" width="${size}" height="${Math.round(size*168/120)}" role="img" aria-label="SurgeAI">
  <ellipse class="s-glow" cx="60" cy="62" rx="62" ry="62" fill="url(#sai-glow)"/>
  <ellipse class="s-shadow" cx="60" cy="146" rx="26" ry="4.5" fill="#000" opacity=".35"/>
  <g class="s-bot">
   <g class="s-leg l"><line x1="46" y1="94" x2="43" y2="128" stroke="url(#sai-limb)" stroke-width="5.5" stroke-linecap="round"/><rect x="35" y="126" width="16" height="8" rx="4" fill="${INK}" stroke="#c6ff3d" stroke-width="1.6"/></g>
   <g class="s-leg r"><line x1="74" y1="94" x2="77" y2="128" stroke="url(#sai-limb)" stroke-width="5.5" stroke-linecap="round"/><rect x="69" y="126" width="16" height="8" rx="4" fill="${INK}" stroke="#c6ff3d" stroke-width="1.6"/></g>
   <g class="s-arm l"><line x1="22" y1="62" x2="6" y2="47" stroke="url(#sai-limb)" stroke-width="5" stroke-linecap="round"/><circle cx="5" cy="46" r="4.6" fill="#f4ffc4" stroke="#a5e01f" stroke-width="1.4"/></g>
   <g class="s-arm r"><line x1="98" y1="62" x2="114" y2="47" stroke="url(#sai-limb)" stroke-width="5" stroke-linecap="round"/><circle cx="115" cy="46" r="4.6" fill="#f4ffc4" stroke="#a5e01f" stroke-width="1.4"/></g>
   <g class="s-head">
    <path d="M98 65 L69 94 L98 94 Z" fill="url(#sai-fold)" stroke="#5d7d0e" stroke-width="2" stroke-linejoin="round"/>
    <path d="M28 18 H92 Q98 18 98 24 V65 L69 94 H28 Q22 94 22 88 V24 Q22 18 28 18 Z" fill="url(#sai-body)" stroke="#a5e01f" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M30 22 H84 Q58 26 28 52 Z" fill="#fff" opacity=".22"/>
    <path d="M69 94 L98 65" stroke="#fff" stroke-opacity=".5" stroke-width="1.6" stroke-linecap="round"/>
    <g class="s-blush"><ellipse cx="34" cy="62" rx="6" ry="3.4" fill="#ff7b7b" opacity=".45"/><ellipse cx="86" cy="62" rx="6" ry="3.4" fill="#ff7b7b" opacity=".45"/></g>
    <g class="s-look">
     <g class="s-eyes"><rect class="e l" x="33" y="36" width="17" height="7" rx="3.5" fill="${INK}" transform="rotate(5 41 40)"/><rect class="e r" x="70" y="36" width="17" height="7" rx="3.5" fill="${INK}" transform="rotate(-5 79 40)"/></g>
     <g class="s-eyes-happy"><path d="M33 42 Q41 33 50 42" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/><path d="M70 42 Q79 33 87 42" fill="none" stroke="${INK}" stroke-width="4" stroke-linecap="round"/></g>
     <g class="s-eyes-sad"><path d="M33 42 L50 36" stroke="${INK}" stroke-width="4.2" stroke-linecap="round"/><path d="M87 42 L70 36" stroke="${INK}" stroke-width="4.2" stroke-linecap="round"/></g>
    </g>
    <g class="s-mouth">
     <path class="m closed" d="M49 66 Q60 70 71 66" fill="none" stroke="${INK}" stroke-width="3.6" stroke-linecap="round"/>
     <ellipse class="m o1" cx="60" cy="67" rx="6" ry="3.4" fill="${INK}"/>
     <g class="m o2"><ellipse cx="60" cy="68" rx="7.5" ry="6.4" fill="${INK}"/><ellipse cx="60" cy="71.6" rx="4.4" ry="2.4" fill="#ff7b86"/></g>
     <path class="m smile" d="M47 64 Q60 79 73 64 Z" fill="${INK}" stroke="${INK}" stroke-width="2.5" stroke-linejoin="round"/>
     <path class="m think" d="M48 68 q4 -4 8 0 t8 0 t8 0" fill="none" stroke="${INK}" stroke-width="3.4" stroke-linecap="round"/>
     <path class="m sad" d="M49 71 Q60 62 71 71" fill="none" stroke="${INK}" stroke-width="3.6" stroke-linecap="round"/>
    </g>
   </g>
  </g>
  <g class="s-dots"><circle cx="96" cy="2" r="2.6" fill="#c6ff3d"/><circle cx="104" cy="-5" r="3.6" fill="#c6ff3d"/><circle cx="114" cy="-13" r="4.8" fill="#c6ff3d"/></g>
  <g class="s-spark"><path d="M14 8 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#fff6a8"/><path d="M104 20 l1.6 4 4 1.6 -4 1.6 -1.6 4 -1.6 -4 -4 -1.6 4 -1.6z" fill="#fff6a8"/></g>
 </svg>`};
 /* set a state; with ms it falls back to idle afterwards */
 window.botState=function(root,s,ms){
  (root.querySelectorAll?root.querySelectorAll(".sai"):[root]).forEach(el=>{
   clearTimeout(el._t);el.dataset.s=s;if(ms)el._t=setTimeout(()=>{el.dataset.s="idle"},ms)})};
})();
