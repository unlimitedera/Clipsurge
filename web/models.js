/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Model hub: hardware, speech models, local AI models. */
let MH={dl:{},speech:null,local:null,hw:null,hits:[],repo:null,files:[],q:""};
const dots=n=>"●".repeat(n)+"○".repeat(5-n);
const FIT={gpu:["Fits on GPU","ok"],part:["Partly on GPU","warn"],cpu:["CPU only","warn"],no:["Too big","bad"]};
const gbf=n=>n>=1?n.toFixed(1)+" GB":Math.round(n*1024)+" MB";

async function renderModelHub(){
 const host=$("modelHub");if(!host)return;
 host.innerHTML=`<div class="card"><h3>Hardware and memory</h3><div id="mhHw"></div></div>
  <div class="card"><h3>Speech models</h3><p class="mu small">Used to turn speech into captions. Pick one, or leave it on Auto and Clipsurge chooses the best model that fits your free memory.</p><div id="mhSpeech"></div>
   <div class="row" style="justify-content:flex-start;gap:8px;margin-top:12px"><input type="text" id="mhCustom" placeholder="Other Hugging Face repo, e.g. org/faster-whisper-name" style="flex:1"><button class="g sm" id="mhCustomUse">Use this repo</button></div></div>
  <div class="card"><h3>Local AI models</h3><p class="mu small">Run a language model on this PC for rating moments and writing titles. Free models come from Hugging Face. Clipsurge sizes the model to your memory and connects it for you.</p>
   <div id="mhRuntime"></div><div id="mhRun"></div>
   <div class="row" style="justify-content:flex-start;gap:8px;margin:14px 0 8px"><input type="text" id="mhQ" placeholder="Search Hugging Face for GGUF models (qwen, llama, gemma...)" style="flex:1"><button class="g sm" id="mhSearch">${ico("search",13)}<span>Search</span></button></div>
   <div id="mhHits"></div><div id="mhFiles"></div>
   <h3 style="margin-top:18px">Downloaded</h3><div id="mhLocal"></div></div>`;
 $("mhSearch").onclick=()=>mhSearch($("mhQ").value);$("mhQ").onkeydown=e=>{if(e.key=="Enter")mhSearch(e.target.value)};
 $("mhCustomUse").onclick=async()=>{const v=$("mhCustom").value.trim();if(!v)return;await setSetting({transcribe:{model:v}});toast("Speech model set");mhLoad()};
 await mhLoad();mhSearch("");mhTick();}

async function setSetting(o){const r=await post("/api/settings",o);if(!r.ok)toast("Could not save","err");return r.ok}
async function mhLoad(){
 try{[MH.speech,MH.local]=await Promise.all([jget("/api/models/speech"),jget("/api/models/local")])}catch(e){return}
 drawSpeech();drawLocal()}

let mhTimer=null;
function mhTick(){
 clearTimeout(mhTimer);
 if(!$("modelHub")||$("settingsView").classList.contains("hide"))return;
 Promise.all([jget("/api/hw"),jget("/api/models/downloads"),jget("/api/settings")]).then(([hw,dl,st])=>{
  MH.hw=hw;const prev=MH.dl;MH.dl=dl;MH.mem=st.settings.memory;drawHw();paintDl();
  if(Object.keys(dl).some(k=>dl[k].state=="done"&&(!prev[k]||prev[k].state!="done"))){mhLoad()}
 }).catch(()=>{}).finally(()=>{mhTimer=setTimeout(mhTick,1500)})}

function memBar(label,used,total,tip){
 const pct=total?Math.round(used/total*100):0;
 return `<div class="mem"><div class="t"><span>${label}</span><span class="mono">${used.toFixed(1)} / ${total.toFixed(1)} GB used</span></div><div class="bar big"><b style="width:${pct}%;background:${pct>88?"var(--red)":"var(--lime)"}!important"></b></div><div class="mu small">${tip}</div></div>`}
function drawHw(){
 const h=MH.hw,m=MH.mem||{mode:"auto"},g=h.gpus[0],el=$("mhHw");if(!el)return;
 const key=JSON.stringify([h,m]);if(el.dataset.k===key)return;el.dataset.k=key;
 const focus=document.activeElement&&el.contains(document.activeElement);if(focus)return;
 el.innerHTML=`<div class="two">${g?memBar(g.name+" video memory",g.used,g.total,`${g.free.toFixed(1)} GB free right now`):'<div class="mu">No NVIDIA GPU found. Everything runs on the CPU.</div>'}
  ${memBar("System memory",h.ram_total-h.ram_free,h.ram_total,`${h.ram_free.toFixed(1)} GB free · ${h.cores} CPU threads`)}</div>
  <div class="row" style="justify-content:flex-start;gap:14px;margin-top:12px;flex-wrap:wrap"><label>Memory use<select id="mmMode"><option value="auto" ${m.mode!="manual"?"selected":""}>Automatic (recommended)</option><option value="manual" ${m.mode=="manual"?"selected":""}>Set limits</option></select></label>
   <label class="${m.mode=="manual"?"":"hide"}" id="mmV">Video memory limit (GB)<input type="number" min="0" step="0.5" id="mmVv" value="${m.vram_gb||Math.floor(g?g.free:0)}"></label>
   <label class="${m.mode=="manual"?"":"hide"}" id="mmR">System memory limit (GB)<input type="number" min="0" step="0.5" id="mmRv" value="${m.ram_gb||Math.floor(h.ram_free)}"></label></div>
  <p class="mu small">${m.mode=="manual"?"Clipsurge stays under these limits.":"Clipsurge checks free memory before every job. It picks the speech model, the precision and how many layers of a local AI model go on the GPU, and falls back to the CPU if memory is short."}</p>`;
 const save=()=>setSetting({memory:{mode:$("mmMode").value,vram_gb:+$("mmVv").value||0,ram_gb:+$("mmRv").value||0}});
 $("mmMode").onchange=async()=>{await save();el.dataset.k="";mhTick()};$("mmVv").onchange=$("mmRv").onchange=save}

