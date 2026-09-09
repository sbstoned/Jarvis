import {FilesetResolver, HandLandmarker} from "/airtouch/vendor/vision_bundle.mjs";

const MEDIAPIPE_VERSION="0.10.35";
const MEDIAPIPE_MODULE_URL="/airtouch/vendor/vision_bundle.mjs";
const MEDIAPIPE_WASM_ROOT="/airtouch/vendor/wasm";
const MEDIAPIPE_MODEL_URL="/airtouch/model/hand_landmarker.task";
const MEDIAPIPE_ASSETS=[
  [MEDIAPIPE_MODULE_URL,"application/javascript"],
  [`${MEDIAPIPE_WASM_ROOT}/vision_wasm_internal.js`,"application/javascript"],
  [`${MEDIAPIPE_WASM_ROOT}/vision_wasm_internal.wasm`,"application/wasm"],
  [`${MEDIAPIPE_WASM_ROOT}/vision_wasm_nosimd_internal.js`,"application/javascript"],
  [`${MEDIAPIPE_WASM_ROOT}/vision_wasm_nosimd_internal.wasm`,"application/wasm"],
  [MEDIAPIPE_MODEL_URL,"application/octet-stream"]
];

const DEFAULTS = Object.freeze({
  enabled:false,
  cameraEnabled:false,
  paused:false,
  cameraId:"",
  resolution:"640x480",
  preferredHand:"Any",
  mirrored:true,
  sensitivity:1.0,
  smoothing:0.32,
  pinchStart:0.052,
  pinchRelease:0.075,
  confirmationFrames:2,
  gestureCooldownMs:220,
  scrollSensitivity:1.0,
  swipeSensitivity:1.0,
  dwellTyping:false,
  dwellDurationMs:850,
  targetSnapping:false,
  cameraPreview:false,
  debug:false,
  cursorVisible:true,
  externalControl:false,
  autoKeyboard:false,
  gesturePauseEnabled:false,
  gesturePauseHoldMs:1800,
  calibration:null
});

const STORAGE_KEY="jarvis.airtouch.settings.v1";
const state={
  settings:{...DEFAULTS},
  status:"AIR TOUCH OFF",
  handLandmarker:null,
  mediaPipeReady:false,
  mediaPipeInitializing:null,
  delegate:"—",
  executionMode:"main thread",
  wasmLoaderUrl:"—",
  wasmBinaryUrl:"—",
  stream:null,
  video:null,
  cursor:null,
  preview:null,
  debugPanel:null,
  externalWarning:null,
  keyboard:null,
  raf:0,
  lastFrameAt:0,
  cameraFrames:0,
  trackingFrames:0,
  fpsWindowAt:performance.now(),
  cameraFps:0,
  trackingFps:0,
  dropped:0,
  processingMs:0,
  hand:null,
  raw:{x:.5,y:.5},
  smooth:{x:.5,y:.5},
  previous:{x:.5,y:.5,t:performance.now()},
  target:null,
  targetKey:"",
  targetSince:0,
  pinch:false,
  pinchFrames:0,
  releaseFrames:0,
  pinchStartedAt:0,
  pinchStartPoint:null,
  lastPinchAt:0,
  drag:false,
  resize:false,
  pointerDownTarget:null,
  pointerId:7711,
  scrollY:null,
  swipeSamples:[],
  palmSince:0,
  calibrationMode:false,
  calibrationIndex:0,
  calibrationSamples:[],
  calibrationOverlay:null,
  keyboardLastKey:"",
  keyboardLastAt:0,
  serverSyncTimer:0,
  targetSyncAt:0,
  externalMoveAt:0,
  logs:[], lastError:"", workerStage:"not started", debugDrag:null, firstInferenceLogged:false, frameLoopStarted:false, lastLoopBlock:"", frameWatchdog:0, inferenceIntervalMs:70, lastInferenceAt:0, visualRaf:0, targetCursor:{x:.5,y:.5}
};

const STATUS={
  OFF:"AIR TOUCH OFF", INIT:"INITIALIZING CAMERA", CALIBRATE:"CALIBRATION REQUIRED",
  TRACKING:"TRACKING", PAUSED:"PAUSED", CLICKING:"CLICKING", DRAGGING:"DRAGGING",
  RESIZING:"RESIZING", SCROLLING:"SCROLLING", KEYBOARD:"KEYBOARD ACTIVE",
  LOST:"TRACKING LOST", EXTERNAL:"EXTERNAL CONTROL ACTIVE", ERROR:"CAMERA ERROR"
};

const q=s=>document.querySelector(s);
const qa=s=>[...document.querySelectorAll(s)];
function airLog(stage,message,error=""){
  const line={at:new Date().toLocaleTimeString(),stage,message,error:String(error||"")};
  state.logs.push(line); if(state.logs.length>40)state.logs.shift();
  if(error)state.lastError=String(error);
  state.workerStage=stage;
  console[error?"error":"log"]("[AirTouch]",stage,message,error||"");
  renderDebug();
}


