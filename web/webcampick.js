/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Choose the webcam by dragging on the video. */
function webcamPicker(jid,done){
 jget("/api/jobs/"+jid).then(j=>{
  const dur=j.info?.duration||60,t0=Math.round(dur*0.3);let t=t0;
  const m=modal(`<h3>Where is the webcam?</h3><p class="mu">Drag a box around the webcam on the picture. Move through the video if it is not visible here.</p>
   <div class="wcbox" id="wcb"><img id="wcimg" alt="video frame" draggable="false"><div id="wcsel" class="hide"></div></div>
   <div class="row" style="margin-top:10px"><span class="mu small">Another moment</span><input type="range" class="glrange" id="wct" min="0" max="${Math.floor(dur)}" step="5" value="${t0}" style="max-width:340px"><span class="mono small" id="wctv"></span></div>
   <div class="mu small" id="wcmsg">Press and drag on the picture.</div>
   <div class="mfoot"><button class="g" data-x>Cancel</button><button class="g" data-none>There is no webcam</button>${j.webcam&&j.webcam.manual?'<button class="g" data-auto>Detect automatically again</button>':""}<button data-ok disabled>Use this area</button></div>`,{wide:true});
  const q=s=>m.box.querySelector(s),img=q("#wcimg"),b=q("#wcb"),sel=q("#wcsel");let box=null;
  const load=()=>{img.src=`/api/jobs/${jid}/frame?t=${t}&w=1280`;q("#wctv").textContent=fmt(t)};
  load();let tm=null;q("#wct").oninput=e=>{t=+e.target.value;q("#wctv").textContent=fmt(t);clearTimeout(tm);tm=setTimeout(load,250)};
  const draw=()=>{if(!box){sel.classList.add("hide");return}const r=img.getBoundingClientRect(),br=b.getBoundingClientRect(),ox=r.left-br.left,oy=r.top-br.top;
   sel.classList.remove("hide");Object.assign(sel.style,{left:ox+box[0]*r.width+"px",top:oy+box[1]*r.height+"px",width:(box[2]-box[0])*r.width+"px",height:(box[3]-box[1])*r.height+"px"})};
  const pt=e=>{const r=img.getBoundingClientRect();return [Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))]};
  b.onmousedown=e=>{if(e.target!==img&&e.target!==sel&&e.target!==b)return;const a=pt(e);
   const mv=ev=>{const c=pt(ev);box=[Math.min(a[0],c[0]),Math.min(a[1],c[1]),Math.max(a[0],c[0]),Math.max(a[1],c[1])];draw();
    const ok=(box[2]-box[0])>=0.04&&(box[3]-box[1])>=0.04;q("[data-ok]").disabled=!ok;q("#wcmsg").textContent=ok?"Looks good? Press Use this area, or drag again.":"Make the box a little bigger."};
   const up=()=>{window.removeEventListener("mousemove",mv);window.removeEventListener("mouseup",up)};window.addEventListener("mousemove",mv);window.addEventListener("mouseup",up);e.preventDefault()};
  img.onload=draw;
  const send=async body=>{const r=await post(`/api/jobs/${jid}/webcam`,body);if(!r.ok){toast((await r.json().catch(()=>({}))).detail||"Could not save","err");return}m.close();done&&done()};
  q("[data-x]").onclick=()=>m.close();
  q("[data-ok]").onclick=()=>send({box:box.map(v=>+v.toFixed(4))});
  q("[data-none]").onclick=()=>send({box:null});
  const au=q("[data-auto]");if(au)au.onclick=()=>send({auto:true})})}
async function webcamChosen(jid){
 toast("Webcam saved");
 if(await confirmBox("Use it now?","Render this video's clips again so they use the webcam you chose?","Re-render all clips"))await api(`/api/jobs/${jid}/rerender-all`,{method:"POST"})}
