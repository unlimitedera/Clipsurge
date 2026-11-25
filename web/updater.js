/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Update checker: header pill, dialog, Settings > About hook. */

(function(){
 const hr=document.querySelector(".hright");if(!hr)return;
 const pill=document.createElement("button");pill.id="updb";pill.className="upd-pill";pill.hidden=true;
 pill.innerHTML=withIco("refresh","Update");pill.title="A new version of Clipsurge is available";
 const rs=document.getElementById("restart");(rs||hr.lastChild).before(pill);
 let info=null;
 const auto=()=>{try{return localStorage.getItem("ct_upd_auto")!=="0"}catch(e){return true}};
 const ago=d=>{if(!d)return"";const s=(Date.now()-new Date(d))/1000;if(s<3600)return Math.max(1,Math.round(s/60))+" min ago";if(s<86400)return Math.round(s/3600)+" h ago";return Math.round(s/86400)+" days ago"};
 const foot=document.createElement("footer");foot.id="appfoot";document.body.appendChild(foot);
 const GH="https://github.com/unlimitedera/Clipsurge";
 function footDraw(state){
  let st,cls;
  if(state==="checking"||(!info&&state!=="offline")){st="Checking for updates";cls="chk"}
  else if(!info){st="Could not check";cls="off"}
  else if(info.error){st="Could not check for updates";cls="off"}
  else if(info.available){st=`Update available${info.latest?" ("+info.latest+")":""}`;cls="new"}
  else{st="Up to date";cls="ok"}
  const v=info&&info.current?info.current:"";
  foot.innerHTML=`<span class="fc">© 2026 unlimitedera. All Rights Reserved.</span>
   <span class="fl"><a href="${GH}" target="_blank" rel="noopener">GitHub</a><a href="${GH}/blob/main/LICENSE" target="_blank" rel="noopener">License</a><a href="${GH}/blob/main/TERMS.md" target="_blank" rel="noopener">Terms</a><a href="#" data-cr>Credits</a><a href="#" data-pr>Platform rules</a></span>
   <button class="fv ${cls}" id="footv" title="${esc(info&&info.current_date?"Installed "+agoTxt(info.current_date)+". ":"")}Click to check for updates"><i></i><span>Clipsurge${v?" <b>"+esc(v)+"</b>":""} · ${st}</span></button>`;
  foot.querySelector("[data-pr]").onclick=e=>{e.preventDefault();if(window.platformRules)platformRules()};
  foot.querySelector("[data-cr]").onclick=e=>{e.preventDefault();if(window.creditsDialog)creditsDialog()};
  foot.querySelector("#footv").onclick=()=>{footDraw("checking");updateDialog(true)}}
 const agoTxt=d=>{const s=(Date.now()-new Date(d))/1000;return s<3600?Math.max(1,Math.round(s/60))+" min ago":s<86400?Math.round(s/3600)+" h ago":Math.round(s/86400)+" days ago"};
 footDraw("checking");
 async function check(force){
  try{info=await jget("/api/update"+(force?"?force=true":""))}catch(e){info=null;footDraw("offline");return null}
  pill.hidden=!(info.available&&(force||auto()));if(window.fitHeader)fitHeader();footDraw();
  window.UPD=info;const v=document.getElementById("updver");if(v)v.textContent=verText();
  return info}
 function verText(){if(!info)return"";return info.current?`${info.current}${info.current_date?" · updated "+ago(info.current_date):""}`:"unknown"}
 window.updateVersionText=verText;
 window.updateDialog=async function(force){
  const i=await check(!!force);
  if(!i){toast("Could not check for updates","err");return}
  if(i.error){modal(`<h3>Updates</h3><p class="mu">${esc(i.error)}. Check your internet connection and try again.</p><div class="mfoot"><button class="g" data-x>Close</button></div>`).box.querySelector("[data-x]").onclick=e=>e.target.closest(".mbg").remove();return}
  if(!i.available){
   const m=modal(`<h3>You are up to date</h3><p class="mu">Installed ${esc(verText())}${i.latest?", latest is "+esc(i.latest):""}.</p><div class="mfoot"><button class="g" data-x>Close</button></div>`);
   m.box.querySelector("[data-x]").onclick=()=>m.close();return}
  const list=(i.commits||[]).map(c=>`<li><span class="mono mu">${esc(c.sha)}</span> ${esc(c.message)} <span class="mu small">${esc(ago(c.date))}</span></li>`).join("");
  const git=i.mode==="git";
  const m=modal(`<h3>Update available</h3>
   <p class="mu">${i.unknown_version?"Your version could not be identified, so Clipsurge will install the latest.":`${i.count||1} new change${(i.count||1)>1?"s":""} on GitHub.`} Installed ${esc(verText())}.</p>
   <ul class="updlist">${list}</ul>
   <p class="mu small">Your projects, videos, clips, settings and YouTube key are kept. Clipsurge restarts when it is done.${git?" This copy is a git clone, so it runs <span class=mono>git pull</span>.":""}</p>
   <div class="updbar" hidden><i></i></div><div class="updst mu small" hidden></div>
   <div class="mfoot"><button class="g" data-x>Later</button><button data-go>Update now</button></div>`,{wide:true,sticky:true});
  const go=m.box.querySelector("[data-go]"),x=m.box.querySelector("[data-x]"),bar=m.box.querySelector(".updbar"),st=m.box.querySelector(".updst");
  x.onclick=()=>m.close();
  go.onclick=async()=>{
   go.disabled=true;x.disabled=true;bar.hidden=false;st.hidden=false;st.textContent="Starting";
   try{const r=await fetch("/api/update/apply",{method:"POST"});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.status)}catch(e){st.textContent=(e.message||"Update failed");go.disabled=false;x.disabled=false;bar.hidden=true;return}
   let seenRestart=false;
   const tick=async()=>{
    try{const s=await jget("/api/update/status");
     if(s.stage==="error"){st.textContent=s.error||"Update failed";go.disabled=false;x.disabled=false;bar.hidden=true;return}
     bar.firstElementChild.style.width=s.pct+"%";st.textContent=s.stage==="restarting"?"Restarting Clipsurge":s.stage;
     if(s.stage==="restarting")seenRestart=true;
    }catch(e){ if(seenRestart||bar.firstElementChild.style.width){st.textContent="Restarting Clipsurge";seenRestart=true;waitBack();return} }
    setTimeout(tick,900)};
   const waitBack=async()=>{for(let k=0;k<90;k++){await new Promise(r=>setTimeout(r,1000));try{await jget("/api/update/status");toast("Clipsurge updated");setTimeout(()=>location.reload(),600);return}catch(e){}}
    st.textContent="Clipsurge did not come back. Start it from the Desktop shortcut."};
   tick()}};
 pill.onclick=()=>updateDialog(false);
 check(false);setInterval(()=>{if(auto())check(false)},30*60*1000);
})();
