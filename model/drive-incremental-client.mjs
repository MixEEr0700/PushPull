/** Heavy graph/JSON/hash/PPC1 work stays in a dedicated worker. HTTP retains
 * the existing OAuth transport; no access token is copied to the worker. */
export async function runIncremental(task,args,transport,{signal}={}){
 signal?.throwIfAborted();
 if(typeof Worker==='undefined')return (await import('./drive-incremental-worker.mjs')).execute(task,args,transport);
 return new Promise((resolve,reject)=>{
  const w=new Worker(new URL('./drive-incremental-worker.mjs',import.meta.url),{type:'module'});let done=false;
  const finish=(e,result)=>{if(done)return;done=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);w.terminate();e?reject(e):resolve(result)};
  const abort=()=>finish(new DOMException('Anulowano','AbortError'));const timer=setTimeout(()=>finish(Error('Przekroczono czas weryfikacji Drive PPC1.')),120000);signal?.addEventListener('abort',abort,{once:true});
  w.onerror=()=>finish(Error('Przerwano worker Drive PPC1.'));
  w.onmessage=async({data})=>{if(done)return;if(data.rpc){const {id,method,args}=data.rpc;if(!['readPoint','createPoint'].includes(method)){finish(Error('Nieznana operacja transportu'));return;}try{const value=await (transport[method]??(method==='readPoint'?transport.read:null)).apply(transport,args);if(!done)w.postMessage({reply:{id,value}});}catch(e){if(!done)w.postMessage({reply:{id,error:{message:e.message,auth:e.auth,status:e.status}}});}return;}finish(data.error?Object.assign(Error(data.error.message),data.error):null,data.result);};
  w.postMessage({task,args});
 });
}
