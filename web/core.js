/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Shared helpers. */
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt=s=>{s=Math.max(0,Math.round(s));const h=Math.floor(s/3600);return (h?h+":":"")+String(Math.floor(s%3600/60)).padStart(h?2:1,"0")+":"+String(s%60).padStart(2,"0")};
const fmtSize=b=>b>1e9?(b/1e9).toFixed(1)+" GB":b>1e6?(b/1e6).toFixed(0)+" MB":Math.max(1,Math.round(b/1e3))+" KB";
const api=(u,o)=>fetch(u,o);
const post=(u,b)=>api(u,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})});
const jget=async u=>{const r=await fetch(u);if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.status);return r.json()};
const ago=ts=>{const d=Date.now()/1000-ts;return d<90?"just now":d<3600?Math.round(d/60)+" min ago":d<86400?Math.round(d/3600)+" h ago":Math.round(d/86400)+" d ago"};

/* update a container's DOM in place (no flicker, CSS transitions such as progress bars keep running) */
function morphInto(el,html){if(el.dataset.h===html)return;el.dataset.h=html;const t=document.createElement("div");t.innerHTML=html;morph(el,t)}
function morph(a,b){
 const ca=[...a.childNodes],cb=[...b.childNodes];
 cb.forEach((y,i)=>{const x=ca[i];
  if(!x){a.appendChild(y.cloneNode(true));return}
  if(x.nodeType!==y.nodeType||(x.nodeType==1&&x.tagName!==y.tagName)){a.replaceChild(y.cloneNode(true),x);return}
  if(x.nodeType==3){if(x.nodeValue!==y.nodeValue)x.nodeValue=y.nodeValue;return}
  if(x.nodeType!=1)return;
  [...x.attributes].forEach(at=>{if(!y.hasAttribute(at.name))x.removeAttribute(at.name)});
  [...y.attributes].forEach(at=>{if(x.getAttribute(at.name)!==at.value)x.setAttribute(at.name,at.value)});
  morph(x,y)});
 while(a.childNodes.length>cb.length)a.removeChild(a.lastChild)}

function toast(msg,kind){
 let box=$("toasts");if(!box){box=document.createElement("div");box.id="toasts";box.setAttribute("aria-live","polite");document.body.appendChild(box)}
 const t=document.createElement("div");t.className="toast "+(kind||"");t.textContent=msg;box.appendChild(t);setTimeout(()=>t.remove(),kind=="err"?6000:3200)}

function modal(html,opts={}){
 const bg=document.createElement("div");bg.className="mbg";
 bg.innerHTML=`<div class="modal ${opts.wide?"wide":""} ${opts.full?"full":""}" role="dialog" aria-modal="true">${html}</div>`;
 document.body.appendChild(bg);const box=bg.firstElementChild;
 const close=v=>{bg.remove();document.removeEventListener("keydown",key);opts.onClose&&opts.onClose(v)};
 const key=e=>{if(e.key=="Escape"&&bg.parentNode&&bg===[...document.querySelectorAll(".mbg")].pop())close()};
 document.addEventListener("keydown",key);
 bg.addEventListener("mousedown",e=>{if(e.target===bg&&!opts.sticky)close()});
 setTimeout(()=>{const f=box.querySelector("[autofocus]")||box.querySelector("input,textarea,button");f&&f.focus()},30);
 return {box,close}}

function confirmBox(title,body,okLabel="Delete"){
 return new Promise(res=>{
  const m=modal(`<h3>${esc(title)}</h3><p class="mu">${esc(body)}</p><div class="mfoot"><button class="g" data-x>Cancel</button><button class="danger" data-ok>${esc(okLabel)}</button></div>`,{onClose:()=>res(false)});
  m.box.querySelector("[data-x]").onclick=()=>m.close();
  m.box.querySelector("[data-ok]").onclick=()=>{res(true);m.box.closest(".mbg").remove()}})}

const ICONS={
 plus:'<path d="M12 5v14M5 12h14"/>',grid:'<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
 sliders:'<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
 refresh:'<path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/>',
 pencil:'<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
 trash:'<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6"/>',
 x:'<path d="M18 6 6 18M6 6l12 12"/>',upload:'<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
 download:'<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',record:'<circle cx="12" cy="12" r="6" fill="currentColor"/>',
 stop:'<rect x="6" y="6" width="12" height="12" fill="currentColor"/>',search:'<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
 play:'<path d="M7 4l13 8-13 8z" fill="currentColor"/>',check:'<path d="M20 6 9 17l-5-5"/>',folder:'<path d="M3 6h6l2 2h10v11H3z"/>',
 film:'<rect x="3" y="3" width="18" height="18"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
 power:'<path d="M12 2v9"/><path d="M18.4 6.6a9 9 0 1 1-12.8 0"/>',scissors:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>',
 sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
 moon:'<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
 calendar:'<rect x="3" y="4" width="18" height="18"/><path d="M16 2v4M8 2v4M3 10h18"/>'};
function ico(n,s=14){return `<svg class="ic" viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" stroke-linejoin="miter" aria-hidden="true">${ICONS[n]||""}</svg>`}
const withIco=(n,t,s)=>ico(n,s)+`<span>${t}</span>`;

function makeTags(host,initial=[],placeholder="Type and press Enter"){
 let tags=[...initial];
 host.classList.add("tagin");
 const draw=()=>{host.innerHTML=tags.map((t,i)=>`<span class="tg">${esc(t)}<button type="button" class="x" data-i="${i}" aria-label="Remove ${esc(t)}">&times;</button></span>`).join("")+`<input type="text" placeholder="${tags.length?"":esc(placeholder)}" aria-label="${esc(placeholder)}">`;
  const inp=host.querySelector("input");
  host.querySelectorAll(".x").forEach(b=>b.onclick=e=>{e.stopPropagation();tags.splice(+b.dataset.i,1);draw();host.querySelector("input").focus()});
  const commit=()=>{const v=inp.value.replace(/,$/,"").trim();if(v&&!tags.includes(v)&&tags.length<30){tags.push(v);draw();host.querySelector("input").focus()}else inp.value=""};
  inp.onkeydown=e=>{if(e.key=="Enter"||e.key==","){e.preventDefault();commit()}else if(e.key=="Backspace"&&!inp.value&&tags.length){tags.pop();draw();host.querySelector("input").focus()}};
  inp.onblur=()=>{if(inp.value.trim())commit()};
  host.onclick=()=>inp.focus()};
 draw();
 return {get:()=>{const i=host.querySelector("input");if(i&&i.value.trim()&&!tags.includes(i.value.trim()))tags.push(i.value.trim());return [...tags]},
  add:t=>{if(!tags.includes(t)&&tags.length<30){tags.push(t);draw()}}}}

/* Clip previews: a click anywhere on the picture plays or pauses it (the bottom strip keeps the normal controls). */
document.addEventListener("click",e=>{
 const v=e.target;if(!(v instanceof HTMLVideoElement)||!v.closest(".phone"))return;
 const r=v.getBoundingClientRect();if(e.clientY>r.bottom-48)return;
 e.stopImmediatePropagation();e.preventDefault();
 if(v.paused){document.querySelectorAll(".phone video").forEach(o=>{if(o!==v)o.pause()});v.play().catch(()=>{})}else v.pause()},true);
