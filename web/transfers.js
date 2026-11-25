/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Upload tray + Transfers page. */

let UP=[],upTimer=null,upTrayOpen=true;
const upDis=()=>{try{return new Set(JSON.parse(localStorage.getItem("ct_up_dis")||"[]"))}catch(e){return new Set()}};
const upDisSave=s=>{try{localStorage.setItem("ct_up_dis",JSON.stringify([...s].slice(-200)))}catch(e){}};
const PAGE_T=Date.now()/1000;
const sz=b=>b>=1e9?(b/1e9).toFixed(2)+" GB":b>=1e6?(b/1e6).toFixed(1)+" MB":Math.max(1,Math.round(b/1e3))+" KB";
const when=t=>{const d=new Date(t*1000);return d.toLocaleDateString(undefined,{month:"short",day:"numeric"})+" "+d.toLocaleTimeString(undefined,{hour:"2-digit",minute:"2-digit"})};
const active=u=>u.state=="queued"||u.state=="uploading";

async function upPoll(){
 clearTimeout(upTimer);
 try{UP=await jget("/api/uploads")}catch(e){}
 drawTray();if(typeof view!="undefined"&&view=="transfers")drawTransfersUploads();
 upTimer=setTimeout(upPoll,UP.some(active)?1000:6000)}
function upKick(){upPoll()}

function drawTray(){
 const dis=upDis();
 const items=UP.filter(u=>active(u)||(!dis.has(u.id)&&((u.t1||0)>PAGE_T-300)));
 let tray=document.getElementById("utray");
 if(!items.length){if(tray)tray.remove();document.documentElement.style.setProperty("--trayh","18px");return}
 if(!tray){tray=document.createElement("div");tray.id="utray";tray.setAttribute("aria-live","polite");document.body.appendChild(tray);
  tray.innerHTML=`<div class="uth"><b></b><span class="grow"></span><button class="uib" data-clr title="Clear finished">Clear</button><button class="uib" data-tog title="Collapse"></button></div><div class="ulist"></div>`;
  tray.querySelector("[data-clr]").onclick=()=>{const d=upDis();UP.filter(u=>!active(u)).forEach(u=>d.add(u.id));upDisSave(d);drawTray()};
  tray.querySelector("[data-tog]").onclick=()=>{upTrayOpen=!upTrayOpen;drawTray()}}
 const act=items.filter(active).length;
 tray.querySelector(".uth b").textContent=act?`Uploading ${act} clip${act>1?"s":""}`:"Uploads";
 tray.querySelector("[data-tog]").innerHTML=upTrayOpen?ico("x",12).replace("x","x"):"▲";tray.querySelector("[data-tog]").textContent=upTrayOpen?"–":"▲";
 tray.classList.toggle("shut",!upTrayOpen);
 const html=items.map(u=>{
  const pct=Math.round((u.progress||0)*100);
  const st=u.state=="done"?`<a href="${u.url}" target="_blank" rel="noopener" class="ulink">${esc(u.url.replace("https://",""))}</a>`:u.state=="error"?`<span class="err small">${esc(u.error||"Failed")}</span>`:`<span class="mu small">${u.state=="queued"?"Waiting to start":"Uploading to YouTube"} · ${sz((u.size||0)*(u.progress||0))} of ${sz(u.size||0)}</span>`;
  return `<div class="uit ${u.state}" data-u="${u.id}"><div class="row sp"><span class="utt">${esc(u.title)}</span><span class="mono small">${u.state=="done"?"Done":u.state=="error"?"Failed":pct+"%"}</span></div>
   <div class="bar sm ub"><b style="width:${u.state=="done"?100:pct}%"></b></div>
   <div class="row sp">${st}<span class="uact">${u.state=="done"?`<button class="uib" data-copy="${esc(u.url)}">Copy link</button>`:""}${u.state=="error"?`<button class="uib" data-retry="${u.jid}|${u.cid}">Retry</button>`:""}${active(u)?"":`<button class="uib" data-dis="${u.id}" title="Remove from this box">✕</button>`}</span></div></div>`}).join("");
 const list=tray.querySelector(".ulist");
 morphInto(list,html);
 list.querySelectorAll("[data-copy]").forEach(b=>b.onclick=()=>{navigator.clipboard.writeText(b.dataset.copy);b.textContent="Copied"});
 list.querySelectorAll("[data-dis]").forEach(b=>b.onclick=()=>{const d=upDis();d.add(b.dataset.dis);upDisSave(d);drawTray()});
 list.querySelectorAll("[data-retry]").forEach(b=>b.onclick=async()=>{const [j,c]=b.dataset.retry.split("|");await post(`/api/jobs/${j}/clips/${c}/upload`);upKick()});
 requestAnimationFrame(()=>document.documentElement.style.setProperty("--trayh",(tray.offsetHeight+30)+"px"))}

