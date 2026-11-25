/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Upload analytics (Overview) and the smart tag upload dialog. */

const fmtN=n=>n==null?"-":n>=1e6?(n/1e6).toFixed(n>=1e7?0:1)+"M":n>=1e4?Math.round(n/1e3)+"K":n>=1e3?(n/1e3).toFixed(1)+"K":String(n);
const agoIso=d=>{if(!d)return"";const s=(Date.now()/1000)-(typeof d=="number"?d:Date.parse(d)/1000);if(s<3600)return Math.max(1,Math.round(s/60))+" min ago";if(s<86400)return Math.round(s/3600)+" h ago";return Math.round(s/86400)+" days ago"};

/* ---------------------------------------------------------------- Overview: performance */
let PERF={t:0,busy:false,trendTopic:null,trend:null};
async function perfRefresh(force){
 const el=$("perf");if(!el)return;
 if(!force&&Date.now()-PERF.t<15000)return;
 PERF.t=Date.now();
 let a;try{a=await jget("/api/insights"+(force?"?refresh=true":""))}catch(e){return}
 PERF.a=a;
 if(PERF.trendTopic==null){const v=(a.videos||[])[0];PERF.trendTopic=v&&v.meta&&v.meta.source?v.meta.source.replace(/[\[\(].*?[\]\)]|[^\w\s]/g," ").split(/\s+/).filter(Boolean).slice(0,5).join(" "):""}
 const h=perfHtml(a);if(el.dataset.h!==h){el.dataset.h=h;el.innerHTML=h;perfWire(el)}}

function perfHtml(a){
 const head=(sub)=>`<div class="phead2"><div><h3 style="margin:0">Performance of your uploads</h3><p class="mu small" style="margin:4px 0 0">${sub}</p></div><div class="row" style="gap:8px"><button class="g sm" data-rf>${withIco("refresh","Refresh stats",13)}</button></div></div>`;
 if(!a.count)return `<div class="card perf">${head("Clipsurge learns from what you post.")}<div class="empty" style="padding:22px 0">Upload clips to YouTube from Clipsurge. Their views, likes and comments show up here, and Clipsurge learns what works for you: clip length, crop, title style, tags and posting time.</div>${trendBox(a)}</div>`;
 const tile=(v,l,s="")=>`<div class="ovt"><b>${v}</b><span>${l}</span>${s?`<small>${s}</small>`:""}</div>`;
 const T=a.totals;
 const tiles=`<div class="ovtiles">${tile(a.count,"Uploads tracked",a.measured+" with numbers")}${tile(fmtN(T.views),"Views")}${tile(fmtN(T.likes),"Likes",fmtN(T.comments)+" comments")}${tile(T.engagement==null?"-":T.engagement+"%","Engagement","likes + 2x comments per view")}</div>`;
 const conf={none:"Not enough data yet",early:"Early signal",fair:"Fair signal",good:"Good signal"}[a.confidence];
 const warn=(a.unreadable&&!a.youtube.stats)?`<div class="note2">${a.unreadable} upload${a.unreadable>1?"s are":" is"} private, so YouTube hides the numbers. <button class="sm" data-allow>Allow Clipsurge to read stats</button> <span class="mu small">(asks Google once more; Clipsurge only reads view, like and comment counts)</span></div>`:(a.unreadable?`<div class="note2 mu small">${a.unreadable} upload${a.unreadable>1?"s":""} could not be read yet. Try Refresh in a minute.</div>`:"");
 const b=a.best;
 const best=b&&b.views!=null?`<div class="card bestc"><h3>Your best so far</h3><a class="bestt" href="${esc(b.url)}" target="_blank" rel="noopener">${esc(b.title||"")}</a><div class="mu small">${fmtN(b.views)} views · ${fmtN(b.likes)} likes · ${fmtN(b.comments)} comments${b.age_days?` · ${Math.round(b.age_days)} days old`:""}</div><div class="chips2">${Object.values(b.feat||{}).map(x=>`<span>${esc(x)}</span>`).join("")}</div><p class="mu small" style="margin:10px 0 0">Clipsurge uses these as the reference: what it picks and how it writes titles lean toward clips like this.</p></div>`:"";
 const mx=Math.max(1,...a.videos.map(v=>v.views||0));
 const rows=[...a.videos].sort((x,y)=>(y.perf??-1)-(x.perf??-1)||(y.views||0)-(x.views||0)).map((v,i)=>`<tr><td class="mu">${i+1}</td><td><a href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title||v.id)}</a><div class="ovbar2"><i style="width:${Math.round((v.views||0)/mx*100)}%"></i></div></td><td>${v.views==null?`<span class="mu" title="Private or not readable yet">?</span>`:fmtN(v.views)}</td><td>${fmtN(v.likes)}</td><td>${fmtN(v.comments)}</td><td class="mu">${v.per_day!=null?fmtN(Math.round(v.per_day))+"/day":"-"}</td><td class="mu">${esc(agoIso(v.published||v.posted))}</td><td>${v.perf==null?"-":`<b class="perfn" style="--p:${v.perf}">${v.perf}</b>`}</td></tr>`).join("");
 const table=`<table class="ovtab perft"><thead><tr><th></th><th>Clip</th><th>Views</th><th>Likes</th><th>Comments</th><th>Pace</th><th>Posted</th><th title="0 to 100, compared with your other uploads: views per day (65%) and engagement (35%)">Score</th></tr></thead><tbody>${rows}</tbody></table>`;
 let ins="";
 if(a.insights.length)ins=a.insights.map(x=>`<li class="${x.good?"up":"dn"}"><b>${x.good?"+":"−"}${Math.abs(x.diff)}</b> ${esc(x.text)} <span class="mu small">(${x.n} clips)</span></li>`).join("");
 else ins=`<li class="mu">${a.measured<4?`Needs at least 4 uploads with numbers to find patterns. You have ${a.measured}.`:"No clear pattern yet. Keep posting."}</li>`;
 const R=a.reco||{};
 const reco=(R.length||R.crop||(R.tags||[]).length)?`<div class="reco">${R.length?`<div><span class="mu small">Length</span><b>${R.length[0]}${R.length[1]!=R.length[0]?" to "+R.length[1]:""} s</b></div>`:""}${R.crop?`<div><span class="mu small">Crop</span><b>${esc(R.crop)}</b></div>`:""}${R.type?`<div><span class="mu small">Video type</span><b>${esc(R.type)}</b></div>`:""}</div>${(R.tags||[]).length?`<div class="mu small" style="margin-top:10px">Tags on your best clips</div><div class="chips2">${R.tags.map(t=>`<span>#${esc(t)}</span>`).join("")}</div>`:""}`:`<p class="mu small">Shown once there are numbers to learn from.</p>`;
 return `<div class="card perf">${head(`${esc(conf)} · updated ${a.fetched?agoIso(a.fetched):"never"}${a.busy?" · reading numbers...":""}`)}${warn}${tiles}
 <div class="ovgrid" style="margin-top:14px">${best||`<div class="card"><h3>Your best so far</h3><p class="mu small">Appears when a clip has numbers.</p></div>`}<div class="card"><h3>What is working</h3><ul class="insl">${ins}</ul><h3 style="margin-top:16px">Aim for next clips</h3>${reco}<p class="mu small" style="margin:12px 0 0">Used automatically when Clipsurge picks moments and writes titles (Settings, Accounts, YouTube). Patterns from few videos can be luck: treat them as hints.</p></div></div>
 <div style="margin-top:14px;overflow:auto">${table}</div>${trendBox(a)}</div>`}

