/* Copyright (c) 2026 unlimitedera. All Rights Reserved. Overview page. */

const OVS={done:["Done","var(--lime)"],running:["Working","var(--vio)"],queued:["Waiting","var(--mu)"],interrupted:["Paused","var(--org)"],error:["Failed","var(--red)"],cancelled:["Cancelled","#556"]};
const fmtMin=m=>m<1?"0 min":m<60?Math.round(m)+" min":Math.floor(m/60)+" h "+String(Math.round(m%60)).padStart(2,"0")+" min";
const jtime=j=>{try{const s=j.id;return Date.UTC(+s.slice(0,4),+s.slice(4,6)-1,+s.slice(6,8),+s.slice(9,11),+s.slice(11,13),+s.slice(13,15))/1000}catch(e){return 0}};

async function overviewView(){
 view="overview";
 app().innerHTML=`<div class="phead"><div><h1>Overview</h1><p class="mu">Everything Clipsurge has done so far, across all projects.</p></div><button data-p>${withIco("grid","Projects")}</button></div><div id="perf"></div><div id="ovbody"><div class="empty big">Loading...</div></div>`;
 app().querySelector("[data-p]").onclick=()=>nav("/projects");
 poll(async()=>{
  if(view!="overview")return;
  const ps=await jget("/api/projects");
  const full=await Promise.all(ps.map(p=>jget("/api/projects/"+p.id).catch(()=>({...p,jobs:[]}))));
  perfRefresh();
  const html=ovHtml(full);const b=$("ovbody");
  if(b&&b.dataset.h!==html){b.dataset.h=html;b.innerHTML=html;
   b.querySelectorAll("img[data-hide]").forEach(i=>i.onerror=()=>i.style.display="none")}
 },4000)}