/* ---------- Transfers page ---------- */
async function transfersView(){
 view="transfers";
 app().innerHTML=`<div class="phead"><div><h1>Uploads and downloads</h1><p class="mu">What you sent to YouTube, and what Clipsurge and you saved to this computer.</p></div></div>
  <div class="two big2"><div class="card"><div class="row sp"><h3 style="margin:0">Uploads</h3><button class="g sm" id="upClr">Clear finished</button></div><div id="upList"></div></div>
  <div class="card"><div class="row sp"><h3 style="margin:0">Downloaded clips</h3><button class="g sm" id="dlClr">Clear list</button></div><div id="dlClips"></div>
  <h3 style="margin-top:22px">Videos fetched from links</h3><div id="dlVids"></div></div></div>`;
 $("upClr").onclick=async()=>{await api("/api/uploads",{method:"DELETE"});upKick()};
 $("dlClr").onclick=async()=>{await api("/api/downloads",{method:"DELETE"});transfersLoad()};
 drawTransfersUploads();transfersLoad();
 poll(async()=>{if(view!="transfers")return;await transfersLoad()},5000)}
function drawTransfersUploads(){
 const el=$("upList");if(!el)return;
 const h=UP.length?UP.map(u=>{const pct=Math.round((u.progress||0)*100);
  return `<div class="trow ${u.state}"><div class="grow"><div class="utt">${esc(u.title)}</div><div class="mu small">${when(u.t0)} · ${u.privacy||""} · ${sz(u.size||0)}</div>
   ${active(u)?`<div class="bar sm ub"><b style="width:${pct}%"></b></div>`:""}${u.state=="error"?`<div class="err small">${esc(u.error||"")}</div>`:""}</div>
   <div class="trt">${u.state=="done"?`<a href="${u.url}" target="_blank" rel="noopener" class="btn g sm">Open</a><button class="g sm" data-copy="${esc(u.url)}">Copy link</button>`:u.state=="error"?`<button class="g sm" data-retry="${u.jid}|${u.cid}">Retry</button>`:`<b class="mono">${pct}%</b>`}
   ${active(u)?"":`<button class="g sm" data-rm="${u.id}" title="Remove from history">✕</button>`}</div></div>`}).join(""):`<p class="mu small" style="margin-top:12px">Nothing uploaded yet. Use Upload to YouTube on a finished clip.</p>`;
 morphInto(el,h);
 el.querySelectorAll("[data-copy]").forEach(b=>b.onclick=()=>{navigator.clipboard.writeText(b.dataset.copy);b.textContent="Copied"});
 el.querySelectorAll("[data-rm]").forEach(b=>b.onclick=async()=>{await api("/api/uploads?uid="+b.dataset.rm,{method:"DELETE"});upKick()});
 el.querySelectorAll("[data-retry]").forEach(b=>b.onclick=async()=>{const [j,c]=b.dataset.retry.split("|");await post(`/api/jobs/${j}/clips/${c}/upload`);upKick()})}
async function transfersLoad(){
 let d;try{d=await jget("/api/downloads")}catch(e){return}
 const c=$("dlClips"),v=$("dlVids");if(!c)return;
 morphInto(c,d.clips.length?d.clips.map(x=>`<div class="trow"><div class="grow"><div class="utt">${esc(x.title||"Clip")}</div><div class="mu small">${when(x.t)} · ${esc(x.kind.toUpperCase())}</div></div><span class="mono mu small">${x.size?sz(x.size):""}</span></div>`).join(""):`<p class="mu small" style="margin-top:12px">No clips downloaded yet. Use the MP4 link on a clip.</p>`);
 morphInto(v,d.videos.length?d.videos.map(x=>`<div class="trow"><div class="grow"><a class="utt" href="#/p/${x.project}/v/${x.id}">${esc(x.title||x.id)}</a><div class="mu small">${x.t?when(x.t):""} · ${esc((x.source||"").replace(/^https?:\/\//,"").slice(0,60))}</div></div><span class="mono mu small">${sz(x.size)}</span></div>`).join(""):`<p class="mu small">No videos yet.</p>`)}

/* log clip downloads (MP4/SRT/ASS links on a clip card) */
document.addEventListener("click",e=>{const a=e.target.closest&&e.target.closest("a[download]");if(!a)return;
 const m=(a.getAttribute("href")||"").match(/^\/files\/([^/]+)\/clips\/clip(\d+)\.(\w+)$/);if(!m)return;
 post("/api/downloads/clip",{jid:m[1],cid:+m[2],kind:m[3]}).catch(()=>{})},true);
upPoll();