/* ---------- speech ---------- */
function drawSpeech(){
 const S=MH.speech,el=$("mhSpeech");if(!S||!el)return;
 const sel=S.selected;
 el.innerHTML=`<div class="mrow ${sel=="auto"?"on":""}"><div class="mmain"><b>Auto</b><span class="mu small">Picks <b class="lime">${esc(S.auto_choice)}</b> right now for your free memory</span></div><div class="mact"><button class="g sm ${sel=="auto"?"on":""}" data-use="auto">${sel=="auto"?"In use":"Use"}</button></div></div>`+
 S.models.map(m=>{const k="speech:"+m.id;return `<div class="mrow ${m.selected?"on":""}" data-k="${k}"><div class="mmain"><b>${esc(m.id)}</b><span class="mu small">${esc(m.note)}</span>
  <span class="mono small mu">${gbf(m.size)} download · needs ${m.vram_int8.toFixed(1)}–${m.vram_fp16.toFixed(1)} GB video memory</span><div class="dlbar hide"><div class="bar"><b style="width:0%"></b></div><span class="dlt mono small"></span></div></div>
  <div class="mscore mono" title="Speed / accuracy"><span>speed ${dots(m.speed)}</span><span>accuracy ${dots(m.accuracy)}</span></div>
  <div class="mact">${m.installed?`<span class="chip idea">Installed</span>`:`<span class="chip">Not installed</span>`}
   ${m.installed?`<button class="g sm" data-use="${m.id}">${m.selected?"In use":"Use"}</button><button class="g sm danger" data-sdel="${m.id}" title="Delete files" aria-label="Delete ${m.id}">${ico("trash",13)}</button>`:`<button class="sm" data-sdl="${m.id}">${withIco("download","Download",13)}</button><button class="g sm" data-use="${m.id}" title="Downloads automatically on first use">Use</button>`}</div></div>`}).join("");
 el.querySelectorAll("[data-use]").forEach(b=>b.onclick=async()=>{if(await setSetting({transcribe:{model:b.dataset.use}})){toast("Speech model: "+b.dataset.use);mhLoad()}});
 el.querySelectorAll("[data-sdl]").forEach(b=>b.onclick=async()=>{await post("/api/models/download",{kind:"speech",name:b.dataset.sdl});mhTick()});
 el.querySelectorAll("[data-sdel]").forEach(b=>b.onclick=async()=>{if(await confirmBox("Delete speech model",`Delete ${b.dataset.sdel} from this PC? You can download it again later.`,"Delete")){await post("/api/models/speech/delete",{kind:"speech",name:b.dataset.sdel});mhLoad()}});
 paintDl()}

