/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Settings tab. */
let S=null,PRESETS={},MCPCFG={},YT={};
const E=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const opt=(v,list)=>list.map(([k,t])=>`<option value="${k}" ${String(v)===String(k)?"selected":""}>${t}</option>`).join("");

async function loadSettings(){
 const r=await (await fetch("/api/settings")).json();
 S=r.settings;PRESETS=r.presets;MCPCFG=r.mcp;YT=r.youtube;renderSettings();applyDefaults()}

function applyDefaults(){
 const d=S.defaults;
 for(const [id,k] of [["mode","mode"],["count","count"],["minlen","minlen"],["maxlen","maxlen"],["layout","layout"],["cap","captions"]]){const el=document.getElementById(id);if(el)el.value=d[k]}}

function renderSettings(){
 const provs=S.ai.providers;
 const roleOpts=[["","First enabled connection"],...provs.map(p=>[p.id,p.name])];
 document.getElementById("settingsView").innerHTML=`
 <div class="card"><h3>AI models and agents</h3>
  <p class="mu">Connect any local model or agent that speaks the OpenAI chat format (LM Studio, Ollama, llama.cpp, an agent's API, or a cloud provider). The AI rates moments, writes titles and hashtags, and powers moment search. Everything still works with no AI connected.</p>
  <div id="provs">${provs.map(provCard).join("")}</div>
  <div class="row" style="justify-content:flex-start;margin-top:10px"><select id="newkind">${opt("lmstudio",Object.entries(PRESETS).map(([k,v])=>[k,v.name]))}</select><button class="g" onclick="addProv()">+ Add connection</button></div>
  <div class="two" style="margin-top:12px"><label>Rating, titles and hashtags<select id="role_rating">${opt(S.ai.roles.rating,roleOpts)}</select></label>
  <label>Moment search<select id="role_search">${opt(S.ai.roles.search,roleOpts)}</select></label></div></div>

 <div class="card"><h3>Let an agent control Cliptastic (MCP)</h3>
  <p class="mu">Works with Hermes, Claude Code, Claude Desktop and any MCP client. The agent can start jobs, check progress, search moments, add clips and upload. Keep this app running.</p>
  ${[["Hermes (run in a terminal)",MCPCFG.hermes],["Claude Code (run in a terminal)",MCPCFG.claude_code],["Claude Desktop / other clients (JSON)",JSON.stringify(MCPCFG.json,null,2)]].map(([t,c],i)=>`<div class="mu" style="margin-top:8px">${t}</div><pre class="code" id="mcp${i}">${E(c)}</pre><button class="g" onclick="navigator.clipboard.writeText(document.getElementById('mcp${i}').textContent);this.textContent='Copied'">Copy</button>`).join("")}</div>

 <div class="card"><h3>Defaults for new clips</h3><div class="three">
  <label>Video type<select id="d_mode">${opt(S.defaults.mode,[["auto","Auto"],["gaming","Gaming"],["podcast","Podcast"],["tutorial","Tutorial"]])}</select></label>
  <label>Clips per video<input type="number" id="d_count" min="1" max="20" value="${S.defaults.count}"></label>
  <label>Crop<select id="d_layout">${opt(S.defaults.layout,[["auto","Auto"],["stack","Webcam + gameplay"],["game","Gameplay only (center)"],["fit","Whole screen + blur"],["follow","Follow face"]])}</select></label>
  <label>Shortest clip (s)<input type="number" id="d_minlen" value="${S.defaults.minlen}"></label>
  <label>Longest clip (s)<input type="number" id="d_maxlen" value="${S.defaults.maxlen}"></label>
  <label>Captions<select id="d_captions">${opt(S.defaults.captions,[["pop","Pop"],["clean","Clean"],["fire","Fire"],["off","Off"]])}</select></label></div></div>

 <div class="card"><h3>Features</h3><div class="three">
  ${[["llm_rating","AI rating and titles","Needs a connected model"],["ocr","Read on-screen text (gaming)","Spots KILL, VICTORY, ACE"],["chat_replay","YouTube chat spikes","Busy chat = good moment"],["webcam_detect","Find the webcam","Stacks webcam over gameplay"],["loudness","Balance loudness","Same volume across clips"]].map(([k,t,h])=>`<label class="chk"><input type="checkbox" id="f_${k}" ${S.features[k]?"checked":""}><span>${t}<small class="mu"> ${h}</small></span></label>`).join("")}</div></div>

 <div class="card"><h3>Speech and video</h3><div class="three">
  <label>Speech model<select id="t_model">${opt(S.transcribe.model,[["tiny","tiny (fastest)"],["base","base"],["small","small (default)"],["medium","medium"],["large-v3","large-v3 (best)"],["distil-large-v3","distil-large-v3 (fast + good)"]])}</select></label>
  <label>Language<input type="text" id="t_language" value="${E(S.transcribe.language)}" placeholder="auto, en, ar, es..."></label>
  <label>Run speech on<select id="t_device">${opt(S.transcribe.device,[["auto","Auto (GPU if possible)"],["cuda","GPU"],["cpu","CPU"]])}</select></label>
  <label>Video encoder<select id="v_encoder">${opt(S.video.encoder,[["auto","Auto"],["nvenc","NVIDIA GPU (NVENC)"],["x264","CPU (x264)"]])}</select></label>
  <label>Loudness target (LUFS)<input type="number" id="v_lufs" value="${S.video.lufs}"></label>
  <label>Caption size<input type="number" id="v_caption_size" min="40" max="140" value="${S.video.caption_size}"></label>
  <label>Download quality (max)<select id="v_max_height">${opt(S.video.max_height,[[480,"480p (fastest)"],[720,"720p"],[1080,"1080p (default)"],[1440,"1440p"],[2160,"4K (slow, huge)"]])}</select></label></div>
  <p class="mu">A new speech model downloads the first time it is used.</p></div>

 <div class="card"><h3>Accounts</h3><div class="three">
  <label>YouTube uploads are<select id="y_privacy">${opt(S.youtube.privacy,[["private","Private"],["unlisted","Unlisted"],["public","Public"]])}</select></label>
  <div><div class="mu">YouTube</div><div>${YT.connected?"Connected":(YT.client_file?"Ready to sign in":"Missing secrets/client_secret.json")}</div>${YT.client_file&&!YT.connected?`<button class="g" onclick="ytConnect()">Sign in</button>`:""}</div><div></div>
  <label>OBS host<input type="text" id="o_host" value="${E(S.obs.host)}"></label>
  <label>OBS port<input type="number" id="o_port" value="${S.obs.port}"></label>
  <label>OBS password<input type="password" id="o_password" value="${E(S.obs.password)}"></label></div></div>

 <div class="savebar"><span id="savemsg" class="mu"></span><button onclick="saveSettings()">Save settings</button></div>`}

