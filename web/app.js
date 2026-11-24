/* Copyright (c) 2026 unlimitedera. All Rights Reserved. App shell: Projects, Project, Video views. */
let timer=null,view="";
const STAGES=["Get video","Transcribe","Find moments","Crop + captions","Export"];
const IDEAS=["Funny reactions","Clutch plays and comebacks","Rage and screaming","Surprising plot twists","Hot takes and arguments","Tips and tricks explained clearly","Epic fails"];
const AVOID=["Sponsor reads","Menus and loading screens","Long silences"];
const MODES=[["auto","Auto"],["gaming","Gaming"],["podcast","Podcast"],["tutorial","Tutorial"]];
const LAYOPT=[["auto","Auto"],["stack","Webcam + gameplay"],["game","Gameplay only"],["fit","Whole screen + blur"],["follow","Follow face"]];
const opt2=(v,l)=>l.map(([k,t])=>`<option value="${k}" ${String(v)===String(k)?"selected":""}>${t}</option>`).join("");
const app=()=>$("app");
function poll(fn,ms){clearTimeout(timer);const run=async()=>{try{await fn()}catch(e){}timer=setTimeout(run,ms)};run()}
function stopPoll(){clearTimeout(timer);timer=null}

/* ---------- router ---------- */
window.addEventListener("hashchange",route);
function nav(h){location.hash=h}
function route(){
 stopPoll();const h=(location.hash||"#/projects").slice(1);const [path,qs]=h.split("?");const q=new URLSearchParams(qs||"");
 let m;
 $("settingsView").classList.add("hide");app().classList.remove("hide");
 document.querySelectorAll(".nav button").forEach(b=>b.classList.remove("on"));
 if(path=="/settings"){app().classList.add("hide");$("settingsView").classList.remove("hide");$("nv_settings").classList.add("on");loadSettings();return}
 $("nv_projects").classList.add("on");
 if(m=path.match(/^\/p\/([^/]+)\/v\/([^/]+)$/))return videoView(m[1],m[2],q.get("clip"));
 if(m=path.match(/^\/p\/([^/]+)$/))return projectView(m[1],q.get("tab")||"videos");
 projectsView()}
function refreshStatus(){api("/api/status").then(r=>r.json()).then(s=>$("st").textContent=s.llm?"AI: "+s.llm.slice(0,28)+" ("+s.provider+")":"AI: not connected").catch(()=>{})}

/* ---------- projects list ---------- */
async function projectsView(){
 view="projects";
 app().innerHTML=`<div class="phead"><div><h1>Projects</h1><p class="mu">Each project holds videos that share the same goals for what to clip.</p></div><button data-new>+ New project</button></div><div class="pgrid" id="pgrid"></div>`;
 app().querySelector("[data-new]").onclick=newProjectModal;
 poll(async()=>{
  if(view!="projects")return;
  const ps=await jget("/api/projects");
  const html=ps.map(p=>`<a class="pcard" href="#/p/${p.id}" aria-label="Open project ${esc(p.name)}">
   <div class="pthumbs">${[0,1,2].map(i=>p.thumbs[i]?`<img loading="lazy" src="/api/jobs/${p.thumbs[i]}/thumb" alt="">`:`<span></span>`).join("")}</div>
   <div class="pbody"><b>${esc(p.name)}</b><p class="mu clamp">${esc(p.description||(p.brief.ideas.length?"Looking for: "+p.brief.ideas.slice(0,3).join(", "):"No goals set yet"))}</p>
   <div class="pmeta"><span>${p.videos} video${p.videos==1?"":"s"}</span><span>${p.clips} clips</span>${p.running?`<span class="live">${p.running} working</span>`:""}<span class="mu">${p.last?ago(p.last):""}</span></div></div></a>`).join("");
  const g=$("pgrid");if(g&&g.dataset.h!==html){g.dataset.h=html;g.innerHTML=html||`<div class="empty big">No projects yet. Create one to start.</div>`}
 },3000)}

