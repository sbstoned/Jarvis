// MediaPipe Tasks Vision is intentionally not imported in this module worker.
// Its generated classic WASM loader publishes `ModuleFactory` as a global; when
// dynamically imported by a module worker that `var` stays module-scoped. The
// supported runtime therefore lives in airtouch.js on the browser main thread.
// This worker remains as a small, frame-free compatibility/state helper only.

self.onmessage=event=>{
  const data=event.data||{};
  if(data.type==="ping"){
    self.postMessage({type:"pong",mode:"state-only",mediaPipe:false});
    return;
  }
  if(data.type==="normalize-result"){
    const result=data.result||{};
    const hands=(result.landmarks||[]).map((landmarks,index)=>({
      landmarks:(landmarks||[]).map(point=>({x:point.x,y:point.y,z:point.z})),
      handedness:result.handedness?.[index]?.[0]?.categoryName||"",
      confidence:result.handedness?.[index]?.[0]?.score||0
    }));
    self.postMessage({type:"normalized-result",id:data.id,hands});
  }
};