function ovHtml(projects){
 const jobs=[],clips=[];
 projects.forEach(p=>(p.jobs||[]).forEach(j=>{jobs.push({...j,_p:p});(j.clips||[]).forEach(c=>clips.push({...c,_j:j,_p:p}))}));
 const done=jobs.filter(j=>j.state=="done"),dur=j=>((j.info&&j.info.duration)||0)/60;
 const mins=done.reduce((a,j)=>a+dur(j),0);
 const rendered=clips.filter(c=>c.file).length;
 const scores=clips.map(c=>+c.score).filter(x=>!isNaN(x));
 const avg=scores.length?scores.reduce((a,b)=>a+b,0)/scores.length:0;
 const active=jobs.filter(j=>j.state=="running"||j.state=="queued");
 const cnt={};jobs.forEach(j=>cnt[j.state]=(cnt[j.state]||0)+1);
 const clipMins=clips.reduce((a,c)=>a+Math.max(0,(c.end-c.start)||0),0)/60;
 const tile=(v,l,s="")=>`<div class="ovt"><b>${v}</b><span>${l}</span>${s?`<small>${s}</small>`:""}</div>`;
 const tiles=`<div class="ovtiles">${tile(jobs.length,"Videos",projects.length+" project"+(projects.length==1?"":"s"))}${tile(fmtMin(mins),"Reviewed",done.length+" finished")}${tile(clips.length,"Moments found",rendered+" rendered")}${tile(avg?Math.round(avg):"-","Average score",scores.length?"best "+Math.round(Math.max(...scores)):"")}${tile(fmtMin(clipMins),"Clip time made")}${tile(active.length,"Working now")}</div>`;
 const order=["done","running","queued","interrupted","error","cancelled"];
 const keys=[...order.filter(k=>cnt[k]),...Object.keys(cnt).filter(k=>!order.includes(k))];
 const seg=jobs.length?`<div class="ovbar">${keys.map(k=>`<i style="flex:${cnt[k]};background:${(OVS[k]||[0,"var(--mu)"])[1]}" title="${(OVS[k]||[k])[0]}: ${cnt[k]}"></i>`).join("")}</div><div class="ovleg">${keys.map(k=>`<span><u style="background:${(OVS[k]||[0,"var(--mu)"])[1]}"></u>${(OVS[k]||[k])[0]} <b>${cnt[k]}</b></span>`).join("")}</div>`:`<div class="empty">No videos yet.</div>`;
 const act=active.length?active.map(j=>`<a class="ovrow" href="#/p/${j.project}/v/${j.id}"><span class="ovn">${esc(j.title||j.source||j.id)}</span><span class="mu small">${esc(j.note||"")}</span><span class="ovp"><i style="width:${Math.max(2,Math.round(j.overall||0))}%"></i></span><b class="mono">${Math.round(j.overall||0)}%</b></a>`).join(""):`<div class="mu small">Nothing is being processed.</div>`;
 const top=[...clips].sort((a,b)=>b.score-a.score).slice(0,10);
 const rank=top.length?top.map((c,i)=>`<a class="ovrow rk" href="#/p/${c._p.id}/v/${c._j.id}?clip=${c.id}"><b class="ovi">${i+1}</b><span class="ovth"><img data-hide loading="lazy" src="/api/jobs/${c._j.id}/clips/${c.id}/poster" alt=""></span><span class="ovn">${esc(c.title||"Untitled")}<small class="mu">${esc(c._j.title||"")} · ${esc(c._p.name)}</small></span><span class="mu small mono">${Math.round(c.end-c.start)}s</span><span class="score">${Math.round(c.score)}</span></a>`).join(""):`<div class="mu small">No moments yet.</div>`;
 const prank=projects.map(p=>{const js=p.jobs||[],cs=js.flatMap(j=>j.clips||[]),sc=cs.map(c=>+c.score).filter(x=>!isNaN(x));
  return {p,v:js.length,m:js.filter(j=>j.state=="done").reduce((a,j)=>a+dur(j),0),c:cs.length,avg:sc.length?sc.reduce((a,b)=>a+b,0)/sc.length:0,best:sc.length?Math.max(...sc):0}}).sort((a,b)=>b.avg-a.avg||b.c-a.c);
 const ptab=`<table class="ovtab"><thead><tr><th>Project</th><th>Videos</th><th>Reviewed</th><th>Moments</th><th>Avg</th><th>Best</th></tr></thead><tbody>${prank.map(r=>`<tr onclick="nav('/p/${r.p.id}')"><td>${esc(r.p.name)}</td><td>${r.v}</td><td>${fmtMin(r.m)}</td><td>${r.c}</td><td>${r.avg?Math.round(r.avg):"-"}</td><td>${r.best?Math.round(r.best):"-"}</td></tr>`).join("")}</tbody></table>`;
 const recent=[...jobs].sort((a,b)=>jtime(b)-jtime(a)).slice(0,8).map(j=>{const s=OVS[j.state]||[j.state,"var(--mu)"];const n=(j.clips||[]).length;
  return `<a class="ovrow" href="#/p/${j.project}/v/${j.id}"><span class="ovn">${esc(j.title||j.source||j.id)}<small class="mu">${esc(j._p.name)} · ${ago(jtime(j))}</small></span><span class="mu small mono">${j.info&&j.info.duration?fmtMin(dur(j)):""}</span><span class="mu small">${n} moment${n==1?"":"s"}</span><span class="ovst" style="color:${s[1]}">${s[0]}</span></a>`}).join("")||`<div class="mu small">No videos yet.</div>`;
 return tiles+`<div class="ovgrid"><div class="card"><h3>Video status</h3>${seg}<h3 style="margin-top:18px">In progress</h3>${act}</div><div class="card"><h3>Projects ranked by average score</h3>${ptab}</div></div>
 <div class="ovgrid"><div class="card"><h3>Top moments</h3>${rank}</div><div class="card"><h3>Recent videos</h3>${recent}</div></div>`}