function newProjectModal(){
 const m=modal(`<h3>New project</h3><div class="form">
  <label>Name<input type="text" data-n placeholder="e.g. GTA 6 streams" autofocus></label>
  <label>Description <span class="mu">(optional)</span><input type="text" data-d></label>
  <label>What should the AI look for? <span class="mu">one idea per line</span><textarea data-i rows="4" placeholder="Funny reactions&#10;Clutch plays and comebacks"></textarea></label>
  <div class="chips">${IDEAS.map(t=>`<button type="button" class="chip2" data-add="${esc(t)}">+ ${t}</button>`).join("")}</div>
  <label>Skip these <span class="mu">one per line</span><textarea data-a rows="2" placeholder="Sponsor reads"></textarea></label>
  <div class="two"><label>Video type<select data-mode>${opt2("auto",MODES)}</select></label><label>Clips per video<input type="number" data-c value="5" min="1" max="20"></label></div></div>
  <div class="mfoot"><button class="g" data-x>Cancel</button><button data-ok>Create project</button></div>`);
 const q=s=>m.box.querySelector(s);
 m.box.querySelectorAll("[data-add]").forEach(b=>b.onclick=()=>{const t=q("[data-i]");if(!t.value.split("\n").includes(b.dataset.add))t.value=(t.value.trim()?t.value.trim()+"\n":"")+b.dataset.add});
 q("[data-x]").onclick=()=>m.close();
 q("[data-ok]").onclick=async()=>{
  const name=q("[data-n]").value.trim();if(!name){q("[data-n]").focus();toast("Give the project a name","err");return}
  const r=await post("/api/projects",{name,description:q("[data-d]").value,brief:{ideas:q("[data-i]").value,avoid:q("[data-a]").value},defaults:{mode:q("[data-mode]").value,count:+q("[data-c]").value}});
  const p=await r.json();m.close();nav("/p/"+p.id);setTimeout(()=>addVideosModal(p.id),300)}}

/* ---------- project ---------- */
async function projectView(pid,tab){
 view="project";
 let P;try{P=await jget("/api/projects/"+pid)}catch(e){toast("Project not found","err");nav("/projects");return}
 app().innerHTML=`<nav class="crumbs2"><a href="#/projects">Projects</a><span>/</span><b>${esc(P.name)}</b></nav>
  <div class="phead"><div><h1>${esc(P.name)}</h1><p class="mu">${esc(P.description||"")}</p><div class="ideas" id="ideasrow"></div></div>
  <div class="btns"><button class="g" id="rec">&#9679; Record (OBS)</button><button data-add>+ Add videos</button></div></div>
  <div class="tabs" role="tablist">${[["videos","Videos"],["clips","All clips"],["brief","Goals and settings"]].map(([k,t])=>`<button role="tab" class="${tab==k?"on":""}" data-tab="${k}">${t}</button>`).join("")}</div>
  <div id="ptab"></div>`;
 app().querySelector("[data-add]").onclick=()=>addVideosModal(pid);
 $("rec").onclick=()=>rec(pid);
 app().querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>nav(`/p/${pid}?tab=${b.dataset.tab}`));
 const draw=async()=>{
  if(view!="project")return;
  P=await jget("/api/projects/"+pid);
  $("ideasrow").innerHTML=(P.brief.ideas.length?P.brief.ideas.map(i=>`<span class="chip">${esc(i)}</span>`).join(""):'<span class="mu small">No goals set. Add some under Goals and settings so the AI knows what to look for.</span>');
  if(tab=="videos")drawVideos(P);else if(tab=="clips")drawClips(P);};
 if(tab=="brief"){drawBrief(P)}else poll(draw,2000)}

function vstate(j){
 const run=["running","queued"].includes(j.state);
 const label={done:"Finished",error:"Failed",cancelled:"Cancelled",interrupted:"Interrupted",queued:"Waiting",running:"Working"}[j.state]||j.state;
 return {run,label}}

