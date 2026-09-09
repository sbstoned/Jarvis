const fs=require("fs");
const app=fs.readFileSync("ui/airtouch/airtouch.js","utf8");
const dashboard=fs.readFileSync("ui/dashboard.py","utf8");
const setup=fs.readFileSync("SETUP_AIR_TOUCH.ps1","utf8");

for(const name of ["pinchStart","pinchEnd","trackingLost","twoFingerScroll","trackSwipe","emergencyStop","toggleKeyboard","performTargetAction"]) {
  if(!app.includes(`function ${name}`) && !app.includes(`${name}(`)) throw new Error(`missing ${name}`);
}
for(const required of [
  'import {FilesetResolver, HandLandmarker}',
  'FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_ROOT)',
  'HandLandmarker.createFromOptions(fileset,options)',
  'delegate:"GPU"',
  'options.baseOptions.delegate="CPU"',
  'detectForVideo(state.video',
  'executionMode:"main thread"',
  'method:"HEAD"',
]) if(!app.includes(required)) throw new Error(`missing main-thread MediaPipe architecture: ${required}`);

if(app.includes("new Worker") || app.includes("createImageBitmap")) {
  throw new Error("MediaPipe must not initialize or run through the module worker");
}
for(const mime of ["application/javascript; charset=utf-8","application/wasm","application/octet-stream"]) {
  if(!dashboard.includes(mime)) throw new Error(`missing asset MIME mapping: ${mime}`);
}
if(!dashboard.includes("def do_HEAD(self):")) throw new Error("Air Touch HEAD endpoint support missing");
const appVersion=app.match(/MEDIAPIPE_VERSION="([^"]+)"/)?.[1];
const setupVersions=[...setup.matchAll(/tasks-vision@([^/]+)\//g)].map(x=>x[1]);
if(!appVersion || !setupVersions.length || setupVersions.some(v=>v!==appVersion)) {
  throw new Error(`MediaPipe version mismatch: runtime=${appVersion}, setup=${setupVersions.join(",")}`);
}
console.log(`Air Touch structural tests passed (MediaPipe ${appVersion}, main-thread runtime, GPU -> CPU).`);
