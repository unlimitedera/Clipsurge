/* Copyright (c) 2026 unlimitedera. All Rights Reserved. SurgeAI: chat with your AI model about a project or a video. */
(function(){
 const fab=document.createElement("button");fab.id="askfab";fab.hidden=true;fab.title="Ask SurgeAI";fab.innerHTML=`<span class="fb">${surgeBot(24)}</span><span class="sname"><b>Surge</b>AI</span>`;
 document.body.appendChild(fab);
 let panel=null,scope=null,busy=false,ctl=null;
 const key=()=>"ct_chat_"+scope.scope+"_"+scope.id;
 const load=()=>{try{return JSON.parse(localStorage.getItem(key())||"[]")}catch(e){return[]}};
 const save=h=>{try{localStorage.setItem(key(),JSON.stringify(h.slice(-30)))}catch(e){}};
 function where(){
  const h=(location.hash||"").slice(1).split("?")[0];let m;
  if(m=h.match(/^\/p\/([^/]+)\/v\/([^/]+)/))return {scope:"video",id:m[2],pid:m[1]};
  if(m=h.match(/^\/p\/([^/]+)$/))return {scope:"project",id:m[1],pid:m[1]};
  return null}
 function sync(){const w=where();fab.hidden=!w;
  if(!w){close();return}
  if(!scope||scope.id!==w.id){const was=!!panel;close();scope=w;if(was)open()}else scope=w}
 function md(s){
  s=esc(s).replace(/```([\s\S]*?)```/g,(_,c)=>`<pre>${c.trim()}</pre>`).replace(/`([^`\n]+)`/g,"<code>$1</code>").replace(/\*\*([^*\n]+)\*\*/g,"<b>$1</b>");
  const out=[];let list=null;
  for(const raw of s.split("\n")){
   let m;
   if(m=raw.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/)){const t=/^\s*\d/.test(raw)?"ol":"ul";if(list!==t){if(list)out.push(`</${list}>`);out.push(`<${t}>`);list=t}out.push(`<li>${m[1]}</li>`);continue}
   if(list){out.push(`</${list}>`);list=null}
   if(m=raw.match(/^#{1,4}\s+(.*)$/)){out.push(`<h5>${m[1]}</h5>`);continue}
   out.push(raw.trim()?`<p>${raw}</p>`:"")}
  if(list)out.push(`</${list}>`);
  return out.join("").replace(/(^|[\s>(])(#[\p{L}\p{N}_]{2,30})/gu,'$1<button class="hashc" data-tag="$2">$2</button>')}
 const SUGG={video:["Give me 5 better titles for my top clip","Which tags should I use for this video?","How can I raise the scores of the low clips?","Which moments did I probably miss?"],
             project:["What kind of clips should I look for next?","Give me ideas for the next 5 clips","How do I improve my average score?","Write a better description of what to look for"]};
 function open(){
  if(panel)return;sync();if(!scope)return;
  panel=document.createElement("aside");panel.id="askpanel";
  panel.innerHTML=`<div class="ah"><div class="abot" id="askBot">${surgeBot(46,"wave")}</div><div class="ttl"><span class="sname big"><b>Surge</b>AI</span><div class="mu small" id="askctx"></div></div><div class="row" style="gap:6px"><button class="g sm" data-clr title="Clear this chat">Clear</button><button class="g sm" data-cl title="Close">✕</button></div></div>
   ${scope.scope=="video"?`<div class="af"><label class="small mu">Focus on<select id="askClip"><option value="">the whole video</option></select></label></div>`:""}
   <div class="alog" id="askLog" aria-live="polite"></div>
   <div class="asug" id="askSug"></div>
   <div class="ain"><textarea id="askIn" rows="2" placeholder="Ask SurgeAI about ideas, titles, tags, or how to raise scores..."></textarea><button id="askGo">Send</button></div>
   <div class="mu small anote">Answers come from your connected model and the data Clipsurge has. They can be wrong, and nobody can promise a video will go viral.</div>`;
  document.body.appendChild(panel);fab.classList.add("on");
  jget("/api/status").then(s=>{$("askctx").textContent=(scope.scope=="video"?"This video":"This project")+" · "+(s.llm?s.llm.slice(0,34):"no model connected")}).catch(()=>{});
  if(scope.scope=="video")jget("/api/jobs/"+scope.id).then(j=>{const sel=$("askClip");if(!sel)return;(j.clips||[]).forEach(c=>{const o=document.createElement("option");o.value=c.id;o.textContent=`#${c.id} ${(c.title||"").slice(0,40)} (${c.score})`;sel.appendChild(o)})}).catch(()=>{});
  const log=$("askLog");const bots=()=>panel?panel.querySelectorAll(".sai"):[];const st=(s,ms)=>{if(panel)botState(panel,s,ms)};
  st("wave",2100);
  const draw=()=>{const h=load();log.innerHTML=h.length?h.map(m=>`<div class="am ${m.role}">${m.role=="user"?`<p>${esc(m.content)}</p>`:md(m.content)}${m.role=="assistant"?`<button class="g sm acp" data-copy>Copy</button>`:""}</div>`).join(""):`<div class="aintro"><div class="mu small">Hi, I'm <span class="sname"><b>Surge</b>AI</span>. Ask me anything about ${scope.scope=="video"?"this video and its clips":"this project"}. I can see its goals, clips, scores, transcript and your upload results, so my answers fit.</div></div>`;
   $("askSug").style.display=h.length?"none":"flex";log.scrollTop=log.scrollHeight;wire()};
  $("askSug").innerHTML=SUGG[scope.scope].map(t=>`<button class="chip3" data-q="${esc(t)}">${esc(t)}</button>`).join("");
  const wire=()=>{log.querySelectorAll("[data-tag]").forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(b.dataset.tag);toast("Copied "+b.dataset.tag)});
   log.querySelectorAll("[data-copy]").forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(b.parentNode.innerText.replace(/Copy$/,"").trim());toast("Copied")})};
  async function send(text){
   text=(text||"").trim();if(!text||busy)return;busy=true;$("askGo").disabled=true;
   const h=load();h.push({role:"user",content:text});save(h);draw();$("askIn").value="";
   const live=document.createElement("div");live.className="am assistant live";live.innerHTML='<div class="rowb">'+surgeBot(34,"thinking")+'<p class="mu" style="margin:0 0 6px">Thinking...</p></div>';st("thinking");log.appendChild(live);log.scrollTop=log.scrollHeight;
   let acc="";let failed=false;ctl=new AbortController();
   try{
    const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},signal:ctl.signal,body:JSON.stringify({scope:scope.scope,id:scope.id,clip:$("askClip")&&$("askClip").value?+$("askClip").value:null,messages:h})});
    if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.status);
    const rd=r.body.getReader(),dec=new TextDecoder();
    let talk;for(;;){const {value,done}=await rd.read();if(done)break;acc+=dec.decode(value,{stream:true});
     if(!talk){talk=true;st("talking")}
     live.innerHTML='<div class="rowb">'+surgeBot(34,"talking")+'<div style="flex:1;min-width:0">'+md(acc)+'</div></div>';log.scrollTop=log.scrollHeight}
   }catch(e){if(e.name!="AbortError"){acc+=(acc?"\n\n":"")+"Could not get an answer: "+e.message;failed=true}}
   if(acc.trim()){const hh=load();hh.push({role:"assistant",content:acc});save(hh)}
   busy=false;ctl=null;if($("askGo"))$("askGo").disabled=false;if(panel){draw();st(failed||/^(No AI model|Cannot reach|The model)/.test(acc)?"sad":"happy",failed||/^(No AI model|Cannot reach|The model)/.test(acc)?3000:2200)}}
  $("askGo").onclick=()=>send($("askIn").value);
  let lt;$("askIn").oninput=()=>{if(busy)return;st("listening");clearTimeout(lt);lt=setTimeout(()=>{if(!busy)st("idle")},1400)};
  $("askIn").onkeydown=e=>{if(e.key=="Enter"&&!e.shiftKey){e.preventDefault();send($("askIn").value)}};
  panel.querySelectorAll("[data-q]").forEach(b=>b.onclick=()=>send(b.dataset.q));
  panel.querySelector("[data-cl]").onclick=close;
  panel.querySelector("[data-clr]").onclick=()=>{if(ctl)ctl.abort();save([]);draw()};
  draw();setTimeout(()=>$("askIn")&&$("askIn").focus(),50)}
 function close(){if(ctl)ctl.abort();if(panel){panel.remove();panel=null}fab.classList.remove("on")}
 fab.onclick=()=>panel?close():open();
 document.addEventListener("keydown",e=>{if(e.key=="Escape"&&panel&&!document.querySelector(".mbg"))close()});
 addEventListener("hashchange",sync);sync();
})();
