/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Per-video goals/settings override and step redo. */

const STEPINFO=[
 ["Get video","Downloads the video again from its link. The transcript, clips and your edits are kept."],
 ["Transcribe","Listens again and rewrites the transcript, using this video's language and speech model. Clips keep their times. Re-render them to refresh the captions."],
 ["Find moments","Picks the moments again with this video's goals. This replaces all clips and their edits. They stay unrendered until you render them."],
 ["Crop + captions","Renders every kept clip again with the current crop, caption and narration choices."],
 ["Export","Writes the timeline files (.otio and .edl) again."]];

function redoStep(i){
 const [name,info]=STEPINFO[i];
 const m=modal(`<h3>Redo: ${esc(name)}</h3><p class="mu">${esc(info)}</p>
  ${i<4?`<label class="chk"><input type="checkbox" data-thru><span>Also redo the steps after it <small class="mu">${i<3?"Finds, renders and exports again, so nothing is out of date.":"Exports again."}</small></span></label>`:""}
  <div class="mfoot"><button class="g" data-x>Cancel</button><button data-go>${withIco("play","Redo "+name)}</button></div>`);
 const q=s=>m.box.querySelector(s);q("[data-x]").onclick=()=>m.close();
 q("[data-go]").onclick=async()=>{
  const thru=!!(q("[data-thru]")&&q("[data-thru]").checked);
  const r=await post(`/api/jobs/${cur}/redo`,{step:i,through_end:thru});
  if(!r.ok){toast((await r.json().catch(()=>({}))).detail||"Could not start","err");return}
  m.close();toast("Working on "+name.toLowerCase());poll1()}}

const VS_KEYS=["mode","count","minlen","maxlen","layout","captions","language","whisper_model","censor"];
async function vsetInit(pid,jid){
 const host=$("vset");if(!host)return;
 let P,j;try{[P,j]=await Promise.all([jget("/api/projects/"+pid),jget("/api/jobs/"+jid)])}catch(e){host.innerHTML="";return}
 if(view!="video"||cur!=jid)return;
 const on=!!j.override;
 const brief=on?(j.brief||{}):(P.brief||{});
 const d={...(j.settings||{}),...(on?{}:(P.defaults||{}))};
 host.innerHTML=`<div class="row sp"><div><b>Goals and settings for this video</b><div class="mu small">${on?"This video uses its own goals and settings. The project's are ignored here.":`Following the project <b>${esc(P.name)}</b>. Turn on to change them for this video only.`}</div></div>
  <label class="vsw"><span class="glsw"><input type="checkbox" id="vsOn" role="switch" ${on?"checked":""}><i class="tr"></i><i class="kn"></i></span><span class="vsl">Override project</span></label></div>
  <div id="vsBody" class="${on?"":"locked"}"><div class="two big2" style="margin-top:12px"><div><label>What to look for</label><div id="vs-i"></div><label style="margin-top:8px">Skip these</label><div id="vs-a"></div>
   <label style="margin-top:8px">Describe it in your own words<textarea id="vs-p" rows="5" ${on?"":"disabled"}>${esc(brief.prompt||"")}</textarea></label></div>
   <div class="two"><label>Video type<select id="vs-mode" ${on?"":"disabled"}>${opt2(d.mode||"auto",MODES)}</select></label><label>Clips<input type="number" id="vs-count" min="1" max="20" value="${d.count||5}" ${on?"":"disabled"}></label>
   <label>Crop<select id="vs-layout" ${on?"":"disabled"}>${opt2(d.layout||"auto",LAYOPT)}</select></label><label>Captions<select id="vs-captions" ${on?"":"disabled"}>${opt2(d.captions||"pop",[["pop","Pop"],["clean","Clean"],["fire","Fire"],["off","Off"]])}</select></label>
   <label>Bad language<select id="vs-censor" ${on?"":"disabled"}>${opt2(d.censor||"",[["","Follow the setting above"],["on","Hide curse words"],["off","Show as spoken"]])}</select></label><label>Spoken language<select id="vs-language" ${on?"":"disabled"}>${opt2(d.language||"auto",LANGS)}</select></label><label>Speech model<select id="vs-whisper_model" ${on?"":"disabled"}>${opt2(d.whisper_model||"",[["","Settings default"],["small","small (fast)"],["medium","medium"],["large-v3","large-v3 (best, use for Arabic)"]])}</select></label>
   <label>Shortest (s)<input type="number" id="vs-minlen" value="${d.minlen||20}" ${on?"":"disabled"}></label><label>Longest (s)<input type="number" id="vs-maxlen" value="${d.maxlen||55}" ${on?"":"disabled"}></label></div></div>
   ${on?`<div class="row" style="justify-content:flex-start;gap:10px;margin-top:10px"><button id="vsSave">Save</button><button class="g" id="vsRedo">Save and find moments again</button></div>`:""}</div>`;
 const TI=makeTags($("vs-i"),brief.ideas||[],"Funny reactions, clutch plays..."),TA=makeTags($("vs-a"),brief.avoid||[],"Sponsor reads, menus...");
 const body=()=>{const s={};for(const k of VS_KEYS){const e=$("vs-"+k);s[k]=e.type=="number"?+e.value:e.value}
  return {enabled:true,brief:{ideas:TI.get(),avoid:TA.get(),prompt:$("vs-p").value},settings:s}};
 $("vsOn").onchange=async e=>{
  const want=e.target.checked,b=$("vsBody");
  b.classList.toggle("locked",!want);                       // unlock (or lock) right away, no waiting
  b.querySelectorAll("input,select,textarea").forEach(x=>x.disabled=!want);
  if(want)await post(`/api/jobs/${jid}/override`,{enabled:true,brief:{ideas:TI.get(),avoid:TA.get(),prompt:$("vs-p").value},settings:Object.fromEntries(VS_KEYS.map(k=>{const el=$("vs-"+k);return [k,el.type=="number"?+el.value:el.value]}))});
  else await post(`/api/jobs/${jid}/override`,{enabled:false});
  vsetInit(pid,jid)};
 if(on){$("vsSave").onclick=async()=>{const r=await post(`/api/jobs/${jid}/override`,body());toast(r.ok?"Saved for this video":"Could not save",r.ok?"":"err")};
  $("vsRedo").onclick=async()=>{const r=await post(`/api/jobs/${jid}/override`,body());if(!r.ok){toast("Could not save","err");return}
   const x=await post(`/api/jobs/${jid}/redo`,{step:2,through_end:true});if(x.ok){toast("Finding moments again");poll1()}else toast((await x.json().catch(()=>({}))).detail||"Could not start","err")}}}