function drawVideos(P){
 const el=$("ptab");const jobs=P.jobs||[];
 if(!jobs.length){el.innerHTML=`<div class="empty big">No videos yet.<br><button data-a2>+ Add videos</button><p class="mu small">Paste links, pick files from this PC, or upload.</p></div>`;el.querySelector("[data-a2]").onclick=()=>addVideosModal(P.id);return}
 if(!el.querySelector(".vlist")){el.innerHTML='<div class="vlist"></div>'}
 const L=el.querySelector(".vlist");const ids=jobs.map(j=>j.id);
 [...L.children].forEach(c=>{if(!ids.includes(c.dataset.id))c.remove()});
 jobs.forEach((j,idx)=>{
  let row=L.querySelector(`[data-id="${j.id}"]`);
  if(!row){row=document.createElement("article");row.className="vrow";row.dataset.id=j.id;
   row.innerHTML=`<div class="vtop"><a class="vthumb" href="#/p/${P.id}/v/${j.id}"><img alt="" loading="lazy"></a>
    <div class="vinfo"><a class="vtitle" href="#/p/${P.id}/v/${j.id}"></a><div class="mu small vmeta"></div><div class="vprog"></div></div>
    <div class="vact"><a class="btn g sm" href="#/p/${P.id}/v/${j.id}">Open</a><button class="g sm" data-refind title="Pick moments again with the current goals">Re-find</button><button class="g sm" data-cancel>Cancel</button><button class="g sm danger" data-del>Remove</button></div></div><div class="vclips"></div>`;
   row.querySelector("[data-refind]").onclick=async()=>{if(await confirmBox("Re-find moments","This picks moments again using the current goals and renders new clips. Your edits on the old clips are replaced.","Re-find")){await api(`/api/jobs/${j.id}/refind`,{method:"POST"});toast("Looking again")}};
   row.querySelector("[data-cancel]").onclick=async()=>{await api(`/api/jobs/${j.id}/cancel`,{method:"POST"});toast("Cancelling")};
   row.querySelector("[data-del]").onclick=async()=>{if(await confirmBox("Remove video",`Delete "${j.title||"this video"}" and all its clips from the project? Files on disk made by Cliptastic are deleted too.`,"Remove")){const r=await api("/api/jobs/"+j.id,{method:"DELETE"});if(!r.ok)toast((await r.json()).detail,"err");else row.remove()}};
   L.appendChild(row)}
  const {run,label}=vstate(j);
  const img=row.querySelector("img");if(j.video&&!img.src)img.src=`/api/jobs/${j.id}/thumb`;
  const t=row.querySelector(".vtitle");const tt=j.title||j.source;if(t.textContent!==tt)t.textContent=tt;
  row.querySelector(".vmeta").textContent=[j.info?fmt(j.info.duration)+" · "+j.info.width+"x"+j.info.height:"",j.clips.length?j.clips.length+" clips":""].filter(Boolean).join(" · ");
  const pr=row.querySelector(".vprog");
  const html=run?`<div class="bar"><b style="width:${j.overall||0}%"></b></div><div class="small"><b class="lime">${Math.round(j.overall||0)}%</b> <span class="mu">${esc(j.note||"Starting")}${j.detail?" · "+esc(j.detail):""}</span></div>`:`<span class="pill ${j.state}">${label}</span>${j.error&&j.state!="done"?`<span class="mu small"> ${esc(j.error)}</span>`:""}`;
  if(pr.dataset.h!==html){pr.dataset.h=html;pr.innerHTML=html}
  row.querySelector("[data-cancel]").classList.toggle("hide",!run);row.querySelector("[data-refind]").classList.toggle("hide",run||!j.video);row.querySelector("[data-del]").classList.toggle("hide",run);
  const vc=row.querySelector(".vclips");
  const ch=j.clips.map(c=>`<a class="mini" href="#/p/${P.id}/v/${j.id}?clip=${c.id}" title="${esc(c.title||"")}">${c.status=="done"&&c.file?`<img class="pst" loading="lazy" alt="" src="/api/jobs/${j.id}/clips/${c.id}/poster?v=${c.rev||0}">`:`<div class="vph">${c.status=="rendering"?Math.round(((j.cprog||{})[c.id]?.f||0)*100)+"%":"..."}</div>`}<span class="sc">${c.score}</span><small>${esc((c.title||"").slice(0,26))}</small></a>`).join("");
  const key=j.clips.map(c=>c.id+c.status+(c.rev||0)+c.title).join("|")+(run?"|"+Math.round(j.overall||0)/10:"");
  if(vc.dataset.k!==key){vc.dataset.k=key;vc.innerHTML=ch||(j.state=="done"?'<span class="mu small">No moments found in this video.</span>':"")}
 })}

