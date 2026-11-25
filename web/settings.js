/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Settings tab. */
let S=null,PRESETS={},MCPCFG={},YT={};
const SCATS=[{id:"ai",name:"AI and agents",subs:[["local","Local models"],["conn","Connections"],["mcp","Agent control (MCP)"]]},
 {id:"clip",name:"Clipping",subs:[["defaults","Defaults for new clips"],["features","Features"]]},
 {id:"media",name:"Speech and video",subs:[["speech","Speech"],["video","Video"],["narration","Narration"]]},
 {id:"acct",name:"Accounts",subs:[["yt","YouTube"],["obs","OBS"]]},
 {id:"about",name:"About",subs:[["about","About Clipsurge"],["license","License"],["terms","Terms of use"]]}];
const CREDITS=[
 ["Download and media",[["yt-dlp","Downloads videos and chat replay","Unlicense","https://github.com/yt-dlp/yt-dlp"],["FFmpeg","Cutting, cropping, captions, encoding, audio","LGPL / GPL","https://ffmpeg.org"],["ffmpeg-normalize","Loudness balancing","MIT","https://github.com/slhck/ffmpeg-normalize"],["OpenTimelineIO","Timeline export (.otio)","Apache-2.0","https://github.com/AcademySoftwareFoundation/OpenTimelineIO"]]],
 ["Speech and language",[["faster-whisper","Speech to text with word timing","MIT","https://github.com/SYSTRAN/faster-whisper"],["OpenAI Whisper","The speech models behind it","MIT","https://github.com/openai/whisper"],["CTranslate2","Fast model engine for Whisper","MIT","https://github.com/OpenNMT/CTranslate2"],["llama.cpp","Runs local language models","MIT","https://github.com/ggml-org/llama.cpp"],["Hugging Face","Hosts the speech and language models","Various","https://huggingface.co"],["edge-tts","Title narration voices","LGPL-3.0","https://github.com/rany2/edge-tts"]]],
 ["Vision",[["OpenCV","Faces, webcam finding, image work","Apache-2.0","https://opencv.org"],["YuNet (OpenCV Zoo)","Face detection for cut to speaker, by Shiqi Yu and team","MIT","https://github.com/opencv/opencv_zoo"],["RapidOCR","Reads on-screen text in gameplay","Apache-2.0","https://github.com/RapidAI/RapidOCR"],["ONNX Runtime","Runs the vision models","MIT","https://github.com/microsoft/onnxruntime"],["NumPy","Number crunching","BSD-3","https://numpy.org"]]],
 ["App and connections",[["FastAPI","The local web service","MIT","https://github.com/fastapi/fastapi"],["Uvicorn","Web server","BSD-3","https://github.com/encode/uvicorn"],["Pydantic","Data checking","MIT","https://github.com/pydantic/pydantic"],["HTTPX","Talks to AI models","BSD-3","https://github.com/encode/httpx"],["MCP Python SDK","Lets agents control Clipsurge","MIT","https://github.com/modelcontextprotocol/python-sdk"],["Google API client","YouTube uploads","Apache-2.0","https://github.com/googleapis/google-api-python-client"],["obs-websocket","Record from OBS (protocol only)","GPL-2.0","https://github.com/obsproject/obs-websocket"],["ASS subtitle format","Captions open in Aegisub","Open format","https://aegisub.org"]]],
 ["Ideas we learned from (no code copied)",[["gaming-clip","Webcam on top, gameplay below","","https://github.com/topics/gaming-clip"],["Stream-clipper","Chat activity spikes as a signal","","https://github.com/topics/stream-clipper"],["Chopify","How moments are scored","","https://github.com/topics/chopify"],["StoryToolkitAI","Searching a transcript","","https://github.com/octimot/StoryToolkitAI"]]]];