/* ---------- local LLMs ---------- */
function drawLocal(){
 const L=MH.local,el=$("mhLocal");if(!L||!el)return;const st=L.status;
 const rt=$("mhRuntime");
 rt.innerHTML=st.runtime?`<div class="mrow"><div class="mmain"><b>Runtime</b><span class="mu small">llama.cpp is installed</span></div><div class="mact"><span class="chip idea">Ready</span></div></div>`
  :`<div class="mrow" data-k="runtime:llama"><div class="mmain"><b>Runtime</b><span class="mu small">Needed once to run models on this PC (about 250 MB, from the official llama.cpp releases)</span><div class="dlbar hide"><div class="bar"><b style="width:0%"></b></div><span class="dlt mono small"></span></div></div><div class="mact"><button class="sm" id="mhRt">${withIco("download","Install runtime",13)}</button></div></div>`;
 const b=$("mhRt");if(b)b.onclick=async()=>{await post("/api/models/download",{kind:"runtime"});mhTick()};
 $("mhRun").innerHTML=st.running?`<div class="mrow on"><div class="mmain"><b>${esc((st.file||"").split("/").pop().replace(".gguf",""))}</b><span class="mu small">${st.ready?"Running and connected as “Clipsurge local model”":"Loading the model..."}</span>${st.plan?`<span class="mono small mu">${esc(st.plan.description)} · context ${st.plan.ctx} · ${st.plan.threads} threads</span>`:""}</div><div class="mact"><button class="g sm danger" id="mhStop">${withIco("stop","Stop",13)}</button></div></div>`:"";
 const sb=$("mhStop");if(sb)sb.onclick=async()=>{await post("/api/models/local/stop");mhLoad()};
 el.innerHTML=L.models.length?L.models.map(m=>`<div class="mrow" data-path="${esc(m.path)}"><div class="mmain"><b>${esc(m.name)}</b><span class="mu small">${esc(m.repo)} · ${gbf(m.size/1024**3)}</span><span class="mono small mu" data-plan>Checking memory...</span></div>
  <div class="mact"><button class="sm" data-run="${esc(m.path)}" ${st.runtime?"":"disabled title='Install the runtime first'"}>${withIco("play","Run",13)}</button><button class="g sm danger" data-ldel="${esc(m.path)}" aria-label="Delete model">${ico("trash",13)}</button></div></div>`).join(""):`<div class="mu small">Nothing downloaded yet.</div>`;
 L.models.forEach(m=>jget("/api/models/plan?path="+encodeURIComponent(m.path)).then(p=>{const r=el.querySelector(`[data-path="${CSS.escape(m.path)}"] [data-plan]`);if(r)r.innerHTML=`${esc(p.description)} · context ${p.ctx}${p.ok?"":' · <span style="color:var(--red)">'+esc(p.notes.slice(-1)[0]||"")+"</span>"}`}).catch(()=>{}));
 el.querySelectorAll("[data-run]").forEach(b=>b.onclick=async()=>{b.disabled=true;const r=await post("/api/models/local/run",{path:b.dataset.run});if(!r.ok)toast((await r.json()).detail,"err");else toast("Model is loading. It connects automatically.");b.disabled=false;mhLoad();setTimeout(mhLoad,4000);setTimeout(mhLoad,10000)});
 el.querySelectorAll("[data-ldel]").forEach(b=>b.onclick=async()=>{if(await confirmBox("Delete model","Delete this model file from the PC?","Delete")){await post("/api/models/local/delete",{path:b.dataset.ldel});mhLoad()}});
 paintDl()}

async function mhSearch(q){
 MH.q=q;const el=$("mhHits");if(!el)return;el.innerHTML='<div class="mu small">Searching...</div>';$("mhFiles").innerHTML="";
 try{MH.hits=await jget("/api/models/hf/search?q="+encodeURIComponent(q||""))}catch(e){el.innerHTML=`<div class="mu small" style="color:var(--red)">${esc(e.message)}</div>`;return}
 el.innerHTML=`<div class="mu small" style="margin-bottom:6px">${q?"Results":"Suggested free models"}</div>`+MH.hits.map(h=>`<button class="hit" data-repo="${esc(h.repo)}"><b>${esc(h.name)}</b><span class="mu small">${esc(h.note)}${h.downloads?" · "+h.downloads.toLocaleString()+" downloads":""}</span></button>`).join("");
 el.querySelectorAll(".hit").forEach(b=>b.onclick=()=>mhFiles(b.dataset.repo))}
async function mhFiles(repo){
 const el=$("mhFiles");el.innerHTML='<div class="mu small">Reading the repository...</div>';
 try{MH.files=await jget("/api/models/hf/files?repo="+encodeURIComponent(repo))}catch(e){el.innerHTML=`<div class="mu small" style="color:var(--red)">${esc(e.message)}</div>`;return}
 el.innerHTML=`<div class="mfiles"><div class="row sp"><b>${esc(repo)}</b><span class="mu small">Choose a size. Bigger files are smarter but need more memory.</span></div>`+(MH.files.length?MH.files.map(f=>{const [t,c]=FIT[f.fit]||FIT.no;const k="gguf:"+repo+"/"+f.file;
  return `<div class="mrow" data-k="${esc(k)}"><div class="mmain"><b>${esc(f.quant||f.file)}</b> <span class="mono small mu">${gbf(f.gb)}</span> ${f.recommended?'<span class="chip idea">Recommended</span>':""}<div class="mu small">${esc(f.file)}</div><div class="dlbar hide"><div class="bar"><b style="width:0%"></b></div><span class="dlt mono small"></span></div></div>
  <div class="mact"><span class="chip fit-${c}">${t}</span><button class="sm" data-gdl="${esc(f.file)}">${withIco("download","Download",13)}</button></div></div>`}).join(""):'<div class="mu small">No single-file GGUF models in this repository.</div>')+`</div>`;
 el.querySelectorAll("[data-gdl]").forEach(b=>b.onclick=async()=>{await post("/api/models/download",{kind:"gguf",repo,file:b.dataset.gdl});toast("Download started");mhTick()})}

function paintDl(){
 document.querySelectorAll("#modelHub [data-k]").forEach(row=>{
  const d=MH.dl[row.dataset.k],bar=row.querySelector(".dlbar");if(!bar)return;
  if(!d||d.state=="done"){bar.classList.add("hide");return}
  bar.classList.remove("hide");bar.querySelector("b").style.width=Math.round(d.f*100)+"%";
  bar.querySelector(".dlt").textContent=d.state=="error"?(d.error||"Failed"):Math.round(d.f*100)+"% · "+d.detail;
  bar.classList.toggle("err",d.state=="error")})}