function drawClips(P){
 const el=$("ptab");const all=[];
 (P.jobs||[]).forEach(j=>j.clips.forEach(c=>all.push({j,c})));
 if(!el.querySelector(".fbar")){el.innerHTML=`<div class="fbar"><label>Video <select id="fv"><option value="">All videos</option>${(P.jobs||[]).map(j=>`<option value="${j.id}">${esc((j.title||j.id).slice(0,50))}</option>`).join("")}</select></label><label>Sort <select id="fs"><option value="score">Best score</option><option value="video">By video</option></select></label><span class="mu" id="fc"></span></div><div class="grid" id="cg"></div>`;$("fv").onchange=$("fs").onchange=()=>{el.dataset.k="";drawClips(P)}}
 let items=all.filter(x=>x.c.approved!==false&&(!$("fv").value||x.j.id==$("fv").value));
 if($("fs").value=="score")items.sort((a,b)=>b.c.score-a.c.score);
 $("fc").textContent=items.length+" clips";
 const key=items.map(x=>x.j.id+x.c.id+x.c.status+(x.c.rev||0)).join("|");
 const g=$("cg");if(g.dataset.k===key)return;g.dataset.k=key;
 g.innerHTML=items.map(({j,c})=>`<div class="clip"><div class="phone">${c.file&&c.status=="done"?`<video src="/files/${j.id}/${c.file}?v=${c.rev||0}" poster="/api/jobs/${j.id}/clips/${c.id}/poster?v=${c.rev||0}" controls loop playsinline preload="none"></video>`:`<div class="ph"><span>${esc(c.status)}</span></div>`}</div>
  <div class="row sp"><b class="clamp1">${esc(c.title||"")}</b><span class="score">${c.score}</span></div>
  ${c.idea?`<span class="chip idea">${esc(c.idea)}</span>`:""}
  <div class="mu small">${esc((j.title||"").slice(0,40))} · ${fmt(c.start)}-${fmt(c.end)}</div>
  <div class="row"><a class="btn g sm" href="#/p/${P.id}/v/${j.id}?clip=${c.id}">Open</a><button class="g sm" data-e="${j.id}|${c.id}">Edit</button>${c.file?`<a href="/files/${j.id}/${c.file}" download>MP4</a>`:""}</div></div>`).join("")||'<div class="empty big">No clips yet.</div>';
 g.querySelectorAll("[data-e]").forEach(b=>b.onclick=()=>{const [a,c]=b.dataset.e.split("|");openEditor(a,+c,()=>{g.dataset.k=""})})}

function drawBrief(P){
 const d=P.defaults||{};const el=$("ptab");
 el.innerHTML=`<div class="two big2"><div class="card"><h3>Tell the AI what to look for</h3>
  <p class="mu">Write the kinds of moments you want, one per line. Plain words are fine. Moments that match get a higher score and a label showing which idea they matched.</p>
  <textarea id="bi" rows="7" placeholder="Funny reactions&#10;Someone gets jump scared">${esc(P.brief.ideas.join("\n"))}</textarea>
  <div class="chips">${IDEAS.map(t=>`<button class="chip2" data-add="${esc(t)}">+ ${t}</button>`).join("")}</div>
  <label style="margin-top:12px">Skip these <span class="mu">one per line</span><textarea id="ba" rows="3">${esc(P.brief.avoid.join("\n"))}</textarea></label>
  <div class="chips">${AVOID.map(t=>`<button class="chip2" data-avoid="${esc(t)}">+ ${t}</button>`).join("")}</div>
  <p class="mu small" id="aihint"></p></div>
  <div><div class="card"><h3>Project</h3><div class="form"><label>Name<input type="text" id="bn" value="${esc(P.name)}"></label><label>Description<input type="text" id="bd" value="${esc(P.description||"")}"></label></div></div>
  <div class="card"><h3>Defaults for videos in this project</h3><div class="two"><label>Video type<select id="bm">${opt2(d.mode||"auto",MODES)}</select></label><label>Clips per video<input type="number" id="bc" min="1" max="20" value="${d.count||5}"></label>
   <label>Crop<select id="bl">${opt2(d.layout||"auto",LAYOPT)}</select></label><label>Captions<select id="bk">${opt2(d.captions||"pop",[["pop","Pop"],["clean","Clean"],["fire","Fire"],["off","Off"]])}</select></label>
   <label>Shortest (s)<input type="number" id="bmin" value="${d.minlen||20}"></label><label>Longest (s)<input type="number" id="bmax" value="${d.maxlen||55}"></label></div></div>
  <div class="row" style="justify-content:flex-start;gap:10px"><button id="bsave">Save</button><button class="g" id="bapply">Save and re-find in all videos</button></div>
  ${P.id!="inbox"?`<div class="card danger-zone"><h3>Delete project</h3><p class="mu small">Removes the project, its videos and all clips Cliptastic made. Your original files are not touched.</p><button class="danger" id="bdel">Delete project</button></div>`:""}</div></div>`;
 api("/api/status").then(r=>r.json()).then(s=>{$("aihint").textContent=s.llm?"AI connected: matching uses the model's judgment as well as keywords.":"No AI connected: matching uses your words directly. Connect a model in Settings for smarter matching."});
 el.querySelectorAll("[data-add]").forEach(b=>b.onclick=()=>{const t=$("bi");if(!t.value.split("\n").includes(b.dataset.add))t.value=(t.value.trim()?t.value.trim()+"\n":"")+b.dataset.add});
 el.querySelectorAll("[data-avoid]").forEach(b=>b.onclick=()=>{const t=$("ba");if(!t.value.split("\n").includes(b.dataset.avoid))t.value=(t.value.trim()?t.value.trim()+"\n":"")+b.dataset.avoid});
 const save=async()=>{const r=await post("/api/projects/"+P.id,{name:$("bn").value,description:$("bd").value,brief:{ideas:$("bi").value,avoid:$("ba").value},
  defaults:{mode:$("bm").value,count:+$("bc").value,layout:$("bl").value,captions:$("bk").value,minlen:+$("bmin").value,maxlen:+$("bmax").value}});if(!r.ok){toast("Could not save","err");return false}toast("Saved");return true};
 $("bsave").onclick=save;
 $("bapply").onclick=async()=>{if(!await save())return;const jobs=(P.jobs||[]).filter(j=>j.video&&!["running","queued"].includes(j.state));
  if(!jobs.length){toast("No finished videos to re-find");return}
  if(!await confirmBox("Re-find in all videos",`This re-picks moments in ${jobs.length} video${jobs.length>1?"s":""} with the new goals and renders new clips. Clip edits are replaced.`,"Re-find"))return;
  for(const j of jobs)await api(`/api/jobs/${j.id}/refind`,{method:"POST"});toast("Working on it");nav("/p/"+P.id)};
 const del=$("bdel");if(del)del.onclick=async()=>{if(await confirmBox("Delete project",`Delete "${P.name}" and everything Cliptastic made for it?`,"Delete project")){const r=await api("/api/projects/"+P.id,{method:"DELETE"});if(!r.ok)toast((await r.json()).detail,"err");else nav("/projects")}}}