function creditsDialog(){
 const body=CREDITS.map(([h,l])=>`<h4 class="cr-h">${h}</h4>`+l.map(([n,w,lic,u])=>`<div class="cr-r"><div><a href="${u}" target="_blank" rel="noopener">${E(n)}</a><div class="mu small">${E(w)}</div></div>${lic?`<span class="chip">${E(lic)}</span>`:""}</div>`).join("")).join("");
 const m=modal(`<h3>Credits</h3><p class="mu">Clipsurge stands on the work of these open projects. Each one stays under its own license and belongs to its authors. Thank you.</p><div class="cr-list">${body}</div><div class="mfoot"><button class="g" data-x>Close</button></div>`,{wide:true});
 m.box.querySelector("[data-x]").onclick=()=>m.close()}
let SN={cat:"ai",sub:null,q:""};
const E=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const opt=(v,list)=>list.map(([k,t])=>`<option value="${k}" ${String(v)===String(k)?"selected":""}>${t}</option>`).join("");

async function loadSettings(){
 const r=await (await fetch("/api/settings")).json();
 S=r.settings;S.narration=Object.assign({enabled:false,title_caption:false,voice:"auto",volume:1},S.narration||{});PRESETS=r.presets;MCPCFG=r.mcp;YT=r.youtube;renderSettings();applyDefaults()}

function applyDefaults(){
 const d=S.defaults;
 for(const [id,k] of [["mode","mode"],["count","count"],["minlen","minlen"],["maxlen","maxlen"],["layout","layout"],["cap","captions"]]){const el=document.getElementById(id);if(el)el.value=d[k]}}