function loadSettings(){
  try { state.settings={...DEFAULTS,...JSON.parse(localStorage.getItem(STORAGE_KEY)||"{}")}; }
  catch { state.settings={...DEFAULTS}; }
  // Runtime power state is intentionally session-only. Keep every preference
  // from localStorage, but a new page/session must never open the webcam.
  state.settings.enabled=false;
  state.settings.cameraEnabled=false;
  syncSettingsFromServer();
}
async function syncSettingsFromServer(){
  try{
    const r=await fetch("/api/airtouch/settings",{cache:"no-store"});
    if(r.ok){
      const server=await r.json();
      state.settings={...state.settings,...server,enabled:false,cameraEnabled:false};
      localStorage.setItem(STORAGE_KEY,JSON.stringify(state.settings));
      renderSettings();
      updateExternalWarning();
    }
  }catch{}
}
function saveSettings(){
  localStorage.setItem(STORAGE_KEY,JSON.stringify(state.settings));
  clearTimeout(state.serverSyncTimer);
  state.serverSyncTimer=setTimeout(()=>{
    fetch("/api/airtouch/settings",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify(state.settings),keepalive:true
    }).catch(()=>{});
  },120);
  renderSettings();
  updateExternalWarning();
}
function setStatus(value){
  state.status=value;
  const pill=q("#airtouch-status-pill");
  if(pill){pill.textContent=value;pill.dataset.state=value;}
  const s=q("#airtouch-settings-status"); if(s)s.textContent=value;
  document.body.dataset.airtouch=value.toLowerCase().replace(/\s+/g,"-");
}
function ensureUi(){
  if(!state.cursor){
    const c=document.createElement("div");
    c.id="airtouch-cursor"; c.className="airtouch-cursor lost";
    c.innerHTML='<span class="airtouch-cursor-core"></span><span class="airtouch-cursor-ring"></span>';
    document.body.appendChild(c); state.cursor=c;
  }
  if(!q("#airtouch-status-pill")){
    const pill=document.createElement("button");
    pill.id="airtouch-status-pill"; pill.className="airtouch-status-pill";
    pill.textContent=STATUS.OFF;
    pill.onclick=()=>openSettings();
    document.body.appendChild(pill);
  }
  if(!state.externalWarning){
    const w=document.createElement("div"); w.id="airtouch-external-warning";
    w.className="airtouch-external-warning"; w.innerHTML="⚠ EXTERNAL AIR CONTROL ACTIVE <button>EMERGENCY STOP</button>";
    w.querySelector("button").onclick=emergencyStop; document.body.appendChild(w); state.externalWarning=w;
  }
  if(!state.preview){
    const wrap=document.createElement("div");wrap.id="airtouch-preview";wrap.className="airtouch-preview hidden";
    wrap.innerHTML='<video id="airtouch-preview-video" playsinline muted></video><canvas id="airtouch-debug-canvas"></canvas>';
    document.body.appendChild(wrap); state.preview=wrap;
  }
  if(!state.debugPanel){
    const d=document.createElement("div");
    d.id="airtouch-debug";
    d.className="airtouch-debug hidden";
    document.body.appendChild(d);
    state.debugPanel=d;
    restoreDebugPanelPosition(d);
    bindMovableDebugPanel(d);
  }
}
const DEBUG_POS_KEY="jarvis.airtouch.debug.position.v1";

function restoreDebugPanelPosition(panel){
  try{
    const pos=JSON.parse(localStorage.getItem(DEBUG_POS_KEY)||"null");
    if(pos&&Number.isFinite(pos.left)&&Number.isFinite(pos.top)){
      panel.style.left=`${Math.max(0,Math.min(innerWidth-180,pos.left))}px`;
      panel.style.top=`${Math.max(0,Math.min(innerHeight-80,pos.top))}px`;
      panel.style.right="auto";
      panel.style.bottom="auto";
    }
  }catch{}
}
function saveDebugPanelPosition(panel){
  try{
    const r=panel.getBoundingClientRect();
    localStorage.setItem(DEBUG_POS_KEY,JSON.stringify({left:Math.round(r.left),top:Math.round(r.top)}));
  }catch{}
}
function bindMovableDebugPanel(panel){
  if(panel.dataset.dragBound==="1")return;
  panel.dataset.dragBound="1";
  panel.addEventListener("pointerdown",event=>{
    const head=event.target.closest(".airtouch-debug-head");
    if(!head||event.button!==0)return;
    const rect=panel.getBoundingClientRect();
    state.debugDrag={
      pointerId:event.pointerId,
      startX:event.clientX,startY:event.clientY,
      left:rect.left,top:rect.top
    };
    panel.style.left=`${rect.left}px`;
    panel.style.top=`${rect.top}px`;
    panel.style.right="auto";
    panel.style.bottom="auto";
    panel.classList.add("dragging");
    try{panel.setPointerCapture(event.pointerId);}catch{}
    event.preventDefault();
  });
  panel.addEventListener("pointermove",event=>{
    const drag=state.debugDrag;
    if(!drag||drag.pointerId!==event.pointerId)return;
    const width=panel.offsetWidth||260,height=panel.offsetHeight||180;
    const left=Math.max(0,Math.min(innerWidth-width,drag.left+event.clientX-drag.startX));
    const top=Math.max(0,Math.min(innerHeight-height,drag.top+event.clientY-drag.startY));
    panel.style.left=`${left}px`;panel.style.top=`${top}px`;
  });
  const finish=event=>{
    const drag=state.debugDrag;
    if(!drag||drag.pointerId!==event.pointerId)return;
    state.debugDrag=null;panel.classList.remove("dragging");
    try{panel.releasePointerCapture(event.pointerId);}catch{}
    saveDebugPanelPosition(panel);
  };
  panel.addEventListener("pointerup",finish);
  panel.addEventListener("pointercancel",finish);
}

