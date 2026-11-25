/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Full video player + manual clipping. */

let VP=null;   // {jid, dur, a, b, energy, clips, o:{...options}}
const tfmt=s=>{s=Math.max(0,s||0);const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=(s%60).toFixed(1).padStart(4,"0");return (h?h+":"+String(m).padStart(2,"0"):m)+":"+x};
const tparse=v=>{v=String(v).trim().replace(",",".");if(!v)return NaN;if(/^\d+(\.\d+)?$/.test(v))return +v;const p=v.split(":").map(Number);if(p.some(isNaN)||p.length>3)return NaN;return p.reduce((a,x)=>a*60+x,0)};
const VPO_DEF={layout:"",cx:0.5,cy:0.5,zoom:1,cstyle:"",cpos:"",csize:"",cper:"",cupper:"",chi:""};
const vpoLoad=()=>{try{return {...VPO_DEF,...JSON.parse(localStorage.getItem("ct_vp_opts")||"{}")}}catch(e){return {...VPO_DEF}}};
const vpoSave=()=>{try{localStorage.setItem("ct_vp_opts",JSON.stringify(VP.o))}catch(e){}};

function vplayInit(jid){
 const host=$("vplay");if(!host)return;
 VP={jid,dur:0,a:null,b:null,energy:null,clips:[],o:vpoLoad()};
 host.innerHTML=`<div class="row sp"><div><b>Full video and manual clips</b><div class="mu small">Watch the whole video, mark a part, choose how it is cropped and captioned, then add it.</div></div><button class="g sm" id="vpToggle">Open</button></div><div id="vpBody" class="hide"></div>`;
 $("vpToggle").onclick=()=>{const b=$("vpBody"),open=b.classList.contains("hide");b.classList.toggle("hide",!open);$("vpToggle").textContent=open?"Close":"Open";if(open&&!b.dataset.ready){b.dataset.ready=1;vplayBuild()}else if(!open){const v=$("vpVid");v&&v.pause()}}}