function renderSettings(){
 const provs=S.ai.providers;
 const roleOpts=[["","First enabled connection"],...provs.map(p=>[p.id,p.name])];
 document.getElementById("settingsView").innerHTML=`
 <div class="setlayout"><nav class="setnav" aria-label="Settings categories"><input type="search" id="setq" placeholder="Search settings" value="${E(SN.q)}" autocomplete="off"><div id="setmenu"></div></nav><div class="setmain">
 <div class="sec" data-cat="ai" data-sub="local" data-t="Local models speech model download llama whisper"><div id="modelHub"></div></div>
 <div class="card sec" data-cat="ai" data-sub="conn" data-t="AI models and agents connections providers"><h3>AI models and agents</h3>
  <p class="mu">Connect any local model or agent that speaks the OpenAI chat format (LM Studio, Ollama, llama.cpp, an agent's API, or a cloud provider). The AI rates moments, writes titles and hashtags, and powers moment search. Everything still works with no AI connected.</p>
  <div id="provs">${provs.map(provCard).join("")}</div>
  <div class="row" style="justify-content:flex-start;margin-top:10px"><select id="newkind">${opt("lmstudio",Object.entries(PRESETS).map(([k,v])=>[k,v.name]))}</select><button class="g" onclick="addProv()">+ Add connection</button></div>
  <div class="two" style="margin-top:12px"><label>Rating, titles and hashtags<select id="role_rating">${opt(S.ai.roles.rating,roleOpts)}</select></label>
  <label>Moment search<select id="role_search">${opt(S.ai.roles.search,roleOpts)}</select></label></div></div>

 <div class="card sec" data-cat="ai" data-sub="mcp" data-t="Agent control MCP Hermes Claude"><h3>Let an agent control Clipsurge (MCP)</h3>
  <p class="mu">Works with Hermes, Claude Code, Claude Desktop and any MCP client. The agent can start jobs, check progress, search moments, add clips and upload. Keep this app running.</p>
  ${[["Hermes (run in a terminal)",MCPCFG.hermes],["Claude Code (run in a terminal)",MCPCFG.claude_code],["Claude Desktop / other clients (JSON)",JSON.stringify(MCPCFG.json,null,2)]].map(([t,c],i)=>`<div class="mu" style="margin-top:8px">${t}</div><pre class="code" id="mcp${i}">${E(c)}</pre><button class="g" onclick="navigator.clipboard.writeText(document.getElementById('mcp${i}').textContent);this.textContent='Copied'">Copy</button>`).join("")}</div>

 <div class="card sec" data-cat="clip" data-sub="defaults" data-t="Defaults for new clips"><h3>Defaults for new clips</h3><div class="three">
  <label>Video type<select id="d_mode">${opt(S.defaults.mode,[["auto","Auto"],["gaming","Gaming"],["podcast","Podcast"],["tutorial","Tutorial"]])}</select></label>
  <label>Clips per video<input type="number" id="d_count" min="1" max="20" value="${S.defaults.count}"></label>
  <label>Crop<select id="d_layout">${opt(S.defaults.layout,[["auto","Auto"],["stack","Webcam + gameplay"],["game","Gameplay only (center)"],["fit","Whole screen + blur"],["follow","Follow face"],["speaker","Cut to speaker"]])}</select></label>
  <label>Shortest clip (s)<input type="number" id="d_minlen" value="${S.defaults.minlen}"></label>
  <label>Longest clip (s)<input type="number" id="d_maxlen" value="${S.defaults.maxlen}"></label>
  <label>Captions<select id="d_captions">${opt(S.defaults.captions,[["pop","Pop"],["clean","Clean"],["fire","Fire"],["off","Off"]])}</select></label></div></div>

 <div class="card sec" data-cat="clip" data-sub="features" data-t="Features"><h3>Features</h3><div class="three">
  ${[["llm_rating","AI rating and titles","Needs a connected model"],["ocr","Read on-screen text (gaming)","Spots KILL, VICTORY, ACE"],["chat_replay","YouTube chat spikes","Busy chat = good moment"],["webcam_detect","Find the webcam","Stacks webcam over gameplay"],["loudness","Balance loudness","Same volume across clips"],["native_only","Captions in the spoken language only","Removes stray English letters from Arabic, Hebrew, Russian and similar"]].map(([k,t,h])=>`<label class="chk"><input type="checkbox" id="f_${k}" ${S.features[k]?"checked":""}><span>${t}<small class="mu"> ${h}</small></span></label>`).join("")}</div></div>

 <div class="card sec" data-cat="media" data-sub="speech" data-t="Speech transcription"><h3>Speech</h3><div class="three">
  <label>Speech model<select id="t_model">${opt(S.transcribe.model,[["auto","Auto (best that fits)"],["tiny","tiny (fastest)"],["base","base"],["small","small (default)"],["medium","medium"],["large-v3","large-v3 (best)"],["distil-large-v3","distil-large-v3 (fast + good)"]])}</select></label>
  <label>Language<input type="text" id="t_language" value="${E(S.transcribe.language)}" placeholder="auto, en, ar, es..."></label>
  <label>Run speech on<select id="t_device">${opt(S.transcribe.device,[["auto","Auto (GPU if possible)"],["cuda","GPU"],["cpu","CPU"]])}</select></label></div>
  <p class="mu">A new speech model downloads the first time it is used.</p></div>
 <div class="card sec" data-cat="media" data-sub="video" data-t="Video encoding captions loudness"><h3>Video</h3><div class="three">
  <label>Video encoder<select id="v_encoder">${opt(S.video.encoder,[["auto","Auto"],["nvenc","NVIDIA GPU (NVENC)"],["x264","CPU (x264)"]])}</select></label>
  <label>Loudness target (LUFS)<input type="number" id="v_lufs" value="${S.video.lufs}"></label>
  <label>Caption size<input type="number" id="v_caption_size" min="40" max="140" value="${S.video.caption_size}"></label>
  <label>Download quality (max)<select id="v_max_height">${opt(S.video.max_height,[[480,"480p (fastest)"],[720,"720p"],[1080,"1080p (default)"],[1440,"1440p"],[2160,"4K (slow, huge)"]])}</select></label></div></div>

 <div class="card sec" data-cat="media" data-sub="narration" data-t="Narration voiceover title read aloud intro"><h3>Narration</h3><div class="three">
  <label class="chk"><input type="checkbox" id="n_enabled" ${S.narration.enabled?"checked":""}><span>Read the title at the start <small class="mu">A voice says the clip's title over the first seconds. The original sound lowers while it talks.</small></span></label>
  <label>Voice<select id="n_voice">${opt(S.narration.voice,[["auto","Auto (matches the spoken language)"],["en-US-AndrewNeural","English, man (US)"],["en-US-AriaNeural","English, woman (US)"],["en-GB-RyanNeural","English, man (UK)"],["ar-EG-ShakirNeural","Arabic, man (Egypt)"],["ar-EG-SalmaNeural","Arabic, woman (Egypt)"],["ar-SA-HamedNeural","Arabic, man (Saudi)"],["es-ES-AlvaroNeural","Spanish, man"],["fr-FR-HenriNeural","French, man"],["de-DE-ConradNeural","German, man"]])}</select></label>
  <label class="chk"><input type="checkbox" id="n_caption" ${S.narration.title_caption?"checked":""}><span>Show the title on screen while it is read <small class="mu">A separate caption at the top, apart from the word captions.</small></span></label>
  <label>Narration volume <b class="mu" id="n_volume_v">${Math.round((S.narration.volume||1)*100)}%</b><input type="range" class="glrange" id="n_volume" min="0.2" max="2" step="0.1" value="${S.narration.volume||1}" style="--p:${((S.narration.volume||1)-0.2)/1.8*100}%"></label></div>
  <p class="mu">Needs an internet connection. If it fails, the clip is made without narration. These are the defaults: each video (on its page) and each clip (in the editor) can override them.</p></div>
 <div class="card sec" data-cat="acct" data-sub="yt" data-t="YouTube account uploads"><h3>YouTube</h3><div class="three">
  <label>YouTube uploads are<select id="y_privacy">${opt(S.youtube.privacy,[["private","Private"],["unlisted","Unlisted"],["public","Public"]])}</select></label>
  <label class="chk"><input type="checkbox" id="y_smart" ${S.youtube.smart_tags!==false?"checked":""}><span>Suggest tags when uploading <small class="mu">Opens a window with tags from your best videos and from trending videos on the topic. You can edit them.</small></span></label>
  <label class="chk"><input type="checkbox" id="y_learn" ${S.youtube.learn!==false?"checked":""}><span>Learn from my results <small class="mu">Uses the views and likes of your uploads to guide which moments it picks and how titles are written.</small></span></label></div>
  <div class="ytbox">
   <div class="yts ${YT.client_file?"ok":""}"><b>1</b><div><div>Get your Google key <span class="mu small">once, about 5 minutes</span></div><button class="g sm" onclick="ytGuide()">Show me how</button></div></div>
   <div class="yts ${YT.client_file?"ok":""}"><b>2</b><div><div>Add the key</div>
    <div class="ytdrop" id="ytdrop" tabindex="0">Drop the downloaded file here, or <u>choose it</u><input type="file" id="ytfile" accept=".json,application/json" hidden></div>
    <details class="ytpaste"><summary class="mu small">or paste the client id and secret</summary><div class="two"><label>Client id<input type="text" id="ytcid" placeholder="123-abc.apps.googleusercontent.com"></label><label>Client secret<input type="password" id="ytsec"></label></div><button class="g sm" onclick="ytPaste()">Use these</button></details>
    ${YT.bundled?`<div class="mu small">Using the key that came with Clipsurge. Nothing to add.</div>`:""}</div></div>
   <div class="yts ${YT.connected?"ok":""}"><b>3</b><div><div>Sign in with Google <span class="mu small">${YT.connected?"Connected":"a Google page opens, you approve once"}</span></div>
    ${YT.connected?`<button class="g sm" onclick="ytOut()">Disconnect</button>`:`<button class="sm" ${YT.client_file?"":"disabled"} onclick="ytConnect()">Sign in</button>`}<span id="ytmsg" class="res mu"></span></div></div>
  </div></div>
 <div class="card sec" data-cat="acct" data-sub="obs" data-t="OBS recording account"><h3>OBS</h3><div class="three">
  <label>OBS host<input type="text" id="o_host" value="${E(S.obs.host)}"></label>
  <label>OBS port<input type="number" id="o_port" value="${S.obs.port}"></label>
  <label>OBS password<input type="password" id="o_password" value="${E(S.obs.password)}"></label></div></div>

 <div class="card sec" data-cat="about" data-sub="about" data-t="About Clipsurge creator unlimitedera credits open source version"><h3>About Clipsurge</h3>
  <p>Clipsurge turns long videos into short vertical clips: it finds the best moments, crops, captions and exports them. It runs on your own computer.</p>
  <div class="two" style="margin-top:10px"><div class="sit"><div class="mu small">Created by</div><div><b>unlimitedera</b></div></div><div class="sit"><div class="mu small">Copyright</div><div>2026 unlimitedera</div></div></div>
  <div class="sit" style="margin-top:10px"><div class="mu small">Version</div><div id="updver">${esc(window.updateVersionText?updateVersionText():"")}</div></div>
  <div class="row" style="justify-content:flex-start;margin-top:14px;gap:10px"><button class="g" onclick="creditsDialog()">Credits</button><button class="g" onclick="updateDialog(true)">Check for updates</button>
  <label class="chk" style="margin-left:6px"><input type="checkbox" ${localStorage.getItem("ct_upd_auto")==="0"?"":"checked"} onchange="localStorage.setItem('ct_upd_auto',this.checked?'1':'0');if(window.UPD&&window.UPD.available)document.getElementById('updb').hidden=!this.checked"><span>Tell me when an update is available</span></label></div></div>
 <div class="card sec" data-cat="about" data-sub="license" data-t="License all rights reserved copyright proprietary"><h3>License</h3>
  <p>Copyright (c) 2026 unlimitedera. All Rights Reserved.</p>
  <p class="mu">Clipsurge and its source code are proprietary. No permission is granted to use, copy, modify, merge, publish, distribute, sublicense, sell or create derivative works of it, in whole or in part, without written permission from unlimitedera. Viewing the source on a hosting platform does not grant any license.</p>
  <p class="mu">Third-party tools used by Clipsurge stay under their own licenses and are not covered by this notice. See Credits.</p></div>
 <div class="card sec" data-cat="about" data-sub="terms" data-t="Terms of use responsibility content rights warranty privacy"><h3>Terms of use</h3>
  <ul class="terms"><li><b>Your content.</b> Only clip videos you own or have permission to use. You are responsible for what you download, edit and publish.</li>
  <li><b>Platform rules.</b> Sites such as YouTube have their own terms. Following them, including rules on downloading and re-uploading, is up to you.</li>
  <li><b>Your data stays with you.</b> Videos, transcripts and clips are stored on this computer. They leave it only when you use a connected AI model, the narration voices, or an upload you start.</li>
  <li><b>AI results can be wrong.</b> Ratings, titles, transcripts and speaker detection are automatic. Check clips before you publish them.</li>
  <li><b>No warranty.</b> Clipsurge is provided as is, without any promise that it fits a purpose or works without errors. Use it at your own risk. Keep copies of anything important.</li></ul></div>
 <div id="setempty" class="mu sx-hide">No settings match your search.</div>
 <div class="savebar"><span id="savemsg" class="mu"></span><button onclick="saveSettings()">Save settings</button></div></div></div>`;
 document.getElementById("setq").oninput=e=>{SN.q=e.target.value;setView()};
 setView();renderModelHub();ytWire();settingsTitle();
 document.querySelectorAll("input.glrange").forEach(r=>{const f=()=>{r.style.setProperty("--p",((r.value-r.min)/(r.max-r.min)*100)+"%");const v=document.getElementById(r.id+"_v");if(v)v.textContent=Math.round(r.value*100)+"%"};r.addEventListener("input",f);f()})}