function updateExternalWarning(){
  if(!state.externalWarning)return;
  state.externalWarning.classList.toggle("active",!!state.settings.externalControl);
}
function settingsRows(){
  return `
  <div class="airtouch-settings-grid">
    <label>Master <input data-at="enabled" type="checkbox"></label>
    <label>Camera <input data-at="cameraEnabled" type="checkbox"></label>
    <label>Pause <input data-at="paused" type="checkbox"></label>
    <label>Camera <select data-at="cameraId" id="airtouch-camera-select"><option value="">Default camera</option></select></label>
    <label>Resolution <select data-at="resolution"><option>640x480</option><option>960x540</option><option>1280x720</option></select></label>
    <label>Hand <select data-at="preferredHand"><option>Any</option><option>Right</option><option>Left</option></select></label>
    <label>Mirrored <input data-at="mirrored" type="checkbox"></label>
    <label>Sensitivity <input data-at="sensitivity" type="range" min=".5" max="2" step=".05"><output></output></label>
    <label>Smoothing <input data-at="smoothing" type="range" min=".05" max=".8" step=".01"><output></output></label>
    <label>Pinch start <input data-at="pinchStart" type="range" min=".025" max=".10" step=".002"><output></output></label>
    <label>Pinch release <input data-at="pinchRelease" type="range" min=".04" max=".14" step=".002"><output></output></label>
    <label>Confirm frames <input data-at="confirmationFrames" type="number" min="1" max="6"></label>
    <label>Cooldown ms <input data-at="gestureCooldownMs" type="number" min="80" max="1000" step="20"></label>
    <label>Scroll <input data-at="scrollSensitivity" type="range" min=".3" max="3" step=".1"><output></output></label>
    <label>Swipe <input data-at="swipeSensitivity" type="range" min=".3" max="3" step=".1"><output></output></label>
    <label>Dwell typing <input data-at="dwellTyping" type="checkbox"></label>
    <label>Dwell ms <input data-at="dwellDurationMs" type="number" min="350" max="2500" step="50"></label>
    <label>Open-palm pause <input data-at="gesturePauseEnabled" type="checkbox"></label>
    <label>Pause hold ms <input data-at="gesturePauseHoldMs" type="number" min="1000" max="5000" step="100"></label>
    <label>Target snapping <input data-at="targetSnapping" type="checkbox"></label>
    <label>Virtual keyboard <button data-at-action="keyboard">OPEN</button></label>
    <label>Camera preview <input data-at="cameraPreview" type="checkbox"></label>
    <label>Debug <input data-at="debug" type="checkbox"></label>
    <label>Cursor <input data-at="cursorVisible" type="checkbox"></label>
    <label class="danger-setting">External Windows control <input data-at="externalControl" type="checkbox"></label>
  </div>
  <div class="airtouch-setting-actions">
    <button data-at-action="start">START CAMERA</button>
    <button data-at-action="stop">STOP CAMERA</button>
    <button data-at-action="calibrate">CALIBRATE</button>
    <button data-at-action="pause">PAUSE / RESUME</button>
    <button data-at-action="emergency">EMERGENCY STOP</button>
    <button data-at-action="defaults">RESTORE DEFAULTS</button>
  </div>`;
}
function openSettings(){
  if(typeof window.openDetailDock==="function"){
    window.openDetailDock("gestures");
    setTimeout(renderSettings,50);
  }
}
function renderSettings(){
  const host=q("#airtouch-control-host");
  if(!host)return;
  if(!host.dataset.built){
    host.innerHTML=`<div class="airtouch-status-line"><b id="airtouch-settings-status">${state.status}</b><span>Local MediaPipe • webcam frames never sent to Hermes</span></div>${settingsRows()}`;
    host.dataset.built="1";
    host.addEventListener("change",onSettingChange);
    host.addEventListener("input",onSettingInput);
    host.addEventListener("click",onSettingAction);
    populateCameras();
  }
  host.querySelectorAll("[data-at]").forEach(el=>{
    const key=el.dataset.at,val=state.settings[key];
    if(el.type==="checkbox")el.checked=!!val; else el.value=val ?? "";
    const out=el.parentElement?.querySelector("output");if(out)out.textContent=String(val);
  });
  const st=q("#airtouch-settings-status");if(st)st.textContent=state.status;
}
function onSettingInput(e){
  const el=e.target.closest("[data-at]");if(!el)return;
  const k=el.dataset.at;
  state.settings[k]=el.type==="checkbox"?el.checked:(el.type==="number"||el.type==="range"?Number(el.value):el.value);
  const out=el.parentElement?.querySelector("output");if(out)out.textContent=String(state.settings[k]);
  saveSettings();
}
function onSettingChange(e){onSettingInput(e);applySettingsChange(e.target?.dataset?.at);}
function applySettingsChange(key){
  if(key==="enabled"){state.settings.enabled?startCamera():(stopCamera(),setStatus(STATUS.OFF));}
  if(key==="cameraEnabled"){state.settings.cameraEnabled?startCamera():stopCamera();}
  if(key==="paused")setStatus(state.settings.paused?STATUS.PAUSED:(state.hand?STATUS.TRACKING:STATUS.LOST));
  if(key==="cameraPreview")state.preview?.classList.toggle("hidden",!state.settings.cameraPreview);
  if(key==="debug")state.debugPanel?.classList.toggle("hidden",!state.settings.debug);
  if(key==="externalControl"&&!state.settings.externalControl)externalRelease();
}
function onSettingAction(e){
  const action=e.target.closest("[data-at-action]")?.dataset?.atAction;if(!action)return;
  if(action==="start")startCamera();
  if(action==="stop")stopCamera();
  if(action==="calibrate")beginCalibration();
  if(action==="pause"){state.settings.paused=!state.settings.paused;saveSettings();applySettingsChange("paused");}
  if(action==="emergency")emergencyStop();
  if(action==="defaults"){state.settings={...DEFAULTS};saveSettings();stopCamera();setStatus(STATUS.OFF);}
  if(action==="keyboard")toggleKeyboard(true);
}
async function populateCameras(){
  try{
    const devices=await navigator.mediaDevices.enumerateDevices();
    const sel=q("#airtouch-camera-select");if(!sel)return;
    const current=state.settings.cameraId;
    sel.innerHTML='<option value="">Default camera</option>'+devices.filter(d=>d.kind==="videoinput").map((d,i)=>`<option value="${d.deviceId}">${escapeHtml(d.label||`Camera ${i+1}`)}</option>`).join("");
    sel.value=current;
  }catch{}
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}

async function preflightMediaPipeAssets(){
  airLog("architecture",`MediaPipe Tasks Vision ${MEDIAPIPE_VERSION}; initialization and inference mode=${state.executionMode} (official browser pattern)`);
  for(const [url,expectedType] of MEDIAPIPE_ASSETS){
    const response=await fetch(url,{method:"HEAD",cache:"no-store"});
    const contentType=(response.headers.get("content-type")||"").toLowerCase();
    const bytes=response.headers.get("content-length")||"unknown";
    if(!response.ok)throw new Error(`Asset ${url} returned HTTP ${response.status}`);
    if(!contentType.includes(expectedType))throw new Error(`Asset ${url} has MIME ${contentType||"missing"}; expected ${expectedType}`);
    airLog("asset",`${url} OK; MIME=${contentType}; bytes=${bytes}`);
  }
}
function loadClassicScript(url){
  return new Promise((resolve,reject)=>{
    try{ delete window.ModuleFactory; }catch{}
    const script=document.createElement("script");
    script.src=`${url}${url.includes("?")?"&":"?"}jarvis=${Date.now()}`;
    script.async=false;
    script.crossOrigin="anonymous";
    script.onload=()=>{
      if(typeof window.ModuleFactory!=="function"){
        script.remove();
        reject(new Error(`Classic WASM loader executed but ModuleFactory was not exported: ${url}`));
        return;
      }
      script.remove();
      resolve();
    };
    script.onerror=()=>{
      script.remove();
      reject(new Error(`Classic WASM loader failed to load: ${url}`));
    };
    document.head.appendChild(script);
  });
}

async function prepareMediaPipeFileset(){
  const simd=await FilesetResolver.isSimdSupported();
  const suffix=simd?"wasm":"wasm_nosimd";
  const loader=`${MEDIAPIPE_WASM_ROOT}/vision_${suffix}_internal.js`;
  const binary=`${MEDIAPIPE_WASM_ROOT}/vision_${suffix}_internal.wasm`;
  state.wasmLoaderUrl=loader;
  state.wasmBinaryUrl=binary;
  airLog("wasm",`SIMD=${simd}; preloading classic loader=${loader}`);
  await loadClassicScript(loader);
  airLog("wasm",`Classic loader exported ModuleFactory successfully`);
  return {wasmLoaderPath:null,wasmBinaryPath:binary};
}

