// JARVIS v2.60 project attachments + resilient dashboard.
// Every dashboard API request is resolved against the HTTP dashboard origin so
// the app-window can never accidentally resolve an API path against file:// or
// another transient document base.
const JARVIS_UI_BUILD_ID = 'v42.55.0-exact-model-protocol';
const __jarvisNativeFetch = window.fetch.bind(window);
const JARVIS_API_ORIGIN = (() => {
  try {
    if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
      return window.location.origin;
    }
  } catch (_e) {}
  return 'http://127.0.0.1:8080';
})();

function jarvisResolveUrl(input){
  if(typeof input !== 'string') return input;
  if(input.startsWith('/api/') || input.startsWith('/downloads/')) return JARVIS_API_ORIGIN + input;
  if(input.startsWith('./api/')) return JARVIS_API_ORIGIN + '/' + input.slice(2);
  return input;
}

async function jarvisFetch(input, init){
  return __jarvisNativeFetch(jarvisResolveUrl(input), init);
}

async function jarvisFetchJson(path, timeoutMs=10000, init={}){
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try{
    const response = await jarvisFetch(path, {...init, cache:'no-store', signal:controller.signal});
    if(!response.ok) throw new Error(`HTTP ${response.status} for ${path}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

let __jarvisClientLogLast = new Map();
function jarvisClientLog(event, detail='', meta={}){
  try{
    const key=String(event)+'|'+String(detail).slice(0,180);
    const now=Date.now();
    const last=__jarvisClientLogLast.get(key)||0;
    if(now-last<5000) return;
    __jarvisClientLogLast.set(key,now);
    __jarvisNativeFetch(JARVIS_API_ORIGIN+'/api/client-log',{
      method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',keepalive:true,
      body:JSON.stringify({event:String(event),detail:String(detail),meta:{...meta,href:location.href,build:JARVIS_UI_BUILD_ID,ts:new Date().toISOString()}})
    }).catch(()=>{});
  }catch(_e){}
}
window.addEventListener('error',e=>jarvisClientLog('window.error',e.message||'error',{file:e.filename,line:e.lineno,col:e.colno}));
window.addEventListener('unhandledrejection',e=>jarvisClientLog('unhandledrejection',String(e.reason||'unknown')));

async function jarvisSafeJson(path, timeoutMs, fallback){
  try{return await jarvisFetchJson(path,timeoutMs);}catch(e){jarvisClientLog('api.failure',`${path}: ${e?.name||''} ${e?.message||e}`);return fallback;}
}

const state = { currentView: 'command', lastUiAction: null, lastAnswer: '', lastUser: '' };
const apps = [
 ['outlook','📧','Outlook'],['word','🟦','Word'],['excel','🟩','Excel'],['powerpoint','🟧','PowerPoint'],
 ['chrome','🌐','Chrome'],['steam','🎮','Steam'],['visualstudio','🧰','Visual Studio'],['vscode','◇','VS Code'],
 ['androidstudio','🤖','Android Studio'],['unreal','U','Unreal'],['blender','◌','Blender'],['discord','◈','Discord'],
 ['epic','E','Epic Games'],['obs','●','OBS'],['calculator','🧮','Calculator'],['notepad','📝','Notepad'],
 ['explorer','📁','Files'],['terminal','>_','Terminal'],['settings','⚙','Settings']
];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));


async function toggleFullscreen(){
  try{
    if(!document.fullscreenElement){
      await document.documentElement.requestFullscreen();
    }else{
      await document.exitFullscreen();
    }
  }catch(e){
    showToast('Fullscreen could not be enabled. Press F11 as a fallback.');
  }
}

function updateFullscreenButton(){
  const btn=$('fullscreen-btn');
  if(!btn) return;
  btn.textContent=document.fullscreenElement?'↙ EXIT FULLSCREEN':'⛶ FULLSCREEN';
}

document.addEventListener('fullscreenchange',updateFullscreenButton);
window.addEventListener('DOMContentLoaded',()=>{ const b=$('dock-close'); if(b) b.onclick=()=>{ closeDetailDock(); document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.view==='command')); }; });

function switchView(view){
  state.currentView=view;

  document.querySelectorAll('.nav').forEach(
    x=>x.classList.toggle('active',x.dataset.view===view)
  );

  // Keep the Jarvis command center/core visible. Side-menu pages open in
  // the lower HUD dock so the three summary panels simply move upward.
  document.querySelectorAll('.view').forEach(x=>x.classList.remove('active'));
  $('command-view').classList.add('active');

  if(view==='command'){
    closeDetailDock();
    return;
  }

  openDetailDock(view);
}

function renderApps(target){
  target.innerHTML=apps.map(([key,icon,label])=>`<button class="app-btn" onclick="launchApp('${key}')"><i>${icon}</i><span>${label}</span></button>`).join('');
}

async function launchApp(app){
  if(app==='calculator'){ openWidget('calculator'); return; }
  const res=await jarvisFetch('/api/apps/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app})});
  const data=await res.json();
  showToast(data.message||'Application request sent.');
}

function showToast(text){
  let t=document.querySelector('.toast'); if(!t){t=document.createElement('div');t.className='toast';document.body.appendChild(t);}
  t.textContent=text; Object.assign(t.style,{position:'fixed',right:'20px',bottom:'20px',zIndex:200,padding:'12px 16px',background:'#05223a',border:'1px solid #29d7ff',borderRadius:'7px',color:'#dff9ff'}); setTimeout(()=>t.remove(),2200);
}

function addBubble(kind,text){
  if(!text) return;
  const logs=$('chat-logs'); const div=document.createElement('div'); div.className=`bubble ${kind}`;
  const raw=String(text);
  const match=raw.match(/DOWNLOAD_URL:\s*(\/downloads\/[^\s]+)/);
  if(match){
    const clean=raw.replace(/\n?DOWNLOAD_URL:\s*\/downloads\/[^\s]+/,'').trim();
    const body=document.createElement('div'); body.textContent=clean; div.appendChild(body);
    const a=document.createElement('a'); a.href=match[1]; a.textContent='⬇ DOWNLOAD ZIP'; a.setAttribute('download',''); a.className='download-link'; div.appendChild(a);
  }else{
    div.textContent=raw;
  }
  logs.appendChild(div); logs.scrollTop=logs.scrollHeight;
}

const commandJobs = new Map();

async function waitForCommandJob(jobId, command){
  const started=Date.now();
  while(Date.now()-started < 1800000){
    try{
      const job=await jarvisFetch(`/api/command/${encodeURIComponent(jobId)}`,{cache:'no-store'}).then(r=>r.json());
      if(job.status==='completed'){
        const answer=job.response||'Command completed.';
        state.lastAnswer=answer;
        addBubble('jarvis',answer);
        setChatCommandStatus(job.attachment_accepted===false?answer:'Request accepted by Jarvis.',job.attachment_accepted===false);
        settleCommandAttachments(jobId,job.attachment_accepted===true);
        commandJobs.delete(jobId);
        return;
      }
      if(job.status==='failed'){
        const errorText=job.error?`Command failed: ${job.error}`:'Command failed.';
        state.lastAnswer=errorText;
        addBubble('jarvis',errorText);
        setChatCommandStatus(errorText,true);
        settleCommandAttachments(jobId,false);
        commandJobs.delete(jobId);
        return;
      }
    }catch(e){}
    await new Promise(resolve=>setTimeout(resolve,350));
  }
  settleCommandAttachments(jobId,false);
  commandJobs.delete(jobId);
  addBubble('jarvis',`Command is still running in the background: ${command}`);
}

function quickCommand(command){
  const input=$('chat-input');
  if(!input) return;
  input.value=command;
  sendCommand();
}



async function loadNvidiaModelsIntoProvider(){
  const select=$('provider-select');
  if(!select)return;
  try{
    const response=await jarvisFetch('/api/nvidia/models');
    if(!response.ok)return;
    const data=await response.json();
    const models=Array.isArray(data.models)?data.models:[];
    // Remove only previously injected model choices.
    [...select.querySelectorAll('option[data-nvidia-model="1"]')].forEach(o=>o.remove());
    const nvidiaBase=[...select.options].find(o=>o.value==='nvidia');
    if(!nvidiaBase)return;
    const group=document.createElement('optgroup');
    group.label=`NVIDIA FREE / HOSTED MODELS (${models.length})`;
    group.dataset.nvidiaModel='1';
    const preferred='deepseek-ai/deepseek-v4-flash-0731';
    const normalized=models.map(raw=>typeof raw==='string'?raw:(raw.id||raw.model||raw.name||'')).filter(Boolean);
    normalized.sort((x,y)=>{
      if(x===preferred)return -1;
      if(y===preferred)return 1;
      return x.localeCompare(y);
    });
    for(const id of normalized){
      const option=document.createElement('option');
      option.value=`nvidia::${id}`;
      option.textContent=id===preferred?`NVIDIA — ${id} ★ RECOMMENDED`:`NVIDIA — ${id}`;
      option.dataset.nvidiaModel='1';
      group.appendChild(option);
    }
    select.appendChild(group);
  }catch(err){
    console.warn('Could not load NVIDIA model catalog:',err);
  }
}
const QWEN_PROVIDER_SELECTION_KEY='jarvis.localQwenSelection.v426';

function restoreLocalQwenSelection(){
  const select=$('provider-select'); if(!select)return;
  try{
    const saved=localStorage.getItem(QWEN_PROVIDER_SELECTION_KEY);
    if(saved && [...select.options].some(o=>o.value===saved)) select.value=saved;
  }catch(_e){}
}

async function switchLocalQwenFromDropdown(value){
  if(!['auto','qwen8b','qwen35','qwen38q2','qwen'].includes(value))return;
  const profile=value==='qwen8b'?'8b':(value==='qwen35'?'9b35':(value==='qwen38q2'?'27b38q2':(value==='qwen'?'27b':'auto')));
  try{ localStorage.setItem(QWEN_PROVIDER_SELECTION_KEY,value); }catch(_e){}
  showToast(profile==='8b'?'8B Qwen selected — switching…':profile==='9b35'?'Qwen3.5 9B selected — switching…':profile==='27b38q2'?'Qwen3.8 27B Aggressive Q2_K_P selected — switching…':profile==='27b'?'27B Qwen selected — switching…':'AUTO HYBRID selected — 9B worker + new 27B Q2_K_P specialist…');
  try{
    const res=await jarvisFetch('/api/command',{
      method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',
      body:JSON.stringify({command:'__JARVIS_SWITCH_QWEN_ONLY__',qwen_profile:profile,attachments:[]})
    });
    const data=await res.json();
    if(!res.ok||!data.job_id)throw new Error(data.response||data.error||`HTTP ${res.status}`);
    // Poll independently so selecting a model does not block normal dashboard rendering.
    const started=Date.now();
    while(Date.now()-started<600000){
      const job=await jarvisFetch(`/api/command/${encodeURIComponent(data.job_id)}`,{cache:'no-store'}).then(r=>r.json());
      if(job.status==='completed'){
        addBubble('jarvis',job.response||'Local Qwen model selection applied.');
        return;
      }
      if(job.status==='failed')throw new Error(job.error||'Model switch failed.');
      await new Promise(resolve=>setTimeout(resolve,500));
    }
    addBubble('jarvis','The model choice is saved. Qwen is still loading in the background.');
  }catch(err){ addBubble('jarvis',`Local Qwen selection: ${err.message||err}`); }
}

window.addEventListener('DOMContentLoaded',()=>{
  restoreLocalQwenSelection();
  loadNvidiaModelsIntoProvider();
  const select=$('provider-select');
  if(select){
    select.addEventListener('change',()=>{
      const value=select.value;
      if(['auto','qwen8b','qwen35','qwen38q2','qwen'].includes(value)) switchLocalQwenFromDropdown(value);
      else { try{localStorage.setItem(QWEN_PROVIDER_SELECTION_KEY,value)}catch(_e){} }
    });
  }
});


let voiceLabData=null;
async function loadVoiceLab(){
  const providerSelect=$('voice-provider-select');
  const voiceList=$('voice-list');
  const status=$('voice-provider-status');
  if(!providerSelect||!voiceList)return;
  try{
    voiceLabData=await jarvisFetch('/api/voice/catalog',{cache:'no-store'}).then(r=>r.json());
    const providers=voiceLabData.providers||{};
    const current=voiceLabData.settings||{};
    providerSelect.innerHTML=['kokoro','piper','elevenlabs'].map(id=>{
      const p=providers[id]||{};
      const label=id==='kokoro'?'Kokoro ONNX (Local / Free)':id==='piper'?'Piper (Local / Free)':'ElevenLabs';
      return `<option value="${id}" ${current.provider===id?'selected':''}>${label}${p.configured?'':' — NOT INSTALLED'}</option>`;
    }).join('');
    providerSelect.addEventListener('change',async()=>{
      await jarvisFetch('/api/voice/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:providerSelect.value})});
      voiceLabData.settings={...(voiceLabData.settings||{}),provider:providerSelect.value};
      renderVoiceChoices(providerSelect.value);
    });
    renderVoiceChoices(providerSelect.value);
    status.textContent='Click any voice to select it and hear a short preview.';
  }catch(e){
    status.textContent=`Voice Lab error: ${e}`;
  }
}
function renderVoiceChoices(provider){
  const voiceList=$('voice-list');
  const status=$('voice-provider-status');
  if(!voiceList||!voiceLabData)return;
  const p=voiceLabData.providers?.[provider]||{};
  const settings=voiceLabData.settings||{};
  const voices=Array.isArray(p.voices)?p.voices:[];

  voiceList.innerHTML=voices.map(v=>{
    const id=typeof v==='string'?v:(v.id||v.name||'');
    const name=typeof v==='string'?v:(v.name||v.id||'');
    const selected=(provider==='kokoro'&&settings.kokoro_voice===id)||
      (provider==='piper'&&settings.piper_voice===id)||
      (provider==='elevenlabs'&&settings.elevenlabs_voice_id===id);
    return `<button class="voice-choice ${selected?'selected':''}" data-provider="${esc(provider)}" data-voice="${esc(id)}"><b>${esc(name)}</b><small>${selected?'Selected — click to preview again':'Click to select & preview'}</small></button>`;
  }).join('')||'<div class="card">No voices found for this provider.</div>';

  voiceList.querySelectorAll('.voice-choice').forEach(btn=>btn.addEventListener('click',async()=>{
    const provider=btn.dataset.provider;
    const voice=btn.dataset.voice;
    const all=[...voiceList.querySelectorAll('.voice-choice')];

    all.forEach(x=>x.disabled=true);
    const sub=btn.querySelector('small');
    if(sub)sub.textContent='Selecting & generating preview…';
    if(status)status.textContent=`Selecting ${voice} and generating preview…`;

    try{
      const res=await jarvisFetch('/api/voice/preview',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          provider,
          voice,
          phrase:'Hello, sir. Jarvis voice preview online and ready.'
        })
      });
      const data=await res.json();

      if(!res.ok || data.status!=='ok'){
        throw new Error(data.error||data.message||`Preview failed (${res.status})`);
      }

      voiceLabData.settings=data.settings||voiceLabData.settings||{};
      renderVoiceChoices(provider);
      if(status)status.textContent=`Selected ${voice}. Preview played successfully.`;
    }catch(err){
      all.forEach(x=>x.disabled=false);
      if(sub)sub.textContent='Preview failed — click to retry';
      if(status)status.textContent=`Voice preview failed: ${err.message||err}`;
      console.error('Voice preview failed:',err);
    }
  }));
}


const chatAttachments=[];
let chatCommandSending=false;
const projectUploadClient=new window.JarvisProjectUploads.Client(jarvisFetch);

function settleCommandAttachments(jobId,accepted){
  const job=commandJobs.get(jobId);
  const submitted=job?.attachments||[];
  for(let i=chatAttachments.length-1;i>=0;i--){
    if(!submitted.includes(chatAttachments[i]))continue;
    if(accepted)chatAttachments.splice(i,1);
    else chatAttachments[i].state='ready';
  }
  if(!accepted&&submitted.length){
    const input=$('chat-input');if(input&&!input.value.trim())input.value=job.originalCommand||job.command;
  }
  renderChatAttachments();
}

function setChatCommandStatus(message,failed=false){
  const status=$('chat-command-status');
  if(status){status.textContent=message;status.classList.toggle('error',failed);}
}

function bindChatControls(){
  const bind=(id,event,handler)=>{
    const element=$(id);
    if(!element||element.dataset['bound'+event])return;
    element.dataset['bound'+event]='true';
    element.addEventListener(event,handler);
  };
  bind('send-btn','click',event=>{event.preventDefault();sendCommand();});
  bind('chat-input','keydown',event=>{
    if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&!event.repeat){
      event.preventDefault();sendCommand();
    }
  });
  bind('attach-btn','click',event=>{event.preventDefault();$('chat-file-input')?.click();});
  bind('chat-file-input','change',event=>uploadChatFiles(event.target.files||[]));
}

function formatBytes(n){
  const v=Number(n||0); if(v<1024)return `${v} B`; if(v<1024*1024)return `${(v/1024).toFixed(1)} KB`; return `${(v/1024/1024).toFixed(1)} MB`;
}
function renderChatAttachments(){
  const blocked=chatAttachments.some(a=>a.state!=='ready');
  const send=$('send-btn');
  if(send){send.disabled=chatCommandSending||blocked;send.title=blocked?'Wait for uploads or retry/remove a failed attachment':'Send';}
  const attach=$('attach-btn');if(attach)attach.disabled=chatCommandSending||chatAttachments.some(a=>a.state==='queued')||chatAttachments.length>=8;
  const box=$('chat-attachments'); if(!box)return;
  box.classList.toggle('has-files',chatAttachments.length>0);
  box.innerHTML=chatAttachments.map((a,i)=>{
    const status=a.state==='ready'?(a.kind==='zip'?'Ready to repair':'Ready'):a.state==='queued'?'Starting repair…':a.state==='error'?a.error:(a.phase==='validating'?'Checking ZIP…':`Uploading ${Math.floor(100*(a.received||0)/Math.max(a.size,1))}%`);
    return `<div class="chat-attachment ${a.state}"><span>${a.kind==='zip'?'🗜':'📄'}</span><span class="name">${esc(a.name)}<small role="status">${esc(status)}</small></span><span class="size">${formatBytes(a.size)}</span>${a.state==='error'?`<button type="button" data-retry-attachment="${i}" title="Retry upload">Retry</button>`:''}<button type="button" data-remove-attachment="${i}" title="Remove attachment">✕</button></div>`;
  }).join('');
  box.querySelectorAll('[data-remove-attachment]').forEach(btn=>btn.addEventListener('click',()=>{
    const index=Number(btn.dataset.removeAttachment), item=chatAttachments[index];
    if(!item)return;
    item.removed=true;projectUploadClient.cancel(item).catch(()=>{});
    chatAttachments.splice(index,1);renderChatAttachments();
  }));
  box.querySelectorAll('[data-retry-attachment]').forEach(btn=>btn.addEventListener('click',()=>{
    const item=chatAttachments[Number(btn.dataset.retryAttachment)];if(item)performChatUpload(item);
  }));
}
async function performChatUpload(item){
  if(item.removed||item.busy)return;
  item.busy=true;item.state='uploading';item.error='';item.controller=new AbortController();renderChatAttachments();
  try{
    const data=await projectUploadClient.upload(item,(received,total,phase)=>{
      item.received=received;item.phase=phase;renderChatAttachments();
    });
    if(item.removed)return;
    Object.assign(item,data,{state:'ready'});
    addBubble('jarvis',`${item.name} attached and ready. Send your request to repair this project.`);
  }catch(err){
    if(item.removed)return;
    item.state='error';item.error=err.message||String(err);
    addBubble('jarvis',`Attachment error: ${item.error}`);
    jarvisClientLog('attachment.upload.failure',String(err),{name:item.name,bytes:item.size,received:item.received||0});
  }finally{
    item.busy=false;renderChatAttachments();
  }
}
async function uploadChatFiles(files){
  const selected=[...files].slice(0,Math.max(0,8-chatAttachments.length));
  const fi=$('chat-file-input');if(fi)fi.value='';
  const added=selected.map(file=>({file,name:file.name,size:file.size,kind:file.name.toLowerCase().endsWith('.zip')?'zip':'file',state:'uploading',received:0}));
  // Reserve every selected attachment synchronously, before the first await.
  // Enter/Send can never race ahead with an empty attachments array.
  chatAttachments.push(...added);renderChatAttachments();
  for(const item of added){
    if(item.removed)continue;
    addBubble('jarvis',`Attaching ${item.name}…`);
    await performChatUpload(item);
  }
}

async function sendCommand(){
  if(chatCommandSending){setChatCommandStatus('Sending your request to Jarvis…');return;}
  if(chatAttachments.some(a=>a.state!=='ready')){
    const waiting=chatAttachments.some(a=>a.state==='queued');
    const message=waiting?'Your request was sent. Waiting for Jarvis to accept it…':'Wait until your ZIP says Ready to repair. Retry or remove any failed attachment before sending.';
    setChatCommandStatus(message);addBubble('jarvis',message);return;
  }
  const input=$('chat-input');
  const command=input.value.trim();
  if(!command)return;
  const submitted=[...chatAttachments];
  chatCommandSending=true;renderChatAttachments();
  setChatCommandStatus('Sending your request to Jarvis…');
  try{
    const providerChoiceNow=$('provider-select')?.value||'auto';
    const effectiveProvider=providerChoiceNow.startsWith('nvidia::')?'nvidia':(['qwen8b','qwen35','qwen38q2'].includes(providerChoiceNow)?'qwen':providerChoiceNow);
    const effectiveCommand=effectiveProvider==='auto'?command:`use ${effectiveProvider} to ${command}`;
    const qwenProfile=providerChoiceNow==='qwen8b'?'8b':(providerChoiceNow==='qwen35'?'9b35':(providerChoiceNow==='qwen38q2'?'27b38q2':(providerChoiceNow==='qwen'?'27b':(providerChoiceNow==='auto'?'auto':''))));
    const res=await jarvisFetch('/api/command',{
      method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',
      body:JSON.stringify({command:effectiveCommand,qwen_profile:qwenProfile,
        require_project_zip:submitted.some(a=>a.kind==='zip'),
        attachments:submitted.map(a=>({path:a.path,name:a.name,kind:a.kind,size:a.size}))})
    });
    const raw=await res.text();let data={};try{data=JSON.parse(raw);}catch(_e){}
    if(!res.ok)throw new Error(data.error||data.response||`Dashboard command API returned HTTP ${res.status}`);
    if(!data.job_id)throw new Error(data.response||data.error||'Command could not be queued.');
    state.lastUser=command;addBubble('user',command);
    if(input.value.trim()===command)input.value='';
    input.focus();
    commandJobs.set(data.job_id,{command:effectiveCommand,originalCommand:command,attachments:submitted,createdAt:Date.now()});
    for(const item of submitted)item.state='queued';
    setChatCommandStatus('Request sent. Waiting for Jarvis to accept it…');
    waitForCommandJob(data.job_id,effectiveCommand);
  }catch(e){
    setChatCommandStatus(`Command error: ${e.message||e}`,true);
    addBubble('jarvis',`Command error: ${e.message||e}`);
  }finally{
    chatCommandSending=false;renderChatAttachments();
  }
}

let __projectStopBusy=false;
async function stopProjectAndCheckpoint(){
  if(__projectStopBusy)return;
  const btn=$('stop-project-btn');
  __projectStopBusy=true;
  if(btn){btn.disabled=true;btn.textContent='■ SAVING CHECKPOINT…';}
  addBubble('user','Stop project and save checkpoint');
  try{
    const res=await jarvisFetch('/api/command',{
      method:'POST',headers:{'Content-Type':'application/json'},cache:'no-store',
      body:JSON.stringify({command:'__JARVIS_STOP_PROJECT_AND_CHECKPOINT__',attachments:[]})
    });
    const data=await res.json();
    if(!res.ok)throw new Error(data.error||`HTTP ${res.status}`);
    if(data.job_id){
      commandJobs.set(data.job_id,{command:'Stop project and save checkpoint',createdAt:Date.now()});
      waitForCommandJob(data.job_id,'Stop project and save checkpoint');
    }else{
      addBubble('jarvis',data.response||'Stop requested. Jarvis will package the accepted workspace at the next safe boundary.');
    }
  }catch(e){
    addBubble('jarvis',`Checkpoint request error: ${e.message||e}`);
  }finally{
    __projectStopBusy=false;
    if(btn){btn.disabled=false;btn.textContent='■ STOP + CHECKPOINT';}
  }
}

let __pollLiveStateBusy=false;
async function pollLiveState(){
  if(__pollLiveStateBusy) return;
  __pollLiveStateBusy=true;
  try{
    const live=await jarvisFetchJson('/api/live_state',3000);
    const vs=String(live.state||'STANDBY').toUpperCase();
    document.body.dataset.voiceState=vs; $('voice-label').textContent=vs; $('side-state').textContent=vs; if($('talk-strip-state')) $('talk-strip-state').textContent=vs==='SPEAKING'?'Speaking…':vs==='THINKING'?'Thinking…':vs==='TRANSCRIBING'?'Transcribing…':vs==='LISTENING'?"I'm listening…":'Standing by…';
    document.querySelectorAll('.state-row span').forEach(x=>x.classList.toggle('active',x.dataset.s===vs));
    if(live.last_user && live.last_user!==state.lastUser && commandJobs.size===0){state.lastUser=live.last_user;addBubble('user',live.last_user);}
    if(live.last_answer && live.last_answer!==state.lastAnswer && commandJobs.size===0){state.lastAnswer=live.last_answer;addBubble('jarvis',live.last_answer);}
    const action=live.ui_action;
    if(action && action.id && action.id!==state.lastUiAction){state.lastUiAction=action.id;handleUiAction(action);}
  }catch(e){jarvisClientLog('live_state.failure',`${e?.name||''} ${e?.message||e}`);}
  finally{__pollLiveStateBusy=false;}
}

function handleUiAction(action){
  if(action.widget==='airtouch' && window.AirTouch){ window.AirTouch.applyRemoteAction(action.payload||{}); return; }
  if(action.widget==='voice_lab'){ openDetailDock('voice'); return; }
  const widget=String(action.widget||'');
  if(widget==='launch_app'){ launchApp(action.payload?.app); return; }
  if(['calculator','email','calendar','agents','projects','apps','controls'].includes(widget)){ openWidget(widget); }
}

let __refreshOverviewBusy=false;
async function refreshOverview(){
  if(__refreshOverviewBusy) return;
  __refreshOverviewBusy=true;
  try{
    const [status,tel,agents,calendar,email,providers,projects]=await Promise.all([
      jarvisSafeJson('/api/status',5000,{}),
      jarvisSafeJson('/api/telemetry',6000,{}),
      jarvisSafeJson('/api/agents',5000,[]),
      jarvisSafeJson('/api/calendar',7000,[]),
      jarvisSafeJson('/api/email',7000,[]),
      jarvisSafeJson('/api/providers',5000,[]),
      jarvisSafeJson('/api/projects',5000,[])
    ]);

    $('status-host').textContent=status.host||'—';
    $('status-user').textContent=status.user||'—';
    $('status-py').textContent=status.python_version||'—';
    $('status-ipc').textContent=status.ipc||'—';
    $('cpu').textContent=`CPU ${tel.cpu_usage||'—'}`;
    $('ram').textContent=`RAM ${tel.memory_percent!=null?tel.memory_percent+'%':'—'}`;

    $('overview-agents').innerHTML=(agents.slice(-4).reverse().map(a=>{const pct=Math.max(0,Math.min(100,Number(a.percent||0)));const prog=(a.job_type==='qwen_project'&&['queued','running','stopping'].includes(String(a.status||'').toLowerCase()))?`<div style="height:6px;background:rgba(255,255,255,.10);border-radius:5px;overflow:hidden;margin-top:7px"><div style="height:100%;width:${pct}%;background:#29d7ff;transition:width .4s"></div></div><small>${pct}% • ${esc(a.stage||'working')}${a.current&&a.total?' • '+esc(a.current)+'/'+esc(a.total):''}${a.generated_tokens_estimate?' • ~'+Number(a.generated_tokens_estimate).toLocaleString()+' tokens':''}</small>`:'';return `<div class="mini-item"><b>Agent ${esc(a.id)} • ${esc(a.provider||'gemini')} • ${esc(a.status)}</b><small>${esc(a.activity||a.user_task||a.task||'')}</small>${prog}${a.turn?`<small>Tool turn ${esc(a.turn)} / ${esc(a.max_turns||'?')} ${a.tool?'• '+esc(a.tool):''}</small>`:''}</div>`}).join('')||'<div class="mini-item">No agents yet.</div>');
    const activeProject=agents.find(a=>a.job_type==='qwen_project'&&['queued','running','stopping'].includes(String(a.status||'').toLowerCase()));
    const stopBtn=$('stop-project-btn');
    if(stopBtn){
      stopBtn.classList.toggle('hidden',!activeProject);
      stopBtn.disabled=__projectStopBusy||String(activeProject?.status||'').toLowerCase()==='stopping';
      if(!__projectStopBusy)stopBtn.textContent=String(activeProject?.status||'').toLowerCase()==='stopping'?'■ SAVING CHECKPOINT…':'■ STOP + CHECKPOINT';
    }
    $('overview-calendar').innerHTML=(calendar.slice(0,4).map(e=>`<div class="mini-item"><b>${esc(e.subject)}</b><small>${esc(e.start)}</small></div>`).join('')||'<div class="mini-item">Calendar clear.</div>');
    $('overview-email').innerHTML=(email.slice(0,3).map(e=>`<div class="mini-item"><b>${esc(e.subject)}</b><small>${esc(e.from)}</small></div>`).join('')||'<div class="mini-item">No email.</div>');

    const cpuPct=Math.max(0,Math.min(100,Number(tel.cpu_value||parseFloat(tel.cpu_usage)||0)));
    const ramPct=Math.max(0,Math.min(100,Number(tel.memory_percent||0)));
    const diskPct=Math.max(0,Math.min(100,Number(tel.disk_percent||0)));
    $('cpu-gauge')?.style.setProperty('--pct',cpuPct);
    $('ram-gauge')?.style.setProperty('--pct',ramPct);
    $('disk-gauge')?.style.setProperty('--pct',diskPct);
    if($('monitor-cpu')) $('monitor-cpu').textContent=`${Math.round(cpuPct)}%`;
    if($('monitor-ram')) $('monitor-ram').textContent=`${Math.round(ramPct)}%`;
    if($('monitor-disk')) $('monitor-disk').textContent=`${Math.round(diskPct)}%`;
    if($('monitor-threads')) $('monitor-threads').textContent=`${tel.active_threads||0} threads`;
    if($('monitor-network')) $('monitor-network').textContent=`NET ↑${tel.network_sent_mb||0} ↓${tel.network_recv_mb||0} MB`;
    if($('cpu-temp')) $('cpu-temp').textContent=tel.cpu_temp_c!=null?`TEMP ${Number(tel.cpu_temp_c).toFixed(0)}°C`:'TEMP N/A';
    if($('ram-temp')) $('ram-temp').textContent=tel.ram_temp_c!=null?`TEMP ${Number(tel.ram_temp_c).toFixed(0)}°C`:'TEMP N/A';
    if($('disk-capacity')) $('disk-capacity').textContent=tel.disk_usage||'CAPACITY N/A';
    if($('gpu-temp')) $('gpu-temp').textContent=tel.gpu_temp_c!=null?`GPU TEMP ${Number(tel.gpu_temp_c).toFixed(0)}°C`:'GPU TEMP N/A';
    if($('cpu-package-temp')) $('cpu-package-temp').textContent=tel.cpu_package_temp_c!=null?`CPU PKG ${Number(tel.cpu_package_temp_c).toFixed(0)}°C`:'CPU PKG N/A';
    if($('cpu-core-max-temp')) $('cpu-core-max-temp').textContent=tel.cpu_core_max_temp_c!=null?`CORE MAX ${Number(tel.cpu_core_max_temp_c).toFixed(0)}°C`:'CORE MAX N/A';
    if($('gpu-hotspot-temp')) $('gpu-hotspot-temp').textContent=tel.gpu_hotspot_temp_c!=null?`GPU HOTSPOT ${Number(tel.gpu_hotspot_temp_c).toFixed(0)}°C`:'GPU HOTSPOT N/A';
    if($('storage-temp')) $('storage-temp').textContent=tel.storage_temp_c!=null?`STORAGE ${Number(tel.storage_temp_c).toFixed(0)}°C`:'STORAGE N/A';
    if($('fan-rpm')) {
      const fans=Array.isArray(tel.fan_rpm)?tel.fan_rpm:[];
      $('fan-rpm').textContent=fans.length?`FANS ${fans.slice(0,2).map(v=>Math.round(v)+' RPM').join(' / ')}`:'FANS N/A';
    }
    if($('temperature-source')) {
      $('temperature-source').textContent=`TEMP SENSOR: ${tel.temperature_source||'Unavailable'}`;
      $('temperature-source').title=tel.temperature_detail||'';
    }
    if($('cpu-telemetry-label')) $('cpu-telemetry-label').title=tel.telemetry_source||'';
    if($('ram-telemetry-label')) $('ram-telemetry-label').title=tel.telemetry_source||'';

    const activeAgents=agents.filter(a=>['running','queued'].includes(String(a.status||'').toLowerCase())).length;
    if($('core-state-widget')) $('core-state-widget').textContent=String(status.status||'STANDBY').toUpperCase();
    if($('core-agent-count')) $('core-agent-count').textContent=`${activeAgents} active`;
    if($('core-project-count')) $('core-project-count').textContent=`${projects.length} managed`;
    if($('core-ipc-widget')) $('core-ipc-widget').textContent=status.ipc||'—';

    if($('mission-timeline')){
      $('mission-timeline').innerHTML=calendar.slice(0,5).map((e,i)=>`<div class="mission-row"><span class="mission-dot"></span><div><b>${esc(e.subject)}</b><small>${esc(e.start)}</small></div></div>`).join('')||'<div class="timeline-empty">No scheduled missions.</div>';
    }

    if($('provider-grid')){
      $('provider-grid').innerHTML=providers.map(p=>`<div class="provider-item ${p.configured?'ready':'offline'}"><span class="provider-orb"></span><div><b>${esc(p.name)}</b><small>${esc(p.model||'')}</small></div><strong>${esc(p.status)}</strong></div>`).join('');
    }

    const intel=[];
    agents.slice(-2).reverse().forEach(a=>intel.push(`<div class="intel-item"><span class="intel-icon">◈</span><div><b>Agent ${esc(a.id)} • ${esc(a.status)}</b><small>${esc((a.activity||a.user_task||a.task||'').slice(0,90))}</small></div></div>`));
    calendar.slice(0,2).forEach(e=>intel.push(`<div class="intel-item"><span class="intel-icon">◷</span><div><b>${esc(e.subject)}</b><small>${esc(e.start)}</small></div></div>`));
    email.slice(0,2).forEach(e=>intel.push(`<div class="intel-item"><span class="intel-icon">✉</span><div><b>${esc(e.subject)}</b><small>${esc(e.from)}</small></div></div>`));
    if($('intel-feed')) $('intel-feed').innerHTML=intel.join('')||'<div class="intel-item">No new intelligence.</div>';

  }catch(e){jarvisClientLog('overview.failure',`${e?.name||''} ${e?.message||e}`);}
  finally{__refreshOverviewBusy=false;}

  if(state.currentView && state.currentView!=='command' && $('detail-dock')?.classList.contains('open')){
    openDetailDock(state.currentView);
  }
}

function closeDetailDock(){
  const dock=$('detail-dock');
  if(dock) dock.classList.remove('open');
  document.body.classList.remove('detail-open');
}

async function openDetailDock(view){
  const dock=$('detail-dock');
  const title=$('dock-title');
  const body=$('dock-body');

  if(!dock || !title || !body) return;

  const titles={
    agents:'AGENT ACTIVITY',
    calendar:'CALENDAR',
    email:'WORK EMAIL',
    projects:'PROJECTS',
    apps:'APPLICATIONS',
    controls:'SYSTEM CONTROLS',
    core:'AI CORE',
    tasks:'TASKS & MISSIONS',
    memory:'MEMORY',
    conversations:'CONVERSATIONS',
    browser:'BROWSER & RESEARCH',
    git:'GIT & REPOSITORIES',
    workspace:'FILES & WORKSPACE',
    knowledge:'KNOWLEDGE BASE',
    skills:'TOOLS & SKILLS',
    voice:'VOICE LAB',
    automation:'AUTOMATION',
    workflows:'WORKFLOWS',
    monitor:'SYSTEM MONITOR',
    diagnostics:'DIAGNOSTICS',
    gestures:'GESTURE LAB'
  };

  title.textContent=titles[view]||String(view).toUpperCase();
  body.innerHTML='<div class="card">Loading…</div>';
  dock.classList.add('open');
  document.body.classList.add('detail-open');

  try{

    if(view==='voice'){
      body.innerHTML=`<div class="cards">
        <div class="card">
          <strong>VOICE PROVIDER</strong>
          <select id="voice-provider-select"></select>
          <small id="voice-provider-status">Loading local voice engines…</small>
        </div>
        <div class="card">
          <strong>AVAILABLE VOICES</strong>
          <div id="voice-list" class="voice-list"></div>
        </div>
      </div>`;
      setTimeout(loadVoiceLab,0);
      return;
    }

    if(view==='agents'){
      const d=await jarvisFetch('/api/agents').then(r=>r.json());
      body.innerHTML=`<div class="cards">${
        d.slice().reverse().map(a=>`<div class="card">
          <strong>Agent ${esc(a.id)} • ${esc(a.provider||'gemini')} • ${esc(a.status)}</strong>
          <small>${esc(a.activity||'')}</small>
          ${a.turn?`<small>Tool turn ${esc(a.turn)} / ${esc(a.max_turns||'?')} ${a.tool?'• '+esc(a.tool):''}</small>`:''}
          <small>${esc(a.user_task||a.task||'')}</small>
          <small><b>Completed result</b><br>${esc(a.full_result||a.result||'')}</small>
          ${a.test_report?`<small><b>Test report</b><br>${esc(a.test_report)}</small>`:''}
        </div>`).join('') || '<div class="card">No agents.</div>'
      }</div>`;
      return;
    }

    if(view==='calendar'){
      const d=await jarvisFetch('/api/calendar').then(r=>r.json());
      body.innerHTML=`<div class="cards">${
        d.map(e=>`<div class="card"><strong>${esc(e.subject)}</strong><small>${esc(e.start)} ${esc(e.location||'')}</small></div>`).join('')
        || '<div class="card">Calendar clear.</div>'
      }</div>`;
      return;
    }

    if(view==='email'){
      const d=await jarvisFetch('/api/email').then(r=>r.json());
      body.innerHTML=`<div class="cards">${
        d.map(e=>`<div class="card"><strong>${esc(e.subject)}</strong><small>${esc(e.from)}</small><small>${esc(e.date||'')}</small></div>`).join('')
        || '<div class="card">No email.</div>'
      }</div>`;
      return;
    }

    if(view==='projects'){
      const d=await jarvisFetch('/api/projects').then(r=>r.json());
      body.innerHTML=`<div class="cards">${
        d.map(p=>`<div class="card"><strong>${esc(p.name)}</strong><small>${esc(p.type)} • ${esc(p.status)}</small><small>${esc(p.path)}</small></div>`).join('')
        || '<div class="card">No projects found.</div>'
      }</div>`;
      return;
    }

    if(view==='apps'){
      body.innerHTML='<div id="dock-apps" class="app-grid large"></div>';
      renderApps($('dock-apps'));
      return;
    }

    if(view==='core'){
      const [status,providers,agents]=await Promise.all([
        jarvisFetch('/api/status').then(r=>r.json()),jarvisFetch('/api/providers').then(r=>r.json()),jarvisFetch('/api/agents').then(r=>r.json())
      ]);
      const active=agents.filter(a=>['queued','running'].includes(a.status)).length;
      body.innerHTML=`<div class="cards"><div class="card"><strong>Neural Core</strong><small>IPC ${esc(status.ipc||'ONLINE')} • ${active} active agent(s)</small></div>${providers.map(p=>`<div class="card"><strong>${esc(p.name)}</strong><small>${esc(p.status)} • ${esc(p.model||'')}</small></div>`).join('')}</div>`;
      return;
    }
    if(view==='tasks'){
      const [agents,calendar]=await Promise.all([jarvisFetch('/api/agents').then(r=>r.json()),jarvisFetch('/api/calendar').then(r=>r.json())]);
      body.innerHTML=`<div class="cards">${agents.filter(a=>['queued','running'].includes(a.status)).map(a=>`<div class="card"><strong>Agent ${esc(a.id)} • ${esc(a.status)}</strong><small>${esc(a.activity||a.user_task||'')}</small></div>`).join('')||'<div class="card">No active agent missions.</div>'}${calendar.slice(0,6).map(e=>`<div class="card"><strong>${esc(e.subject)}</strong><small>${esc(e.start)}</small></div>`).join('')}</div>`;
      return;
    }
    if(view==='memory'){
      body.innerHTML=`<div class="cards"><div class="card"><strong>Persistent Memory</strong><small>Jarvis persistent memory and conversation context are online.</small></div><div class="card"><strong>Self-maintenance</strong><small>Current files and Git state are authoritative during coding work.</small></div></div>`; return;
    }
    if(view==='conversations'){
      const bubbles=[...document.querySelectorAll('#chat-logs .bubble')].slice(-20).map(b=>`<div class="card"><small>${esc(b.textContent)}</small></div>`).join('');
      body.innerHTML=`<div class="cards">${bubbles||'<div class="card">No conversation history in this dashboard session.</div>'}</div>`; return;
    }
    if(view==='browser'){
      body.innerHTML=`<div class="cards">
        <button class="control-card" onclick="quickCommand('research the web for the latest AI developer tools')">Deep Web Research</button>
        <button class="control-card" onclick="quickCommand('read this page')">Read Active Page</button>
        <button class="control-card" onclick="quickCommand('what page am i on')">Current URL</button>
        <button class="control-card" onclick="quickCommand('scroll down')">Scroll Down</button>
        <button class="control-card" onclick="quickCommand('open new tab')">New Tab</button>
        <div class="card"><strong>Browser & Research</strong><small>Navigate Chrome, read rendered page text, search within pages, manage tabs, scroll, and run multi-source research in the background.</small></div>
      </div>`; return;
    }
    if(view==='git'){
      body.innerHTML=`<div class="cards">
        <button class="control-card" onclick="quickCommand('inspect the Jarvis project Git status and remote. Do not change anything')">Jarvis Git Status</button>
        <div class="card"><strong>Local-first</strong><small>C:\\Users\\gunsh\\Jarvis is Jarvis&apos;s live source of truth. Explicit GitHub repos can be cloned into Documents\\JarvisProjects.</small></div>
        <div class="card"><strong>Git safety</strong><small>Edits/tests are automatic. Commit/push only occur when explicitly requested; destructive Git operations remain guarded.</small></div>
      </div>`; return;
    }
    if(view==='workspace'){
      const d=await jarvisFetch('/api/projects').then(r=>r.json());
      body.innerHTML=`<div class="cards">${d.map(p=>`<div class="card"><strong>${esc(p.name)}</strong><small>${esc(p.type)} • ${esc(p.path)}</small></div>`).join('')||'<div class="card">No projects discovered.</div>'}</div>`; return;
    }
    if(view==='knowledge'){
      body.innerHTML=`<div class="cards"><div class="card"><strong>Project Knowledge</strong><small>Current project files and Git state remain authoritative for coding agents.</small></div><div class="card"><strong>Research Workspace</strong><small>Use Browser & Research for web navigation and background agents for deeper analysis.</small></div></div>`; return;
    }
    if(view==='automation'){
      body.innerHTML=`<div class="cards"><button class="control-card" onclick="quickCommand('what are my agents doing')">Agent Briefing</button><button class="control-card self-improve-action" onclick="quickCommand('improve yourself by making one safe high-confidence local improvement to the current Jarvis project, test it, and do not commit or push')">Self Improvement</button><div class="card"><strong>Safe Restart</strong><small>After a successful self-improvement job, Jarvis offers to restart the stack through the external restart helper.</small></div></div>`; return;
    }

    if(view==='skills'){
      body.innerHTML=`<div class="cards"><div class="card"><strong>PC Automation</strong><small>Open and control installed applications.</small></div><div class="card"><strong>Coding Agent</strong><small>Read, edit, validate and inspect project Git state.</small></div><div class="card"><strong>Email & Calendar</strong><small>Outlook/Himalaya tools with confirmation for write actions.</small></div><div class="card"><strong>Multi-provider AI</strong><small>Gemini/Hermes, OpenAI and Claude routing.</small></div><div class="card"><strong>Hardware Telemetry</strong><small>CPU, RAM, disk and hardware sensor bridge.</small></div></div>`; return;
    }
    if(view==='workflows'){
      body.innerHTML=`<div class="cards"><button class="control-card" onclick="quickCommand('improve yourself by making one safe high-confidence local improvement to the current Jarvis project, test it, and do not commit or push')">Improve Jarvis</button><button class="control-card" onclick="quickCommand('deploy an agent using OpenAI to inspect the Jarvis project for current bugs. Do not change anything.')">Inspect Jarvis</button><button class="control-card" onclick="quickCommand('what are my agents doing')">Agent Briefing</button><button class="control-card" onclick="quickCommand('what is on my calendar today')">Daily Schedule</button></div>`; return;
    }
    if(view==='monitor'){
      const [t,h]=await Promise.all([jarvisFetch('/api/telemetry').then(r=>r.json()),jarvisFetch('/api/hardware').then(r=>r.json())]);
      const s=h.summary||{};
      body.innerHTML=`<div class="cards"><div class="card"><strong>CPU ${esc(t.cpu_usage)}</strong><small>Package ${esc(s.cpuPackageTempC??'N/A')}°C • Core max ${esc(s.cpuCoreMaxTempC??'N/A')}°C</small></div><div class="card"><strong>RAM ${esc(t.memory_percent)}%</strong><small>${esc(t.memory_usage)} • Temp ${esc(s.ramTempC??'N/A')}°C</small></div><div class="card"><strong>GPU</strong><small>Core ${esc(s.gpuCoreTempC??'N/A')}°C • Hotspot ${esc(s.gpuHotspotTempC??'N/A')}°C</small></div><div class="card"><strong>Sensor Source</strong><small>${esc(h.source||t.temperature_source||'Unavailable')}</small><small>${esc(h.error||'')}</small></div></div>`; return;
    }

    if(view==='diagnostics'){
      const [status,tel,agents]=await Promise.all([jarvisFetch('/api/status').then(r=>r.json()),jarvisFetch('/api/telemetry').then(r=>r.json()),jarvisFetch('/api/agents').then(r=>r.json())]);
      body.innerHTML=`<div class="cards"><div class="card"><strong>Core</strong><small>IPC ${esc(status.ipc||'ONLINE')} • Python ${esc(status.python||'')}</small></div><div class="card"><strong>Hardware</strong><small>CPU ${esc(tel.cpu_usage||'--')} • RAM ${esc(tel.memory_percent??'--')}% • ${esc(tel.temperature_source||'Unavailable')}</small></div><div class="card"><strong>Agents</strong><small>${agents.filter(a=>['queued','running'].includes(a.status)).length} active</small></div><button class="control-card" data-action="ping">Run IPC Diagnostics</button></div>`;
      body.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>controlAction(b.dataset.action));return;
    }
    if(view==='gestures'){
      body.innerHTML=`<div id="airtouch-control-host"></div>`;
      setTimeout(()=>window.AirTouch?.renderSettings?.(),0);
      return;
    }

    if(view==='controls'){
      body.innerHTML=`<div class="cards">
        <button class="control-card" data-action="ping">Diagnostics</button>
        <button class="control-card" data-action="test_speech">Voice Test</button>
        <button class="control-card" onclick="openWidget('calculator')">Calculator Widget</button>
        <button class="control-card" onclick="openWidget('email')">Email Widget</button>
      </div>`;
      body.querySelectorAll('[data-action]').forEach(
        b=>b.onclick=()=>controlAction(b.dataset.action)
      );
      return;
    }
  }catch(e){
    body.innerHTML=`<div class="card">Could not load ${esc(view)}: ${esc(e)}</div>`;
  }
}

async function refreshView(view){
  if(view==='agents'){const d=await jarvisFetch('/api/agents').then(r=>r.json());$('agents-list').innerHTML=d.slice().reverse().map(a=>{const pct=Math.max(0,Math.min(100,Number(a.percent||0)));const prog=a.job_type==='qwen_project'?`<div style="height:8px;background:rgba(255,255,255,.10);border-radius:6px;overflow:hidden;margin:8px 0"><div style="height:100%;width:${pct}%;background:#29d7ff;transition:width .4s"></div></div><small><b>${pct}% • ${esc(a.stage||'working')}</b>${a.current&&a.total?' • '+esc(a.current)+'/'+esc(a.total):''}${a.generated_tokens_estimate?' • ~'+Number(a.generated_tokens_estimate).toLocaleString()+' streamed tokens':''}</small>`:'';return `<div class="card"><strong>Agent ${esc(a.id)} • ${esc(a.provider||'gemini')} • ${esc(a.status)}</strong><small>${esc(a.activity||'')}</small>${prog}${a.turn?`<small>Tool turn ${esc(a.turn)} / ${esc(a.max_turns||'?')} ${a.tool?'• '+esc(a.tool):''}</small>`:''}<small>${esc(a.user_task||a.task||'')}</small><small><b>Completed result</b><br>${esc(a.full_result||a.result||'')}</small>${a.test_report?`<small><b>Test report</b><br>${esc(a.test_report)}</small>`:''}</div>`}).join('')||'<div class="card">No agents.</div>';}
  if(view==='calendar'){const d=await jarvisFetch('/api/calendar').then(r=>r.json());$('calendar-list').innerHTML=d.map(e=>`<div class="card"><strong>${esc(e.subject)}</strong><small>${esc(e.start)} ${esc(e.location)}</small></div>`).join('')||'<div class="card">Calendar clear.</div>';}
  if(view==='email'){const d=await jarvisFetch('/api/email').then(r=>r.json());$('email-list').innerHTML=d.map(e=>`<div class="card"><strong>${esc(e.subject)}</strong><small>${esc(e.from)}</small><small>${esc(e.date)}</small></div>`).join('');}
  if(view==='projects'){const d=await jarvisFetch('/api/projects').then(r=>r.json());$('projects-list').innerHTML=d.map(p=>`<div class="card"><strong>${esc(p.name)}</strong><small>${esc(p.type)} • ${esc(p.status)}</small><small>${esc(p.path)}</small></div>`).join('');}
  if(view==='apps') renderApps($('apps-list'));
}

async function openWidget(type){
  $('widget-layer').classList.remove('hidden'); $('widget-title').textContent=String(type).toUpperCase(); const box=$('widget-content');
  if(type==='calculator'){
    box.innerHTML=`<div class="calc"><input id="calc-display" value="" readonly>${['7','8','9','/','4','5','6','*','1','2','3','-','0','.','C','+','=','(',')','⌫'].map(v=>`<button onclick="calcPress('${v}')">${v}</button>`).join('')}</div>`;return;
  }
  if(type==='email'){const d=await jarvisFetch('/api/email').then(r=>r.json());box.innerHTML=`<div class="widget-list">${d.map(e=>`<div class="card"><strong>${esc(e.subject)}</strong><small>${esc(e.from)}</small><small>${esc(e.date)}</small></div>`).join('')}</div>`;return;}
  if(type==='calendar'){const d=await jarvisFetch('/api/calendar').then(r=>r.json());box.innerHTML=`<div class="widget-list">${d.map(e=>`<div class="card"><strong>${esc(e.subject)}</strong><small>${esc(e.start)}</small></div>`).join('')||'<div class="card">Calendar clear.</div>'}</div>`;return;}
  if(type==='agents'){const d=await jarvisFetch('/api/agents').then(r=>r.json());box.innerHTML=`<div class="widget-list">${d.slice().reverse().map(a=>`<div class="card"><strong>Agent ${esc(a.id)} • ${esc(a.status)}</strong><small>${esc(a.user_task||a.task||'')}</small></div>`).join('')}</div>`;return;}
  if(type==='projects'){const d=await jarvisFetch('/api/projects').then(r=>r.json());box.innerHTML=`<div class="widget-list">${d.map(p=>`<div class="card"><strong>${esc(p.name)}</strong><small>${esc(p.path)}</small></div>`).join('')}</div>`;return;}
  if(type==='apps'){box.innerHTML='<div id="widget-apps" class="app-grid large"></div>';renderApps($('widget-apps'));return;}
  if(type==='controls'){box.innerHTML='<div class="cards"><button class="control-card" onclick="controlAction(\'ping\')">Diagnostics</button><button class="control-card" onclick="controlAction(\'test_speech\')">Voice Test</button></div>';return;}
}
function closeWidget(){$('widget-layer').classList.add('hidden');}
function calcPress(v){const d=$('calc-display');if(v==='C'){d.value='';return}if(v==='⌫'){d.value=d.value.slice(0,-1);return}if(v==='='){try{if(!/^[0-9+\-*/().\s]+$/.test(d.value))throw 0;d.value=Function(`"use strict";return (${d.value})`)()}catch(e){d.value='Error'}return}d.value+=v;}
async function controlAction(action){const r=await jarvisFetch('/api/controls/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});const d=await r.json();$('control-output').textContent=d.message||'';showToast(d.message||'Action complete.');}

const PANEL_LAYOUT_VERSION=2;
const PANEL_LAYOUT_KEY='jarvis.dashboard.layout.v2';
let adjustablePanels=[];
let panelLayout={version:PANEL_LAYOUT_VERSION,panels:{}};
let panelSaveTimer=null;

function panelLayoutId(panel,index){
  return panel.id || (panel.classList.contains('widget-shell')?'widget-shell':`panel-${index}`);
}

function boundedPanelSize(panel,width,height){
  const chat=panel.id==='conversation-panel';
  const minWidth=chat?260:180;
  const minHeight=chat?260:100;
  const maxWidth=Math.max(minWidth,window.innerWidth-24);
  const maxHeight=Math.max(minHeight,window.innerHeight-(chat?56:24));
  return {
    width:Math.max(minWidth,Math.min(maxWidth,Number(width)||minWidth)),
    height:Math.max(minHeight,Math.min(maxHeight,Number(height)||minHeight))
  };
}

function keepPanelReachable(panel){
  const rect=panel.getBoundingClientRect();
  if(!rect.width||!rect.height)return;
  let dx=0,dy=0;
  if(panel.id==='conversation-panel'){
    if(rect.left<8)dx=8-rect.left;
    else if(rect.right>window.innerWidth-8)dx=(window.innerWidth-8)-rect.right;
    if(rect.top<44)dy=44-rect.top;
    else if(rect.bottom>window.innerHeight-8)dy=(window.innerHeight-8)-rect.bottom;
  }else{
    if(rect.right<80)dx=80-rect.right;
    else if(rect.left>window.innerWidth-80)dx=(window.innerWidth-80)-rect.left;
    if(rect.bottom<42)dy=42-rect.bottom;
    else if(rect.top>window.innerHeight-42)dy=(window.innerHeight-42)-rect.top;
  }
  if(!dx&&!dy)return;
  const x=(Number(panel.dataset.layoutX)||0)+dx;
  const y=(Number(panel.dataset.layoutY)||0)+dy;
  panel.dataset.layoutX=String(Math.round(x));
  panel.dataset.layoutY=String(Math.round(y));
  panel.style.setProperty('transform',`translate(${x}px, ${y}px)`,'important');
}

function compatiblePanelLayout(value){
  return Boolean(value&&Number(value.version)===PANEL_LAYOUT_VERSION&&value.panels&&typeof value.panels==='object');
}

function applyGeometry(panel){
  const geometry=panelLayout.panels[panel.dataset.layoutId];
  if(!geometry) return;
  const x=Number(geometry.x)||0;
  const y=Number(geometry.y)||0;
  panel.dataset.layoutX=String(x);
  panel.dataset.layoutY=String(y);
  panel.style.setProperty('transform',`translate(${x}px, ${y}px)`,'important');
  const bounds=boundedPanelSize(panel,geometry.width,geometry.height);
  if(Number.isFinite(Number(geometry.width))) panel.style.setProperty('width',`${bounds.width}px`,'important');
  if(Number.isFinite(Number(geometry.height))) panel.style.setProperty('height',`${bounds.height}px`,'important');
  requestAnimationFrame(()=>keepPanelReachable(panel));
}

function collectPanelLayout(){
  const panels={};
  adjustablePanels.forEach(panel=>{
    const rect=panel.getBoundingClientRect();
    if(!rect.width || !rect.height) return;
    panels[panel.dataset.layoutId]={
      x:Number(panel.dataset.layoutX)||0,
      y:Number(panel.dataset.layoutY)||0,
      width:Math.round(rect.width),
      height:Math.round(rect.height)
    };
  });
  panelLayout={version:PANEL_LAYOUT_VERSION,panels};
  return panelLayout;
}

window.persistPanelLayout = function persistPanelLayout(immediate=false){
  const layout=collectPanelLayout();
  localStorage.setItem(PANEL_LAYOUT_KEY,JSON.stringify(layout));
  clearTimeout(panelSaveTimer);
  const save=()=>jarvisFetch('/api/layout',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(layout),keepalive:true
  }).catch(()=>{});
  if(immediate) save(); else panelSaveTimer=setTimeout(save,180);
}

async function restorePanelLayout(panels){
  let cached={};
  try{ cached=JSON.parse(localStorage.getItem(PANEL_LAYOUT_KEY)||'{}'); }catch(_e){}
  if(compatiblePanelLayout(cached)){
    panelLayout=cached;
    panels.forEach(applyGeometry);
  }else{
    localStorage.removeItem(PANEL_LAYOUT_KEY);
  }
  try{
    const saved=await jarvisFetch('/api/layout',{cache:'no-store'}).then(r=>r.json());
    if(compatiblePanelLayout(saved) && Object.keys(saved.panels).length){
      panelLayout=saved;
      panels.forEach(applyGeometry);
      localStorage.setItem(PANEL_LAYOUT_KEY,JSON.stringify(saved));
    }else if(compatiblePanelLayout(cached) && Object.keys(cached.panels).length){
      persistPanelLayout(true);
    }
  }catch(_e){}
  panels.forEach(keepPanelReachable);
}

function clearPanelGeometry(panel){
  panel.style.removeProperty('transform');
  panel.style.removeProperty('width');
  panel.style.removeProperty('height');
  panel.dataset.layoutX='0';
  panel.dataset.layoutY='0';
}

function initializeAdjustablePanels(){
  const panels=[...document.querySelectorAll('.panel, .widget-shell')];
  adjustablePanels=panels;
  panels.forEach((panel,index)=>{
    panel.dataset.adjustable='true';
    panel.dataset.layoutId=panelLayoutId(panel,index);
    panel.dataset.layoutX='0';
    panel.dataset.layoutY='0';

    panel.addEventListener('pointerdown',event=>{
      if(event.button!==0) return;
      const rect=panel.getBoundingClientRect();
      const onRight=event.clientX>=rect.right-12;
      const onBottom=event.clientY>=rect.bottom-12;
      const title=event.target.closest('.panel-title, .widget-head');
      const resizing=onRight || onBottom;
      if(!resizing && !title) return;
      if(event.target.closest('button,input,select,textarea,a')&&!event.target.closest('.panel-resize-handle')) return;

      event.preventDefault();
      panel.setPointerCapture?.(event.pointerId);
      panel.classList.add('panel-adjusting');
      const startX=event.clientX;
      const startY=event.clientY;
      const startLayoutX=Number(panel.dataset.layoutX)||0;
      const startLayoutY=Number(panel.dataset.layoutY)||0;
      const startWidth=rect.width;
      const startHeight=rect.height;

      const move=moveEvent=>{
        const dx=moveEvent.clientX-startX;
        const dy=moveEvent.clientY-startY;
        if(resizing){
          const bounds=boundedPanelSize(panel,startWidth+(onRight?dx:0),startHeight+(onBottom?dy:0));
          if(onRight) panel.style.setProperty('width',`${bounds.width}px`,'important');
          if(onBottom) panel.style.setProperty('height',`${bounds.height}px`,'important');
        }else{
          const x=startLayoutX+dx;
          const y=startLayoutY+dy;
          panel.dataset.layoutX=String(Math.round(x));
          panel.dataset.layoutY=String(Math.round(y));
          panel.style.setProperty('transform',`translate(${x}px, ${y}px)`,'important');
        }
      };
      const finish=()=>{
        panel.classList.remove('panel-adjusting');
        panel.removeEventListener('pointermove',move);
        panel.removeEventListener('pointerup',finish);
        panel.removeEventListener('pointercancel',finish);
        keepPanelReachable(panel);
        persistPanelLayout(true);
      };
      panel.addEventListener('pointermove',move);
      panel.addEventListener('pointerup',finish);
      panel.addEventListener('pointercancel',finish);
    });

    panel.addEventListener('dblclick',event=>{
      if(!event.target.closest('.panel-title, .widget-head')) return;
      clearPanelGeometry(panel);
      persistPanelLayout(true);
      showToast('Panel position and size reset.');
    });
  });

  $('reset-layout-btn')?.addEventListener('click',async()=>{
    panels.forEach(clearPanelGeometry);
    panelLayout={version:PANEL_LAYOUT_VERSION,panels:{}};
    localStorage.removeItem(PANEL_LAYOUT_KEY);
    try{ await jarvisFetch('/api/layout',{method:'DELETE'}); }catch(_e){}
    showToast('Dashboard layout reset.');
  });

  $('chat-panel-reset')?.addEventListener('click',event=>{
    event.preventDefault();
    event.stopPropagation();
    const chat=$('conversation-panel');
    if(!chat)return;
    clearPanelGeometry(chat);
    keepPanelReachable(chat);
    persistPanelLayout(true);
    setTimeout(()=>$('chat-input')?.focus(),0);
    showToast('Chat panel restored.');
  });

  restorePanelLayout(panels);
  window.addEventListener('resize',()=>adjustablePanels.forEach(keepPanelReachable));
  window.addEventListener('beforeunload',()=>{
    const layout=collectPanelLayout();
    localStorage.setItem(PANEL_LAYOUT_KEY,JSON.stringify(layout));
    if(navigator.sendBeacon){
      navigator.sendBeacon('/api/layout',new Blob([JSON.stringify(layout)],{type:'application/json'}));
    }
  });
}

function tickClock(){const d=new Date();$('clock').textContent=d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}

document.addEventListener('DOMContentLoaded',()=>{
  document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
  $('stop-project-btn')?.addEventListener('click',e=>{e.preventDefault();stopProjectAndCheckpoint();});
$('fullscreen-btn')?.addEventListener('click',toggleFullscreen);$('widget-close').addEventListener('click',closeWidget);$('widget-layer').addEventListener('click',e=>{if(e.target===$('widget-layer'))closeWidget()});
  renderApps($('quick-apps'));initializeAdjustablePanels();tickClock();refreshOverview();pollLiveState();
  setInterval(tickClock,1000);setInterval(pollLiveState,750);setInterval(refreshOverview,12000);
});

// Bind the chat independently of optional panel/widget initialization, including
// when this script is loaded after DOMContentLoaded.
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bindChatControls,{once:true});
else bindChatControls();


// =============================================================
// JARVIS v2.56 — reliable restart/offline overlay watchdog
// =============================================================
let __jarvisRestartOverlay = null;
let __jarvisBackendFailures = 0;
let __jarvisHadConfirmedOutage = false;
let __jarvisRestartOverlayReason = '';
let __jarvisRestartRequestSeen = '';

function showJarvisRestartOverlay(message,reason='restart'){
  if(__jarvisRestartOverlay){
    const title=__jarvisRestartOverlay.querySelector('.restart-title');
    if(title) title.textContent=message;
    if(reason==='restart') __jarvisRestartOverlayReason='restart';
    return;
  }
  const overlay=document.createElement('div');
  overlay.id='jarvis-restart-overlay';
  overlay.innerHTML=`
    <div class="restart-reactor"></div>
    <div class="restart-title">${message}</div>
    <div class="restart-sub">VOICE • DASHBOARD • HERMES • HARDWARE</div>
    <div class="restart-pulse">WAITING FOR JARVIS CORE</div>`;
  document.body.appendChild(overlay);
  __jarvisRestartOverlay=overlay;
  __jarvisRestartOverlayReason=reason;
}

function hideJarvisRestartOverlay(){
  if(__jarvisRestartOverlay){
    __jarvisRestartOverlay.remove();
    __jarvisRestartOverlay=null;
  }
  __jarvisRestartOverlayReason='';
}

function showDashboardConnectionWarning(text='Dashboard heartbeat delayed — reconnecting…'){
  let el=document.getElementById('jarvis-dashboard-health-warning');
  if(!el){
    el=document.createElement('div');
    el.id='jarvis-dashboard-health-warning';
    document.body.appendChild(el);
  }
  el.textContent=text;
  el.classList.add('show');
}

function hideDashboardConnectionWarning(){
  const el=document.getElementById('jarvis-dashboard-health-warning');
  if(el) el.classList.remove('show');
}

async function fetchWithDeadline(url,timeoutMs=5000){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{
    return await jarvisFetch(url,{cache:'no-store',signal:controller.signal});
  } finally {
    clearTimeout(timer);
  }
}

async function jarvisBackendWatchdog(){
  try{
    // Same-origin /api/health is intentionally tiny and contains no provider,
    // sensor, IPC or Qwen work. A busy 27B generation must not blank the UI.
    const r=await fetchWithDeadline('/api/health?watchdog='+Date.now(),20000);
    if(!r.ok) throw new Error('dashboard health probe unavailable');
    const data=await r.json();
    if(!data || data.ok!==true || data.service!=='jarvis-dashboard' ||
       typeof data.build_id!=='string' || !data.build_id.trim()){
      throw new Error('dashboard health response invalid');
    }

    // Detect the common upgrade case where app.js was read from newly-extracted
    // files but an older dashboard.py process is still serving port 8080.
    // Use the same page identity as client diagnostics, so the watchdog cannot
    // retain a separate release number after an upgrade.
    if(data.build_id!==JARVIS_UI_BUILD_ID){
      __jarvisBackendFailures=0;
      showDashboardConnectionWarning(`Dashboard version mismatch: page ${JARVIS_UI_BUILD_ID}; server ${data.build_id}. After checkpoint saving finishes, restart Jarvis and its dashboard, then reload this page.`);
      return;
    }

    const recovered=__jarvisBackendFailures>0;
    window.__jarvisLastHealthOk = Date.now();
    window.__jarvisHealth = data;
    __jarvisBackendFailures=0;
    __jarvisHadConfirmedOutage=false;
    hideDashboardConnectionWarning();
    // A normal heartbeat is never allowed to control the full-screen restart overlay.
    // That overlay belongs only to an explicitly active restart supervisor.
    if(__jarvisRestartOverlayReason==='watchdog') hideJarvisRestartOverlay();
    if(recovered){
      // State polling will naturally catch up; avoid reload loops after transient stalls.
    }
  }catch(_e){
    __jarvisBackendFailures++;
    jarvisClientLog('heartbeat.failure',`${_e?.name||''} ${_e?.message||_e}`,{failures:__jarvisBackendFailures});
    // Keep the dashboard usable during transient CPU/RAM saturation. Show only
    // a small warning after a sustained failure; never cover the entire UI.
    if(__jarvisBackendFailures>=20){
      __jarvisHadConfirmedOutage=true;
      showDashboardConnectionWarning('Dashboard heartbeat delayed — reconnecting in background…');
    }
  }
}

async function jarvisRestartStatusWatchdog(){
  try{
    const r=await fetchWithDeadline('/api/restart/status?watchdog='+Date.now(),12000);
    if(!r.ok) return;
    const data=await r.json();
    const stage=String(data.stage||'').toLowerCase();
    const requestId=String(data.request_id||'');
    const activeStages=new Set(['supervisor-ready','starting','shutdown','shutdown-ui','shutdown-services','shutdown-hermes','stopping','restarting','launching','waiting','verify-down','force-clean','offline-confirmed','verify-up','health-check','reopening-ui']);
    if(data.active===true && activeStages.has(stage)){
      __jarvisRestartRequestSeen=requestId || __jarvisRestartRequestSeen;
      hideDashboardConnectionWarning();
      showJarvisRestartOverlay('JARVIS CORE OFFLINE — RESTARTING ALL SYSTEMS','restart');
      return;
    }
    // A stale JSON status without the supervisor flag is informational only.
    if(__jarvisRestartOverlayReason==='restart' && data.active!==true){
      hideJarvisRestartOverlay();
    }
    if(__jarvisRestartOverlayReason==='restart' && (stage==='complete' || stage==='failure')){
      hideJarvisRestartOverlay();
    }
  }catch(_e){
    // Health warning is non-blocking; never infer a restart from a failed status poll.
  }
}

setInterval(jarvisBackendWatchdog,3000);
setInterval(jarvisRestartStatusWatchdog,2000);
jarvisBackendWatchdog();
jarvisRestartStatusWatchdog();

// v2.59: command/restart acknowledgement is handled by normal API polling.
// Do not monkey-patch window.fetch; keeping the native fetch untouched prevents
// stale wrappers from breaking dashboard commands or heartbeat probes.