function setView(){
 const q=SN.q.trim().toLowerCase(),counts={};let total=0;
 document.querySelectorAll("#settingsView .sec").forEach(sec=>{
  const items=[...sec.querySelectorAll("label,.prov,.sit")].filter(e=>e.classList.contains("prov")||!e.closest(".prov"));
  let ok;
  if(q){
   const hm=(sec.dataset.t+" "+(sec.querySelector("h3")?.textContent||"")).toLowerCase().includes(q);
   if(items.length){let any=false;items.forEach(it=>{const m=hm||it.textContent.toLowerCase().includes(q)||[...it.querySelectorAll("input[type=text],input[type=number]")].some(i=>i.value.toLowerCase().includes(q));it.classList.toggle("sx-hide",!m);any=any||m});ok=any}
   else ok=hm||false;
   if(ok){counts[sec.dataset.cat]=(counts[sec.dataset.cat]||0)+1;total++}
  }else{items.forEach(it=>it.classList.remove("sx-hide"));ok=sec.dataset.cat==SN.cat&&(!SN.sub||sec.dataset.sub==SN.sub)}
  sec.classList.toggle("sx-hide",!ok)});
 const em=document.getElementById("setempty");if(em)em.classList.toggle("sx-hide",!(q&&!total));
 renderSetMenu(q,counts);settingsTitle()}