function trendBox(a){
 const t=PERF.trend;
 const chips=t?(t.tags||[]).map(x=>`<button class="chip3" data-tag="${esc(x.tag)}" title="${x.count} channel${x.count>1?"s":""} · click to copy">#${esc(x.tag)}</button>`).join("")+((t.related||[]).length?`</div><div class="mu small" style="margin:10px 0 6px">People also search</div><div class="chips2">${t.related.map(x=>`<button class="chip3 s" data-tag="${esc(x)}">${esc(x)}</button>`).join("")}`:""):"";
 return `<div class="card" style="margin-top:14px"><h3>Trending tags</h3><div class="row" style="gap:8px;justify-content:flex-start"><input id="trTopic" placeholder="Topic, for example: GTA 6 clutch" value="${esc(PERF.trendTopic||"")}" style="max-width:340px"><button class="g sm" data-tr>Look up</button></div><p class="mu small" style="margin:8px 0">Public tags used by popular short videos on the topic. Used by two or more different channels, so they are real trends and not one channel's branding. They are added to your uploads only when they fit the clip.</p><div class="chips2" id="trOut">${t?(t.pending?`<span class="mu small">Looking up...</span>`:(chips||`<span class="mu small">Nothing found for this topic.</span>`)):`<span class="mu small">Type a topic and press Look up.</span>`}</div></div>`}

