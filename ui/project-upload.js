/* Project ZIP transport. Works with any project language and keeps files out of JSON. */
(function(root){
  'use strict';
  class UploadFailure extends Error {
    constructor(message, status=0, code='network_error'){
      super(message); this.status=status; this.code=code;
    }
  }
  function newId(){
    if(root.crypto?.randomUUID) return root.crypto.randomUUID().replaceAll('-','');
    const bytes=new Uint8Array(16);
    if(root.crypto?.getRandomValues) root.crypto.getRandomValues(bytes);
    else for(let i=0;i<bytes.length;i++)bytes[i]=Math.floor(Math.random()*256);
    return [...bytes].map(n=>n.toString(16).padStart(2,'0')).join('');
  }
  class Client {
    constructor(fetcher, options={}){
      this.fetcher=fetcher;
      this.timeout=options.timeout||90000;
      this.retryDelay=options.retryDelay??350;
    }
    async request(path, init={}, signal){
      let last;
      for(let attempt=0;attempt<3;attempt++){
        if(signal?.aborted)throw new DOMException('Upload cancelled','AbortError');
        const controller=new AbortController();
        const cancel=()=>controller.abort();
        signal?.addEventListener('abort',cancel,{once:true});
        const timer=setTimeout(cancel,this.timeout);
        try{
          const res=await this.fetcher(path,{...init,cache:'no-store',signal:controller.signal});
          const raw=await res.text(); let data;
          try{data=JSON.parse(raw);}catch(_e){
            throw new UploadFailure('The dashboard upload API is unavailable. Fully close Jarvis and reopen the updated copy.',res.status,'upload_api_unavailable');
          }
          if(!res.ok||data.status!=='ok'){
            throw new UploadFailure(data.error||`Upload request failed (${res.status}).`,res.status,data.code);
          }
          return data;
        }catch(error){
          if(signal?.aborted)throw new DOMException('Upload cancelled','AbortError');
          last=error;
          const retryable=!(error instanceof UploadFailure)||[408,429,500,502,503,504].includes(error.status);
          if(!retryable||attempt===2)break;
        }finally{
          clearTimeout(timer);signal?.removeEventListener('abort',cancel);
        }
        await new Promise(resolve=>setTimeout(resolve,this.retryDelay*(attempt+1)));
      }
      if(last instanceof UploadFailure)throw last;
      throw new UploadFailure('Connection to Jarvis was interrupted. Keep the dashboard running and press Retry; saved chunks will be reused.');
    }
    async upload(item, onProgress=()=>{}){
      const file=item.file, signal=item.controller?.signal;
      if(!file||!Number.isSafeInteger(file.size)||file.size<=0)throw new UploadFailure('Select a saved, nonempty file.');
      item.uploadId=item.uploadId||newId();
      // The same ID makes even a lost creation response safe to retry.
      let state=await this.request('/api/uploads',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:item.uploadId,name:file.name,size:file.size})
      },signal);
      onProgress(state.received,file.size,state.upload_status);
      if(state.upload_status==='complete')return state;
      const chunkSize=Math.min(Number(state.chunk_size)||1048576,1048576);
      let offset=Number(state.received);
      if(!Number.isSafeInteger(offset)||offset<0||offset>file.size)throw new UploadFailure('The upload returned an invalid saved position. Remove and reselect this file.');
      while(offset<file.size){
        if(signal?.aborted)throw new DOMException('Upload cancelled','AbortError');
        const end=Math.min(offset+chunkSize,file.size);
        let bytes;
        try{
          // Read only this chunk before networking. Passing a mutable Windows
          // File directly to fetch can fail when the file is still being saved.
          bytes=await file.slice(offset,end).arrayBuffer();
        }catch(_e){
          throw new UploadFailure('The selected file could not be read. Let Windows finish saving the ZIP, then remove this attachment and select it again.');
        }
        if(bytes.byteLength!==end-offset)throw new UploadFailure('The selected ZIP changed while being read. Select the finished ZIP again.');
        state=await this.request(`/api/uploads/${item.uploadId}/chunk`,{
          method:'POST',headers:{'Content-Type':'application/octet-stream','X-Upload-Offset':String(offset)},body:bytes
        },signal);
        const received=Number(state.received);
        if(!Number.isSafeInteger(received)||received<end||received>file.size)throw new UploadFailure('The upload did not acknowledge the complete chunk. Press Retry.');
        offset=received;
        onProgress(offset,file.size,'uploading');
      }
      onProgress(offset,file.size,'validating');
      state=await this.request(`/api/uploads/${item.uploadId}/complete`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:'{}'
      },signal);
      if(state.upload_status!=='complete'||!state.path||state.size!==file.size)throw new UploadFailure('The file was not finalized. Press Retry before sending the project request.');
      return state;
    }
    async cancel(item){
      item.controller?.abort();
      if(item.uploadId)return this.request(`/api/uploads/${item.uploadId}/cancel`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:'{}'
      });
    }
  }
  const api={Client,UploadFailure};
  root.JarvisProjectUploads=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