function provCard(p){
 return `<div class="prov" data-id="${p.id}">
  <div class="two"><label>Name<input type="text" data-f="name" value="${E(p.name)}"></label>
   <label>Address (base URL)<input type="text" data-f="base_url" value="${E(p.base_url)}"></label>
   <label>API key (optional)<input type="password" data-f="api_key" value="${E(p.api_key)}" placeholder="not needed for local models"></label>
   <label>Model<input type="text" data-f="model" list="ml_${p.id}" value="${E(p.model)}" placeholder="empty = use whatever is loaded"><datalist id="ml_${p.id}"></datalist></label></div>
  <div class="row" style="justify-content:flex-start;margin-top:8px"><label class="chk"><input type="checkbox" data-f="enabled" ${p.enabled?"checked":""}><span>Enabled</span></label>
   <button class="g" onclick="testProv('${p.id}')">Test connection</button><button class="g" onclick="delProv('${p.id}')">Remove</button><span class="res mu"></span></div></div>`}

function readProvs(){
 return [...document.querySelectorAll(".prov")].map(el=>{
  const g=f=>el.querySelector(`[data-f=${f}]`);const old=S.ai.providers.find(x=>x.id==el.dataset.id)||{};
  return {id:el.dataset.id,kind:old.kind||"custom",name:g("name").value,base_url:g("base_url").value.trim(),api_key:g("api_key").value,model:g("model").value.trim(),enabled:g("enabled").checked}})}
function addProv(){
 S.ai.providers=readProvs();const k=document.getElementById("newkind").value;const pr=PRESETS[k];
 S.ai.providers.push({id:k+"-"+Math.random().toString(36).slice(2,6),kind:k,name:pr.name,base_url:pr.base_url,api_key:"",model:"",enabled:true});keepRoles();renderSettings()}
function delProv(id){S.ai.providers=readProvs().filter(p=>p.id!=id);keepRoles();renderSettings()}
function keepRoles(){S.ai.roles={rating:document.getElementById("role_rating").value,search:document.getElementById("role_search").value}}
async function testProv(id){
 const el=document.querySelector(`.prov[data-id="${id}"]`);const res=el.querySelector(".res");res.textContent="Testing...";res.className="res mu";
 const p=readProvs().find(x=>x.id==id);
 const r=await (await fetch("/api/ai/test",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)})).json();
 if(r.models&&r.models.length)el.querySelector("datalist").innerHTML=r.models.map(m=>`<option value="${E(m)}">`).join("");
 if(r.ok){res.textContent=`Connected: ${r.model}, replied in ${r.ms} ms`;res.className="res ok"}
 else{res.textContent=r.error||"Failed";res.className="res err"}}
async function ytConnect(){const r=await fetch("/api/youtube/connect",{method:"POST"});if(!r.ok)alert((await r.json()).detail);loadSettings()}
async function saveSettings(){
 const v=id=>document.getElementById(id).value,c=id=>document.getElementById(id).checked;
 const body={ai:{providers:readProvs(),roles:{rating:v("role_rating"),search:v("role_search")}},
  defaults:{mode:v("d_mode"),count:+v("d_count"),layout:v("d_layout"),minlen:+v("d_minlen"),maxlen:+v("d_maxlen"),captions:v("d_captions")},
  features:Object.fromEntries(["llm_rating","ocr","chat_replay","webcam_detect","loudness"].map(k=>[k,c("f_"+k)])),
  transcribe:{model:v("t_model"),language:v("t_language")||"auto",device:v("t_device")},
  video:{encoder:v("v_encoder"),lufs:+v("v_lufs"),caption_size:+v("v_caption_size"),max_height:+v("v_max_height")},
  youtube:{privacy:v("y_privacy")},obs:{host:v("o_host"),port:+v("o_port"),password:v("o_password")}};
 const r=await fetch("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 const m=document.getElementById("savemsg");
 if(r.ok){const j=await r.json();S=j.settings;m.textContent="Saved";applyDefaults();refreshStatus&&refreshStatus();setTimeout(()=>m.textContent="",2500)}else m.textContent="Could not save"}