function renderSetMenu(q,counts){
 document.getElementById("setmenu").innerHTML=SCATS.map(c=>{
  const on=!q&&SN.cat==c.id,n=q?(counts[c.id]||0):0;
  return `<div class="sn-grp"><button type="button" class="sn-c ${on&&!SN.sub?"on":""} ${q&&!n?"dim":""}" onclick="setNav('${c.id}')"><span>${c.name}</span>${q&&n?`<em>${n}</em>`:`<i class="chev ${on?"open":""}"></i>`}</button>
  ${on?`<div class="sn-subs">${c.subs.map(([k,t])=>`<button type="button" class="sn-s ${SN.sub==k?"on":""}" onclick="setNav('${c.id}','${k}')">${t}</button>`).join("")}</div>`:""}</div>`}).join("")}

function settingsTitle(){
 if(typeof setTitle!="function"||(location.hash||"").slice(1).split("?")[0]!="/settings")return;
 const q=(SN.q||"").trim(),c=SCATS.find(x=>x.id==SN.cat),s=c&&c.subs.find(x=>x[0]==SN.sub);
 setTitle(q?"Settings: searching "+q:"Settings: "+(s?s[1]:(c?c.name:"")))}
function setNav(cat,sub){
 SN.cat=cat;SN.sub=sub||null;SN.q="";const i=document.getElementById("setq");if(i)i.value="";setView()}

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
async function ytConnect(){
 const m=document.getElementById("ytmsg");if(m){m.className="res mu";m.textContent="Finish signing in on the Google page..."}
 const r=await fetch("/api/youtube/connect",{method:"POST"});
 if(!r.ok){const d=(await r.json().catch(()=>({}))).detail||"Sign in failed";if(m){m.className="res err";m.textContent=d}return}
 toast("YouTube connected");loadSettings()}