async function initializeMediaPipe(){
  if(state.mediaPipeReady&&state.handLandmarker)return state.handLandmarker;
  if(state.mediaPipeInitializing)return state.mediaPipeInitializing;
  state.mediaPipeInitializing=(async()=>{
    try{
      await preflightMediaPipeAssets();
      airLog("module",`ES module loaded: ${MEDIAPIPE_MODULE_URL}; version=${MEDIAPIPE_VERSION}; mode=${state.executionMode}`);

      let lastError=null;
      for(const delegate of ["GPU","CPU"]){
        try{
          // MediaPipe consumes and clears ModuleFactory during task creation,
          // therefore prepare a fresh classic loader for every delegate attempt.
          const fileset=await prepareMediaPipeFileset();
          const options={
            baseOptions:{modelAssetPath:MEDIAPIPE_MODEL_URL,delegate},
            runningMode:"VIDEO",
            numHands:1,
            minHandDetectionConfidence:.55,
            minHandPresenceConfidence:.55,
            minTrackingConfidence:.5
          };
          airLog("model",`Creating Hand Landmarker; model=${MEDIAPIPE_MODEL_URL}; delegate=${delegate}`);
          state.handLandmarker=await HandLandmarker.createFromOptions(fileset,options);
          state.delegate=delegate;
          state.mediaPipeReady=true;
          airLog("ready",`MediaPipe initialized; delegate=${delegate}; mode=${state.executionMode}; loader=${state.wasmLoaderUrl}; binary=${state.wasmBinaryUrl}`);
          return state.handLandmarker;
        }catch(error){
          lastError=error;
          state.handLandmarker=null;
          state.mediaPipeReady=false;
          airLog("delegate",`${delegate} initialization failed${delegate==="GPU"?"; retrying CPU":""}`,error?.stack||error);
        }
      }
      throw lastError||new Error("MediaPipe failed to initialize with GPU and CPU.");
    }catch(error){
      state.mediaPipeReady=false;
      airLog("init-error",`MediaPipe initialization failed; version=${MEDIAPIPE_VERSION}; mode=${state.executionMode}; model=${MEDIAPIPE_MODEL_URL}`,error?.stack||error);
      notifyAssetsMissing(error);
      throw error;
    }finally{
      state.mediaPipeInitializing=null;
    }
  })();
  return state.mediaPipeInitializing;
}

function notifyAssetsMissing(message){
  if(/Failed to fetch|404|Asset .* HTTP|MIME/i.test(String(message))){
    window.showToast?.("Air Touch MediaPipe assets failed validation. Run SETUP_AIR_TOUCH.bat once.");
  }
}
async function startCamera(){
  ensureUi();
  airLog("camera","Start camera requested");
  state.settings.enabled=true;
  state.settings.cameraEnabled=true;
  state.settings.paused=false;
  saveSettings();
  setStatus(STATUS.INIT);

  try{
    await initializeMediaPipe();

    const [w,h]=String(state.settings.resolution).split("x").map(Number);
    if(state.stream)state.stream.getTracks().forEach(t=>t.stop());

    const video=document.createElement("video");
    video.playsInline=true;
    video.muted=true;
    video.autoplay=true;

    const constraints={audio:false,video:{
      width:{ideal:w||640},
      height:{ideal:h||480},
      frameRate:{ideal:60,max:60},
      deviceId:state.settings.cameraId?{exact:state.settings.cameraId}:undefined
    }};

    airLog("camera","Requesting getUserMedia");
    state.stream=await navigator.mediaDevices.getUserMedia(constraints);
    airLog("camera","Camera permission granted / stream opened");

    video.srcObject=state.stream;
    state.video=video;

    // Do not let device enumeration or preview setup block the inference loop.
    await video.play();
    airLog("camera",`Video play resolved; readyState=${video.readyState}; size=${video.videoWidth||w}x${video.videoHeight||h}`);

    // Reassert runtime state after async setup in case a stale server/localStorage
    // sync completed while camera permission was being granted.
    state.settings.enabled=true;
    state.settings.cameraEnabled=true;
    state.settings.paused=false;

    setStatus(state.settings.calibration?STATUS.LOST:STATUS.CALIBRATE);

    cancelAnimationFrame(state.raf);
    state.lastFrameAt=0;
    state.lastInferenceAt=0;
    state.inferenceIntervalMs=70;
    state.cameraFrames=0;
    state.trackingFrames=0;
    state.frameLoopStarted=false;
    state.lastLoopBlock="";
    state.raf=requestAnimationFrame(frameLoop);
    airLog("loop","requestAnimationFrame inference loop scheduled");

    clearTimeout(state.frameWatchdog);
    state.frameWatchdog=setTimeout(()=>{
      if(state.cameraFrames===0){
        airLog(
          "loop-error",
          `Inference loop produced zero camera frames after 2 seconds; lastBlock=${state.lastLoopBlock||"unknown"}; `+
          `enabled=${state.settings.enabled}; cameraEnabled=${state.settings.cameraEnabled}; paused=${state.settings.paused}; `+
          `videoReady=${state.video?.readyState}; mediaPipeReady=${state.mediaPipeReady}`,
          "Frame loop stalled"
        );
      }else{
        airLog("loop",`Inference loop healthy; cameraFrames=${state.cameraFrames}; trackingFrames=${state.trackingFrames}`);
      }
    },2000);

    const pv=q("#airtouch-preview-video");
    if(pv){
      pv.srcObject=state.stream;
      pv.play().catch(error=>airLog("preview","Preview video play failed",error?.message||error));
    }

    // Noncritical async UI work must not delay the loop.
    populateCameras().catch(error=>airLog("camera","Camera enumeration failed",error?.message||error));
    state.preview?.classList.toggle("hidden",!state.settings.cameraPreview);
    state.debugPanel?.classList.toggle("hidden",!state.settings.debug);

    airLog("camera","Camera pipeline startup completed");
  }catch(error){
    airLog("startup-error","Air Touch pipeline could not start",error?.stack||error);
    setStatus(STATUS.ERROR);
    state.settings.cameraEnabled=false;
    saveSettings();
    window.showToast?.(
      state.mediaPipeReady
        ? "Air Touch camera could not start. Open Debug for details."
        : "Air Touch MediaPipe initialization failed. Open Debug for asset/runtime details."
    );
  }
}

