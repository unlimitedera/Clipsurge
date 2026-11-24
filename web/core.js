/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Shared helpers. */
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const fmt=s=>{s=Math.max(0,Math.round(s));const h=Math.floor(s/3600);return (h?h+":":"")+String(Math.floor(s%3600/60)).padStart(h?2:1,"0")+":"+String(s%60).padStart(2,"0")};
const fmtSize=b=>b>1e9?(b/1e9).toFixed(1)+" GB":b>1e6?(b/1e6).toFixed(0)+" MB":Math.max(1,Math.round(b/1e3))+" KB";
const api=(u,o)=>fetch(u,o);
const post=(u,b)=>api(u,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b||{})});
const jget=async u=>{const r=await fetch(u);if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.status);return r.json()};
const ago=ts=>{const d=Date.now()/1000-ts;return d<90?"just now":d<3600?Math.round(d/60)+" min ago":d<86400?Math.round(d/3600)+" h ago":Math.round(d/86400)+" d ago"};

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