async function vplayBuild(){
 const j=await jget("/api/jobs/"+VP.jid);
 if(!j.video){$("vpBody").innerHTML=`<p class="mu">The video is not downloaded yet. Come back when step 1 is done.</p>`;$("vpBody").dataset.ready="";return}
 try{const h=await fetch(`/files/${VP.jid}/${encodeURIComponent(j.video)}`,{method:"HEAD"});if(!h.ok)throw 0}catch(e){
  $("vpBody").innerHTML=`<p class="mu">The downloaded video was deleted to free space. Get it again to watch it and mark clips.</p><button id="vpRefetch">Get the video again</button>`;$("vpBody").dataset.ready="";
  $("vpRefetch").onclick=async()=>{await post(`/api/jobs/${VP.jid}/redo`,{step:0,through_end:false});toast("Downloading the video again");$("vpBody").innerHTML=`<p class="mu">Downloading... open this again when the first step is done.</p>`};return}
 VP.dur=j.info?.duration||0;VP.clips=j.clips||[];const o=VP.o;
 const sel=(id,v,l)=>`<label>${l[0]}<select id="${id}">${l[1].map(([k,t])=>`<option value="${k}" ${String(v)===String(k)?"selected":""}>${t}</option>`).join("")}</select></label>`;
 $("vpBody").innerHTML=`<div class="vpwrap" id="vpWrap"><video id="vpVid" controls preload="metadata" playsinline src="/files/${VP.jid}/${encodeURIComponent(j.video)}"></video><div id="vpCrop" class="hide" title="Drag to place the crop"><i></i></div></div>
  <div class="vpmsg err small hide" id="vpErr">This browser cannot play this video format. You can still type times, and the clip is cut from the original file.</div>
  <canvas id="vpTl" height="84" aria-label="Loudness timeline: click to jump"></canvas>
  <div class="vprow"><button id="vpPart">＋ Add clip part</button><button class="g sm hide" id="vpDrop">Remove part</button><span class="mu small" id="vpTip">Click the timeline to jump. Press the button to mark a part at the playhead, then drag it or its ends.</span></div>
  <div class="vprow hide" id="vpRange"><button class="g sm" id="vpIn">Set start (I)</button><label class="vpt"><input type="text" id="vpA" placeholder="0:00.0"></label>
   <span class="mu">to</span><label class="vpt"><input type="text" id="vpB" placeholder="0:00.0"></label><button class="g sm" id="vpOut">Set end (O)</button><b class="mono" id="vpLen"></b>
   <span class="mu small">Length:</span>${[15,30,45,60].map(s=>`<button class="chip2" data-len="${s}">${s} s</button>`).join("")}<button class="g sm" id="vpPrev">Preview</button></div>
  <div class="vpopts"><div><h4 class="cr-h">Crop</h4>
    <div class="two">${sel("vpLayout",o.layout,["Crop style",[["","Same as the video"],...LAYOPT.filter(x=>x[0]!="auto"||1),["manual","Manual crop (place it on the video)"]]])}
     <label id="vpZoomL" class="${o.layout=="manual"?"":"hide"}">Zoom <b class="mu" id="vpZoomV"></b><input type="range" class="glrange" id="vpZoom" min="0.3" max="1" step="0.01" value="${o.zoom}"></label></div>
    <p class="mu small" id="vpCropNote"></p></div>
   <div><h4 class="cr-h">Captions</h4><div class="three">
    ${sel("vpCStyle",o.cstyle,["Style",[["","Same as the video"],["pop","Pop"],["clean","Clean"],["fire","Fire"],["off","No captions"]]])}
    ${sel("vpCPos",o.cpos,["Position",[["","Default"],["bottom","Bottom"],["middle","Middle"],["top","Top"]]])}
    <label>Size<input type="number" id="vpCSize" min="40" max="160" placeholder="auto" value="${o.csize}"></label>
    ${sel("vpCPer",o.cper,["Words per line",[["","Default"],...[1,2,3,4,5,6].map(n=>[n,n])]])}
    ${sel("vpCens",o.cens,["Bad language",[["","Follow the setting above"],["on","Hide curse words"],["off","Show as spoken"]]])}
    ${sel("vpCUp",o.cupper,["Letters",[["","Default"],["1","ALL CAPS"],["0","Normal"]]])}
    <label>Highlight colour<input type="color" id="vpCHi" value="${o.chi||"#c6ff3d"}"></label></div></div></div>
  <div class="vprow"><label class="grow vpttl">Title<input type="text" id="vpTitle" dir="auto" placeholder="Custom clip" maxlength="95"></label><button id="vpAdd">Add clip</button><button class="g" id="vpAddEd">Add and open editor</button></div>
  <div class="mu small" id="vpHint"></div>`;
 const v=$("vpVid"),cv=$("vpTl");
 v.onerror=()=>$("vpErr").classList.remove("hide");
 v.addEventListener("loadedmetadata",()=>{if(!VP.dur)VP.dur=v.duration;draw();cropPlace()});
 v.addEventListener("timeupdate",()=>{draw();if(VP.prev&&v.currentTime>=VP.b){v.pause();VP.prev=false}});
 try{VP.energy=await jget(`/api/jobs/${VP.jid}/energy`)}catch(e){VP.energy=[]}
 const xOf=t=>t/Math.max(VP.dur,1)*cv.width,tOf=x=>Math.min(VP.dur,Math.max(0,x/cv.width*VP.dur));
 function size(){const w=cv.clientWidth||800;if(cv.width!==w){cv.width=w;draw()}}
 window.addEventListener("resize",()=>{size();cropPlace()});
 const has=()=>VP.a!=null&&VP.b!=null&&VP.b>VP.a;
 function draw(){
  if(!cv.isConnected)return;size();const g=cv.getContext("2d"),W=cv.width,H=cv.height,css=getComputedStyle(document.documentElement);
  const lime=css.getPropertyValue("--lime").trim()||"#c6ff3d",mu=css.getPropertyValue("--mu").trim()||"#888",ln=css.getPropertyValue("--ln").trim()||"#333";
  g.clearRect(0,0,W,H);
  VP.clips.forEach(c=>{g.fillStyle=lime+"22";g.fillRect(xOf(c.start),0,Math.max(2,xOf(c.end)-xOf(c.start)),H)});
  const e=VP.energy||[];
  if(e.length){const n=e.length;g.fillStyle=mu+"aa";for(let x=0;x<W;x++){const i0=Math.floor(x/W*n),i1=Math.max(i0+1,Math.floor((x+1)/W*n));let m=0;for(let i=i0;i<i1&&i<n;i++)if(e[i]>m)m=e[i];const h=Math.max(1,m*(H-10));g.fillRect(x,(H-h)/2,1,h)}}
  if(has()){const x1=xOf(VP.a),x2=xOf(VP.b);g.fillStyle=lime+"40";g.fillRect(x1,0,x2-x1,H);g.strokeStyle=lime;g.lineWidth=2;g.strokeRect(x1+1,1,x2-x1-2,H-2);
   g.fillStyle=lime;g.fillRect(x1-2,H/2-14,6,28);g.fillRect(x2-4,H/2-14,6,28)}
  g.fillStyle=css.getPropertyValue("--tx").trim()||"#fff";g.fillRect(xOf(v.currentTime||0)-1,0,2,H);
  g.strokeStyle=ln;g.lineWidth=1;g.strokeRect(.5,.5,W-1,H-1)}
 window.vpDraw=draw;
 // timeline: a plain click only seeks (and dragging scrubs). A marked part can be moved or resized.
 const px=e=>e.clientX-cv.getBoundingClientRect().left;
 const hit=x=>{if(!has())return null;const x1=xOf(VP.a),x2=xOf(VP.b);if(Math.abs(x-x1)<9)return "a";if(Math.abs(x-x2)<9)return "b";if(x>x1&&x<x2)return "move";return null};
 cv.onmousemove=e=>{if(!cv.dataset.drag){const h=hit(px(e));cv.style.cursor=h=="a"||h=="b"?"ew-resize":h=="move"?"grab":"pointer"}};
 cv.onmousedown=e=>{const x=px(e),h=hit(x);let last=x;cv.dataset.drag=1;if(h=="move")cv.style.cursor="grabbing";
  if(!h)v.currentTime=tOf(x);
  const mv=ev=>{const xx=px(ev);
   if(!h){v.currentTime=tOf(xx)}
   else if(h=="move"){const d=tOf(xx)-tOf(last),len=VP.b-VP.a;let a=VP.a+d;a=Math.max(0,Math.min(VP.dur-len,a));VP.a=a;VP.b=a+len;last=xx;v.currentTime=VP.a}
   else{VP[h]=tOf(xx);if(VP.a>VP.b-0.5){if(h=="a")VP.a=VP.b-0.5;else VP.b=VP.a+0.5}}
   sync()};
  const up=()=>{window.removeEventListener("mousemove",mv);window.removeEventListener("mouseup",up);delete cv.dataset.drag;sync()};
  window.addEventListener("mousemove",mv);window.addEventListener("mouseup",up);e.preventDefault()};
 function sync(){
  const ok=has(),R=$("vpRange");R.classList.toggle("hide",!ok);$("vpDrop").classList.toggle("hide",!ok);$("vpTip").classList.toggle("hide",ok);
  const A=$("vpA"),B=$("vpB");if(document.activeElement!==A)A.value=VP.a!=null?tfmt(VP.a):"";if(document.activeElement!==B)B.value=VP.b!=null?tfmt(VP.b):"";
  const len=ok?VP.b-VP.a:0;$("vpLen").textContent=ok?len.toFixed(1)+" s":"";
  $("vpAdd").disabled=!ok;$("vpAddEd").disabled=!ok;
  $("vpHint").textContent=!ok?"Press Add clip part to mark a part of the video.":len<3?"Very short clip. Most platforms like 15 s or more.":len>180?"Long for a short clip (over 3 minutes).":"";draw()}
 window.vpSync=sync;
 function mark(){const t=v.currentTime||0,len=Math.min(30,Math.max(5,VP.dur-t));VP.a=Math.max(0,Math.min(t,VP.dur-len));VP.b=Math.min(VP.dur||t+len,VP.a+len);sync()}
 $("vpPart").onclick=mark;$("vpDrop").onclick=()=>{VP.a=VP.b=null;sync()};
 function setIn(){VP.a=v.currentTime;if(VP.b==null||VP.b<=VP.a)VP.b=Math.min(VP.dur,VP.a+30);sync()}
 function setOut(){VP.b=v.currentTime;if(VP.a==null||VP.a>=VP.b)VP.a=Math.max(0,VP.b-30);sync()}
 window.vpKeys={setIn,setOut};
 $("vpIn").onclick=setIn;$("vpOut").onclick=setOut;
 for(const [id,k] of [["vpA","a"],["vpB","b"]]){$(id).onchange=e=>{const t=tparse(e.target.value);if(!isNaN(t)){VP[k]=Math.min(VP.dur||t,Math.max(0,t));if(k=="a"&&v.readyState)v.currentTime=VP.a}sync();e.target.value=VP[k]!=null?tfmt(VP[k]):""}}
 $("vpBody").querySelectorAll("[data-len]").forEach(b=>b.onclick=()=>{if(VP.a==null)return;VP.b=Math.min(VP.dur||1e9,VP.a+(+b.dataset.len));sync()});
 $("vpPrev").onclick=()=>{v.currentTime=VP.a;VP.prev=true;v.play()};
 // ---- crop box on the video ----
 const cb=$("vpCrop");
 function vrect(){const w=$("vpWrap"),r=v.getBoundingClientRect(),W=w.getBoundingClientRect(),vw=v.videoWidth||16,vh=v.videoHeight||9,s=Math.min(r.width/vw,r.height/vh),dw=vw*s,dh=vh*s;
  return {x:r.left-W.left+(r.width-dw)/2,y:r.top-W.top+(r.height-dh)/2,w:dw,h:dh}}
 function cropPlace(){
  const manual=VP.o.layout=="manual";cb.classList.toggle("hide",!manual);$("vpZoomL").classList.toggle("hide",!manual);
  $("vpZoomV").textContent=Math.round(VP.o.zoom*100)+"%";$("vpZoom").style.setProperty("--p",((VP.o.zoom-0.3)/0.7*100)+"%");
  $("vpCropNote").textContent=manual?"Drag the green box on the video to choose what stays in the vertical clip. Zoom makes it tighter.":({"":"The clip is cropped the same way as the rest of this video.",auto:"Finds the webcam, else follows faces.",stack:"Webcam on top, gameplay below.",game:"Centre slice of the screen.",fit:"Whole screen over a blurred copy.",follow:"Follows one face.",speaker:"Cuts to whoever is talking."}[VP.o.layout]||"");
  if(!manual)return;const r=vrect(),ch=VP.o.zoom*r.h,cw=ch*9/16;
  const cx=Math.min(1-cw/r.w/2,Math.max(cw/r.w/2,VP.o.cx)),cy=Math.min(1-VP.o.zoom/2,Math.max(VP.o.zoom/2,VP.o.cy));VP.o.cx=cx;VP.o.cy=cy;
  Object.assign(cb.style,{left:(r.x+cx*r.w-cw/2)+"px",top:(r.y+cy*r.h-ch/2)+"px",width:cw+"px",height:ch+"px"})}
 cb.onmousedown=e=>{const r0=vrect(),sx=e.clientX,sy=e.clientY,cx0=VP.o.cx,cy0=VP.o.cy;
  const mv=ev=>{VP.o.cx=cx0+(ev.clientX-sx)/r0.w;VP.o.cy=cy0+(ev.clientY-sy)/r0.h;cropPlace()};
  const up=()=>{window.removeEventListener("mousemove",mv);window.removeEventListener("mouseup",up);vpoSave()};
  window.addEventListener("mousemove",mv);window.addEventListener("mouseup",up);e.preventDefault()};
 $("vpLayout").onchange=e=>{VP.o.layout=e.target.value;vpoSave();cropPlace()};
 $("vpZoom").oninput=e=>{VP.o.zoom=+e.target.value;cropPlace()};$("vpZoom").onchange=vpoSave;
 for(const [id,k] of [["vpCens","cens"],["vpCStyle","cstyle"],["vpCPos","cpos"],["vpCSize","csize"],["vpCPer","cper"],["vpCUp","cupper"]])$(id).onchange=e=>{VP.o[k]=e.target.value;vpoSave()};
 $("vpCHi").onchange=e=>{VP.o.chi=e.target.value;vpoSave()};
 // ---- add ----
 function buildEdit(){const o=VP.o,e={};
  if(o.layout){e.layout=o.layout;if(o.layout=="manual")e.manual={cx:+o.cx.toFixed(4),cy:+o.cy.toFixed(4),zoom:+(+o.zoom).toFixed(3)}}
  const c={};if(o.cstyle)c.style=o.cstyle;if(o.cpos)c.pos=o.cpos;if(o.csize)c.size=+o.csize;if(o.cper)c.per=+o.cper;if(o.cupper!=="")c.upper=o.cupper=="1";if(o.chi)c.hi=o.chi;
  if(o.cens)e.censor=o.cens;
  if(Object.keys(c).length)e.captions=c;return Object.keys(e).length?e:null}
 async function add(openEd){
  const title=$("vpTitle").value.trim()||"Custom clip";$("vpAdd").disabled=$("vpAddEd").disabled=true;
  const r=await post(`/api/jobs/${VP.jid}/clips`,{start:+VP.a.toFixed(2),end:+VP.b.toFixed(2),title,edit:buildEdit()});
  if(r.ok){const d=await r.json();VP.clips.push({start:VP.a,end:VP.b});$("vpTitle").value="";toast(openEd?"Clip added. Opening the editor.":"Clip added. Rendering it now.");
   if(openEd&&typeof openEditor=="function")setTimeout(()=>openEditor(VP.jid,d.id),400)}
  else toast((await r.json().catch(()=>({}))).detail||"Could not add the clip","err");
  sync()}
 $("vpAdd").onclick=()=>add(false);$("vpAddEd").onclick=()=>add(true);
 if(!window.__vpKeys){window.__vpKeys=true;document.addEventListener("keydown",e=>{
  const v=$("vpVid"),b=document.getElementById("vpBody");if(!v||typeof view=="undefined"||view!="video"||!VP||!b||b.classList.contains("hide"))return;
  if(/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)||e.ctrlKey||e.metaKey||e.altKey)return;
  const k=e.key.toLowerCase();
  if(k=="i"){window.vpKeys.setIn()}else if(k=="o"){window.vpKeys.setOut()}else if(k==" "){v.paused?v.play():v.pause()}
  else if(e.key=="ArrowLeft"){v.currentTime=Math.max(0,v.currentTime-5)}else if(e.key=="ArrowRight"){v.currentTime=Math.min(VP.dur,v.currentTime+5)}else return;
  e.preventDefault()})}
 size();sync();cropPlace()}

function vplayUpdate(j){if(VP&&VP.jid==j.id){VP.clips=j.clips||[];if(window.vpDraw&&$("vpTl"))window.vpDraw()}}