function stopCamera(){
  cancelAnimationFrame(state.raf);state.raf=0;
  clearTimeout(state.frameWatchdog);state.frameWatchdog=0;
  state.frameLoopStarted=false;state.lastLoopBlock="";
  state.stream?.getTracks().forEach(t=>t.stop());state.stream=null;state.video=null;state.hand=null;
  state.settings.cameraEnabled=false;saveSettings();safeRelease();state.cursor?.classList.add("lost");
  setStatus(state.settings.enabled?STATUS.LOST:STATUS.OFF);
}
function frameLoop(now){
  state.raf=requestAnimationFrame(frameLoop);

  if(!state.frameLoopStarted){
    state.frameLoopStarted=true;
    airLog("loop","First animation frame callback received");
  }

  let block="";
  if(!state.settings.enabled) block="master-disabled";
  else if(!state.settings.cameraEnabled) block="camera-disabled";
  else if(state.settings.paused) block="paused";
  else if(!state.video) block="no-video";
  else if(!state.mediaPipeReady) block="mediapipe-not-ready";
  else if(state.video.readyState<2) block=`video-readyState-${state.video.readyState}`;

  if(block){
    if(block!==state.lastLoopBlock){
      state.lastLoopBlock=block;
      airLog("loop-wait",`Inference waiting: ${block}`);
    }
    updateFps(now);
    return;
  }

  if(state.lastLoopBlock){
    airLog("loop",`Inference resumed after ${state.lastLoopBlock}`);
    state.lastLoopBlock="";
  }

  // MediaPipe inference is intentionally throttled. On this PC each inference
  // can take ~100 ms; trying to run it every animation frame only blocks the UI.
  // The cursor itself still animates at display refresh rate via visualCursorLoop().
  if(now-state.lastInferenceAt<state.inferenceIntervalMs){
    updateFps(now);
    return;
  }

  state.lastInferenceAt=now;
  state.lastFrameAt=now;
  state.cameraFrames++;

  const started=performance.now();
  try{
    const result=state.handLandmarker.detectForVideo(state.video,now);
    state.trackingFrames++;
    state.processingMs=performance.now()-started;
    // Keep inference from queueing faster than this machine can finish it.
    state.inferenceIntervalMs=Math.max(55,Math.min(120,state.processingMs*0.82));

    const hands=(result.landmarks||[]).map((landmarks,index)=>({
      landmarks:landmarks.map(p=>({x:p.x,y:p.y,z:p.z})),
      handedness:result.handedness?.[index]?.[0]?.categoryName||"",
      confidence:result.handedness?.[index]?.[0]?.score||0
    }));

    if(!state.firstInferenceLogged){
      state.firstInferenceLogged=true;
      airLog("tracking",`First MediaPipe result received using ${state.delegate}; hands=${hands.length}`);
    }
    processHands(hands);
  }catch(error){
    state.dropped++;
    if(state.dropped<=5 || state.dropped%60===0){
      airLog("frame-error","Hand detection frame failed",error?.stack||error);
    }
  }

  updateFps(now);
}

