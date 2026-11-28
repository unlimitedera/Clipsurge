/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Settings > Loaded models: what is in memory right now, and offloading it. */
let LD={t:null,busy:0};
function renderLoaded(){
 const host=document.getElementById("ldHost");if(!host)return;
 host.innerHTML=`<div class="row sp" style="margin-bottom:10px"><span class="mu small">What is in memory right now. This page refreshes by itself.</span><button class="g sm" id="ldAll">Offload all Clipsurge models</button></div><div id="ldList"></div>
  <p class="mu small" style="margin-top:12px">Offloading frees the memory straight away. Clipsurge loads a model again the next time it needs one. Speech recognition is only loaded while a video is being transcribed, so it usually does not show here. Models inside LM Studio or Ollama are listed when those apps are running and connected, and are offloaded only when you press their own button.</p>`;
 document.getElementById("ldAll").onclick=()=>off("all");
 ldTick()}
async function off(id){
 const busy=LD.busy>0;
 if(id!=="all"||busy){const nm=id==="all"?"every Clipsurge model":"this model";
  if(busy&&!await confirmBox("Offload model",`${LD.busy} video${LD.busy>1?"s are":" is"} being processed. Offloading ${nm} can stop AI rating for ${LD.busy>1?"them":"it"}. Offload anyway?`,"Offload"))return;
  if(!busy&&id.startsWith("ext:")&&!await confirmBox("Offload model","This model is loaded by another app. Offload it now?","Offload"))return}
 const r=await post("/api/models/offload",{id});let d={};try{d=await r.json()}catch(e){}
 if(!r.ok)toast(d.detail||"Could not offload","err");else toast((d.offloaded||[]).length?"Offloaded, memory freed":"Nothing was loaded");
 ldTick(true)}
async function ldTick(once){
 clearTimeout(LD.t);const el=document.getElementById("ldList");
 if(!el||document.getElementById("settingsView").classList.contains("hide"))return;
 try{const d=await jget("/api/models/loaded");LD.busy=d.busy;
  const h=d.items.length?d.items.map(m=>`<div class="mrow"><div class="mmain"><b>${esc(m.name)}</b> <span class="chip ${m.external?"":"idea"}">${esc(m.source)}</span><span class="mu small">${esc(m.detail||"")}</span></div>
   <div class="mact">${m.can_offload?`<button class="sm" data-off="${esc(m.id)}">${withIco("power","Offload",13)}</button>`:'<span class="chip">In use</span>'}</div></div>`).join("")
   :'<div class="mu small" style="padding:10px 0">Nothing is loaded right now.</div>';
  if(el.dataset.h!==h){el.dataset.h=h;el.innerHTML=h;el.querySelectorAll("[data-off]").forEach(b=>b.onclick=()=>off(b.dataset.off))}
  document.getElementById("ldAll").disabled=!d.items.some(m=>m.can_offload&&!m.external)}catch(e){}
 if(!once||true)LD.t=setTimeout(ldTick,3000)}