/* ---------- add videos ---------- */
function addVideosModal(pid){
 const links=[],files=new Map(),ups=[];
 const m=modal(`<h3>Add videos</h3><p class="mu">Each video is clipped using this project's goals.</p>
  <label>Paste links <span class="mu">one per line (YouTube, Twitch, and more)</span><textarea data-l rows="4" placeholder="https://www.youtube.com/watch?v=..." autofocus></textarea></label>
  <div class="row" style="justify-content:flex-start;gap:10px;margin-top:10px"><button class="g" data-browse>Browse this PC...</button><button class="g" data-up>Upload files...</button><input type="file" data-fi multiple accept="video/*" class="hide"></div>
  <div class="sel" data-sel></div>
  <div class="mfoot"><span class="mu" data-n></span><button class="g" data-x>Cancel</button><button data-ok disabled>Add videos</button></div>`,{wide:true});
 const q=s=>m.box.querySelector(s);
 const upd=()=>{const ls=q("[data-l]").value.split("\n").map(x=>x.trim()).filter(Boolean);
  q("[data-sel]").innerHTML=[...files.keys()].map(p=>`<span class="chip">${esc(p.split("/").pop())} <button class="x" data-rm="${esc(p)}" aria-label="Remove">&times;</button></span>`).join("")+ups.map((f,i)=>`<span class="chip">${esc(f.name)} <button class="x" data-ru="${i}" aria-label="Remove">&times;</button></span>`).join("");
  q("[data-sel]").querySelectorAll("[data-rm]").forEach(b=>b.onclick=()=>{files.delete(b.dataset.rm);upd()});
  q("[data-sel]").querySelectorAll("[data-ru]").forEach(b=>b.onclick=()=>{ups.splice(+b.dataset.ru,1);upd()});
  const n=ls.length+files.size+ups.length;q("[data-ok]").disabled=!n;q("[data-ok]").textContent=n?`Add ${n} video${n>1?"s":""}`:"Add videos";q("[data-n]").textContent=""};
 q("[data-l]").oninput=upd;q("[data-x]").onclick=()=>m.close();
 q("[data-browse]").onclick=async()=>{const r=await pickFiles({title:"Choose videos from this PC",okLabel:"Select"});if(r)r.forEach(p=>files.set(p,1));upd()};
 q("[data-up]").onclick=()=>q("[data-fi]").click();q("[data-fi]").onchange=e=>{ups.push(...e.target.files);upd()};
 q("[data-ok]").onclick=async()=>{
  const ls=q("[data-l]").value.split("\n").map(x=>x.trim()).filter(Boolean);q("[data-ok]").disabled=true;
  const src=[...ls,...files.keys()];let n=0;
  if(src.length){const r=await post(`/api/projects/${pid}/videos`,{sources:src});if(r.ok)n+=src.length;else toast("Could not add some videos","err")}
  if(ups.length){const f=new FormData();ups.forEach(x=>f.append("files",x));const r=await api(`/api/projects/${pid}/upload`,{method:"POST",body:f});if(r.ok)n+=ups.length}
  m.close();toast(`${n} video${n==1?"":"s"} added`);nav("/p/"+pid)}}