function updateFps(now){
  if(now-state.fpsWindowAt>=1000){
    const seconds=(now-state.fpsWindowAt)/1000;
    state.cameraFps=Math.round(state.cameraFrames/seconds);state.trackingFps=Math.round(state.trackingFrames/seconds);
    state.cameraFrames=0;state.trackingFrames=0;state.fpsWindowAt=now;renderDebug();
  }
}
function selectHand(hands){
  if(!hands.length)return null;
  const pref=state.settings.preferredHand;
  if(pref==="Any")return hands[0];
  return hands.find(h=>String(h.handedness).toLowerCase()===pref.toLowerCase())||hands[0];
}
function processHands(hands){
  const hand=selectHand(hands);
  if(!hand){trackingLost();return;}
  state.hand=hand;const lm=hand.landmarks;if(!lm||lm.length<21){trackingLost();return;}
  let x=lm[8].x,y=lm[8].y;
  if(state.settings.mirrored)x=1-x;
  const calibrated=mapCalibration(x,y);
  x=calibrated.x;y=calibrated.y;
  x=(x-.5)*state.settings.sensitivity+.5;y=(y-.5)*state.settings.sensitivity+.5;
  x=Math.max(0,Math.min(1,x));y=Math.max(0,Math.min(1,y));
  state.raw={x,y};
  smoothCursor(x,y);
  const px=state.targetCursor.x*innerWidth,py=state.targetCursor.y*innerHeight;
  updateTarget(px,py);

  const pinchDistance=dist(lm[4],lm[8]);
  const now=performance.now();
  processGestureState(lm,pinchDistance,px,py,now);
  if(state.calibrationMode)renderCalibrationPointer(px,py);

  if(state.settings.externalControl)externalMove(px,py);
  if(!state.settings.paused && !state.drag && !state.resize)setStatus(STATUS.TRACKING);
  renderDebug(pinchDistance,hand);
}
function mapCalibration(x,y){
  const c=state.settings.calibration;
  if(!c)return {x,y};
  if(c.viewportW&&Math.abs(innerWidth-c.viewportW)/c.viewportW>.15)return {x,y};
  const dx=Math.max(.1,c.maxX-c.minX),dy=Math.max(.1,c.maxY-c.minY);
  return {x:(x-c.minX)/dx,y:(y-c.minY)/dy};
}
function smoothCursor(x,y){
  state.targetCursor.x=x;
  state.targetCursor.y=y;
  state.previous={x,y,t:performance.now()};
}
function visualCursorLoop(){
  const responsiveness=Math.max(.18,Math.min(.55,0.62-(Number(state.settings.smoothing)||.32)));
  state.smooth.x += (state.targetCursor.x-state.smooth.x)*responsiveness;
  state.smooth.y += (state.targetCursor.y-state.smooth.y)*responsiveness;
  moveCursor(state.smooth.x*innerWidth,state.smooth.y*innerHeight);
  state.visualRaf=requestAnimationFrame(visualCursorLoop);
}
function moveCursor(px,py){
  ensureUi();state.cursor.style.transform=`translate3d(${px}px,${py}px,0)`;
  state.cursor.classList.toggle("hidden",!state.settings.cursorVisible);state.cursor.classList.remove("lost");
}
function dist(a,b){return Math.hypot(a.x-b.x,a.y-b.y);}
function fingerExtended(lm,tip,pip){return lm[tip].y<lm[pip].y-.018;}
function isOpenPalm(lm){return [8,12,16,20].every((tip,i)=>fingerExtended(lm,tip,[6,10,14,18][i]));}
function isFist(lm){return [8,12,16,20].every((tip,i)=>lm[tip].y>lm[[6,10,14,18][i]].y-.008);}
function isTwoFinger(lm){
  return fingerExtended(lm,8,6)&&fingerExtended(lm,12,10)&&!fingerExtended(lm,16,14)&&!fingerExtended(lm,20,18);
}
function processGestureState(lm,pinchDistance,px,py,now){
  if(state.settings.paused){
    if(isFist(lm))safeRelease();
    return;
  }
  if(isFist(lm)){safeRelease();return;}
  if(state.settings.gesturePauseEnabled && isOpenPalm(lm) && !state.pinch){
    const motion=Math.hypot(state.raw.x-state.previous.x,state.raw.y-state.previous.y);
    if(motion<0.012){
      if(!state.palmSince)state.palmSince=now;
      if(now-state.palmSince>Number(state.settings.gesturePauseHoldMs||1800)){
        state.settings.paused=true;
        saveSettings();
        safeRelease();
        setStatus(STATUS.PAUSED);
        state.palmSince=0;
      }
    }else{
      state.palmSince=0;
    }
    return;
  }else state.palmSince=0;

  const start=pinchDistance<=state.settings.pinchStart;
  const release=pinchDistance>=state.settings.pinchRelease;
  if(!state.pinch){
    state.pinchFrames=start?state.pinchFrames+1:0;
    if(state.pinchFrames>=state.settings.confirmationFrames)pinchStart(px,py,now);
  }else{
    state.releaseFrames=release?state.releaseFrames+1:0;
    if(state.releaseFrames>=state.settings.confirmationFrames)pinchEnd(px,py,now);
    else pinchHold(px,py,now);
  }

  if(!state.pinch&&isTwoFinger(lm))twoFingerScroll(py);
  else if(!isTwoFinger(lm))state.scrollY=null;

  trackSwipe(lm,now);
}
function pinchStart(px,py,now){
  state.pinch=true;state.pinchFrames=0;state.releaseFrames=0;state.pinchStartedAt=now;state.pinchStartPoint={x:px,y:py};
  state.cursor.classList.add("pinching");setStatus(STATUS.CLICKING);
  const target=elementAt(px,py);
  state.pointerDownTarget=target;
  const panel=target?.closest?.(".panel,.widget-shell");
  const rect=panel?.getBoundingClientRect();
  state.resize=!!(panel&&rect&&(rect.right-px<14||rect.bottom-py<14));
  state.drag=!!(panel&&!state.resize&&target.closest(".panel-title,.widget-head"));
  if(state.drag||state.resize)dispatchPointer(target,"pointerdown",px,py,0);
  if(state.settings.externalControl)externalAction("down",{x:px,y:py});
}
function pinchHold(px,py,now){
  if(state.drag||state.resize){
    dispatchPointer(state.pointerDownTarget||elementAt(px,py),"pointermove",px,py,0);
    setStatus(state.resize?STATUS.RESIZING:STATUS.DRAGGING);
  }
}
function pinchEnd(px,py,now){
  const duration=now-state.pinchStartedAt;
  if(state.drag||state.resize)dispatchPointer(state.pointerDownTarget||elementAt(px,py),"pointerup",px,py,0);
  else if(duration<520){
    const doublePinch=now-state.lastPinchAt<420&&state.pinchStartPoint&&Math.hypot(px-state.pinchStartPoint.x,py-state.pinchStartPoint.y)<80;
    clickAt(px,py,doublePinch?2:1);state.lastPinchAt=now;
  }
  if(state.settings.externalControl)externalAction("up",{x:px,y:py});
  state.pinch=false;state.drag=false;state.resize=false;state.pointerDownTarget=null;state.cursor.classList.remove("pinching");
  setStatus(STATUS.TRACKING);
}
function dispatchPointer(el,type,x,y,button=0){
  if(!el)return;
  try{el.dispatchEvent(new PointerEvent(type,{bubbles:true,cancelable:true,clientX:x,clientY:y,button,buttons:type==="pointerup"?0:1,pointerId:state.pointerId,pointerType:"pen"}));}catch{}
}
function elementAt(px,py){state.cursor?.classList.add("probe");const el=document.elementFromPoint(px,py);state.cursor?.classList.remove("probe");return el;}
function clickAt(px,py,count=1){
  const el=elementAt(px,py);if(!el)return;
  if(el.matches('input[type="password"]')){window.showToast?.("Air Touch is blocked from password fields.");return;}
  if(el.matches("input,textarea,select"))el.focus();
  for(let i=0;i<count;i++){try{el.click();}catch{}}
  state.cursor.classList.add("click");setTimeout(()=>state.cursor?.classList.remove("click"),140);
}
function twoFingerScroll(py){
  if(state.scrollY==null){state.scrollY=py;return;}
  const dy=py-state.scrollY;if(Math.abs(dy)<5)return;state.scrollY=py;
  const el=elementAt(state.smooth.x*innerWidth,py);
  const scrollable=findScrollable(el);
  (scrollable||window).scrollBy({top:dy*6*state.settings.scrollSensitivity,behavior:"auto"});
  setStatus(STATUS.SCROLLING);
}
function findScrollable(el){
  for(let n=el;n&&n!==document.body;n=n.parentElement){
    const s=getComputedStyle(n);if(/auto|scroll/.test(s.overflowY)&&n.scrollHeight>n.clientHeight)return n;
  }return null;
}
function trackSwipe(lm,now){
  const x=state.settings.mirrored?1-lm[0].x:lm[0].x;
  state.swipeSamples.push({x,t:now});while(state.swipeSamples.length&&now-state.swipeSamples[0].t>260)state.swipeSamples.shift();
  if(state.swipeSamples.length<3||state.pinch)return;
  const first=state.swipeSamples[0],last=state.swipeSamples[state.swipeSamples.length-1],dx=last.x-first.x;
  const threshold=.22/Math.max(.3,state.settings.swipeSensitivity);
  if(Math.abs(dx)>threshold){cycleDashboard(dx>0?1:-1);state.swipeSamples=[];}
}
function cycleDashboard(dir){
  const nav=qa(".nav").filter(n=>n.dataset.view);if(!nav.length)return;
  const active=Math.max(0,nav.findIndex(n=>n.classList.contains("active")));
  nav[(active+dir+nav.length)%nav.length].click();
}
function trackingLost(){
  state.hand=null;state.cursor?.classList.add("lost");safeRelease();setStatus(state.settings.paused?STATUS.PAUSED:STATUS.LOST);
}
function safeRelease(){
  if(state.pinch&&state.pointerDownTarget)dispatchPointer(state.pointerDownTarget,"pointerup",state.smooth.x*innerWidth,state.smooth.y*innerHeight,0);
  state.pinch=false;state.drag=false;state.resize=false;state.pointerDownTarget=null;externalRelease();
}
function updateTarget(px,py){
  const el=elementAt(px,py);
  const interactive=el?.closest?.("button,input,textarea,select,a,.panel,.widget-shell,.nav");
  const panel=el?.closest?.(".panel,.widget-shell");
  const title=panel?.querySelector?.(".panel-title,.widget-head")?.textContent?.trim()||"";
  const id=interactive?.id||panel?.dataset?.layoutId||panel?.id||interactive?.dataset?.view||"";
  const key=`${id}|${title}|${interactive?.tagName||""}`;
  if(key!==state.targetKey){state.targetKey=key;state.targetSince=performance.now();}
  state.target={
    id:String(id||title||"target").slice(0,100),widget:title.slice(0,100),
    type:String(interactive?.tagName||"").toLowerCase(),
    interactive:!!interactive,
    actions:safeActions(interactive,panel)
  };
  state.cursor?.classList.toggle("hover",!!interactive);
  if(performance.now()-state.targetSince>180)syncTarget();
}
function safeActions(el,panel){
  const a=[];if(el?.matches?.("button,a,.nav"))a.push("click","open");
  if(panel)a.push("move","resize","scroll","minimize","maximize");
  if(el?.matches?.("input:not([type=password]),textarea"))a.push("type");
  return [...new Set(a)];
}
function syncTarget(){
  const now=performance.now();if(now-state.targetSyncAt<300||!state.target)return;state.targetSyncAt=now;
  fetch("/api/airtouch/target",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(state.target),keepalive:true}).catch(()=>{});
}
function performTargetAction(action,payload={}){
  const t=state.target;if(!t)return false;
  const px=state.smooth.x*innerWidth,py=state.smooth.y*innerHeight,el=elementAt(px,py);
  if(!el)return false;
  flashTarget(el);
  if(action==="click"||action==="open"){clickAt(px,py,1);return true;}
  if(action==="scroll_up"||action==="scroll_down"){const s=findScrollable(el)||window;s.scrollBy({top:(action==="scroll_up"?-1:1)*(payload.amount||280),behavior:"smooth"});return true;}
  if(action==="type"){toggleKeyboard(true);el.focus();return true;}
  if(action==="minimize"){el.closest(".panel,.widget-shell")?.classList.toggle("airtouch-minimized",true);return true;}
  if(action==="maximize"){el.closest(".panel,.widget-shell")?.classList.toggle("airtouch-maximized",true);return true;}
  if(action==="move_left"||action==="move_right"){
    const panel=el.closest(".panel,.widget-shell");if(!panel)return false;
    const x=(Number(panel.dataset.layoutX)||0)+(action==="move_left"?-80:80);
    panel.dataset.layoutX=String(x);panel.style.setProperty("transform",`translate(${x}px, ${Number(panel.dataset.layoutY)||0}px)`,"important");
    window.persistPanelLayout?.(true);return true;
  }
  return false;
}
function flashTarget(el){el.classList.add("airtouch-target-flash");setTimeout(()=>el.classList.remove("airtouch-target-flash"),420);}