async function ytSend(body){const r=await post("/api/youtube/client",body);
 if(!r.ok){const m=document.getElementById("ytmsg");const d=(await r.json().catch(()=>({}))).detail||"Could not use that";if(m){m.className="res err";m.textContent=d}toast(d,"err");return}
 toast("Key added. Now sign in.");loadSettings()}
function ytPaste(){ytSend({client_id:document.getElementById("ytcid").value,client_secret:document.getElementById("ytsec").value})}
async function ytOut(){await post("/api/youtube/disconnect",{});toast("Disconnected");loadSettings()}
function ytWire(){
 const dz=document.getElementById("ytdrop"),fi=document.getElementById("ytfile");if(!dz)return;
 const read=f=>{if(!f)return;const rd=new FileReader();rd.onload=()=>ytSend({json_text:String(rd.result)});rd.readAsText(f)};
 dz.onclick=()=>fi.click();dz.onkeydown=e=>{if(e.key=="Enter"||e.key==" ")fi.click()};fi.onchange=()=>read(fi.files[0]);
 dz.ondragover=e=>{e.preventDefault();dz.classList.add("over")};dz.ondragleave=()=>dz.classList.remove("over");
 dz.ondrop=e=>{e.preventDefault();dz.classList.remove("over");read(e.dataTransfer.files[0])}}