let recording=false;
async function rec(pid){
 const r=await api(recording?`/api/obs/stop?project=${pid}`:"/api/obs/start",{method:"POST"});
 if(!r.ok){toast((await r.json()).detail,"err");return}
 recording=!recording;$("rec").innerHTML=recording?"&#9632; Stop and clip":"&#9679; Record (OBS)";
 if(!recording)toast("Recording added to the project")}

/* ---------- video ---------- */
async function videoView(pid,jid,focusClip){
 view="video";let P;try{P=await jget("/api/projects/"+pid)}catch(e){nav("/projects");return}
 app().innerHTML=`<nav class="crumbs2"><a href="#/projects">Projects</a><span>/</span><a href="#/p/${pid}">${esc(P.name)}</a><span>/</span><b id="vt">Video</b></nav>
 <div class="layout"><div class="card"><b>Pipeline</b><div id="pipe"></div><div class="mu" id="info" style="margin-top:10px"></div></div>
 <div><div class="card"><div class="row sp"><div><b id="jt"></b> <span id="jchips"></span></div><div class="row"><button class="g sm" id="refind">Re-find with current goals</button></div></div>
  <div id="goals" class="ideas"></div><div class="err" id="jerr"></div><div class="log" id="jlog"></div>
  <div style="margin-top:8px" class="row" ><button id="rbtn" class="hide" onclick="renderPending()">Render pending clips</button><button class="g sm" onclick="rerenderAll()">Re-render all clips</button></div></div>
 <div class="card"><div class="row"><input type="text" id="q" placeholder='Find a moment: "the funny story about the server"' onkeydown="if(event.key==\'Enter\')search()"><button class="g" onclick="search()">Search</button><span id="tl" class="hide"><a id="otio" download>Timeline (.otio)</a> &nbsp; <a id="edl" download>EDL</a></span></div><div id="hits"></div></div>
 <div class="grid" id="grid"></div></div></div>`;
 window.cur=jid;window.curP=pid;window.focusClip=focusClip;
 $("refind").onclick=async()=>{if(await confirmBox("Re-find moments","Pick moments again with the project's current goals? Edits on the old clips are replaced.","Re-find")){await api(`/api/jobs/${jid}/refind`,{method:"POST"});poll1()}};
 poll1()}
function poll1(){poll(async()=>{if(view!="video")return;const j=await jget("/api/jobs/"+cur);paint(j);},1000)}

function subRow(x){
 const pct=Math.round(x.f*100),cls=x.state=="run"?(x.unk?"unk":"on"):x.state;
 const right=x.state=="skip"?"skipped":(x.state=="wait"?"":(x.unk&&x.state=="run"?"working":pct+"%"));
 return `<div class="sub ${cls}"><div class="t"><span>${esc(x.name)}</span><span>${right}</span></div><div class="bar sm"><b style="width:${x.state=="done"||x.state=="skip"?100:pct}%"></b></div>${x.detail&&x.state!="wait"?`<div class="dt">${esc(x.detail)}</div>`:""}</div>`}
