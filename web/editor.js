/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Clip editor: timing, crop, captions, sound, look. */
let GN={enabled:false,title_caption:false};const loadGN=()=>jget("/api/settings").then(r=>{GN={...GN,...(r.settings.narration||{})}}).catch(()=>{});loadGN();
const VOICES=[["","None"],["deep","Deep"],["high","High"],["chipmunk","Chipmunk"],["monster","Monster"],["robot","Robot"],["radio","Radio"],["telephone","Telephone"],["megaphone","Megaphone"],["echo","Echo"],["stadium","Stadium"]];
const LAYOUTS=[["","Project default","Uses the crop chosen for the video"],["auto","Auto","Finds the webcam, else follows the action"],["stack","Webcam + gameplay","Webcam on top, game below"],["game","Gameplay only","Centered vertical slice of the screen"],["fit","Whole screen","Full frame over a blurred copy"],["follow","Follow face","Keeps one face in frame"],["speaker","Cut to speaker","Hard cuts to whoever is talking, no camera movement"],["manual","Manual crop","You place the crop box, optionally pan across the clip"]];

async function openEditor(jid,cid,onSaved){
 loadGN();
 let job;try{job=await jget("/api/jobs/"+jid)}catch(e){toast("Cannot open editor","err");return}
 const clip=job.clips.find(c=>c.id==cid);if(!clip)return;
 const S={jid,cid,job,start:clip.start,end:clip.end,dur:job.info?.duration||clip.end+60,tab:"timing",
  ed:JSON.parse(JSON.stringify(clip.edit||{})),words:[],energy:null,rev:clip.rev||0,file:clip.file,sel:null,mTime:null,mWhich:"a"};
 const ed=()=>S.ed;
 const sub=(k)=>(ed()[k]=ed()[k]||{});
 const m=modal(`<div class="ed"><div class="edhead"><div><b>Edit clip</b> <span class="mu">${esc(clip.title||"")}</span></div><button class="g sm" data-close>Close</button></div>
  <div class="edbody"><aside class="edprev"><div class="phone sm"><video controls loop playsinline preload="metadata"></video><div class="ph hide"><span class="pt"></span><div class="bar"><b></b></div></div></div>
   <div class="mu small" data-status></div><div class="mu small" data-len></div></aside>
  <section class="edmain"><div class="tabs" role="tablist">${[["timing","Timing"],["crop","Crop"],["captions","Captions"],["sound","Sound"],["look","Look"]].map(([k,t])=>`<button role="tab" data-t="${k}">${t}</button>`).join("")}</div><div class="edpanel" data-panel></div></section></div>
  <div class="mfoot"><button class="g" data-reset>Reset edits</button><span class="grow"></span><button class="g" data-save>Save</button><button data-render>Save and render</button></div></div>`,{full:true,sticky:true});
 const q=s=>m.box.querySelector(s);
 q("[data-close]").onclick=()=>m.close();
 const vid=q("video");
 function setVideo(){if(S.file){vid.src=`/files/${jid}/${S.file}?v=${S.rev}`;vid.classList.remove("hide")}}
 setVideo();
 const lenInfo=()=>q("[data-len]").textContent=`${fmt(S.start)} to ${fmt(S.end)} · ${(S.end-S.start).toFixed(1)} s`+(((ed().video||{}).speed||1)!=1?` · plays in ${((S.end-S.start)/(ed().video.speed)).toFixed(1)} s`:"");
 lenInfo();

 m.box.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{S.tab=b.dataset.t;panel()});
 async function loadWords(){S.words=await jget(`/api/jobs/${jid}/words?start=${Math.max(0,S.start-6)}&end=${S.end+6}`)}
 function sl(label,key,min,max,step,val,unit="",obj){return `<label class="slr"><span>${label}<b data-v="${key}">${val}${unit}</b></span><input type="range" min="${min}" max="${max}" step="${step}" value="${val}" data-k="${key}"></label>`}

 /* ---------------- panels ---------------- */
 async function panel(){
  m.box.querySelectorAll(".tabs button").forEach(b=>{b.classList.toggle("on",b.dataset.t==S.tab);b.setAttribute("aria-selected",b.dataset.t==S.tab)});
  const P=q("[data-panel]");
  if(S.tab=="timing")await timing(P);else if(S.tab=="crop")crop(P);else if(S.tab=="captions")await captions(P);else if(S.tab=="sound")sound(P);else look(P)}

 async function timing(P){
  await loadWords();
  P.innerHTML=`<p class="mu">Drag the green handles or the region on the loudness map. Click a word to cut exactly at it.</p>
   <canvas class="tl" height="120"></canvas>
   <div class="trow"><div class="tcol"><b>Start</b><div class="nud">${[-1,-0.1].map(d=>`<button class="g sm" data-ns="${d}">${d}</button>`).join("")}<input type="number" step="0.1" data-in="start" value="${S.start.toFixed(1)}">${[0.1,1].map(d=>`<button class="g sm" data-ns="${d}">+${d}</button>`).join("")}</div><img class="fr" data-fr="start" alt="Start frame"></div>
   <div class="tcol"><b>End</b><div class="nud">${[-1,-0.1].map(d=>`<button class="g sm" data-ne="${d}">${d}</button>`).join("")}<input type="number" step="0.1" data-in="end" value="${S.end.toFixed(1)}">${[0.1,1].map(d=>`<button class="g sm" data-ne="${d}">+${d}</button>`).join("")}</div><img class="fr" data-fr="end" alt="End frame"></div></div>
   <div class="wordsbar"><b>Words</b><span class="mu small">select a word, then</span><button class="g sm" data-ws disabled>Start here</button><button class="g sm" data-we disabled>End here</button></div>
   <div class="words" data-words></div>`;
  const cv=P.querySelector("canvas");cv.width=cv.clientWidth*devicePixelRatio;cv.style.height="120px";
  const view=()=>({a:Math.max(0,S.start-45),b:Math.min(S.dur,S.end+45)});
  function drawTL(){
   if(S.tab!="timing"||!cv.isConnected)return;
   const c=cv.getContext("2d"),W=cv.width,H=cv.height,{a,b}=view(),x=t=>(t-a)/(b-a)*W;
   c.clearRect(0,0,W,H);c.fillStyle="#0f141b";c.fillRect(0,0,W,H);
   if(S.energy){const n=Math.floor(W/3);for(let i=0;i<n;i++){const t=a+(i+.5)/n*(b-a),v=S.energy[Math.min(S.energy.length-1,Math.floor(t))]||0,h=Math.max(2,v*H*.8);
     c.fillStyle=(t>=S.start&&t<=S.end)?"#c6ff3d":"#3a4558";c.fillRect(i*3,H-h,2,h)}}
   c.fillStyle="rgba(198,255,61,.12)";c.fillRect(x(S.start),0,x(S.end)-x(S.start),H);
   c.fillStyle="#c6ff3d";c.fillRect(x(S.start)-2,0,4,H);c.fillRect(x(S.end)-2,0,4,H);
   c.fillStyle="#7d8798";c.font=`${11*devicePixelRatio}px sans-serif`;
   for(let k=0;k<=4;k++){const t=a+(b-a)*k/4;c.fillText(fmt(t),Math.min(W-40,x(t)+3),12*devicePixelRatio)}}
  S.drawTL=drawTL;drawTL();
  if(!S.energy)jget(`/api/jobs/${jid}/energy`).then(e=>{S.energy=e;drawTL()}).catch(()=>{});
  let drag=null;
  const tOf=e=>{const r=cv.getBoundingClientRect(),{a,b}=view();return a+(e.clientX-r.left)/r.width*(b-a)};
  cv.onpointerdown=e=>{const t=tOf(e),{a,b}=view(),px=(b-a)/cv.clientWidth*10;cv.setPointerCapture(e.pointerId);
   drag=Math.abs(t-S.start)<px?{k:"s"}:Math.abs(t-S.end)<px?{k:"e"}:(t>S.start&&t<S.end)?{k:"m",o:t-S.start}:null};
  cv.onpointermove=e=>{if(!drag)return;const t=Math.round(tOf(e)*10)/10;
   if(drag.k=="s")S.start=Math.max(0,Math.min(t,S.end-3));else if(drag.k=="e")S.end=Math.min(S.dur,Math.max(t,S.start+3));
   else{const L=S.end-S.start;S.start=Math.max(0,Math.min(S.dur-L,Math.round((t-drag.o)*10)/10));S.end=S.start+L}
   sync(false)};
  cv.onpointerup=()=>{drag=null;sync(true)};
  const frames=debounce(()=>{["start","end"].forEach(k=>{const im=P.querySelector(`[data-fr=${k}]`);if(im)im.src=`/api/jobs/${jid}/frame?w=320&t=${S[k].toFixed(1)}`})},350);
  function sync(full){P.querySelector('[data-in=start]').value=S.start.toFixed(1);P.querySelector('[data-in=end]').value=S.end.toFixed(1);lenInfo();drawTL();frames();if(full){loadWords().then(words)}}
  P.querySelectorAll("[data-ns]").forEach(b=>b.onclick=()=>{S.start=Math.max(0,Math.min(S.end-3,+(S.start+ +b.dataset.ns).toFixed(1)));sync(true)});
  P.querySelectorAll("[data-ne]").forEach(b=>b.onclick=()=>{S.end=Math.min(S.dur,Math.max(S.start+3,+(S.end+ +b.dataset.ne).toFixed(1)));sync(true)});
  P.querySelector("[data-in=start]").onchange=e=>{S.start=Math.max(0,Math.min(S.end-3,+e.target.value));sync(true)};
  P.querySelector("[data-in=end]").onchange=e=>{S.end=Math.min(S.dur,Math.max(S.start+3,+e.target.value));sync(true)};
  const ws=P.querySelector("[data-ws]"),we=P.querySelector("[data-we]");
  function words(){const box=P.querySelector("[data-words]");if(!box)return;
   box.innerHTML=S.words.map(w=>`<button dir="auto" class="w ${w.s>=S.start-0.05&&w.e<=S.end+0.3?"in":""} ${S.sel==w.i?"sel":""}" data-i="${w.i}" title="${fmt(w.s)}">${esc((ed().word_edits||{})[w.i]??w.w)}</button>`).join("")||'<span class="mu">No speech detected here.</span>';
   box.querySelectorAll(".w").forEach(b=>b.onclick=()=>{S.sel=+b.dataset.i;ws.disabled=we.disabled=false;words()})}
  ws.onclick=()=>{const w=S.words.find(x=>x.i==S.sel);if(w&&w.s<S.end-3){S.start=Math.max(0,+(w.s-0.1).toFixed(1));sync(true)}};
  we.onclick=()=>{const w=S.words.find(x=>x.i==S.sel);if(w&&w.e>S.start+3){S.end=+(w.e+0.2).toFixed(1);sync(true)}};
  words();frames()}

 function crop(P){
  const cur=ed().layout||"";const mn=sub("manual");
  P.innerHTML=`<div class="cards">${LAYOUTS.map(([k,t,d])=>`<label class="card2 ${cur==k?"on":""}"><input type="radio" name="lay" value="${k}" ${cur==k?"checked":""}><b>${t}</b><span class="mu small">${d}</span></label>`).join("")}</div>
   <div data-manual class="${cur=="manual"?"":"hide"}">
    <div class="trow"><label class="slr grow"><span>Zoom<b data-v="zoom">${Math.round((mn.zoom??1)*100)}%</b></span><input type="range" min="30" max="100" step="1" value="${Math.round((mn.zoom??1)*100)}" data-m="zoom"></label>
     <label class="chk"><input type="checkbox" data-pan ${mn.cx2!=null?"checked":""}><span>Pan to a second position</span></label>
     <div class="seg ${mn.cx2!=null?"":"hide"}" data-which><button class="g sm ${S.mWhich=="a"?"on":""}" data-w="a">Start box</button><button class="g sm ${S.mWhich=="b"?"on":""}" data-w="b">End box</button></div></div>
    <div class="stage"><img data-img alt="Source frame"><div class="cbox a"><span>start</span></div><div class="cbox b hide"><span>end</span></div></div>
    <label class="slr"><span>Frame time<b data-v="mt">${fmt(S.mTime??((S.start+S.end)/2))}</b></span><input type="range" min="${S.start}" max="${S.end}" step="0.5" value="${S.mTime??((S.start+S.end)/2)}" data-mt></label>
    <p class="mu small">Drag the box over the picture. The clip shows what is inside the box.</p></div>`;
  P.querySelectorAll("[name=lay]").forEach(r=>r.onchange=()=>{ed().layout=r.value||undefined;if(!r.value)delete ed().layout;crop(P)});
  if(cur!="manual")return;
  const img=P.querySelector("[data-img]"),A=P.querySelector(".cbox.a"),B=P.querySelector(".cbox.b");
  const loadImg=()=>{S.mTime=+P.querySelector("[data-mt]").value;img.src=`/api/jobs/${jid}/frame?w=960&t=${S.mTime.toFixed(1)}`};
  P.querySelector("[data-mt]").oninput=e=>{P.querySelector('[data-v=mt]').textContent=fmt(+e.target.value)};
  P.querySelector("[data-mt]").onchange=loadImg;
  function place(){
   const iw=img.clientWidth,ih=img.clientHeight;if(!iw)return;const z=mn.zoom??1,h=z*ih,w=h*9/16;
   const set=(el,cx,cy)=>{el.style.height=h+"px";el.style.width=w+"px";el.style.left=Math.min(iw-w,Math.max(0,cx*iw-w/2))+"px";el.style.top=Math.min(ih-h,Math.max(0,cy*ih-h/2))+"px"};
   set(A,mn.cx??0.5,mn.cy??0.5);const pan=mn.cx2!=null;B.classList.toggle("hide",!pan);if(pan)set(B,mn.cx2,mn.cy??0.5);
   A.classList.toggle("act",!pan||S.mWhich=="a");B.classList.toggle("act",pan&&S.mWhich=="b")}
  img.onload=place;if(!img.src)loadImg();else place();
  const dragBox=(el,key)=>{el.onpointerdown=e=>{el.setPointerCapture(e.pointerId);const iw=img.clientWidth,ih=img.clientHeight,z=mn.zoom??1;
    const mv=ev=>{const r=img.getBoundingClientRect();mn[key]=Math.min(1,Math.max(0,(ev.clientX-r.left)/iw));if(z<1)mn.cy=Math.min(1,Math.max(0,(ev.clientY-r.top)/ih));place()};
    el.onpointermove=mv;el.onpointerup=()=>{el.onpointermove=null}}};
  dragBox(A,"cx");dragBox(B,"cx2");
  P.querySelector("[data-m=zoom]").oninput=e=>{mn.zoom=e.target.value/100;P.querySelector('[data-v=zoom]').textContent=e.target.value+"%";place()};
  P.querySelector("[data-pan]").onchange=e=>{if(e.target.checked){mn.cx2=Math.min(1,(mn.cx??0.5)+0.25);S.mWhich="b"}else{delete mn.cx2;S.mWhich="a"}crop(P)};
  P.querySelectorAll("[data-w]").forEach(b=>b.onclick=()=>{S.mWhich=b.dataset.w;crop(P)});
  mn.cx=mn.cx??0.5;mn.cy=mn.cy??0.5;mn.zoom=mn.zoom??1}

 async function captions(P){
  await loadWords();const c=sub("captions");const edits=ed().word_edits||{};
  P.innerHTML=`<div class="two">
   <label>Style<select data-c="style">${[["","Project default"],["pop","Pop (word highlight)"],["clean","Clean"],["fire","Fire"],["off","No captions"]].map(([k,t])=>`<option value="${k}" ${(c.style||"")==k?"selected":""}>${t}</option>`).join("")}</select></label>
   <label>Position<select data-c="pos">${[["bottom","Bottom"],["middle","Middle"],["top","Top"]].map(([k,t])=>`<option value="${k}" ${(c.pos||"bottom")==k?"selected":""}>${t}</option>`).join("")}</select></label>
   ${sl("Size","size",40,140,2,c.size||84)}${sl("Words per line","per",1,6,1,c.per||3)}
   <label>Highlight color<input type="color" data-c="hi" value="${c.hi||"#c6ff3d"}"></label>
   <label class="chk"><input type="checkbox" data-c="upper" ${c.upper===false?"":"checked"}><span>ALL CAPS</span></label></div>
   <div class="capprev"><div class="capmock ${c.pos||"bottom"}" style="font-size:${Math.round((c.size||84)/5)}px"><span>${(c.upper===false?"this is":"THIS IS")}</span> <b style="color:${c.hi||"#c6ff3d"}">${c.upper===false?"your caption":"YOUR CAPTION"}</b></div></div>
   <div class="wordsbar"><b>Fix wording</b><span class="mu small">edit any misheard word</span></div>
   <div class="words edit">${S.words.filter(w=>w.s>=S.start-0.05&&w.e<=S.end+0.3).map(w=>`<input dir="auto" data-wi="${w.i}" value="${esc(edits[w.i]??w.w)}" size="${Math.max(3,(edits[w.i]??w.w).length)}" aria-label="word at ${fmt(w.s)}">`).join("")||'<span class="mu">No speech in this clip.</span>'}</div>`;
  P.querySelectorAll("[data-c]").forEach(el=>el.onchange=()=>{const k=el.dataset.c;let v=el.type=="checkbox"?el.checked:el.value;if(k=="style"&&!v){delete c.style}else c[k]=v;captions(P)});
  P.querySelectorAll("[data-k=size],[data-k=per]").forEach(el=>el.oninput=()=>{c[el.dataset.k]=+el.value;P.querySelector(`[data-v=${el.dataset.k}]`).textContent=el.value});
  P.querySelectorAll("[data-k=size],[data-k=per]").forEach(el=>el.onchange=()=>captions(P));
  P.querySelectorAll("[data-wi]").forEach(el=>el.onchange=()=>{const i=el.dataset.wi,o=S.words.find(w=>w.i==i);ed().word_edits=ed().word_edits||{};
   if(el.value.trim()&&el.value.trim()!==o.w)ed().word_edits[i]=el.value.trim();else delete ed().word_edits[i];el.size=Math.max(3,el.value.length)})}

 function sound(P){
  const a=sub("audio"),nr=sub("narration"),clipTitle=S.job.clips.find(c=>c.id==S.cid)?.title||"",jn=S.job.settings?.narration||{};
  const nOn=nr.on??jn.on??GN.enabled,nCap=nr.title_caption??jn.title_caption??GN.title_caption;
  P.innerHTML=`<div class="two">
   ${sl("Volume","gain",-12,12,1,a.gain||0," dB")}
   <div class="chks"><label class="chk"><input type="checkbox" data-a="denoise" ${a.denoise?"checked":""}><span>Reduce background noise</span></label>
    <label class="chk"><input type="checkbox" data-a="leveler" ${a.leveler?"checked":""}><span>Even out the voice</span></label>
    <label class="chk"><input type="checkbox" data-a="mute" ${a.mute?"checked":""}><span>Mute the original sound</span></label>
    <label class="chk"><input type="checkbox" data-a="normalize" ${a.normalize===false?"":"checked"}><span>Auto loudness balance <small class="mu">(turn off to keep your volume exactly)</small></span></label></div>
   ${sl("Bass","bass",-10,10,1,a.bass||0," dB")}${sl("Treble","treble",-10,10,1,a.treble||0," dB")}</div>
   <b>Voice effect</b><div class="chips">${VOICES.map(([k,t])=>`<button class="chip2 ${(a.voice||"")==k?"on":""}" data-voice="${k}">${t}</button>`).join("")}</div>
   <b>Title narration</b><div class="two"><label class="chk"><input type="checkbox" data-nar="on" ${nOn?"checked":""}><span>Read a title at the start <small class="mu">(the original sound lowers while it talks)</small></span></label>
    <label>Words to read <input type="text" dir="auto" data-nar="text" value="${esc(nr.text??clipTitle)}" ${nOn?"":"disabled"}></label>
    <label class="chk"><input type="checkbox" data-nar="title_caption" ${nCap?"checked":""}><span>Show the title on screen while it is read</span></label></div>
   <p class="mu small">Unset choices follow this video's narration, then Settings.</p>
   <b>Background music</b><div class="trow"><button class="g" data-music>${a.music?"Change file":"Choose a music file"}</button><span class="mu small grow">${a.music?esc(a.music.split("/").pop()):"None"}</span>${a.music?'<button class="g sm" data-nomusic>Remove</button>':""}</div>
   ${a.music?`<div class="two">${sl("Music volume","music_vol",5,100,5,Math.round((a.music_vol??0.25)*100),"%")}<label class="chk"><input type="checkbox" data-a="duck" ${a.duck===false?"":"checked"}><span>Lower the music when someone speaks</span></label></div>`:""}`;
  P.querySelectorAll("[data-a]").forEach(el=>el.onchange=()=>{a[el.dataset.a]=el.checked;lenInfo()});
  P.querySelectorAll("[data-nar]").forEach(el=>el.onchange=()=>{const k=el.dataset.nar;nr[k]=el.type=="checkbox"?el.checked:el.value;if(k=="on")sound(P)});
  P.querySelectorAll("[data-k]").forEach(el=>{el.oninput=()=>{const k=el.dataset.k;a[k]=k=="music_vol"?el.value/100:+el.value;P.querySelector(`[data-v=${k}]`).textContent=el.value+(k=="music_vol"?"%":" dB")}});
  P.querySelectorAll("[data-voice]").forEach(b=>b.onclick=()=>{a.voice=b.dataset.voice||undefined;if(!b.dataset.voice)delete a.voice;sound(P)});
  P.querySelector("[data-music]").onclick=async()=>{const r=await pickFiles({kind:"audio",multi:false,title:"Choose background music",okLabel:"Use"});if(r&&r[0]){a.music=r[0];sound(P)}};
  const nm=P.querySelector("[data-nomusic]");if(nm)nm.onclick=()=>{delete a.music;sound(P)}}

 function look(P){
  const v=sub("video");
  P.innerHTML=`<div class="two">${sl("Speed","speed",0.5,2,0.05,v.speed||1,"x")}${sl("Fade in","fade_in",0,3,0.1,v.fade_in||0," s")}${sl("Fade out","fade_out",0,3,0.1,v.fade_out||0," s")}
   ${sl("Brightness","brightness",-0.3,0.3,0.02,v.brightness||0,"")}${sl("Contrast","contrast",0.6,1.6,0.05,v.contrast||1,"")}${sl("Saturation","saturation",0,2,0.05,v.saturation||1,"")}</div>
   <p class="mu small">Speed changes the sound too, and the clip gets shorter or longer.</p>`;
  P.querySelectorAll("[data-k]").forEach(el=>el.oninput=()=>{v[el.dataset.k]=+el.value;P.querySelector(`[data-v=${el.dataset.k}]`).textContent=el.value+({speed:"x",fade_in:" s",fade_out:" s"}[el.dataset.k]||"");lenInfo()})}

 /* ---------------- save / render ---------------- */
 function payload(){
  const e=JSON.parse(JSON.stringify(S.ed));
  for(const k of ["captions","audio","video","manual","narration"]){if(e[k]&&!Object.keys(e[k]).length)delete e[k]}
  if(e.layout!="manual")delete e.manual;
  return {start:S.start,end:S.end,edit:e}}
 async function save(render){
  const r=await post(`/api/jobs/${jid}/clips/${cid}?render=${render}`,payload());
  if(!r.ok){toast((await r.json()).detail||"Could not save","err");return false}
  onSaved&&onSaved();return true}
 q("[data-save]").onclick=async()=>{if(await save(false))toast("Saved")};
 q("[data-reset]").onclick=async()=>{if(await confirmBox("Reset edits","Remove all edits from this clip and go back to the project's automatic look?","Reset")){S.ed={};S.start=clip.start;S.end=clip.end;lenInfo();panel()}};
 q("[data-render]").onclick=async()=>{
  const btn=q("[data-render]");btn.disabled=true;if(!await save(true)){btn.disabled=false;return}
  const ph=q(".ph"),bar=ph.querySelector("b"),pt=ph.querySelector(".pt");ph.classList.remove("hide");vid.classList.add("hide");
  for(;;){await new Promise(r=>setTimeout(r,900));const j=await jget("/api/jobs/"+jid),c=j.clips.find(x=>x.id==cid);
   const p=Math.round(((j.cprog||{})[cid]?.f||0)*100);pt.textContent=c.status=="rendering"?`Rendering ${p}%`:"Waiting in queue";bar.style.width=p+"%";
   if(c.status=="done"){S.file=c.file;S.rev=c.rev;ph.classList.add("hide");setVideo();vid.play().catch(()=>{});toast("Clip rendered");break}
   if(c.status=="error"){ph.classList.add("hide");vid.classList.remove("hide");toast("Render failed. See the log on the video page.","err");break}}
  btn.disabled=false;onSaved&&onSaved()};
 panel()}

function debounce(f,ms){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>f(...a),ms)}}