function ytGuide(){
 const L=(u,t)=>`<a href="${u}" target="_blank" rel="noopener">${t}</a>`;
 const m=modal(`<h3>Get your Google key</h3><p class="mu">Google needs to know which app uploads for you. You make a free key for yourself once. Clipsurge never sees your password.</p>
  <ol class="ytsteps"><li>${L("https://console.cloud.google.com/projectcreate","Create a project")}. Any name, for example Clipsurge.</li>
  <li>${L("https://console.cloud.google.com/apis/library/youtube.googleapis.com","Turn on YouTube Data API v3")}. Press Enable.</li>
  <li>${L("https://console.cloud.google.com/apis/credentials/consent","Set up the consent screen")}. Choose External, fill the app name and your email, then add <b>your own Google account as a test user</b>.</li>
  <li>${L("https://console.cloud.google.com/apis/credentials","Create the key")}. Create credentials, OAuth client ID, type <b>Desktop app</b>. Press Download JSON.</li>
  <li>Drop that file into step 2 here. Then press Sign in.</li></ol>
  <p class="small"><b>Seeing "Access blocked ... error 403 access_denied"?</b> Your Google account is not on the test list. ${L("https://console.cloud.google.com/auth/audience","Open Audience")}, find <b>Test users</b>, press Add users, enter the same Google email you sign in with, Save, then press Sign in again.</p>
  <p class="mu small">Tip: while the app is in Testing, Google signs you out every 7 days. To stop that, press <b>Publish app</b> on that same Audience page. You can ignore the verification warning for your own use.</p>
  <p class="mu small">When Google says the app is not verified, press Advanced, then continue. That message is normal for your own key. Uploads stay private until you change that in the setting above.</p>
  <div class="mfoot"><button class="g" data-x>Close</button></div>`,{wide:true});
 m.box.querySelector("[data-x]").onclick=()=>m.close()}
async function saveSettings(){
 const v=id=>document.getElementById(id).value,c=id=>document.getElementById(id).checked;
 const body={ai:{providers:readProvs(),roles:{rating:v("role_rating"),search:v("role_search")}},
  defaults:{mode:v("d_mode"),count:+v("d_count"),layout:v("d_layout"),minlen:+v("d_minlen"),maxlen:+v("d_maxlen"),captions:v("d_captions")},
  features:Object.fromEntries(["llm_rating","ocr","chat_replay","webcam_detect","loudness","native_only"].map(k=>[k,c("f_"+k)])),
  transcribe:{model:v("t_model"),language:v("t_language")||"auto",device:v("t_device")},
  video:{encoder:v("v_encoder"),lufs:+v("v_lufs"),caption_size:+v("v_caption_size"),max_height:+v("v_max_height")},
  narration:{enabled:c("n_enabled"),title_caption:c("n_caption"),voice:v("n_voice"),volume:+v("n_volume")||1},
  youtube:{privacy:v("y_privacy"),smart_tags:c("y_smart"),learn:c("y_learn")},obs:{host:v("o_host"),port:+v("o_port"),password:v("o_password")}};
 const r=await fetch("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 const m=document.getElementById("savemsg");
 if(r.ok){const j=await r.json();S=j.settings;m.textContent="Saved";applyDefaults();refreshStatus&&refreshStatus();setTimeout(()=>m.textContent="",2500)}else m.textContent="Could not save"}