function setHTML(id,h){const e=$(id);if(e&&e.dataset.h!==h){e.dataset.h=h;e.innerHTML=h}}
function paint(j){
 const running=["running","queued"].includes(j.state),done=j.state=="done";
 const stages=STAGES.map((s,i)=>{const st=done||i<j.stage?"d":(i==j.stage&&running?"a":"");const pct=st=="d"?100:(st=="a"?Math.round(j.sp*100):0);
  const subs=st=="a"&&j.subs?j.subs.map(subRow).join(""):"";
  return `<div class="step ${st}"><div class="t"><span>${i+1}. ${s}</span><span>${st?pct+"%":""}</span></div><div class="bar"><b style="width:${pct}%"></b></div>${subs?`<div class="subs">${subs}</div>`:""}</div>`}).join("");
 const warn=running&&j.idle>20?`<div class="warn">No new data for ${j.idle}s. The site may be throttling. Cancel and retry, or lower Download quality in Settings.</div>`:"";
 const state=done?"Finished":(j.state=="cancelled"?"Cancelled":(j.state=="interrupted"?"Interrupted by an app restart":(j.state=="error"?"Failed":esc((j.note||"Starting")+(j.detail?" · "+j.detail:"")))));
 setHTML("pipe",`<div class="overall"><div class="t"><b>Overall</b><b>${Math.round(j.overall||0)}%</b></div><div class="bar big"><b style="width:${j.overall||0}%"></b></div><div class="now">${state}</div>${warn}${running?`<button class="g cx" onclick="cancelJob()">Cancel</button>`:(["interrupted","cancelled","error"].includes(j.state)?`<button class="cx" onclick="resumeJob()">Resume</button>`:"")}</div>${stages}`);
 setHTML("info",j.info?fmt(j.info.duration)+" · "+j.info.width+"x"+j.info.height:"");
 $("jt").textContent=j.title||"";$("vt").textContent=(j.title||"Video").slice(0,60);
 setHTML("jchips",`<span class="chip">${j.settings.mode}</span><span class="chip">${j.clips.length} moments</span><span class="chip">${j.state}</span>`);
 const br=j.brief||{};setHTML("goals",(br.ideas||[]).length?`<span class="mu small">Looking for:</span> `+br.ideas.map(i=>`<span class="chip">${esc(i)}</span>`).join(""):"");
 setHTML("jerr",j.error?esc(j.error):"");setHTML("jlog",(j.log||[]).slice(-6).map(esc).join("<br>"));
 $("rbtn").classList.toggle("hide",!j.clips.some(c=>c.approved&&["pending","error"].includes(c.status)));
 $("tl").classList.toggle("hide",!j.clips.some(c=>c.status=="done"));$("otio").href=`/files/${j.id}/timeline.otio`;$("edl").href=`/files/${j.id}/timeline.edl`;
 const grid=$("grid");
 [...grid.children].forEach(el=>{if(!j.clips.some(c=>"clip"+c.id==el.id))el.remove()});
 j.clips.forEach(c=>{let el=document.getElementById("clip"+c.id);if(!el){el=makeClip(c);grid.appendChild(el)}paintClip(el,c,j)});
 if(window.focusClip){const e=document.getElementById("clip"+window.focusClip);if(e){e.scrollIntoView({block:"center"});e.classList.add("flash");window.focusClip=null}}}
function makeClip(c){
 const el=document.createElement("div");el.className="clip";el.id="clip"+c.id;
 el.innerHTML=`<div class="phone"><div class="vslot"></div><div class="ph"><span class="pt">queued</span><div class="bar"><b style="width:0%"></b></div></div><div class="badge hide"><span></span><div class="bar"><b style="width:0%"></b></div></div></div>
  <div class="row sp"><input class="title" data-k="title" style="flex:1;min-width:0"><span class="score"></span></div><div class="tags"></div>
  <div class="row"><label class="mu">Start <input type="number" step="0.5" data-k="start"></label><label class="mu">End <input type="number" step="0.5" data-k="end"></label></div>
  <div class="row sp"><label class="mu keepl"><input type="checkbox" class="keep"> Keep</label><button class="sm" data-edit>Edit</button><button class="g sm rr">Re-render</button></div>
  <div class="row"><button class="g sm ytb hide">Upload</button></div><div class="links"></div>
  <div class="row sch hide"><input type="datetime-local" class="when"><button class="g sm sb">Schedule</button></div>`;
 const id=c.id;
 el.querySelector('[data-k=title]').onchange=e=>edit(id,{title:e.target.value});
 el.querySelector('.keep').onchange=e=>edit(id,{approved:e.target.checked});
 el.querySelector('.rr').onclick=()=>edit(id,{start:+el.querySelector('[data-k=start]').value,end:+el.querySelector('[data-k=end]').value},true);
 el.querySelector('[data-edit]').onclick=()=>openEditor(cur,id,()=>{});
 el.querySelector('.sb').onclick=()=>sched(id);el.querySelector('.ytb').onclick=()=>up(id);
 return el}