function perfWire(el){
 const rf=el.querySelector("[data-rf]");if(rf)rf.onclick=async()=>{rf.disabled=true;await perfRefresh(true);setTimeout(()=>perfRefresh(true),6000)};
 const al=el.querySelector("[data-allow]");if(al)al.onclick=async()=>{toast("Finish signing in on the Google page that opened...");const r=await post("/api/youtube/connect");toast(r.ok?"Done. Reading stats":"Could not connect",r.ok?"":"err");perfRefresh(true)};
 const go=async force=>{const v=($("trTopic").value||"").trim();if(!v)return;PERF.trendTopic=v;PERF.trend={pending:true,tags:[]};perfRefresh(true);
  for(let k=0;k<60;k++){try{PERF.trend=await jget("/api/insights/trending?topic="+encodeURIComponent(v)+(force?"&force=true":""));force=false}catch(e){break}
   const o=$("trOut");if(!o)return;PERF.t=0;await perfRefresh(true);if(!PERF.trend.pending)break;await new Promise(r=>setTimeout(r,1500))}};
 const tb=el.querySelector("[data-tr]");if(tb)tb.onclick=()=>go(false);
 const ti=$("trTopic");if(ti)ti.onkeydown=e=>{if(e.key=="Enter")go(false)};
 el.querySelectorAll("[data-tag]").forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText("#"+b.dataset.tag.replace(/\s+/g,""));toast("Copied #"+b.dataset.tag.replace(/\s+/g,""))})}