function toggleKeyboard(show){
  ensureKeyboard();state.keyboard.classList.toggle("active",show===undefined?!state.keyboard.classList.contains("active"):!!show);
  if(state.keyboard.classList.contains("active"))setStatus(STATUS.KEYBOARD);
}
function ensureKeyboard(){
  if(state.keyboard)return;
  const k=document.createElement("div");k.id="airtouch-keyboard";k.className="airtouch-keyboard";
  const rows=[["1","2","3","4","5","6","7","8","9","0","Backspace"],["q","w","e","r","t","y","u","i","o","p"],["a","s","d","f","g","h","j","k","l","Enter"],["Shift","z","x","c","v","b","n","m",".","/"],["Tab","←","↑","↓","→","Space","Close"]];
  k.innerHTML='<div class="airtouch-kb-head">AIR TOUCH KEYBOARD <button data-key="Close">×</button></div>'+rows.map(r=>`<div class="airtouch-kb-row">${r.map(v=>`<button data-key="${v}">${v}</button>`).join("")}</div>`).join("");
  k.addEventListener("click",e=>{const key=e.target.closest("[data-key]")?.dataset?.key;if(key)pressKey(key);});
  document.body.appendChild(k);state.keyboard=k;
}
function focusedTextField(){
  const el=document.activeElement;if(!el)return null;
  if(el.matches('input[type="password"]'))return null;
  if(el.matches("textarea,input:not([type=button]):not([type=submit]):not([type=checkbox]):not([type=radio])"))return el;
  return null;
}
function pressKey(key){
  if(key==="Close"){toggleKeyboard(false);return;}
  const el=focusedTextField();if(!el){window.showToast?.("Select a text field first.");return;}
  const now=performance.now();if(key===state.keyboardLastKey&&now-state.keyboardLastAt<130)return;state.keyboardLastKey=key;state.keyboardLastAt=now;
  let v=el.value||"",start=el.selectionStart??v.length,end=el.selectionEnd??start,insert="";
  if(key==="Backspace"){if(start===end&&start>0)start--;el.value=v.slice(0,start)+v.slice(end);el.setSelectionRange(start,start);}
  else if(key==="Enter"){insert="\n";insertText();}
  else if(key==="Tab"){insert="\t";insertText();}
  else if(key==="Space"){insert=" ";insertText();}
  else if(["←","→"].includes(key)){const p=Math.max(0,Math.min(v.length,start+(key==="←"?-1:1)));el.setSelectionRange(p,p);}
  else if(["↑","↓","Shift"].includes(key)){}
  else{insert=key;insertText();}
  function insertText(){el.value=v.slice(0,start)+insert+v.slice(end);const p=start+insert.length;el.setSelectionRange(p,p);}
  el.dispatchEvent(new Event("input",{bubbles:true}));
}