function paintClip(el,c,j){
 el.classList.toggle("off",!c.approved);
 const setIn=(sel,val)=>{const i=el.querySelector(sel);if(document.activeElement!==i&&i.dataset.srv!==String(val)){i.value=val;i.dataset.srv=String(val)}};
 setIn('[data-k=title]',c.title||"");setIn('[data-k=start]',c.start);setIn('[data-k=end]',c.end);
 el.querySelector(".keep").checked=c.approved;el.querySelector(".score").textContent=c.score||"-";
 const tg=el.querySelector(".tags"),th=(c.idea?`<span class="chip idea" title="Matched your goal">${esc(c.idea)}</span>`:"")+(c.edit&&Object.keys(c.edit).length?'<span class="chip">edited</span>':"")+(c.tags||[]).map(t=>`<span class="mu small">${esc(t)}</span>`).join(" ");
 if(tg.dataset.h!==th){tg.dataset.h=th;tg.innerHTML=th}
 const pct=Math.round(((j.cprog||{})[c.id]?.f||0)*100);
 const slot=el.querySelector(".vslot"),ph=el.querySelector(".ph"),bd=el.querySelector(".badge"),hasVideo=!!c.file;
 if(hasVideo&&slot.dataset.rev!==String(c.rev)){slot.dataset.rev=String(c.rev);slot.innerHTML=`<video src="/files/${j.id}/${c.file}?v=${c.rev}" poster="/api/jobs/${j.id}/clips/${c.id}/poster?v=${c.rev}" controls loop playsinline preload="none" style="width:100%;height:100%;object-fit:cover"></video>`}
 const busy=["queued","rendering"].includes(c.status);ph.classList.toggle("hide",hasVideo);
 if(!hasVideo){ph.querySelector(".pt").textContent=c.status=="error"?"render failed":(c.status=="rendering"?"Rendering "+pct+"%":(c.status=="queued"?"Waiting in queue":c.status));ph.querySelector("b").style.width=(c.status=="rendering"?pct:0)+"%"}
 bd.classList.toggle("hide",!(hasVideo&&busy));if(hasVideo&&busy){bd.querySelector("span").textContent=c.status=="rendering"?"Re-rendering "+pct+"%":"Queued";bd.querySelector("b").style.width=pct+"%"}
 const L=el.querySelector(".links");
 const lh=c.status=="done"&&c.file?(c.youtube?`<a href="${c.youtube}" target="_blank">On YouTube</a> `:"")+`<a href="/files/${j.id}/${c.file}" download>MP4</a> <a href="/files/${j.id}/${c.file.replace(".mp4",".srt")}" download>SRT</a> <a href="/files/${j.id}/clips/clip${c.id}.ass" download>ASS</a>`:"";
 if(L.dataset.h!==lh){L.dataset.h=lh;L.innerHTML=lh}
 el.querySelector(".ytb").classList.toggle("hide",!(c.status=="done"&&!c.youtube));el.querySelector(".sch").classList.toggle("hide",!(c.status=="done"&&!c.youtube));
 el.querySelector(".rr").disabled=busy;el.querySelector("[data-edit]").disabled=!c.file&&c.status!="pending"&&c.status!="error"&&busy}
async function edit(id,body,render){const r=await post(`/api/jobs/${cur}/clips/${id}?render=${render?"true":"false"}`,body);if(!r.ok)toast((await r.json()).detail,"err")}
async function renderPending(){await api(`/api/jobs/${cur}/render`,{method:"POST"})}
async function rerenderAll(){if(await confirmBox("Re-render all clips","Render every kept clip again?","Re-render"))await api(`/api/jobs/${cur}/rerender-all`,{method:"POST"})}
async function cancelJob(){if(await confirmBox("Cancel this video","Stop processing this video?","Cancel video")){await api(`/api/jobs/${cur}/cancel`,{method:"POST"})}}
async function resumeJob(){await api(`/api/jobs/${cur}/resume`,{method:"POST"})}
async function search(){const q=$("q").value.trim();if(!q||!cur)return;
 const r=await (await api(`/api/jobs/${cur}/search?q=`+encodeURIComponent(q))).json();
 $("hits").innerHTML=r.length?r.map(h=>`<div class="row" style="margin:6px 0"><span class="mu">${fmt(h.start)}-${fmt(h.end)}</span><span style="flex:1;margin:0 10px">${esc(h.text.slice(0,120))}</span><button class="g sm" onclick="addClip(${h.start},${h.end},this.dataset.q)" data-q="${esc(q)}">Make clip</button></div>`).join(""):'<span class="mu">No matches</span>'}
async function addClip(s,e,t){await post(`/api/jobs/${cur}/clips`,{start:s,end:e,title:t});toast("Clip added")}
async function sched(id){const w=document.querySelector(`#clip${id} .when`).value;if(!w){toast("Pick a date and time","err");return}
 const r=await post(`/api/jobs/${cur}/clips/${id}/schedule`,{when:w});toast(r.ok?"Scheduled for YouTube (private). Keep Cliptastic running.":"Failed",r.ok?"":"err")}
async function up(id){const s=await (await api("/api/youtube")).json();
 if(!s.client_file){toast("Add your Google OAuth file at secrets/client_secret.json first (see README)","err");return}
 if(!s.connected){const r=await api("/api/youtube/connect",{method:"POST"});if(!r.ok){toast((await r.json()).detail,"err");return}}
 const r=await api(`/api/jobs/${cur}/clips/${id}/upload`,{method:"POST"});if(!r.ok)toast((await r.json()).detail,"err");else toast("Uploaded")}

refreshStatus();setInterval(refreshStatus,30000);route();
