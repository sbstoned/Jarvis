'use strict';
// Evaluates the production upload client and dashboard actions. Minimal DOM
// objects replace rendering only; file IO, requests and the upload API are real.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {Client}=require('./ui/project-upload.js');
const [base,source]=process.argv.slice(2);
const bytes=fs.readFileSync(source);
const file=new File([bytes],path.basename(source),{type:'application/zip'});

async function main(){
  let dropped=false, chunkCalls=0;
  const client=new Client(async(url,init)=>{
    const response=await fetch(base+url,init);
    if(url.endsWith('/chunk')){
      chunkCalls++;
      if(!dropped){dropped=true;await response.text();throw new TypeError('Simulated lost response after persistence');}
    }
    return response;
  },{retryDelay:1});
  const received=[];
  const ready=await client.upload({file},n=>received.push(n));
  assert(chunkCalls>=4,'multi-chunk retry path did not run');
  assert.equal(ready.size,bytes.length);
  assert.deepEqual(fs.readFileSync(ready.path),bytes,'lost-response retry duplicated or omitted data');
  assert(received.some(n=>n>0&&n<bytes.length),'intermediate progress was not reported');

  // A visible failure must be recoverable from the saved offset with the same ID.
  let failSecond=true;
  const resumable=new Client(async(url,init)=>{
    if(failSecond&&url.endsWith('/chunk')&&Number(init.headers['X-Upload-Offset'])>0)throw new TypeError('connection lost');
    return fetch(base+url,init);
  },{retryDelay:1});
  const item={file};
  await assert.rejects(()=>resumable.upload(item),/Retry/);
  const saved=await fetch(base+'/api/uploads/'+item.uploadId).then(r=>r.json());
  assert.equal(saved.received,1048576);
  failSecond=false;
  const recovered=await resumable.upload(item);
  assert.deepEqual(fs.readFileSync(recovered.path),bytes);

  const elements=new Map();
  const element=(id)=>{
    const classes=new Set();
    const listeners=new Map();
    if(!elements.has(id))elements.set(id,{id,value:'',disabled:false,innerHTML:'',textContent:'',style:{},dataset:{},
      classList:{toggle(name,force){const on=force===undefined?!classes.has(name):force;if(on)classes.add(name);else classes.delete(name);return on;},
        add(...names){names.forEach(name=>classes.add(name));},remove(...names){names.forEach(name=>classes.delete(name));},contains(name){return classes.has(name);}},
      addEventListener(name,handler){if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(handler);},
      removeEventListener(){},
      dispatch(name,properties={}){
        if(name==='click'&&this.disabled)return;
        const event={target:this,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;},...properties};
        for(const handler of listeners.get(name)||[])handler(event);
        return event;
      },querySelectorAll(){return[];},
      querySelector(){return null;},appendChild(){},focus(){},setAttribute(){},remove(){},
      getBoundingClientRect(){return{x:0,y:0,width:100,height:100};}});
    return elements.get(id);
  };
  const bubbles=[];let commands=0,allowChunks=false,failCommands=false;
  let healthOverride=null;
  const deferred=[];
  const doc={readyState:'complete',getElementById:element,querySelectorAll(){return[];},querySelector(){return null;},
    addEventListener(){},createElement(){return element('new-'+Math.random());},
    documentElement:element('documentElement'),body:element('body')};
  const apiFetch=async(url,init={})=>{
    if(url.includes('/api/health?watchdog=')&&healthOverride!==null){
      return new Response(JSON.stringify(healthOverride),{status:200});
    }
    if(url.includes('/api/command')&&init.method==='POST'){
      commands++;
      if(failCommands)return new Response(JSON.stringify({error:'fixture IPC unavailable'}),{status:503});
    }
    if(url.endsWith('/chunk')&&!allowChunks)await new Promise(resolve=>deferred.push(resolve));
    return fetch(url,init);
  };
  const sandbox={document:doc,location:{protocol:'http:',origin:base,href:base+'/'},
    fetch:apiFetch,addEventListener(){},removeEventListener(){},
    console,Date,Map,Set,Promise,JSON,Math,Number,String,Array,Error,TypeError,
    AbortController,DOMException,Uint8Array,File,Blob,URL,URLSearchParams,crypto:globalThis.crypto,
    setTimeout,clearTimeout,setInterval(){return 0;},clearInterval(){},
    requestAnimationFrame(){},cancelAnimationFrame(){},navigator:{},
    localStorage:{getItem(){return null;},setItem(){},removeItem(){}},
    innerWidth:1200,innerHeight:900,testFile:file};
  sandbox.window=sandbox;sandbox.globalThis=sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync('ui/project-upload.js','utf8'),sandbox);
  vm.runInContext(fs.readFileSync('ui/app.js','utf8'),sandbox);
  sandbox.testBubble=(kind,text)=>bubbles.push(text);
  vm.runInContext('addBubble=testBubble; jarvisClientLog=()=>{};',sandbox);
  const waitUntil=async(predicate)=>{
    for(let i=0;i<300;i++){
      if(predicate())return;
      await new Promise(resolve=>setTimeout(resolve,20));
    }
    assert.fail('Command event did not settle');
  };
  // Rebinding must not duplicate requests; test the real event handlers rather
  // than invoking sendCommand directly for keyboard/button acceptance.
  vm.runInContext('bindChatControls(); bindChatControls();',sandbox);
  element('provider-select').value='auto';element('chat-input').value='fix and finish this project';
  const pending=vm.runInContext('uploadChatFiles([testFile])',sandbox);
  assert.equal(element('send-btn').disabled,true,'Send was enabled before upload finished');
  const enterDuringUpload=element('chat-input').dispatch('keydown',{key:'Enter'});
  assert.equal(enterDuringUpload.defaultPrevented,true,'Enter handler was not installed');
  assert.equal(commands,0,'a project was started while the ZIP was uploading');
  allowChunks=true;for(const resume of deferred)resume();
  await pending;
  assert.equal(element('send-btn').disabled,false);
  assert(element('chat-attachments').innerHTML.includes('Ready to repair'));
  failCommands=true;
  const failedClick=element('send-btn').dispatch('click');
  assert.equal(failedClick.defaultPrevented,true,'send button handler was not installed');
  await waitUntil(()=>!vm.runInContext('chatCommandSending',sandbox));
  assert.equal(element('chat-input').value,'fix and finish this project','failed handoff erased the draft');
  assert.equal(vm.runInContext('chatAttachments.length',sandbox),1,'failed command lost the uploaded ZIP');
  assert(element('chat-command-status').textContent.includes('Command error'));
  failCommands=false;
  const beforeEnter=commands;
  element('chat-input').dispatch('keydown',{key:'Enter',isComposing:true});
  element('chat-input').dispatch('keydown',{key:'Enter',repeat:true});
  assert.equal(commands,beforeEnter,'composing/repeated Enter submitted a request');
  element('chat-input').dispatch('keydown',{key:'Enter'});
  element('chat-input').dispatch('keydown',{key:'Enter'});
  await waitUntil(()=>!vm.runInContext('chatCommandSending || commandJobs.size',sandbox));
  assert.equal(commands,beforeEnter+1,'Enter submitted duplicate requests');
  assert.equal(vm.runInContext('chatAttachments.length',sandbox),0,'accepted repair did not consume the attachment');
  assert.equal(element('chat-input').value,'','accepted Enter did not clear the draft');
  assert(bubbles.includes('Existing project accepted for repair.'));
  assert.equal(element('chat-command-status').textContent,'Request accepted by Jarvis.');

  await vm.runInContext('uploadChatFiles([testFile])',sandbox);
  element('chat-input').value='repair this project';
  const beforeClick=commands;
  element('send-btn').dispatch('click');
  await waitUntil(()=>!vm.runInContext('chatCommandSending || commandJobs.size',sandbox));
  assert.equal(commands,beforeClick+1,'send button did not submit exactly once');
  assert.equal(vm.runInContext('chatAttachments.length',sandbox),0,'send button did not hand off the ZIP');
  assert.equal(element('chat-input').value,'');
  console.log('PASS JavaScript: actual Enter and send-button handlers, duplicate prevention, busy feedback and draft/ZIP clearing after acceptance.');

  // A worker decline is different from the dashboard merely accepting a command.
  vm.runInContext(`chatAttachments.push({name:'held.zip',kind:'zip',size:1,state:'queued'});
    commandJobs.set('declined',{attachments:[chatAttachments[0]],originalCommand:'finish this project'});
    settleCommandAttachments('declined',false);`,sandbox);
  assert.equal(vm.runInContext('chatAttachments[0].state',sandbox),'ready');
  assert.equal(element('chat-input').value,'finish this project');

  // Exercise the production watchdog against the actual server identity, then
  // deliberately incompatible replies. A release must not warn about itself.
  const actualHealth=await fetch(base+'/api/health').then(response=>response.json());
  const uiBuild=vm.runInContext('JARVIS_UI_BUILD_ID',sandbox);
  assert.equal(actualHealth.build_id,uiBuild,'packaged page and server versions differ');
  const warning=element('jarvis-dashboard-health-warning');
  await vm.runInContext('jarvisBackendWatchdog()',sandbox);
  assert.equal(warning.classList.contains('show'),false,'matching dashboard displayed a false build mismatch');
  assert.equal(sandbox.__jarvisHealth.build_id,uiBuild,'matching dashboard health was not recorded');

  sandbox.__jarvisLastHealthOk=1;
  healthOverride={...actualHealth,build_id:'v0.0-test-server'};
  await vm.runInContext('jarvisBackendWatchdog()',sandbox);
  assert.equal(warning.classList.contains('show'),true,'a genuinely stale server was accepted');
  assert(warning.textContent.includes(uiBuild)&&warning.textContent.includes(healthOverride.build_id),
    'mismatch warning must identify the actual page and server versions');
  assert.equal(sandbox.__jarvisLastHealthOk,1,'mismatch was recorded as a healthy connection');
  healthOverride=null;
  await vm.runInContext('jarvisBackendWatchdog()',sandbox);
  assert.equal(warning.classList.contains('show'),false,'matching health did not clear the mismatch');

  sandbox.__jarvisLastHealthOk=1;
  healthOverride={...actualHealth,service:'unrelated-service'};
  for(let i=0;i<20;i++)await vm.runInContext('jarvisBackendWatchdog()',sandbox);
  assert.equal(sandbox.__jarvisLastHealthOk,1,'a different service was recorded as healthy');
  assert(warning.classList.contains('show')&&warning.textContent.includes('heartbeat delayed'));
  assert.equal(vm.runInContext('__jarvisRestartOverlay',sandbox),null,'heartbeat failure blanked the dashboard');
  healthOverride=null;
  await vm.runInContext('jarvisBackendWatchdog()',sandbox);
  assert.equal(warning.classList.contains('show'),false);
  assert.equal(vm.runInContext('__jarvisBackendFailures',sandbox),0);
  assert(sandbox.__jarvisLastHealthOk>1,'recovered health was not recorded');
  console.log('PASS JavaScript: matching server identity, genuine version mismatch, wrong-service rejection and heartbeat recovery.');
  console.log('PASS JavaScript: lost-response retry, saved-offset resume, upload/send race, draft retention, acknowledged ZIP handoff and worker-decline recovery.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
