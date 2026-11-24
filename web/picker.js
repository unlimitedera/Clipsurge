/* Copyright (c) 2026 unlimitedera. All Rights Reserved. File browser for this PC. */
function pickFiles({kind="video",multi=true,title="Choose files",okLabel="Add"}={}){
 return new Promise(async res=>{
  const sel=new Map();let cur=localStorage.getItem("ct_dir_"+kind)||"";let data=null,roots=null,filter="";
  const m=modal(`<div class="pk"><div class="pkhead"><h3>${esc(title)}</h3><button class="g sm" data-x>Close</button></div>
   <div class="pkbody"><nav class="pkside" aria-label="Places"></nav><div class="pkmain"><div class="pkbar"><div class="crumbs"></div><input type="text" placeholder="Filter this folder" data-f></div><div class="pklist" role="list"></div></div></div>
   <div class="mfoot"><span class="mu" data-n>Nothing selected</span><button class="g" data-all>Select all here</button><button data-ok disabled>${esc(okLabel)}</button></div></div>`,{wide:true,onClose:()=>res(null)});
  const q=s=>m.box.querySelector(s);
  const upd=()=>{q("[data-n]").textContent=sel.size?`${sel.size} selected`:"Nothing selected";q("[data-ok]").disabled=!sel.size;q("[data-ok]").textContent=sel.size?`${okLabel} ${sel.size}`:okLabel;q("[data-all]").classList.toggle("hide",!multi)};
  q("[data-x]").onclick=()=>m.close();
  q("[data-ok]").onclick=()=>{res([...sel.keys()]);m.box.closest(".mbg").remove()};
  q("[data-all]").onclick=()=>{(data?.files||[]).forEach(f=>sel.set(f.path,f));draw()};
  q("[data-f]").oninput=e=>{filter=e.target.value.toLowerCase();draw()};
  async function load(p){
   try{data=await jget("/api/fs?kind="+kind+"&path="+encodeURIComponent(p));cur=data.path;localStorage.setItem("ct_dir_"+kind,cur)}
   catch(e){toast("Cannot open that folder","err");return}
   filter="";q("[data-f]").value="";draw()}
  function side(){
   if(!roots)return;
   q(".pkside").innerHTML=`<div class="pkh">Places</div>`+roots.quick.map(r=>`<button class="pl" data-p="${esc(r.path)}">${esc(r.name)}</button>`).join("")+`<div class="pkh">Drives</div>`+roots.drives.map(r=>`<button class="pl" data-p="${esc(r.path)}">${esc(r.name)}</button>`).join("");
   q(".pkside").querySelectorAll(".pl").forEach(b=>b.onclick=()=>load(b.dataset.p))}
  function draw(){
   if(!data)return;
   const parts=data.path.split("/").filter(Boolean);let acc="";
   q(".crumbs").innerHTML=parts.map((p,i)=>{acc+=(i==0?"":"/")+p+(i==0?"/":"");return `<button class="cr" data-p="${esc(acc)}">${esc(p)}</button>`}).join('<span class="mu">/</span>');
   q(".crumbs").querySelectorAll(".cr").forEach(b=>b.onclick=()=>load(b.dataset.p));
   const dirs=data.dirs.filter(d=>d.name.toLowerCase().includes(filter));
   const files=data.files.filter(f=>f.name.toLowerCase().includes(filter));
   let h=data.parent?`<button class="row dir" data-p="${esc(data.parent)}"><span class="ic">..</span><span>Up one folder</span></button>`:"";
   h+=dirs.map(d=>`<button class="row dir" data-p="${esc(d.path)}"><span class="ic">&#9656;</span><span>${esc(d.name)}</span></button>`).join("");
   h+=files.map(f=>`<div class="row file ${sel.has(f.path)?"on":""}" data-f="${esc(f.path)}" role="listitem" tabindex="0">
     <input type="${multi?"checkbox":"radio"}" tabindex="-1" ${sel.has(f.path)?"checked":""}>
     ${kind=="video"?`<img loading="lazy" src="/api/fs/thumb?path=${encodeURIComponent(f.path)}" alt="">`:`<span class="ic">&#9835;</span>`}
     <span class="nm">${esc(f.name)}</span><span class="mu">${fmtSize(f.size)}</span><span class="mu">${new Date(f.mtime*1000).toLocaleDateString()}</span></div>`).join("");
   if(!dirs.length&&!files.length)h+=`<div class="empty">No ${kind} files here${filter?" matching the filter":""}.</div>`;
   const L=q(".pklist");L.innerHTML=h;
   L.querySelectorAll(".dir").forEach(b=>b.onclick=()=>load(b.dataset.p));
   L.querySelectorAll(".file").forEach(r=>{
    const tog=()=>{const p=r.dataset.f,f=data.files.find(x=>x.path==p);
     if(!multi){res([p]);m.box.closest(".mbg").remove();return}
     sel.has(p)?sel.delete(p):sel.set(p,f);r.classList.toggle("on",sel.has(p));r.querySelector("input").checked=sel.has(p);upd()};
    r.onclick=tog;r.onkeydown=e=>{if(e.key==" "||e.key=="Enter"){e.preventDefault();tog()}}});
   upd()}
  roots=await jget("/api/fs/roots");side();
  await load(cur||(roots.quick[0]||roots.drives[0]||{path:"C:/"}).path);upd()})}
