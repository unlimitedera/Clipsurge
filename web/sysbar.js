/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Header: memory meter, unload models, stop service. */

(function(){
 const hr=document.querySelector(".hright");if(!hr)return;
 const mem=document.createElement("div");mem.id="mem";mem.className="memmeter mono";mem.hidden=true;hr.insertBefore(mem,hr.firstChild);
 const stop=document.createElement("button");stop.className="g sm";stop.id="stopb";stop.title="Stop Clipsurge";stop.innerHTML=withIco("stop","Stop",13);
 const rs=document.getElementById("restart");rs.after(stop);
 let last=null,dead=false;
 const gb=n=>n==null?"-":(n>=10?Math.round(n):n.toFixed(1));
 async function tick(){
  if(dead)return;
  try{const m=await jget("/api/memory");last=m;
   const parts=[];
   if(m.vram_total)parts.push(`<span title="Graphics memory in use">VRAM <b>${gb(m.vram_used)}</b>/${gb(m.vram_total)} GB</span>`);
   if(m.storage!=null)parts.push(`<span title="Space Clipsurge uses on disk (videos, clips, models). Click to open the folder." class="stor" id="stor">DISK <b>${m.storage>=1e11?Math.round(m.storage/1e9):(m.storage/1e9).toFixed(1)}</b> GB</span>`);
   parts.push(`<span title="System memory in use">RAM <b>${gb(m.ram_used)}</b>/${gb(m.ram_total)} GB</span>`);
   if(m.llm.loaded)parts.push(`<button class="g sm unl" id="unl" title="Unload ${esc(m.llm.name||"the language model")} (loaded by Clipsurge)">${withIco("power","Unload model",12)}</button>`);
   const h=parts.join("");if(mem.dataset.h!==h){mem.dataset.h=h;mem.innerHTML=h;const u=document.getElementById("unl");if(u)u.onclick=unload;const s=document.getElementById("stor");if(s)s.onclick=()=>post("/api/open-folder",{})}
   mem.hidden=false}
  catch(e){mem.hidden=true}
  setTimeout(tick,5000)}
 async function unload(){
  const u=document.getElementById("unl");if(u)u.disabled=true;
  const busy=last&&last.busy;
  if(busy&&!await confirmBox("Unload model",`${busy} video${busy>1?"s are":" is"} being processed. Unloading the language model can stop AI rating for it. Unload anyway?`,"Unload"))return tick();
  const r=await post("/api/models/unload");if(r.ok)toast("Model unloaded, memory freed");else toast("Could not unload","err");
  tick()}
 stop.onclick=async()=>{
  let st={busy:0};try{st=await jget("/api/status")}catch(e){}
  const m=modal(`<h3>Stop Clipsurge</h3><p class="mu">${st.busy?`<b class="lime">${st.busy}</b> video${st.busy>1?"s are":" is"} being processed. ${st.busy>1?"They":"It"} will pause and can be resumed the next time Clipsurge starts. Finished work is kept.`:"Nothing is being processed right now."}</p>
   <p class="mu small">This closes the service and unloads its models. Start it again with start.bat.</p>
   <div class="mfoot"><button class="g" data-x>Cancel</button><button class="danger" data-go>${withIco("stop","Stop now")}</button></div>`);
  m.box.querySelector("[data-x]").onclick=()=>m.close();
  m.box.querySelector("[data-go]").onclick=async()=>{
   try{await post("/api/stop")}catch(e){}
   dead=true;stopPoll&&stopPoll();m.close();
   document.body.insertAdjacentHTML("beforeend",`<div class="stopped"><div><h2>Clipsurge is stopped</h2><p class="mu">Memory is freed. Run <b>start.bat</b> to start it again, then reload this page.</p><button onclick="location.reload()">Reload</button></div></div>`)}};
 tick()})();