function beginCalibration(){
  state.calibrationMode=true;state.calibrationIndex=0;state.calibrationSamples=[];
  ensureCalibrationOverlay();setStatus(STATUS.CALIBRATE);positionCalibrationTarget();
}
function ensureCalibrationOverlay(){
  if(state.calibrationOverlay)return;
  const o=document.createElement("div");o.className="airtouch-calibration";
  o.innerHTML='<div class="airtouch-calibration-help">Point at each target and pinch</div><div class="airtouch-calibration-target"></div><button>Cancel</button>';
  o.querySelector("button").onclick=()=>endCalibration(false);document.body.appendChild(o);state.calibrationOverlay=o;
}
function positionCalibrationTarget(){
  const pts=[[.08,.10],[.92,.10],[.92,.90],[.08,.90],[.5,.5]],p=pts[state.calibrationIndex]||pts[0],t=state.calibrationOverlay.querySelector(".airtouch-calibration-target");
  t.style.left=`${p[0]*100}%`;t.style.top=`${p[1]*100}%`;state.calibrationOverlay.classList.add("active");
}
function renderCalibrationPointer(){}
function captureCalibrationSample(){
  state.calibrationSamples.push({...state.raw});state.calibrationIndex++;
  if(state.calibrationIndex>=5)endCalibration(true);else positionCalibrationTarget();
}
function endCalibration(save){
  if(save&&state.calibrationSamples.length>=4){
    const xs=state.calibrationSamples.map(p=>p.x),ys=state.calibrationSamples.map(p=>p.y);
    state.settings.calibration={minX:Math.min(...xs),maxX:Math.max(...xs),minY:Math.min(...ys),maxY:Math.max(...ys),viewportW:innerWidth,viewportH:innerHeight,at:new Date().toISOString()};
    saveSettings();window.showToast?.("Air Touch calibration saved.");
  }
  state.calibrationMode=false;state.calibrationOverlay?.classList.remove("active");
}

async function externalAction(action,data={}){
  if(!state.settings.externalControl)return;
  try{await fetch("/api/airtouch/external",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,...data}),keepalive:true});}catch{}
}
function externalMove(px,py){
  const now=performance.now();if(now-state.externalMoveAt<20)return;state.externalMoveAt=now;
  externalAction("move",{x:px/innerWidth,y:py/innerHeight});
}
function externalRelease(){if(state.settings.externalControl)externalAction("up",{});}
async function emergencyStop(){
  safeRelease();state.settings.paused=true;state.settings.externalControl=false;saveSettings();
  await fetch("/api/airtouch/emergency_stop",{method:"POST"}).catch(()=>{});
  setStatus(STATUS.PAUSED);window.showToast?.("AIR TOUCH EMERGENCY STOP");
}
function renderDebug(pinchDistance=0,hand=state.hand){
  if(!state.debugPanel)return;
  // Error/status data should remain useful even before tracking succeeds.
  if(!state.settings.debug && !state.lastError)return;
  state.debugPanel.classList.remove("hidden");
  const recent=state.logs.slice(-8).map(x=>`<div class="${x.error?"err":""}">${escapeHtml(x.at)} [${escapeHtml(x.stage)}] ${escapeHtml(x.message)}${x.error?` — ${escapeHtml(x.error).slice(0,260)}`:""}</div>`).join("");
  state.debugPanel.innerHTML=`<div class="airtouch-debug-head"><b>AIR TOUCH DEBUG</b><span>DRAG ME</span></div>
  <span>Status ${escapeHtml(state.status)}</span><span>Stage ${escapeHtml(state.workerStage)}</span>
  <span>MediaPipe ${MEDIAPIPE_VERSION} ready ${state.mediaPipeReady}</span><span>Mode ${escapeHtml(state.executionMode)}</span>
  <span>Delegate ${escapeHtml(state.delegate)}</span><span>Camera FPS ${state.cameraFps}</span>
  <span>Tracking FPS ${state.trackingFps}</span><span>Latency ${state.processingMs.toFixed(1)} ms</span>
  <span>Inference interval ${state.inferenceIntervalMs.toFixed(0)} ms</span>
  <span>WASM loader ${escapeHtml(state.wasmLoaderUrl)}</span><span>WASM binary ${escapeHtml(state.wasmBinaryUrl)}</span>
  <span>Model ${escapeHtml(MEDIAPIPE_MODEL_URL)}</span>
  <span>Dropped ${state.dropped}</span><span>Hand ${escapeHtml(hand?.handedness||"—")} ${Math.round((hand?.confidence||0)*100)}%</span>
  <span>Gesture ${state.status}</span><span>Pinch ${Number(pinchDistance||0).toFixed(3)}</span>
  <span>Target ${escapeHtml(state.target?.widget||state.target?.id||"—")}</span>
  <hr><b>PIPELINE LOG</b>${recent||"<div>No events yet.</div>"}`;
}
function applyRemoteAction(action){
  if(!action)return;
  if(action.type==="airtouch"){
    const name=action.action;
    if(name==="enable"){state.settings.enabled=true;saveSettings();startCamera();}
    if(name==="disable"){state.settings.enabled=false;saveSettings();stopCamera();setStatus(STATUS.OFF);}
    if(name==="pause"){state.settings.paused=true;saveSettings();setStatus(STATUS.PAUSED);}
    if(name==="resume"){state.settings.paused=false;saveSettings();}
    if(name==="calibrate")beginCalibration();
    if(name==="keyboard_open")toggleKeyboard(true);
    if(name==="keyboard_close")toggleKeyboard(false);
    if(name==="target_action")performTargetAction(action.payload?.action,action.payload||{});
    if(name==="sensitivity_up"){state.settings.sensitivity=Math.min(2,state.settings.sensitivity+.1);saveSettings();}
    if(name==="sensitivity_down"){state.settings.sensitivity=Math.max(.5,state.settings.sensitivity-.1);saveSettings();}
  }
}
function onResize(){
  if(state.settings.calibration){
    const c=state.settings.calibration;
    if(Math.abs(innerWidth-c.viewportW)/Math.max(1,c.viewportW)>.15||Math.abs(innerHeight-c.viewportH)/Math.max(1,c.viewportH)>.15){
      setStatus(STATUS.CALIBRATE);
    }
  }
}
function init(){
  ensureUi();loadSettings();ensureKeyboard();
  cancelAnimationFrame(state.visualRaf);
  state.visualRaf=requestAnimationFrame(visualCursorLoop);
  window.addEventListener("resize",onResize);
  document.addEventListener("keydown",e=>{
    if(e.ctrlKey&&e.altKey&&e.shiftKey&&e.code==="KeyX"){e.preventDefault();emergencyStop();}
  });
  // Render only: camera startup requires a deliberate UI or voice action.
  setTimeout(()=>{renderSettings();},350);
  window.addEventListener("beforeunload",()=>{state.stream?.getTracks().forEach(t=>t.stop());state.handLandmarker?.close?.();});
}
window.AirTouch={init,start:startCamera,stop:stopCamera,pause:()=>{state.settings.paused=true;saveSettings();},resume:()=>{state.settings.paused=false;saveSettings();},calibrate:beginCalibration,openSettings,renderSettings,toggleKeyboard,emergencyStop,performTargetAction,applyRemoteAction,getState:()=>({status:state.status,settings:{...state.settings},target:state.target})};
init();
