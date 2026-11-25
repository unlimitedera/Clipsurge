/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Platform rules, TikTok connection. */

const PLAT_NAMES={youtube:"YouTube",tiktok:"TikTok",twitch:"Twitch and other streaming sites"};
function platformRulesHtml(D,only){
 const keys=Object.keys(D.platforms).filter(k=>!only||k==only);
 return `<div class="note2" style="margin-bottom:14px"><b>General guidance, not legal advice.</b> Platforms change their rules without notice: the official links are the source of truth. You are responsible for what you download, clip and post. Only clip content you own or have permission to use.</div>`+
 keys.map(k=>{const P=D.platforms[k];const up=P.roles.includes("upload");
  return `<div class="prule"><h4>${esc(P.name)}${up?`<span class="pill2 ${P.acknowledged?"ok":""}">${P.acknowledged?"Rules confirmed":"Not confirmed yet"}</span>`:`<span class="pill2">Download source</span>`}</h4>
  <p class="mu small">${esc(P.summary)}</p>
  <b class="small">Rules to know</b><ul class="small">${P.rules.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
  ${P.limits.length?`<b class="small">Limits</b><ul class="small">${P.limits.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:""}
  ${up?`<p class="small"><b>When Clipsurge warns you:</b> after ${P.warn_at} posts to ${esc(P.name)} in 24 hours it shows a warning and asks you to confirm. After ${P.high_at} it warns strongly. These two numbers are Clipsurge's own cautious defaults, not limits set by ${esc(P.name)}. If you continue, you do so at your own risk.${P.risk&&P.risk.count?` You have posted <b>${P.risk.count}</b> in the last 24 hours.`:""}</p>`:""}
  <div class="plinks">${P.links.map(([t,u])=>`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`).join("")}</div></div>`}).join("")}

async function platformRules(only){
 let D;try{D=await jget("/api/platforms")}catch(e){toast("Could not load the rules","err");return}
 const m=modal(`<h3>Platform rules and risk</h3><div class="prules">${platformRulesHtml(D,only)}</div><div class="mfoot"><a class="g btn" href="https://github.com/unlimitedera/Clipsurge/blob/main/docs/PLATFORMS.md" target="_blank" rel="noopener">Open on GitHub</a><button data-x>Close</button></div>`,{wide:true});
 m.box.querySelector("[data-x]").onclick=()=>m.close()}

async function platFill(){
 const el=document.getElementById("platRules");
 if(el){try{const D=await jget("/api/platforms");el.innerHTML=platformRulesHtml(D)}catch(e){el.textContent="Could not load the rules."}}
 ttDraw()}

async function ttDraw(){
 const box=document.getElementById("ttBox");if(!box)return;
 let s;try{s=await jget("/api/tiktok")}catch(e){box.textContent="";return}
 box.innerHTML=`<div class="ytbox"><div class="row sp"><div><b>${s.connected?"Connected to TikTok":s.client_file?"Key saved. Sign in next":"Not connected"}</b>
  <div class="mu small">${s.connected?(s.can_publish?"Can post videos.":"Signed in, but without permission to post. Connect again and allow posting."):"Follow the steps, then paste your Client key and secret."}</div></div>
  <div class="row" style="gap:8px">${s.connected?`<button class="g" id="ttOut">Disconnect</button>`:`<button id="ttIn" ${s.client_file?"":"disabled"}>Connect TikTok</button>`}</div></div>
  ${s.connected?"":`<div class="three" style="margin-top:12px"><label>Client key<input type="text" id="tt_key" autocomplete="off" placeholder="from your TikTok app"></label><label>Client secret<input id="tt_secret" type="password" autocomplete="off" placeholder="stays on this computer"></label><div style="align-self:end"><button class="g" id="ttSave">Save key</button></div></div>`}</div>`;
 const k=document.getElementById("ttSave");if(k)k.onclick=async()=>{const r=await post("/api/tiktok/client",{client_key:$("tt_key").value,client_secret:$("tt_secret").value});if(!r.ok){toast((await r.json()).detail||"Could not save","err");return}toast("Saved");ttDraw()};
 const i=document.getElementById("ttIn");if(i)i.onclick=async()=>{i.disabled=true;toast("Finish signing in on the TikTok page that opened...");const r=await post("/api/tiktok/connect");if(!r.ok)toast((await r.json()).detail||"Could not connect","err");else toast("TikTok connected");ttDraw()};
 const o=document.getElementById("ttOut");if(o)o.onclick=async()=>{await post("/api/tiktok/disconnect",{});toast("Disconnected");ttDraw()}}