/* ---------------------------------------------------------------- Upload dialog: platform, rules, risk, smart tags */
async function uploadDialog(jid,cid,platform){
 const clip=((await jget("/api/jobs/"+jid)).clips||[]).find(c=>String(c.id)===String(cid))||{};
 const [set,PL]=await Promise.all([jget("/api/settings"),jget("/api/platforms")]);
 const S=set.settings.youtube||{};
 let plat=platform||"youtube";
 let tags=[];let edited=false;const gone=new Set();let risk=null;let loadId=0;
 const conn=p=>p=="tiktok"?PL.tiktok.connected:PL.youtube.connected;
 const m=modal(`<h3>Upload</h3>
  <div class="ptabs" id="uPlat">${[["youtube","YouTube"],["tiktok","TikTok"]].map(([k,n])=>`<button class="ptab" data-p="${k}">${n}<small></small></button>`).join("")}</div>
  <div id="uConn" class="note2 hide"></div>
  <label style="margin-top:10px">Title<input id="uTitle" maxlength="95" value="${esc(clip.title||"")}"></label>
  <div class="two" style="margin-top:8px"><label>Visibility<select id="uPriv">${[["private","Private"],["unlisted","Unlisted"],["public","Public"]].map(([v,l])=>`<option value="${v}" ${S.privacy==v?"selected":""}>${l}</option>`).join("")}</select></label><div id="uPrivNote" class="mu small" style="align-self:end"></div></div>
  <div style="margin-top:12px"><div class="mu small">Tags <span id="uSt"></span></div><div class="chips2 tagedit" id="uTags"></div>
   <input id="uAdd" placeholder="Add a tag and press Enter" style="margin-top:8px"></div>
  <div class="legend small mu"><span><u class="dd dd-clip"></u>from this clip</span><span><u class="dd dd-yours"></u>from your best videos</span><span><u class="dd dd-trending"></u>trending on this topic</span><span><u class="dd dd-search"></u>people also search</span></div>
  <label style="margin-top:10px"><span id="uDescL">Description</span><textarea id="uDesc" rows="3"></textarea></label>
  <div id="uRisk"></div>
  <p class="mu small" style="margin:6px 0 0">Only tags that fit the video are suggested. Remove any you do not want. Nothing can guarantee views.</p>
  <div class="mfoot"><button class="g" data-x>Cancel</button><button data-go>Upload</button></div>`,{wide:true});
 const B=m.box,q=s=>B.querySelector(s);
 const NAME={youtube:"YouTube",tiktok:"TikTok"};
 const desc=()=>{if(edited)return;const n=plat=="tiktok"?5:3;const hs=tags.slice(0,n).map(t=>"#"+t.tag.replace(/\s+/g,""));q("#uDesc").value=q("#uTitle").value+(hs.length?(plat=="tiktok"?" ":"\n\n")+hs.join(" "):"")};
 const draw=()=>{q("#uTags").innerHTML=tags.map((t,i)=>`<span class="tg"><u class="dd dd-${t.src}"></u>${esc(t.tag)}<button data-rm="${i}" title="Remove">×</button></span>`).join("")||`<span class="mu small">No tags</span>`;
  q("#uTags").querySelectorAll("[data-rm]").forEach(b=>b.onclick=()=>{gone.add(tags[+b.dataset.rm].tag);tags.splice(+b.dataset.rm,1);draw();desc()});desc()};
 q("#uDesc").oninput=()=>edited=true;q("#uTitle").oninput=desc;
 q("#uAdd").onkeydown=e=>{if(e.key=="Enter"||e.key==","){e.preventDefault();const v=e.target.value.trim().replace(/^#/,"").toLowerCase();if(v&&!tags.some(t=>t.tag==v)){tags.push({tag:v,src:"clip",added:true});gone.delete(v)}e.target.value="";draw()}};
 const ready=()=>{const go=q("[data-go]");let ok=conn(plat);
  const a=q("#uAck"),r=q("#uRiskOk");if(a&&!a.checked)ok=false;if(r&&!r.checked)ok=false;go.disabled=!ok;go.textContent="Upload to "+NAME[plat]};
 async function drawRisk(){
  try{risk=await jget(`/api/platforms/${plat}/risk`)}catch(e){risk={level:"none",messages:[]}}
  const P=PL.platforms[plat];
  const lvl=risk.level;
  let h="";
  if(risk.needs_ack)h+=`<div class="rbox"><b>Rules for ${NAME[plat]}</b><ul class="small">${P.rules.slice(0,4).map(x=>`<li>${esc(x)}</li>`).join("")}</ul><a href="#" data-rules class="small">Read all the rules, limits and links</a>
    <label class="chk" style="margin-top:8px"><input type="checkbox" id="uAck"><span>I have read the ${NAME[plat]} rules and I am responsible for what I post <small class="mu">You only confirm this once.</small></span></label></div>`;
  if(lvl=="warn"||lvl=="high")h+=`<div class="rbox ${lvl}"><b>${lvl=="high"?"Slow down":"Heads up"}</b>${risk.messages.filter(x=>!/First time/.test(x)).map(x=>`<p class="small" style="margin:6px 0">${esc(x)}</p>`).join("")}
    <label class="chk"><input type="checkbox" id="uRiskOk"><span>I understand and proceed at my own risk</span></label></div>`;
  q("#uRisk").innerHTML=h;
  q("#uRisk").querySelectorAll("input").forEach(x=>x.onchange=ready);
  const lk=q("#uRisk [data-rules]");if(lk)lk.onclick=e=>{e.preventDefault();platformRules(plat)};
  ready()}
 async function loadTags(){
  const my=++loadId;
  if(S.smart_tags===false){q("#uSt").textContent="";return}
  q("#uSt").textContent="· looking up trending tags...";
  for(let k=0;k<50;k++){let r;try{r=await jget(`/api/jobs/${jid}/clips/${cid}/tags`)}catch(e){break}
   if(!document.body.contains(B)||my!==loadId)return;
   const mine=tags.filter(t=>t.added);tags=[...r.tags.filter(t=>!gone.has(t.tag)),...mine.filter(t=>!r.tags.some(x=>x.tag==t.tag))];draw();
   if(!r.pending){q("#uSt").textContent=r.tags.length?"· "+r.tags.length+" suggested":"";return}await new Promise(x=>setTimeout(x,1500))}
  if(document.body.contains(B)&&my===loadId)q("#uSt").textContent=""}
 function setPlat(p){
  plat=p;edited=false;
  q("#uPlat").querySelectorAll(".ptab").forEach(b=>{b.classList.toggle("on",b.dataset.p==p);b.querySelector("small").textContent=conn(b.dataset.p)?"":" (not connected)"});
  const c=q("#uConn");c.classList.toggle("hide",conn(p));
  c.innerHTML=conn(p)?"":`${NAME[p]} is not connected. <button class="sm" data-set>Open Settings</button>`;
  const cb=c.querySelector("[data-set]");if(cb)cb.onclick=()=>{m.close();nav("/settings");setTimeout(()=>window.setNav&&setNav("acct",p=="tiktok"?"tt":"yt"),400)};
  q("#uDescL").textContent=p=="tiktok"?"Caption":"Description";
  q("#uPrivNote").textContent=p=="tiktok"?"TikTok apps that have not passed TikTok's audit can only post privately.":"";
  q("#uTitle").maxLength=p=="tiktok"?150:95;
  desc();drawRisk()}
 q("#uPlat").querySelectorAll(".ptab").forEach(b=>b.onclick=()=>setPlat(b.dataset.p));
 q("[data-x]").onclick=()=>m.close();
 q("[data-go]").onclick=async()=>{const go=q("[data-go]");go.disabled=true;
  const r=await post(`/api/jobs/${jid}/clips/${cid}/upload`,{platform:plat,title:q("#uTitle").value,privacy:q("#uPriv").value,tags:tags.map(t=>t.tag),description:q("#uDesc").value,
   ack_rules:!!(q("#uAck")&&q("#uAck").checked),risk_ok:!!(q("#uRiskOk")&&q("#uRiskOk").checked)});
  if(!r.ok){const e=await r.json().catch(()=>({}));if(r.status==409){toast("Please confirm the notes below first","err");await drawRisk()}else toast(typeof e.detail=="string"?e.detail:"Upload failed","err");go.disabled=false;return}
  m.close();toast("Upload started. Progress is in the box at the bottom right.");if(window.upKick)upKick()};
 draw();setPlat(plat);loadTags()}
